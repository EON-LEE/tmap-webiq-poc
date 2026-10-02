"""One local-first web service for the voice interface."""

import asyncio
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
import time

import aiohttp
from azure.core.exceptions import AzureError
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect, WebSocketState

from tmap_poc.app_settings import AppSettings
from tmap_poc.config import ConfigError
from tmap_poc.navigation import NavigationError, demo_configuration
from tmap_poc.profiles import PROVIDER_LABELS
from tmap_poc.trace_view import FoundryTraceReader, TraceAccess, TraceReadError, TraceSocket
from tmap_poc.voice import VoiceProtocolError, VoiceServiceError, VoiceSession, parse_control
from tmap_poc.voice_options import MODEL_MODE, VoiceOptionsError, option_schema, validate_options

STATIC = Path(__file__).with_name("static")
# One comparison runs a WebIQ and a Bing session together; allow two comparisons or a reconnect overlap.
MAX_ACTIVE_SESSIONS = 4
logger = logging.getLogger(__name__)


def create_app(settings=None, *, voice_factory=VoiceSession, trace_reader=None):
    settings = settings or AppSettings.from_env()
    tracing_mode = os.environ.get("TMAP_TRACE_EXPORTER", "console").strip().lower()
    reader = trace_reader or (FoundryTraceReader(settings) if tracing_mode == "foundry" else None)
    trace_access = TraceAccess()

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            if reader is not None:
                await reader.close()

    app = FastAPI(title="Navigation voice agent", lifespan=lifespan)
    app.state.active_sessions = 0
    app.mount("/static", StaticFiles(directory=STATIC, check_dir=False), name="static")

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/healthz")
    async def health():
        return {"status": "ok"}

    @app.get("/api/config")
    async def config():
        return JSONResponse({
            "providers": [settings.provider_config(provider) for provider in PROVIDER_LABELS],
            "voice": settings.voice_name,
            "voice_options": option_schema(settings.voice_name) if settings.voice_name else None,
            "errors": settings.problems(),
            "model_connection": {
                "configured": not settings.problems(connection_mode=MODEL_MODE),
                "errors": settings.problems(connection_mode=MODEL_MODE),
                "readiness_scope": "configuration_only",
            },
            "navigation": {**demo_configuration(), "recommended_mode": MODEL_MODE},
            "observability": {
                "flow_schema_version": 1,
                "scope": "client_observed",
                "reasoning_content": False,
                "automatic_trace_queries": False,
            },
            "tracing": {
                "destination": tracing_mode,
                "portal_url": "https://ai.azure.com",
                "embedded_enabled": reader is not None,
            },
        }, headers={"Cache-Control": "no-store"})

    @app.get("/api/traces/{trace_id}")
    async def get_trace(trace_id: str, request: Request):
        headers = {"Cache-Control": "no-store"}
        grant = trace_access.authorize(trace_id, request.headers.get("x-trace-access", ""))
        if grant is None:
            return JSONResponse(
                {"error": {"code": "trace_access", "message": "이 대화의 조회 권한이 없거나 만료됐습니다."}},
                status_code=404, headers=headers,
            )
        if reader is None:
            return JSONResponse(
                {"error": {"code": "trace_disabled", "message": "Foundry 트레이스 연결을 먼저 설정해 주세요."}},
                status_code=503, headers=headers,
            )
        try:
            async with asyncio.timeout(125), grant.lock:
                if trace_access.authorize(trace_id, request.headers.get("x-trace-access", "")) is None:
                    raise TraceReadError("trace_access", "이 대화의 조회 권한이 만료됐습니다.", 404)
                if grant.cached is None or time.monotonic() - grant.cached_at >= 15:
                    grant.cached = await reader.read(trace_id)
                    grant.cached_at = time.monotonic()
                return JSONResponse(grant.cached, headers=headers)
        except TraceReadError as exc:
            logger.warning("Trace read failed (%s)", exc.code)
            return JSONResponse(
                {"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status, headers=headers,
            )
        except TimeoutError:
            logger.warning("Trace read request timed out")
            return JSONResponse(
                {"error": {"code": "trace_timeout", "message": "트레이스 조회 시간이 초과됐습니다. 다시 불러와 주세요."}},
                status_code=504, headers=headers,
            )

    @app.websocket("/ws/voice")
    async def voice(socket: WebSocket):
        if socket.headers.get("origin", "").rstrip("/") not in settings.allowed_origins:
            await socket.close(code=1008)
            return
        await socket.accept()
        if app.state.active_sessions >= MAX_ACTIVE_SESSIONS:
            await socket.send_json({
                "type": "error", "code": "busy", "terminal": True,
                "message": f"동시에 {MAX_ACTIVE_SESSIONS}개 세션까지 사용할 수 있습니다. 다른 비교 화면을 닫고 다시 시도하세요.",
            })
            await socket.close(code=1013)
            return
        app.state.active_sessions += 1
        disconnected = False
        session, provider = None, None
        try:
            first = await asyncio.wait_for(socket.receive(), timeout=15)
            if first["type"] == "websocket.disconnect":
                disconnected = True
                return
            start = parse_control(first.get("text") or "")
            if start["type"] != "start":
                raise VoiceProtocolError("먼저 시작 메시지를 보내세요.")
            chosen = validate_options(start.get("voice_options", {}), settings.voice_name)
            provider = start["provider"] if chosen["connection_mode"] != MODEL_MODE else None
            settings.require(start["provider"], connection_mode=chosen["connection_mode"])
            await socket.send_json({"type": "status", "state": "connecting"})
            kwargs = {"voice_options": chosen} if "voice_options" in start else {}
            session = voice_factory(settings, start["provider"], start.get("context", ""), **kwargs)
            reason = await session.run(TraceSocket(socket, trace_access) if reader is not None else socket)
            await socket.send_json({
                "type": "done", "reason": reason, "provider": provider,
                "session_id": getattr(session, "session_id", None),
            })
        except WebSocketDisconnect:
            disconnected = True
        except (VoiceProtocolError, VoiceOptionsError, ConfigError, VoiceServiceError, NavigationError) as exc:
            correlation = {
                key: getattr(exc, key) for key in ("response_id", "item_id", "source_event")
                if isinstance(getattr(exc, key, None), str)
            }
            await socket.send_json({
                "type": "error", "code": type(exc).__name__, "message": str(exc),
                "terminal": True, "provider": provider,
                "session_id": getattr(session, "session_id", None), **correlation,
            })
        except (AzureError, aiohttp.ClientError, TimeoutError, OSError) as exc:
            logger.error("Voice session failed (%s)", type(exc).__name__)
            await socket.send_json({
                "type": "error", "code": type(exc).__name__,
                "message": "음성 연결을 완료할 수 없습니다. 네트워크, 설정과 Azure 접근 권한을 확인하세요.",
                "terminal": True, "provider": provider,
                "session_id": getattr(session, "session_id", None),
            })
        finally:
            app.state.active_sessions -= 1
            if not disconnected and socket.application_state == WebSocketState.CONNECTED:
                await socket.close()

    return app
