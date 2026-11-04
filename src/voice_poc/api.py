"""One local-first web service for the voice interface."""

import asyncio
import hashlib
import logging
from pathlib import Path

import aiohttp
from azure.core.exceptions import AzureError
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect, WebSocketState

from voice_poc.agents import PROVIDER_LABELS
from voice_poc.live import LiveSession
from voice_poc.settings import AppSettings, ConfigError
from voice_poc.voice import VoiceProtocolError, VoiceServiceError, VoiceSession, parse_control
from voice_poc.voice_options import VoiceOptionsError, option_schema, validate_options

STATIC = Path(__file__).with_name("static")
# One comparison runs a WebIQ and a Bing session together; allow two comparisons or a reconnect overlap.
MAX_ACTIVE_SESSIONS = 4
logger = logging.getLogger(__name__)


def static_version():
    """Content hash of the browser files. A new build gets new asset URLs, so no browser mixes old and new files."""
    digest = hashlib.sha256()
    for path in sorted(STATIC.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(STATIC).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def create_app(settings=None, *, voice_factory=VoiceSession, live_factory=LiveSession):
    settings = settings or AppSettings.from_env()
    app = FastAPI(title="WebIQ vs Bing voice POC")
    app.state.active_sessions = 0
    assets = f"/assets/{static_version()}"
    page = (STATIC / "index.html").read_text(encoding="utf-8").replace('"/static/', f'"{assets}/')

    @app.middleware("http")
    async def cache_policy(request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith(assets + "/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path == "/" or path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.mount(assets, StaticFiles(directory=STATIC, check_dir=False), name="assets")
    app.mount("/static", StaticFiles(directory=STATIC, check_dir=False), name="static")

    @app.get("/")
    async def index():
        return HTMLResponse(page)

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
            "live": {
                "configured": not settings.live_problems(),
                "deployment": settings.live_deployment or None,
                "errors": settings.live_problems(),
            },
            "observability": {
                "flow_schema_version": 1,
                "scope": "client_observed",
                "reasoning_content": False,
                "automatic_trace_queries": False,
            },
        }, headers={"Cache-Control": "no-store"})

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
            provider = start["provider"]
            settings.require(provider)
            live = chosen["connection_mode"] == "gpt_live"
            if live:
                settings.require_live()
            await socket.send_json({"type": "status", "state": "connecting"})
            kwargs = {"voice_options": chosen} if live or "voice_options" in start else {}
            if start.get("news") is not None:
                kwargs["news"] = start["news"]
            factory = live_factory if live else voice_factory
            session = factory(settings, start["provider"], start.get("context", ""), **kwargs)
            reason = await session.run(socket)
            await socket.send_json({
                "type": "done", "reason": reason, "provider": provider,
                "session_id": getattr(session, "session_id", None),
            })
        except WebSocketDisconnect:
            disconnected = True
        except (VoiceProtocolError, VoiceOptionsError, ConfigError, VoiceServiceError) as exc:
            correlation = {
                key: getattr(exc, key) for key in ("response_id", "item_id", "source_event")
                if isinstance(getattr(exc, key, None), str)
            }
            await socket.send_json({
                "type": "error", "code": getattr(exc, "code", None) or type(exc).__name__, "message": str(exc),
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
