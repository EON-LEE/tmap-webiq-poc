"""Azure OpenAI GPT-Live sessions that delegate search to the configured Foundry Agents.

GPT-Live listens and speaks itself. With client delegation it hands work to the app, which runs the
provider's existing Foundry Agent through the Responses API and returns the answer as commentary.
"""

import asyncio
import base64
import binascii
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime
import json
import logging
import math
import re
from time import monotonic, time
from uuid import uuid4
from zoneinfo import ZoneInfo

import aiohttp
from starlette.websockets import WebSocketDisconnect

from voice_poc.agents import PROVIDER_LABELS
from voice_poc.citations import citation_links
from voice_poc.news import news_rules, validate_news
from voice_poc.settings import ConfigError
from voice_poc.telemetry import span, trace_headers
from voice_poc.voice import MAX_AUDIO_BYTES, VoiceProtocolError, VoiceServiceError, parse_control
from voice_poc.voice_options import VoiceOptionsError, build_live_session, validate_options

LIVE_SCOPE = "https://cognitiveservices.azure.com/.default"
AGENT_SCOPE = "https://ai.azure.com/.default"
# Commentary is limited to 500 tokens; Korean text stays well below that at this length.
MAX_COMMENTARY_CHARS = 600
MAX_ANSWER_CHARS = 2000
MAX_TOOL_OUTPUT_CHARS = 6000
_READY_SECONDS = 30
_CLOSE_SECONDS = 5
_AGENT_TIMEOUT_SECONDS = 60
_REQUEST_WAIT_SECONDS = 1.5
_REQUEST_SETTLE_SECONDS = 0.3
_UNKNOWN_REQUEST = "직전 사용자 발화를 확인하지 못했습니다"
_FAILED_COMMENTARY = "검색 결과를 가져오지 못했습니다. 다시 질문해 달라고 안내하세요."
logger = logging.getLogger(__name__)


class LiveServiceError(VoiceServiceError):
    def __init__(self, message, *, code="live_error"):
        super().__init__(message)
        self.code = code


class AgentCallError(RuntimeError):
    """The Foundry Agent call failed; the message is safe to show."""


class _Tokens:
    """Entra tokens per scope, refreshed five minutes before expiry; owns one credential."""

    def __init__(self, settings):
        self.settings = settings
        self.credential = None
        self.cache = {}
        self.lock = asyncio.Lock()

    async def get(self, scope):
        async with self.lock:
            token = self.cache.get(scope)
            if token is None or token.expires_on - 300 < time():
                if self.credential is None:
                    self.credential = self.settings.credential()
                try:
                    async with asyncio.timeout(65):
                        token = await asyncio.to_thread(self.credential.get_token, scope)
                except RuntimeError as exc:
                    raise ConfigError("Entra 인증에 실패했습니다. 로컬 로그인과 지정 구독을 확인하세요.") from exc
                self.cache[scope] = token
            return token.token

    async def close(self):
        credential, self.credential = self.credential, None
        close = getattr(credential, "close", None)
        if close is not None:
            await asyncio.to_thread(close)


class LiveConnection:
    """JSON events over the GPT-Live WebSocket."""

    def __init__(self, transport):
        self.transport = transport

    async def send_json(self, event):
        await self.transport.send_str(json.dumps(event, ensure_ascii=False))

    def __aiter__(self):
        return self

    async def __anext__(self):
        while True:
            message = await self.transport.receive()
            if message.type == aiohttp.WSMsgType.TEXT:
                try:
                    event = json.loads(message.data)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    return event
            elif message.type in (
                aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING,
                aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR,
            ):
                raise StopAsyncIteration

    async def close(self):
        await self.transport.close()


@asynccontextmanager
async def open_live_connection(settings, *, tokens):
    settings.require_live()
    token = await tokens.get(LIVE_SCOPE)
    timeout = aiohttp.ClientTimeout(total=None, connect=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with AsyncExitStack() as stack:
            async with asyncio.timeout(20):
                transport = await stack.enter_async_context(session.ws_connect(
                    settings.live_url,
                    headers={"Authorization": f"Bearer {token}", **trace_headers()},
                    heartbeat=30,
                    max_msg_size=4 * 1024 * 1024,
                    timeout=aiohttp.ClientWSTimeout(ws_close=5),
                ))
            yield LiveConnection(transport)


def _tool_output(value):
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text[:MAX_TOOL_OUTPUT_CHARS]


def _tool_arguments(value):
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value[:2000]
        return parsed if isinstance(parsed, dict) else value[:2000]
    return value if isinstance(value, dict) else {}


def agent_result(data):
    """Return {"answer", "citations", "tools"} from a Responses API result."""
    if not isinstance(data, dict):
        raise AgentCallError("Foundry Agent 응답 형식이 올바르지 않습니다.")
    texts, annotations, tools, calls = [], [], [], {}
    for item in data.get("output") or []:
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            continue
        kind = item["type"]
        if kind == "message":
            for part in item.get("content") or []:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    texts.append(part["text"])
                    annotations.extend(
                        note for note in part.get("annotations") or []
                        if isinstance(note, dict) and note.get("type") == "url_citation"
                    )
        elif kind.endswith("_call"):
            name = item.get("name") if isinstance(item.get("name"), str) else kind[:-5]
            tool = {
                "name": name[:128],
                "arguments": _tool_arguments(item.get("arguments")),
                "output": _tool_output(item.get("output") if item.get("output") is not None else item.get("error")),
            }
            tools.append(tool)
            if isinstance(item.get("call_id"), str):
                calls[item["call_id"]] = tool
        elif kind.endswith("_call_output"):
            tool = calls.get(item.get("call_id"))
            if tool is not None and not tool["output"]:
                tool["output"] = _tool_output(item.get("output"))
    answer = "\n\n".join(text.strip() for text in texts if text.strip())
    if not answer:
        raise AgentCallError("Foundry Agent 답변이 비어 있습니다.")
    return {"answer": answer, "citations": citation_links(annotations)[:12], "tools": tools[:16]}


class FoundryAgentCaller:
    """Run the provider's Foundry Agent once through the project's OpenAI-compatible Responses API."""

    def __init__(self, settings, tokens):
        self.settings = settings
        self.tokens = tokens
        self.url = f"{settings.project_endpoint}/openai/v1/responses"

    async def __call__(self, provider, text):
        agent = self.settings.agents.get(provider)
        if agent is None:
            raise AgentCallError("검색 Agent가 설정되지 않았습니다.")
        token = await self.tokens.get(AGENT_SCOPE)
        body = {"input": text, "agent_reference": agent.as_dict()}
        headers = {"Authorization": f"Bearer {token}", **trace_headers()}
        timeout = aiohttp.ClientTimeout(total=_AGENT_TIMEOUT_SECONDS)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as http:
                async with http.post(self.url, json=body, headers=headers) as response:
                    if response.status >= 400:
                        raise AgentCallError(f"Foundry Agent가 응답하지 않았습니다 (HTTP {response.status}).")
                    data = await response.json(content_type=None)
        except AgentCallError:
            raise
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise AgentCallError("Foundry Agent에 연결하지 못했습니다.") from exc
        return agent_result(data)


def spoken_text(answer, limit=MAX_COMMENTARY_CHARS):
    """Plain speakable text: no markdown, citation markers, or URLs."""
    text = re.sub(r"\ue200[^\ue201]*\ue201", " ", answer)
    text = re.sub(r"【[^】]*†[^】]*】", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"(?m)^\s{0,3}(#{1,6}|>|[-*+])\s+", "", text)
    text = re.sub(r"\*\*|__|`+|~~", "", text)
    text = text.replace("|", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    ends = [match.end() for match in re.finditer(r"[.!?。](?=\s|$)", cut)]
    if ends and ends[-1] >= limit // 2:
        return cut[:ends[-1]]
    return cut.rstrip() + "…"


def _ms(value):
    if type(value) in (int, float) and math.isfinite(value):
        return int(value)
    return None


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def _text(value, limit=300):
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def _event_id():
    return "evt_" + uuid4().hex


def _message_type(text):
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return data.get("type") if isinstance(data, dict) else None


class LiveSession:
    def __init__(
        self, settings, provider, context="", *, voice_options, news=None, connector=None, agent_caller=None,
    ):
        self.options = validate_options(voice_options, settings.voice_name)
        if self.options["connection_mode"] != "gpt_live":
            raise VoiceOptionsError("LiveSession은 gpt_live 실행 구조 전용입니다.")
        settings.require(provider)
        settings.require_live()
        self.news = validate_news(news)
        if self.news is not None and provider != "webiq":
            raise VoiceProtocolError("뉴스 브리핑은 WebIQ로만 실행합니다.", code="news_requires_webiq")
        self.settings = settings
        self.provider = provider
        self.agent = settings.agents[provider]
        self.context = context
        self.session_id = uuid4().hex
        self.tokens = _Tokens(settings)
        self.connector = connector or open_live_connection
        self.agent_caller = agent_caller or FoundryAgentCaller(settings, self.tokens)
        self.connection = None
        self.send_lock = asyncio.Lock()
        self.connection_opened = asyncio.Event()
        self.started = asyncio.Event()
        self.service_closed = asyncio.Event()
        self.closed = asyncio.Event()
        self.stop_requested = False
        self.user_fragments = []
        self.fragment_arrived = asyncio.Event()
        self.last_request = ""
        self.commentary = {}
        self.background = set()
        self.session_payload = None

    async def _send(self, socket, event):
        await socket.send_json({**event, "session_id": self.session_id, "provider": self.provider})

    async def _service_send(self, event):
        connection = self.connection
        if connection is None:
            return False
        try:
            async with self.send_lock:
                await connection.send_json(event)
        except (aiohttp.ClientError, ConnectionError):
            return False
        return True

    def _status(self, state):
        return {
            "type": "status", "state": state, "connection_mode": "gpt_live",
            "provider_label": PROVIDER_LABELS[self.provider],
            "agent": {"name": self.agent.name, "version": self.agent.version},
        }

    async def run(self, socket):
        attributes = {
            "app.transport": "gpt_live",
            "gen_ai.agent.name": self.agent.name,
            "app.voice.connection_mode": "gpt_live",
            "gen_ai.request.model": self.settings.live_deployment,
        }
        if self.agent.version:
            attributes["gen_ai.agent.version"] = self.agent.version
        with span("voice.session", **attributes):
            try:
                return await self._run(socket)
            finally:
                await self.tokens.close()

    async def _run(self, socket):
        await self._send(socket, self._status("connecting"))
        tasks = [
            asyncio.create_task(self._serve(socket)),
            asyncio.create_task(self._from_browser(socket)),
            asyncio.create_task(self._ready_deadline()),
        ]
        try:
            async with asyncio.timeout(900):
                completed, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in completed:
                    task.result()
        finally:
            self.closed.set()
            pending = [*tasks, *self.background]
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        return "stopped" if self.stop_requested else "service_closed"

    async def _ready_deadline(self):
        await self.connection_opened.wait()
        try:
            await asyncio.wait_for(self.started.wait(), timeout=_READY_SECONDS)
        except TimeoutError as exc:
            raise LiveServiceError(
                "GPT-Live 세션이 30초 안에 시작되지 않았습니다. 배포, 지역과 권한을 확인하세요.",
                code="live_start_timeout",
            ) from exc
        await self.closed.wait()

    async def _serve(self, socket):
        self.session_payload = build_live_session(
            self.options, deployment=self.settings.live_deployment, news=self.news,
        )
        async with self.connector(self.settings, tokens=self.tokens) as connection:
            self.connection = connection
            self.connection_opened.set()
            try:
                await self._service_send({
                    "type": "session.start", "event_id": _event_id(), "session": self.session_payload,
                })
                async for event in connection:
                    if isinstance(event, dict) and await self.handle_event(event, socket):
                        return
                    await asyncio.sleep(0)
                if not self.started.is_set() and not self.stop_requested:
                    raise LiveServiceError(
                        "GPT-Live 연결이 세션 시작 전에 끊겼습니다. 배포, 지역과 권한을 확인하세요.",
                        code="live_closed_before_start",
                    )
            finally:
                self.connection = None

    async def _from_browser(self, socket):
        while True:
            message = await socket.receive()
            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))
            audio = message.get("bytes")
            if audio is not None:
                if len(audio) > MAX_AUDIO_BYTES:
                    raise VoiceProtocolError("24kHz 모노 PCM16 오디오 프레임이 필요합니다.")
                if audio and not len(audio) % 2 and self.started.is_set() and not self.stop_requested:
                    await self._service_send({
                        "type": "session.input_audio.append",
                        "audio": base64.b64encode(audio).decode("ascii"),
                    })
                await asyncio.sleep(0)
                continue
            text = message.get("text") or ""
            if _message_type(text) == "text":
                await self._send(socket, {
                    "type": "error", "code": "live_voice_only",
                    "message": "GPT-Live는 음성으로만 질문할 수 있습니다.", "terminal": False,
                })
                continue
            control = parse_control(text)
            if control["type"] != "stop":
                raise VoiceProtocolError("지원하지 않는 메시지 형식입니다.")
            self.stop_requested = True
            if await self._service_send({"type": "session.close", "event_id": _event_id()}):
                try:
                    await asyncio.wait_for(self.service_closed.wait(), timeout=_CLOSE_SECONDS)
                except TimeoutError:
                    logger.warning("GPT-Live close was not acknowledged (session=%s)", self.session_id)
            return

    async def handle_event(self, event, socket):
        """Relay one service event; return True when the service closed the session."""
        kind = event.get("type")
        if kind == "session.output_audio.delta":
            if self.stop_requested or not isinstance(event.get("delta"), str):
                return False
            try:
                audio = base64.b64decode(event["delta"], validate=True)
            except (binascii.Error, ValueError):
                return False
            if audio and not len(audio) % 2:
                await self._send(socket, {
                    "type": "audio", "data": event["delta"],
                    "start_ms": _ms(event.get("start_ms")), "end_ms": _ms(event.get("end_ms")),
                })
        elif kind in ("session.input_transcript.delta", "session.output_transcript.delta"):
            delta = event.get("delta")
            if not isinstance(delta, str) or not delta:
                return False
            role = "user" if kind == "session.input_transcript.delta" else "assistant"
            if role == "user":
                self.user_fragments.append(delta)
                self.fragment_arrived.set()
            await self._send(socket, {
                "type": "live_transcript", "role": role, "delta": delta,
                "start_ms": _ms(event.get("start_ms")), "end_ms": _ms(event.get("end_ms")),
            })
        elif kind == "session.started":
            await self._started(event, socket)
        elif kind == "session.delegation.created":
            delegation = event.get("delegation") if isinstance(event.get("delegation"), dict) else {}
            delegation_id = delegation.get("id")
            if not isinstance(delegation_id, str) or not delegation_id or delegation.get("target", "client") != "client":
                return False
            task = asyncio.create_task(self._delegate(
                socket, delegation_id, _ms(event.get("offset_ms")), self._take_request(), monotonic(),
            ))
            self.background.add(task)
            task.add_done_callback(self.background.discard)
        elif kind == "session.commentary.appended":
            client_event_id = event.get("client_event_id")
            delegation_id = self.commentary.pop(client_event_id, None) if isinstance(client_event_id, str) else None
            if delegation_id is not None:
                await self._send(socket, {
                    "type": "delegation", "id": delegation_id, "status": "delivered",
                    "start_ms": _ms(event.get("start_ms")), "end_ms": _ms(event.get("end_ms")),
                })
        elif kind == "session.usage.updated":
            usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
            window = event.get("context_window") if isinstance(event.get("context_window"), dict) else {}
            await self._send(socket, {
                "type": "live_usage", "seconds": _number(usage.get("seconds")),
                "usage_ratio": _number(window.get("usage_ratio")),
            })
        elif kind == "session.closed":
            usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
            self.service_closed.set()
            await self._send(socket, {
                "type": "live_closed", "reason": _text(event.get("reason"), 120),
                "seconds": _number(usage.get("seconds")),
            })
            return True
        elif kind == "error":
            await self._service_error(event, socket)
        return False

    async def _started(self, event, socket):
        session = event.get("session") if isinstance(event.get("session"), dict) else {}
        audio = session.get("audio") if isinstance(session.get("audio"), dict) else {}
        output = audio.get("output") if isinstance(audio.get("output"), dict) else {}
        delegation = session.get("delegation") if isinstance(session.get("delegation"), dict) else {}
        requested = self.session_payload
        await self._send(socket, {
            "type": "live_session",
            "model": _text(session.get("model"), 128) or requested["model"],
            "voice": _text(output.get("voice"), 64) or requested["audio"]["output"]["voice"],
            "instructions": session.get("instructions") if isinstance(session.get("instructions"), str)
            else requested["instructions"],
            "language": self.options["live_language"],
            "backchannel": self.options["live_backchannel"],
            "delegation": _text(delegation.get("type"), 32) or "client",
            "session": _text(session.get("id"), 128),
        })
        self.started.set()
        await self._send(socket, self._status("ready"))

    async def _service_error(self, event, socket):
        detail = event.get("error") if isinstance(event.get("error"), dict) else {}
        code = detail.get("code")
        code = re.sub(r"[^a-z0-9_]+", "_", code.lower()).strip("_")[:64] if isinstance(code, str) else ""
        code = "live_" + code if code else "live_error"
        message = _text(detail.get("message"))
        message = "GPT-Live 오류: " + message if message else "GPT-Live 서비스 오류가 발생했습니다."
        if not self.started.is_set():
            raise LiveServiceError(message, code=code)
        await self._send(socket, {"type": "error", "code": code, "message": message, "terminal": False})

    def _take_request(self):
        text = "".join(self.user_fragments)
        self.user_fragments.clear()
        return text

    async def _wait_fragment(self, timeout):
        self.fragment_arrived.clear()
        try:
            await asyncio.wait_for(self.fragment_arrived.wait(), timeout=max(timeout, 0))
        except TimeoutError:
            return False
        return True

    async def _request_text(self, text):
        # Delegation events carry no task text, so the request is the user's latest utterance,
        # whose transcript may still be arriving.
        deadline = monotonic() + _REQUEST_WAIT_SECONDS
        if text.strip() or self.user_fragments or await self._wait_fragment(deadline - monotonic()):
            while await self._wait_fragment(min(_REQUEST_SETTLE_SECONDS, deadline - monotonic())):
                pass
        text = (text + self._take_request()).strip()
        if text:
            self.last_request = text
            return text
        return self.last_request or _UNKNOWN_REQUEST

    def _agent_input(self, request):
        parts = [request]
        if self.news is not None:
            parts.append(news_rules(self.news))
        if self.context.strip():
            parts.append(f"앱에서 전달한 맥락:\n{self.context}")
        parts.append(f"대화 기준시각: {datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}")
        return "\n\n".join(parts)

    async def _commentary(self, delegation_id, content):
        if self.stop_requested:
            return
        event_id = _event_id()
        self.commentary[event_id] = delegation_id
        if not await self._service_send({
            "type": "session.commentary.append", "event_id": event_id,
            "delegation_id": delegation_id, "content": content,
        }):
            self.commentary.pop(event_id, None)

    async def _delegate(self, socket, delegation_id, offset_ms, text, received):
        request = await self._request_text(text)
        await self._send(socket, {
            "type": "delegation", "id": delegation_id, "status": "created",
            "offset_ms": offset_ms, "request": request,
        })
        try:
            result = await self.agent_caller(self.provider, self._agent_input(request))
            if not isinstance(result, dict) or not isinstance(result.get("answer"), str):
                raise AgentCallError("Foundry Agent 응답 형식이 올바르지 않습니다.")
            spoken = spoken_text(result["answer"])
            if not spoken:
                raise AgentCallError("Foundry Agent 답변이 비어 있습니다.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("GPT-Live delegation failed (%s, session=%s)", type(exc).__name__, self.session_id)
            message = str(exc) if isinstance(exc, (AgentCallError, ConfigError)) else "Foundry Agent 검색을 완료하지 못했습니다."
            await self._send(socket, {
                "type": "delegation", "id": delegation_id, "status": "failed", "message": message,
                "elapsed_ms": round((monotonic() - received) * 1000),
            })
            await self._commentary(delegation_id, _FAILED_COMMENTARY)
            return
        tools = [
            {
                "name": str(tool.get("name") or "tool")[:128],
                "arguments": tool.get("arguments") if isinstance(tool.get("arguments"), (dict, str)) else {},
                "output": _tool_output(tool.get("output")),
            }
            for tool in result.get("tools") or [] if isinstance(tool, dict)
        ]
        await self._send(socket, {
            "type": "delegation", "id": delegation_id, "status": "completed",
            "answer": result["answer"][:MAX_ANSWER_CHARS], "spoken": spoken,
            "citations": citation_links(result.get("citations") or []),
            "tools": tools, "elapsed_ms": round((monotonic() - received) * 1000),
        })
        # The browser sees "completed" before the service can acknowledge the commentary as "delivered".
        await self._commentary(delegation_id, spoken)
