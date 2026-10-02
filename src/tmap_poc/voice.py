"""Voice Live transport for the same Foundry agents used by experiments."""

import asyncio
import base64
from collections import deque
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime
import json
import logging
import math
import re
from time import monotonic
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4
from zoneinfo import ZoneInfo

import aiohttp
from azure.ai.voicelive.aio import VoiceLiveConnection
from azure.ai.voicelive.models import (
    FunctionCallOutputItem,
    InputTextContentPart,
    MessageItem,
    ResponseCreateParams,
)
from starlette.websockets import WebSocketDisconnect

from tmap_poc.config import ConfigError
from tmap_poc.navigation import NavigationError
from tmap_poc.navigation_voice import NavigationVoice
from tmap_poc.profiles import PROVIDER_LABELS
from tmap_poc.serialization import citation_links
from tmap_poc.telemetry import foundry_response_link, span, trace_headers, trace_id
from tmap_poc.tool_spans import ToolLifecycle
from tmap_poc.voice_options import (
    FOLLOWUP_INSTRUCTIONS, MODEL_MODE, SEARCH_MODE, build_model_session, build_search_session,
    build_session_options, build_web_search_session, validate_options,
)

API_VERSION = "2026-07-15"
SAMPLE_RATE = 24000
MAX_TEXT = 4000
MAX_AUDIO_BYTES = 48000
_SLOW_RELAY_SECONDS = 0.25
_RESPONSE_TAG = "navigation_request"
logger = logging.getLogger(__name__)
_TOOL_ARGUMENT_FIELDS = (
    "query", "q", "search_query", "url", "language", "region", "vertical", "maxResults",
    "contentFormat", "maxLength", "location", "safeSearch",
    "count", "market", "set_lang", "freshness",
    "input",
    "app", "destination_id", "place_id",
)
_TOOL_FLOW_EVENTS = {
    f"response.{tool}.{status}": (tool, status)
    for tool, statuses in (
        ("mcp_call", ("in_progress", "completed", "failed")),
        ("foundry_agent_call", ("in_progress", "completed", "failed")),
        ("web_search_call", ("in_progress", "searching", "completed")),
        ("file_search_call", ("in_progress", "searching", "completed")),
    )
    for status in statuses
}
_TOOL_ARGUMENT_EVENTS = {
    f"response.{tool}_arguments.done": tool
    for tool in ("mcp_call", "foundry_agent_call", "function_call")
}


def _flow_fields(mapping, fields, *, limit=256):
    if not isinstance(mapping, dict):
        return {}
    return {
        key: value for key in fields if key in mapping
        if (
            isinstance(value := mapping[key], str) and len(value) <= limit
            or type(value) is bool
            or type(value) is int and abs(value) <= 2**53 - 1
            or type(value) is float and math.isfinite(value)
        )
    }


def _flow_arguments(arguments):
    observed = arguments is not None
    if isinstance(arguments, str) and len(arguments) <= 65536:
        try:
            arguments = json.loads(arguments)
        except (ValueError, RecursionError):
            arguments = None
    if not isinstance(arguments, dict):
        return {"arguments_observed": observed, "arguments_parseable": False}
    safe = _flow_fields(arguments, _TOOL_ARGUMENT_FIELDS, limit=MAX_TEXT)
    if "url" in safe:
        links = citation_links([{"url": safe["url"]}])
        parsed = urlparse(links[0]["url"]) if links else None
        private_keys = {
            "key", "apikey", "token", "accesstoken", "authtoken", "authorization",
            "clientsecret", "password", "credential", "sig", "signature", "traceaccess",
            "traceaccesstoken", "xtraceaccess",
        }
        parameters = parse_qsl(parsed.query) + parse_qsl(parsed.fragment) if parsed else []
        if parsed is None or any(re.sub(r"[_-]", "", key.lower()) in private_keys for key, _ in parameters):
            del safe["url"]
    return {
        "arguments": safe, "arguments_observed": True, "arguments_parseable": True,
        "arguments_filtered": set(arguments) != set(safe),
    }


def _flow_session(session):
    data = _flow_fields(session, (
        "model", "id", "expires_at", "input_audio_sampling_rate",
        "input_audio_format", "output_audio_format",
    ))
    if isinstance(data.get("model"), str):
        data["service_model"] = data.pop("model")
        data["model_scope"] = "voice_live_session"
    else:
        data.pop("model", None)
    if isinstance(data.get("id"), str):
        data["service_session_id"] = data.pop("id")
    else:
        data.pop("id", None)
    if isinstance(session, dict):
        for key, fields in (
            ("voice", ("type", "name", "rate")),
            ("input_audio_transcription", ("model", "language")),
            ("turn_detection", ("type", "create_response", "interrupt_response", "silence_duration_ms")),
        ):
            value = _flow_fields(session.get(key), fields)
            if value:
                data[key] = value
    return data


class VoiceProtocolError(ValueError):
    pass


class VoiceServiceError(RuntimeError):
    def __init__(self, message, detail=None, *, response_id=None, item_id=None, source_event=None):
        detail = detail if isinstance(detail, dict) else {}
        self.service_code = detail.get("code")
        self.service_parameter = detail.get("param")
        self.response_id = response_id if isinstance(response_id, str) and response_id else None
        self.item_id = item_id if isinstance(item_id, str) and item_id else None
        self.source_event = source_event
        metadata = []
        for label, value in (("code", self.service_code), ("parameter", self.service_parameter)):
            if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_.\[\]-]{1,120}", value):
                metadata.append(f"{label}={value}")
        super().__init__(message + (f" ({', '.join(metadata)})" if metadata else ""))


def parse_control(text):
    if len(text) > 20000:
        raise VoiceProtocolError("메시지가 너무 큽니다.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VoiceProtocolError("올바른 JSON 메시지가 필요합니다.") from exc
    if not isinstance(data, dict):
        raise VoiceProtocolError("메시지는 JSON 객체여야 합니다.")
    kind = data.get("type")
    fields = {
        "start": {"type", "provider", "context", "voice_options"},
        "text": {"type", "text"},
        "stop": {"type"},
        "navigation_ack": {"type", "action_id", "revision"},
    }
    if not isinstance(kind, str) or kind not in fields or set(data) - fields[kind]:
        raise VoiceProtocolError("지원하지 않는 메시지 형식입니다.")
    if kind == "start":
        if data.get("provider") not in ("bing", "webiq"):
            raise VoiceProtocolError("Bing 또는 Web IQ를 선택하세요.")
        context = data.get("context", "")
        if not isinstance(context, str) or len(context) > MAX_TEXT:
            raise VoiceProtocolError("앱 맥락은 4,000자 이내여야 합니다.")
        if "voice_options" in data and not isinstance(data["voice_options"], dict):
            raise VoiceProtocolError("voice_options는 JSON 객체여야 합니다.")
    if kind == "text":
        prompt = data.get("text")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_TEXT:
            raise VoiceProtocolError("질문은 비어 있지 않은 4,000자 이내 문장이어야 합니다.")
    if kind == "navigation_ack":
        action_id, revision = data.get("action_id"), data.get("revision")
        if (
            not isinstance(action_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", action_id)
            or type(revision) is not int or not 0 <= revision <= 256
        ):
            raise VoiceProtocolError("앱 화면 반영 확인 메시지가 올바르지 않습니다.")
    return data


def context_message(context, at=None):
    at = at or datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    return (
        f"대화 기준시각: {at}\n"
        f"앱에서 전달한 내비게이션 맥락:\n{context or '별도 앱 맥락 없음'}\n"
        "이 메시지 자체에는 답하지 말고 다음 사용자 질문을 해석할 때 참고하세요."
    )


def connection_url(settings, agent, *, voice_options=None):
    parsed = urlparse(settings.voice_endpoint)
    options = validate_options({} if voice_options is None else voice_options, settings.voice_name)
    params = {"api-version": API_VERSION}
    if options["connection_mode"] in (MODEL_MODE, SEARCH_MODE):
        params["model"] = options["llm_model"]
    elif options["connection_mode"] == "realtime_agent_tool":
        params["model"] = options["realtime_model"]
    else:
        if agent is None:
            raise ConfigError("직접 연결할 Foundry Agent 설정이 필요합니다.")
        params.update({"agent-name": agent.name, "agent-project-name": settings.project_name})
        if agent.version:
            params["agent-version"] = agent.version
        if settings.foundry_resource_override:
            params["foundry-resource-override"] = settings.foundry_resource_override
        if settings.agent_identity_client_id:
            params["agent-authentication-identity-client-id"] = settings.agent_identity_client_id
    return urlunparse((
        "wss", parsed.netloc, parsed.path.rstrip("/") + "/voice-live/realtime",
        "", urlencode(params), "",
    ))


@asynccontextmanager
async def open_connection(settings, agent, *, voice_options=None, credential=None):
    owns_credential = credential is None
    credential = settings.credential() if owns_credential else credential
    try:
        try:
            async with asyncio.timeout(65):
                token = await asyncio.to_thread(credential.get_token, "https://ai.azure.com/.default")
        except RuntimeError as exc:
            raise ConfigError("Entra 인증에 실패했습니다. 로컬 로그인과 지정 구독을 확인하세요.") from exc
        # Own the HTTP session so handshake cancellation also closes its transport.
        timeout = aiohttp.ClientTimeout(total=None, connect=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with AsyncExitStack() as stack:
                async with asyncio.timeout(20):
                    transport = await stack.enter_async_context(session.ws_connect(
                        connection_url(settings, agent, voice_options=voice_options),
                        headers={"Authorization": f"Bearer {token.token}", **trace_headers()},
                        heartbeat=30,
                        max_msg_size=4 * 1024 * 1024,
                        timeout=aiohttp.ClientWSTimeout(ws_close=5),
                    ))
                yield VoiceLiveConnection(session, transport)
    finally:
        close = getattr(credential, "close", None)
        if owns_credential and close is not None:
            await asyncio.to_thread(close)


class VoiceSession:
    def __init__(self, settings, provider, context="", *, connector=open_connection, voice_options=None):
        self.options = validate_options({} if voice_options is None else voice_options, settings.voice_name)
        settings.require(provider, connection_mode=self.options["connection_mode"])
        self.settings = settings
        self.provider = provider
        self.agent = settings.agents.get(provider)
        self.context = context
        self.navigation = NavigationVoice() if self.options["connection_mode"] == MODEL_MODE else None
        self.navigation_queue = asyncio.Queue()
        self.navigation_responses = set()
        self.pending_responses = {}
        self.cancellation_requests = deque(maxlen=256)
        self.response_generation = 0
        self.connector = connector
        self.ready = asyncio.Event()
        self.connection_opened = asyncio.Event()
        self.closed = asyncio.Event()
        self.context_id = uuid4().hex
        self.context_sent = False
        self.active_response = None
        self.response_pending = False
        self.interrupted = set()
        self.user_transcripts = {}
        self.assistant_transcripts = {}
        self.item_responses = {}
        self.completed_responses = set()
        self.citations = set()
        self.flow_notifications = deque(maxlen=1024)
        self.audio_input_received = False
        self.audio_input_sent = False
        self.stop_requested = False
        self.session_id = uuid4().hex
        self.connection = None
        self.tools = ToolLifecycle()
        self.context_ready = False
        self.mcp_tools_required = False
        self.mcp_tools_ready = False
        self.mcp_tools_failed = False
        self.tool_followups = 0
        # MCP calls run after the response that requested them ends, so the answer waits for their results.
        self.mcp_settled = set()
        self.followup_after = None
        # End-to-end Bing runs the Toolbox's Bing-based Web Search as an app-executed function.
        self.web_search = None
        if (
            self.options["connection_mode"] == "realtime_agent_tool" and provider == "bing"
            and settings.web_search_toolbox_url
        ):
            from tmap_poc.web_search import ToolboxWebSearch

            self.web_search = ToolboxWebSearch(settings)
        self.web_search_queue = asyncio.Queue()
        self.mcp_search = "web_search" if self.web_search is not None else "webiq"

    async def _send(self, socket, event):
        started = monotonic()
        await socket.send_json({
            **event,
            "session_id": self.session_id,
            "provider": None if self.navigation is not None else self.provider,
        })
        elapsed = monotonic() - started
        if elapsed >= _SLOW_RELAY_SECONDS:
            logger.warning(
                "Slow Voice browser send (event=%s, wall_ms=%.0f, session=%s)",
                event.get("type"), elapsed * 1000, self.session_id,
            )

    async def _flow(
        self, socket, stage, status, *, source_event=None, operation=None,
        item_id=None, response_id=None, tool_id=None, data=None, once=False,
    ):
        if once:
            key = (stage, status, source_event, item_id, response_id, tool_id)
            if key in self.flow_notifications:
                return
            self.flow_notifications.append(key)
        await self._send(socket, {
            "type": "flow", "stage": stage, "status": status,
            "observation": "service_event" if source_event else "app_operation",
            **({"source_event": source_event} if source_event else {"operation": operation}),
            "item_id": item_id, "response_id": response_id, "tool_id": tool_id,
            "data": data or {},
        })

    async def _mark_ready_if_possible(self, socket):
        if self.ready.is_set() or not self.context_ready:
            return
        if self.mcp_tools_required and not self.mcp_tools_ready:
            return
        if self.navigation is not None:
            await self.navigation.publish(socket)
        self.ready.set()
        await self._send(socket, {
            "type": "status", "state": "ready",
            "connection_mode": self.options["connection_mode"],
            "provider_label": None if self.navigation is not None else PROVIDER_LABELS[self.provider],
            "agent": (
                {"name": self.agent.name, "version": self.agent.version, "pinned": bool(self.agent.version)}
                if self.navigation is None else None
            ),
        })

    async def _tool_flow(self, event, socket, response_id, tool_id, tool):
        kind = event.get("type")
        item = event.get("item")
        item = item if isinstance(item, dict) else {}
        summary = self.tools.summary(tool_id) or tool or {}
        if kind in _TOOL_FLOW_EVENTS:
            tool_kind, status = _TOOL_FLOW_EVENTS[kind]
        elif kind in _TOOL_ARGUMENT_EVENTS:
            tool_kind, status = _TOOL_ARGUMENT_EVENTS[kind], "arguments_ready"
        elif kind in ("response.output_item.added", "response.output_item.done") and item.get("type") in (
            "mcp_call", "foundry_agent_call", "function_call", "web_search_call", "file_search_call",
            "bing_grounding_call",
        ):
            tool_kind = item["type"]
            status = "announced" if kind.endswith(".added") else "output_observed"
        else:
            return
        if response_id in self.interrupted:
            return
        data = {"kind": tool_kind, **_flow_fields(summary, ("name",))}
        data.update(_flow_fields(item, ("name", "server_label", "call_id", "status")))
        data.update(_flow_fields(event, ("name", "call_id", "agent_response_id")))
        if kind in _TOOL_ARGUMENT_EVENTS:
            data.update(_flow_arguments(event.get("arguments")))
        elif "arguments" in item:
            data.update(_flow_arguments(item["arguments"]))
        await self._flow(
            socket, "tool", status, source_event=kind,
            response_id=response_id, tool_id=tool_id, data=data, once=tool_id is not None,
        )

    async def _user_transcript(self, event, socket, *, pending=False):
        item_id = event.get("item_id")
        if not isinstance(item_id, str) or not item_id or item_id == self.context_id:
            return
        previous = self.user_transcripts.get(item_id)
        if previous is not None and (pending or previous["final"]):
            return
        final = event.get("type") == "conversation.item.input_audio_transcription.completed"
        text = "" if pending else event.get("transcript" if final else "delta")
        if not isinstance(text, str):
            return
        self.user_transcripts[item_id] = {
            "text": text if final else (previous["text"] if previous else "") + text,
            "final": final,
        }
        await self._send(socket, {
            "type": "transcript", "role": "user", "text": text,
            "final": final, "item_id": item_id, "input_mode": "audio",
            "source_event": event.get("type"),
        })

    async def _assistant_transcript(self, socket, response_id, item_id, channel, text, *, final):
        if not isinstance(text, str) or (not text and not final):
            return
        if not item_id or response_id in self.interrupted:
            return
        if not final and response_id in self.completed_responses:
            return
        previous = self.assistant_transcripts.get(item_id)
        if previous is None:
            previous = {
                "response_id": response_id, "channel": channel, "text": "", "final": False,
            }
            self.assistant_transcripts[item_id] = previous
        if previous["response_id"] not in (None, response_id):
            return
        # Stream one channel per message; only a final audio transcript may replace text.
        if previous["channel"] != channel and not (channel == "audio" and final):
            return
        if previous["final"] and (not final or previous["text"] == text):
            if final:
                previous["channel"] = channel
            return
        previous.update(
            response_id=response_id,
            channel=channel,
            text=text if final else previous["text"] + text,
            final=final,
        )
        await self._send(socket, {
            "type": "transcript", "role": "assistant", "item_id": item_id,
            "response_id": response_id, "text": text, "final": final,
        })

    async def _annotations(self, socket, annotations, response_id, item_id):
        if not isinstance(annotations, list) or response_id in self.interrupted:
            return
        for citation in citation_links(annotations):
            key = (response_id, item_id, citation["url"])
            if key in self.citations:
                continue
            self.citations.add(key)
            await self._send(socket, {
                "type": "citation", "item_id": item_id, "response_id": response_id,
                "source": "annotation", **citation,
            })

    async def _content(self, socket, content, response_id, item_id):
        if not isinstance(content, list):
            return
        texts, transcripts = [], []
        for part in content:
            if not isinstance(part, dict):
                continue
            await self._annotations(socket, part.get("annotations"), response_id, item_id)
            if part.get("type") in ("text", "output_text") and isinstance(part.get("text"), str):
                texts.append(part["text"])
            elif part.get("type") in ("audio", "output_audio") and isinstance(part.get("transcript"), str):
                transcripts.append(part["transcript"])
        if transcripts or texts:
            await self._assistant_transcript(
                socket, response_id, item_id, "audio" if transcripts else "text",
                "".join(transcripts or texts), final=True,
            )

    async def run(self, socket):
        attributes = {
            "app.transport": "voice_live",
            "gen_ai.agent.name": "navigation-app" if self.navigation else self.agent.name,
            "app.voice.connection_mode": self.options.get("connection_mode", "agent"),
        }
        model = self.options["llm_model"] or self.options["realtime_model"]
        if model:
            attributes["gen_ai.request.model"] = model
        if self.agent is not None and self.agent.version and not self.navigation:
            attributes["gen_ai.agent.version"] = self.agent.version
        with span("navigation.voice.session", **attributes) as current:
            self.trace_span = current
            self.tools.parent = current
            status, error = "incomplete", "session_closed"
            try:
                await self._send(socket, {
                    "type": "trace", "trace_id": trace_id(), "session_id": self.session_id,
                })
                return await self._run(socket)
            except TimeoutError:
                error = "session_timeout"
                raise
            except (WebSocketDisconnect, asyncio.CancelledError):
                status, error = "cancelled", "session_cancelled"
                raise
            finally:
                if self.stop_requested:
                    status, error = "cancelled", "session_stopped"
                self.tools.close(status, error)

    async def _run(self, socket):
        tasks = [
            asyncio.create_task(self._serve_cloud(socket)),
            asyncio.create_task(self._from_browser(None, socket)),
            asyncio.create_task(self._ready_deadline()),
            asyncio.create_task(self._monitor_event_loop()),
        ]
        if self.navigation is not None:
            tasks.append(asyncio.create_task(self._navigation_worker(socket)))
        if self.web_search is not None:
            tasks.append(asyncio.create_task(self._web_search_worker(socket)))
        try:
            async with asyncio.timeout(900):
                completed, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in completed:
                    task.result()
        finally:
            self.closed.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.pending_responses.clear()
            self.cancellation_requests.clear()
        return "stopped" if self.stop_requested else "service_closed"

    async def _serve_cloud(self, socket):
        mode = self.options["connection_mode"]
        connector_options = {"voice_options": self.options} if mode != "agent" else {}
        search_attachment = None
        if mode == MODEL_MODE:
            session_options = build_model_session(self.options)
        elif self.web_search is not None:
            # End-to-end reaches Bing without an Agent: the app runs the Toolbox's Bing-based Web Search.
            session_options = build_web_search_session(self.options)
            search_attachment = "web_search_function"
        elif mode in (SEARCH_MODE, "realtime_agent_tool"):
            agent_config = {
                "agent_name": self.agent.name,
                "project_name": self.settings.project_name,
                "agent_version": self.agent.version,
                "foundry_resource_override": self.settings.foundry_resource_override or None,
                "client_id": self.settings.agent_identity_client_id or None,
            }
            if self.provider == "webiq":
                from tmap_poc.webiq_mcp import resolve_webiq_mcp_target

                target_config = await resolve_webiq_mcp_target(self.settings, self.agent)
                search_attachment = "mcp"
            else:
                target_config = {key: value for key, value in agent_config.items() if value is not None}
                search_attachment = "foundry_agent"
            session_options = build_search_session(self.options, target_config)
        else:
            session_options = build_session_options(self.options)
        self.mcp_tools_required = search_attachment == "mcp"
        target = {
            "api_version": API_VERSION, "connection_mode": mode,
            "target_scope": "configured",
            "endpoint_host": urlparse(self.settings.voice_endpoint).hostname,
        }
        if self.navigation is None:
            target.update(
                agent={"name": self.agent.name, "version": self.agent.version},
                project_name=self.settings.project_name,
            )
            if self.settings.foundry_resource_override:
                target["foundry_resource_override"] = self.settings.foundry_resource_override
        requested_model = self.options["llm_model"] or self.options["realtime_model"]
        if requested_model:
            target["requested_model"] = requested_model
        if search_attachment:
            target["search_attachment"] = search_attachment
        await self._flow(socket, "connection", "connecting", operation="connect", data=target)
        async with self.connector(self.settings, self.agent, **connector_options) as connection:
            self.connection = connection
            self.connection_opened.set()
            await self._flow(socket, "connection", "connected", operation="connect")
            await connection.session.update(session=session_options)
            request = session_options.as_dict()
            visible = _flow_session(request)
            for tool in request.get("tools") or []:
                if isinstance(tool, dict) and tool.get("type") == "foundry_agent":
                    visible["agent_tool"] = _flow_fields(tool, (
                        "agent_name", "agent_version", "project_name",
                        "foundry_resource_override", "return_agent_response_directly",
                    ))
                elif isinstance(tool, dict) and tool.get("type") == "mcp":
                    host = urlparse(tool.get("server_url", "")).hostname
                    visible["search_tool"] = {
                        "type": "mcp",
                        **_flow_fields(tool, ("server_label",)),
                        **({"server_host": host} if host else {}),
                        "allowed_tools": [
                            name for name in tool.get("allowed_tools", [])
                            if isinstance(name, str) and len(name) <= 64
                        ][:64],
                    }
            await self._flow(
                socket, "request", "sent", operation="session.update", data=visible,
            )
            try:
                await self._from_service(connection, socket)
            finally:
                self.connection = None

    async def _ready_deadline(self):
        await self.connection_opened.wait()
        try:
            await asyncio.wait_for(self.ready.wait(), timeout=30)
        except TimeoutError as exc:
            if self.mcp_tools_required and not self.mcp_tools_ready:
                raise VoiceServiceError(self._mcp_tools_error()) from exc
            raise
        await self.closed.wait()

    async def _monitor_event_loop(self):
        previous = monotonic()
        while True:
            await asyncio.sleep(0.1)
            current = monotonic()
            lag = current - previous - 0.1
            previous = current
            if lag >= _SLOW_RELAY_SECONDS:
                logger.warning(
                    "Voice event-loop lag (lag_ms=%.0f, session=%s)", lag * 1000, self.session_id,
                )

    def _mcp_tools_error(self):
        return "WebIQ 검색 도구를 불러오지 못했습니다. 잠시 후 다시 시작하거나 WebIQ 연결을 확인하세요."

    async def _maybe_followup(self, connection, socket):
        """Ask for the answer once every search the last response started has returned."""
        if self.followup_after is None:
            return
        origin, waiting = self.followup_after
        waiting.difference_update(self.mcp_settled)
        if waiting:
            return
        self.followup_after = None
        connection = self.connection or connection
        if connection is None or self.stop_requested or self.active_response is not None or self.response_pending:
            return
        await self._request_response(connection, origin, socket, purpose="tool_followup")

    async def _request_response(self, connection, origin, socket=None, *, purpose=None):
        self.response_pending = True
        if self.navigation is None and purpose == "tool_followup":
            await connection.response.create(response=ResponseCreateParams(instructions=FOLLOWUP_INSTRUCTIONS[self.mcp_search]))
        elif self.navigation is None:
            await connection.response.create()
        else:
            request_id = uuid4().hex
            # The originating turn must survive the gap before response.created.
            self.pending_responses[request_id] = origin
            await connection.response.create(response=ResponseCreateParams(
                metadata={_RESPONSE_TAG: request_id},
            ))
        if socket is not None:
            await self._flow(
                socket, "response", "requested", operation="response.create",
                data={"purpose": purpose} if purpose else None,
            )

    async def _web_search_worker(self, socket):
        """Run the model's web_search calls on the Foundry Toolbox, then ask for the answer."""
        from tmap_poc.web_search import WebSearchError

        await self.connection_opened.wait()
        while True:
            response_id, generation, calls, over_limit = await self.web_search_queue.get()
            try:
                connection = self.connection
                if connection is None:
                    raise VoiceServiceError("웹 검색 중 음성 연결이 종료되었습니다.")
                for call in calls:
                    started = monotonic()
                    query = ""
                    try:
                        arguments = json.loads(call.get("arguments") or "{}")
                        query = arguments.get("search_query") if isinstance(arguments, dict) else ""
                        if not isinstance(query, str) or not query.strip() or len(query) > 200:
                            raise WebSearchError("검색어가 올바르지 않습니다.")
                        query = query.strip()
                        if over_limit:
                            raise WebSearchError("이 질문으로 이미 세 번 검색했습니다. 지금까지 찾은 내용으로 답하세요.")
                        with span("execute_tool web_search", **{
                            "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "web_search",
                            "gen_ai.tool.call.id": call["call_id"], "app.execution.location": "application",
                        }):
                            result = await self.web_search.search(query)
                        status, output = "completed", result
                    except (WebSearchError, json.JSONDecodeError) as exc:
                        message = str(exc) if isinstance(exc, WebSearchError) else "검색어가 올바르지 않습니다."
                        status, output = "failed", {"error": message}
                    if self.stop_requested or response_id in self.interrupted:
                        break
                    await connection.conversation.item.create(item=FunctionCallOutputItem(
                        call_id=call["call_id"], output=json.dumps(output, ensure_ascii=False),
                    ))
                    await self._send(socket, {
                        "type": "tool", "kind": "function_call", "id": call.get("id") or call["call_id"],
                        "name": "web_search", "arguments": {"search_query": query} if query else {},
                        "status": status, "output": output, "response_id": response_id,
                        "observed_elapsed_ms": round((monotonic() - started) * 1000, 2),
                        "timing_scope": "application_foundry_toolbox_call",
                    })
                # A new question during the search keeps its own answer; this result is not spoken then.
                if (
                    response_id not in self.interrupted and generation == self.response_generation
                    and not self.stop_requested and self.active_response is None and not self.response_pending
                ):
                    await self._request_response(connection, response_id, socket, purpose="tool_followup")
            finally:
                self.web_search_queue.task_done()

    async def _navigation_worker(self, socket):
        await self.connection_opened.wait()
        while True:
            response_id, generation, calls = await self.navigation_queue.get()
            try:
                connection = self.connection
                if connection is None:
                    raise VoiceServiceError("앱 명령 실행 중 음성 연결이 종료되었습니다.")
                executed = await self.navigation.dispatch(
                    calls, connection, socket,
                    cancelled=lambda: self.stop_requested or response_id in self.interrupted,
                )
                # Keep receiving speech/interrupts while the browser confirms its state.
                if executed and response_id not in self.interrupted and generation == self.response_generation:
                    await self._request_response(connection, response_id, socket)
                    await self._send(socket, {"type": "activity", "state": "thinking"})
            finally:
                self.navigation_responses.discard(response_id)
                self.navigation_queue.task_done()

    async def _from_browser(self, connection, socket):
        while True:
            message = await socket.receive()
            active = self.connection or connection
            if message["type"] == "websocket.disconnect":
                if active is not None and (self.active_response or self.response_pending):
                    await active.response.cancel()
                raise WebSocketDisconnect(message.get("code", 1000))
            audio = message.get("bytes")
            if audio is not None:
                if not self.ready.is_set() or active is None:
                    raise VoiceProtocolError("음성 연결 준비가 끝난 뒤 녹음을 시작하세요.")
                if not audio or len(audio) > MAX_AUDIO_BYTES or len(audio) % 2:
                    raise VoiceProtocolError("24kHz 모노 PCM16 오디오 프레임이 필요합니다.")
                if not self.audio_input_received:
                    self.audio_input_received = True
                    await self._flow(socket, "input", "received", operation="browser.audio", data={
                        "input_mode": "audio", "format": "pcm16", "sample_rate": SAMPLE_RATE,
                        "first_frame_bytes": len(audio),
                    })
                started = monotonic()
                await active.input_audio_buffer.append(
                    audio=base64.b64encode(audio).decode("ascii")
                )
                elapsed = monotonic() - started
                if elapsed >= _SLOW_RELAY_SECONDS:
                    logger.warning(
                        "Slow Voice audio upload (wall_ms=%.0f, bytes=%d, session=%s)",
                        elapsed * 1000, len(audio), self.session_id,
                    )
                if not self.audio_input_sent:
                    self.audio_input_sent = True
                    await self._flow(
                        socket, "request", "sent", operation="input_audio_buffer.append",
                        data={"input_mode": "audio", "first_frame_bytes": len(audio)},
                    )
                # Buffered receives and uncongested sends need not suspend this task.
                await asyncio.sleep(0)
                continue
            control = parse_control(message.get("text") or "")
            if control["type"] == "navigation_ack":
                if self.navigation is None or not self.navigation.acknowledge(control["action_id"], control["revision"]):
                    raise VoiceProtocolError("대기 중인 앱 명령과 화면 반영 확인이 일치하지 않습니다.")
                continue
            if control["type"] == "stop":
                self.stop_requested = True
                if active is not None and (self.active_response or self.response_pending):
                    await active.response.cancel()
                return
            if control["type"] != "text" or not self.ready.is_set() or active is None:
                raise VoiceProtocolError("연결이 준비된 뒤 질문을 보내세요.")
            await self._flow(
                socket, "input", "received", operation="browser.text",
                data={"input_mode": "text", "text": control["text"]},
            )
            if self.active_response or self.response_pending or self.navigation_responses or self.pending_responses:
                await self._send(socket, {
                    "type": "error", "code": "response_busy",
                    "message": "텍스트 질문은 현재 응답이 끝난 뒤 보내세요. 음성으로는 끼어들 수 있습니다.",
                })
                continue
            request_id = uuid4().hex
            await active.conversation.item.create(item=MessageItem(
                id=request_id, role="user", content=[InputTextContentPart(text=control["text"])]
            ))
            await self._send(socket, {
                "type": "transcript", "role": "user", "text": control["text"],
                "final": True, "item_id": request_id, "input_mode": "text",
            })
            await self._flow(
                socket, "request", "sent", operation="conversation.item.create", item_id=request_id,
                data={"purpose": "user_input", "role": "user", "input_mode": "text", "text": control["text"]},
            )
            self.tool_followups = 0
            self.followup_after = None
            await self._request_response(active, request_id, socket)

    async def _from_service(self, connection, socket):
        async for event in connection:
            started = monotonic()
            data = event if isinstance(event, dict) else event.as_dict()
            await self.handle_event(data, connection, socket)
            elapsed = monotonic() - started
            if elapsed >= _SLOW_RELAY_SECONDS:
                logger.warning(
                    "Slow Voice event relay (event=%s, wall_ms=%.0f, session=%s)",
                    data.get("type"), elapsed * 1000, self.session_id,
                )
            await asyncio.sleep(0)

    async def handle_event(self, event, connection, socket):
        if self.stop_requested or self.closed.is_set():
            return
        kind = event.get("type", "")
        item = event.get("item")
        item = item if isinstance(item, dict) else {}
        response = event.get("response")
        response = response if isinstance(response, dict) else {}
        event_item_id = event.get("item_id") or item.get("id")
        event_item_id = event_item_id if isinstance(event_item_id, str) and event_item_id else None
        reported_response = event.get("response_id") or response.get("id")
        reported_response = reported_response if isinstance(reported_response, str) and reported_response else None
        if kind.startswith("response.") and event_item_id and reported_response:
            previous_response = self.item_responses.get(event_item_id)
            if previous_response is not None and previous_response != reported_response:
                return
            self.item_responses[event_item_id] = reported_response
        observed_response = reported_response or self.item_responses.get(event_item_id)
        local_call = item.get("type") == "function_call" and (self.navigation is not None or self.web_search is not None)
        tool = None if local_call else self.tools.observe(event)
        if tool is not None and observed_response not in self.interrupted:
            if "arguments" in tool:
                tool["arguments"] = _flow_arguments(tool["arguments"]).get("arguments", {})
            await self._send(socket, {
                "type": "tool", "response_id": observed_response, "source_event": kind, **tool,
            })
        await self._tool_flow(event, socket, observed_response, event_item_id, tool)
        response_id = observed_response
        if response_id is None and kind.startswith((
            "response.audio", "response.text", "response.output_text", "response.content_part",
        )):
            response_id = self.active_response
        item_id = event_item_id or response_id
        if response_id in self.interrupted and kind.startswith((
            "response.audio", "response.text", "response.output_text", "response.content_part",
            "response.output_item",
        )):
            return
        if kind in ("session.created", "session.updated"):
            await self._flow(
                socket, "session", kind.split(".")[-1], source_event=kind,
                data=_flow_session(event.get("session")),
            )
        if kind == "session.updated" and not self.context_sent:
            self.context_sent = True
            context = context_message(self.context)
            if self.navigation is not None:
                context += "\n앱 실행 상태 (서버 제공 시연 데이터):\n" + json.dumps(
                    self.navigation.state.snapshot(), ensure_ascii=False,
                )
            await connection.conversation.item.create(item=MessageItem(
                id=self.context_id, role="user",
                content=[InputTextContentPart(text=context)],
            ))
            await self._flow(
                socket, "request", "sent", operation="conversation.item.create", item_id=self.context_id,
                data={"purpose": "app_context", "role": "user", "content_omitted": True},
            )
        elif kind == "conversation.item.created" and item.get("id") == self.context_id:
            self.context_ready = True
            await self._mark_ready_if_possible(socket)
        elif kind == "input_audio_buffer.speech_started":
            await self._flow(
                socket, "speech", "started", source_event=kind, item_id=event_item_id,
                data=_flow_fields(event, ("audio_start_ms",)),
            )
            await self._user_transcript(event, socket, pending=True)
            if self.options["interrupt_response"]:
                if self.active_response:
                    self.interrupted.add(self.active_response)
                self.interrupted.update(self.navigation_responses)
                self.interrupted.update(self.pending_responses.values())
                await self._send(socket, {"type": "interrupt", "response_id": self.active_response})
            await self._send(socket, {"type": "activity", "state": "listening"})
        elif kind == "input_audio_buffer.speech_stopped":
            await self._flow(
                socket, "speech", "stopped", source_event=kind, item_id=event_item_id,
                data=_flow_fields(event, ("audio_end_ms",)),
            )
            await self._user_transcript(event, socket, pending=True)
            await self._send(socket, {"type": "activity", "state": "thinking"})
        elif kind == "input_audio_buffer.committed":
            self.tool_followups = 0
            self.followup_after = None
            await self._flow(
                socket, "input", "committed", source_event=kind, item_id=event_item_id,
                data=_flow_fields(event, ("previous_item_id",)),
            )
            await self._user_transcript(event, socket, pending=True)
        elif kind in ("mcp_list_tools.in_progress", "mcp_list_tools.completed", "mcp_list_tools.failed"):
            if self.mcp_tools_required and kind == "mcp_list_tools.failed":
                self.mcp_tools_failed = True
                raise VoiceServiceError(
                    self._mcp_tools_error(),
                    event.get("error"), item_id=event_item_id, source_event=kind,
                )
            await self._flow(
                socket, "tool_discovery", kind.rsplit(".", 1)[-1],
                source_event=kind, tool_id=event_item_id, once=event_item_id is not None,
            )
            if self.mcp_tools_required and kind == "mcp_list_tools.completed":
                self.mcp_tools_ready = True
                await self._mark_ready_if_possible(socket)
        elif item.get("type") == "mcp_list_tools" and kind in (
            "conversation.item.created", "response.output_item.added", "response.output_item.done",
        ):
            catalog = item.get("tools")
            data = _flow_fields(item, ("server_label",))
            if isinstance(catalog, list):
                names = [_flow_fields(tool, ("name",)).get("name") for tool in catalog[:64]]
                data.update(
                    tools=[name for name in names if isinstance(name, str)],
                    tools_truncated=len(catalog) > 64,
                )
            await self._flow(
                socket, "tool_discovery", "catalog_observed", source_event=kind,
                tool_id=event_item_id, data=data, once=event_item_id is not None,
            )
        elif kind == "conversation.item.created" and item.get("type") == "message" and item.get("role") == "user":
            await self._flow(
                socket, "input", "accepted", source_event=kind, item_id=event_item_id,
                data={"role": "user"},
            )
        elif kind == "response.created":
            created_id = response.get("id")
            if isinstance(created_id, str) and (
                created_id in self.completed_responses or created_id in self.interrupted
            ):
                return
            metadata = response.get("metadata")
            request_id = metadata.get(_RESPONSE_TAG) if isinstance(metadata, dict) else None
            origin = self.pending_responses.pop(request_id, None) if isinstance(request_id, str) else None
            self.response_pending = bool(self.pending_responses)
            if origin is not None and origin in self.interrupted:
                if not isinstance(created_id, str) or not created_id:
                    raise VoiceServiceError("중단할 음성 응답의 ID가 없습니다.")
                self.interrupted.add(created_id)
                cancellation_id = uuid4().hex
                self.cancellation_requests.append(cancellation_id)
                await connection.response.cancel(response_id=created_id, event_id=cancellation_id)
                return
            self.response_generation += 1
            self.active_response = created_id
            await self._flow(
                socket, "response", "created", source_event=kind,
                response_id=reported_response, data=_flow_fields(response, ("status",)),
            )
            current = getattr(self, "trace_span", None)
            if current is not None and isinstance(self.active_response, str):
                current.add_event("voice.response.created", {"app.voice.response_id": self.active_response})
            await self._send(socket, {
                "type": "activity", "state": "thinking", "response_id": self.active_response,
            })
        elif kind in (
            "conversation.item.input_audio_transcription.delta",
            "conversation.item.input_audio_transcription.completed",
        ):
            await self._user_transcript(event, socket)
        elif kind == "response.audio.delta":
            if response_id not in self.completed_responses and event.get("delta"):
                await self._flow(
                    socket, "audio", "started", source_event=kind,
                    item_id=event_item_id, response_id=observed_response,
                    data={"scope": "service_audio_generation"}, once=True,
                )
                await self._send(socket, {
                    "type": "audio", "data": event["delta"], "response_id": response_id,
                })
        elif kind == "response.audio.done":
            await self._flow(
                socket, "audio", "done", source_event=kind,
                item_id=event_item_id, response_id=observed_response,
                data={"scope": "service_audio_generation"}, once=True,
            )
        elif kind in ("response.audio_transcript.delta", "response.audio_transcript.done"):
            await self._assistant_transcript(
                socket, response_id, item_id, "audio",
                event.get("transcript") if kind.endswith(".done") else event.get("delta"),
                final=kind.endswith(".done"),
            )
        elif kind in (
            "response.audio_transcript.annotation.added", "response.text.annotation.added",
            "response.output_text.annotation.added",
        ):
            await self._annotations(socket, [event.get("annotation")], response_id, item_id)
        elif kind in (
            "response.text.delta", "response.text.done",
            "response.output_text.delta", "response.output_text.done",
        ):
            await self._assistant_transcript(
                socket, response_id, item_id, "text",
                event.get("text") if kind.endswith(".done") else event.get("delta"),
                final=kind.endswith(".done"),
            )
        elif kind == "response.content_part.done":
            await self._content(socket, [event.get("part")], response_id, item_id)
        elif kind == "response.output_item.done" and item.get("role") == "assistant":
            await self._content(socket, item.get("content"), response_id, item_id)
        elif kind == "response.foundry_agent_call.completed":
            current = getattr(self, "trace_span", None)
            if current is not None:
                foundry_response_link(event.get("agent_response_id"), parent=current)
        elif kind in ("response.mcp_call.completed", "response.mcp_call.failed"):
            if event_item_id:
                self.mcp_settled.add(event_item_id)
            await self._maybe_followup(connection, socket)
        elif kind == "response.done":
            done_id = response.get("id") or response_id
            completed_output = response.get("output")
            output_items = completed_output if isinstance(completed_output, list) else []
            has_other_call = any(
                isinstance(item, dict) and item.get("type") in ("function_call", "foundry_agent_call")
                for item in output_items
            )
            # A realtime model may speak a filler and then call a tool in the same response; only the
            # response's final item tells whether the tool result still needs an answer.
            final_item = next((
                item for item in reversed(output_items)
                if isinstance(item, dict) and item.get("type") in ("message", "mcp_call", "function_call", "foundry_agent_call")
            ), None)
            ends_with_mcp_call = final_item is not None and final_item.get("type") == "mcp_call"
            answered = final_item is not None and final_item.get("type") == "message" and final_item.get("role") == "assistant"
            if response.get("usage") is not None:
                await self._send(socket, {
                    "type": "usage", "source": "voice_live",
                    "response_id": done_id, "usage": response["usage"],
                })
            if response.get("status") == "completed" and done_id not in self.interrupted:
                for output_item in output_items:
                    if not isinstance(output_item, dict) or output_item.get("role") != "assistant":
                        continue
                    output_id = output_item.get("id") or done_id
                    if not isinstance(output_id, str):
                        continue
                    previous_response = self.item_responses.get(output_id)
                    if previous_response is not None and previous_response != done_id:
                        continue
                    if done_id:
                        self.item_responses[output_id] = done_id
                    await self._content(socket, output_item.get("content"), done_id, output_id)
                for key, buffer in list(self.assistant_transcripts.items()):
                    if buffer["response_id"] == done_id and not buffer["final"] and buffer["text"]:
                        await self._assistant_transcript(
                            socket, done_id, key, buffer["channel"], buffer["text"], final=True,
                        )
                if answered:
                    self.tool_followups = 0
            if isinstance(done_id, str):
                self.completed_responses.add(done_id)
            if self.active_response == done_id:
                self.active_response = None
            if isinstance(done_id, str) and response.get("status") in ("cancelled", "failed", "incomplete"):
                cancelled = response.get("status") == "cancelled"
                self.tools.close(
                    "cancelled" if cancelled else "incomplete",
                    "response_cancelled" if cancelled else "response_incomplete",
                    response_id=done_id,
                )
            should_followup = (
                self.mcp_tools_required
                and response.get("status") == "completed"
                and done_id not in self.interrupted
                and ends_with_mcp_call
                and not has_other_call
                and not self.stop_requested
                and self.active_response is None
                and not self.response_pending
                and self.tool_followups < 3
            )
            # web_search calls always get an output; after three searches for one question they report a limit.
            web_calls = [
                item for item in output_items
                if self.web_search is not None and isinstance(item, dict) and item.get("type") == "function_call"
                and item.get("name") == "web_search" and isinstance(item.get("call_id"), str)
                and re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", item["call_id"])
            ] if response.get("status") == "completed" and done_id not in self.interrupted and not self.stop_requested else []
            # The page treats anything said in this response as talk before the search, not the answer.
            await self._send(socket, {
                "type": "response_done", "response_id": done_id,
                "status": response.get("status"), "interrupted": done_id in self.interrupted,
                "followup": should_followup or bool(web_calls), "source_event": kind,
            })
            if web_calls:
                self.tool_followups += 1
                self.web_search_queue.put_nowait((done_id, self.response_generation, web_calls, self.tool_followups > 3))
            if should_followup:
                self.tool_followups += 1
                self.followup_after = (done_id, {
                    item["id"] for item in output_items
                    if isinstance(item, dict) and item.get("type") == "mcp_call" and isinstance(item.get("id"), str)
                    and item.get("output") is None and item.get("error") is None
                    and item.get("status") not in ("completed", "failed")
                })
                await self._maybe_followup(connection, socket)
            if response.get("status") in ("failed", "incomplete") and done_id not in self.interrupted:
                status_details = response.get("status_details")
                detail = status_details.get("error") if isinstance(status_details, dict) else None
                raise VoiceServiceError(
                    "Voice Live 응답이 완료되지 않았습니다. 모델·검색 도구 설정과 접근 권한을 확인하세요.",
                    detail, response_id=done_id, source_event=kind,
                )
            if self.navigation is not None and response.get("status") == "completed":
                calls = self.navigation.calls(response)
                if calls:
                    if not isinstance(done_id, str) or not done_id:
                        raise NavigationError("invalid_response", "앱 명령을 요청한 응답 ID가 없습니다.")
                    self.navigation_responses.add(done_id)
                    self.navigation_queue.put_nowait((done_id, self.response_generation, calls))
        elif kind == "conversation.item.input_audio_transcription.failed":
            # A realtime model hears the audio itself, so only its unused caption failed and the session goes on.
            if self.options["connection_mode"] != "realtime_agent_tool":
                raise VoiceServiceError(
                    "음성 전사(STT)에 실패했습니다. 마이크 입력과 선택한 전사 모델·지역·접근 권한을 확인하거나 텍스트로 다시 질문하세요.",
                    event.get("error"), item_id=event_item_id, source_event=kind,
                )
            logger.warning("Caption transcription failed in a realtime session (session=%s)", self.session_id)
        elif kind == "warning":
            detail = _flow_fields(event.get("warning"), ("code", "param"))
            await self._flow(socket, "service", "warning", source_event=kind, data={
                key: value for key, value in detail.items()
                if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_.\[\]-]{1,120}", value)
            })
        elif kind == "error":
            detail = event.get("error")
            if (
                kind == "error" and isinstance(detail, dict)
                and detail.get("code") == "response_cancel_not_active"
                and detail.get("event_id") in self.cancellation_requests
            ):
                self.cancellation_requests.remove(detail["event_id"])
                logger.info("Interrupted navigation response was already terminal when cancellation arrived.")
                return
            raise VoiceServiceError(
                "Voice Live 서비스가 설정을 처리하지 못했습니다. 선택한 모델·지역·설정과 접근 권한을 확인하세요.",
                event.get("error"), response_id=reported_response, source_event=kind,
            )
