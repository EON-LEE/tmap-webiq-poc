import asyncio
from contextlib import asynccontextmanager
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import aiohttp

from voice_poc import live as live_module
from voice_poc.agents import AgentReference, PROVIDER_LABELS
from voice_poc.live import (
    MAX_COMMENTARY_CHARS, AgentCallError, FoundryAgentCaller, LiveServiceError, LiveSession, agent_result,
    spoken_text,
)
from voice_poc.news import news_rules
from voice_poc.settings import AppSettings, ConfigError
from voice_poc.voice import VoiceProtocolError
from voice_poc.voice_options import VoiceOptionsError, build_live_session, validate_options

TIMEOUT = 10
NOW = "2026-10-01T09:00:00+09:00"


def live_settings(**overrides):
    return AppSettings(**{
        "project_endpoint": "https://agent.example.invalid/api/projects/voice-poc",
        "voice_endpoint": "https://voice.example.invalid",
        "model": "test-model", "subscription": "explicit-test-subscription",
        "agents": {
            "bing": AgentReference("test-bing", "1"),
            "webiq": AgentReference("test-webiq", "2"),
        },
        "live_endpoint": "https://live.example.invalid",
        "live_deployment": "gpt-live-1",
        **overrides,
    })


def live_options(**options):
    return validate_options({"connection_mode": "gpt_live", **options}, "ko-KR-SunHiNeural")


class FakeLive:
    """GPT-Live service double that acknowledges client events like the documented protocol."""

    def __init__(self, *, start=True):
        self.start = start
        self.sent = []
        self.sent_events = asyncio.Queue()
        self.events = asyncio.Queue()

    async def send_json(self, event):
        self.sent.append(event)
        await self.sent_events.put(event)
        kind = event["type"]
        if kind == "session.start" and self.start:
            await self.events.put({"type": "session.started", "session": {
                "id": "sess_1", "expires_at": 1790000000, **event["session"],
            }})
        elif kind == "session.close":
            await self.events.put({"type": "session.closed", "reason": "client_requested", "usage": {"seconds": 3.5}})
        elif kind == "session.commentary.append":
            await self.events.put({
                "type": "session.commentary.appended", "client_event_id": event["event_id"],
                "start_ms": 4000, "end_ms": 9000,
            })

    def __aiter__(self):
        return self

    async def __anext__(self):
        event = await self.events.get()
        if event is None:
            raise StopAsyncIteration
        return event


class Harness:
    def __init__(self, provider="webiq", context="", *, options=None, news=None, answer=None, service=None, config=None):
        self.service = service or FakeLive()
        self.browser = asyncio.Queue()
        self.outbox = asyncio.Queue()
        self.events = []
        self.agent_calls = []
        self.connector_calls = []
        self.answer = answer or (lambda provider, text: {
            "answer": "오늘 주요 뉴스입니다.", "citations": [], "tools": [],
        })

        async def caller(provider, text):
            self.agent_calls.append((provider, text))
            result = self.answer(provider, text)
            if asyncio.iscoroutine(result):
                result = await result
            if isinstance(result, Exception):
                raise result
            return result

        @asynccontextmanager
        async def connector(settings, *, tokens):
            self.connector_calls.append((settings, tokens))
            yield self.service

        async def send_json(event):
            self.events.append(event)
            await self.outbox.put(event)

        self.socket = SimpleNamespace(receive=self.browser.get, send_json=send_json)
        self.session = LiveSession(
            config or live_settings(), provider, context,
            voice_options={"connection_mode": "gpt_live", **(options or {})}, news=news,
            connector=connector, agent_caller=caller,
        )
        self.task = None

    def start(self):
        self.task = asyncio.create_task(self.session.run(self.socket))
        return self

    async def expect(self, kind, **fields):
        async with asyncio.timeout(TIMEOUT):
            while True:
                event = await self.outbox.get()
                if event["type"] == kind and all(event.get(key) == value for key, value in fields.items()):
                    return event

    async def sent(self, kind):
        async with asyncio.timeout(TIMEOUT):
            while True:
                event = await self.service.sent_events.get()
                if event["type"] == kind:
                    return event

    async def ready(self):
        await self.expect("status", state="ready")
        return self

    async def emit(self, **event):
        await self.service.events.put(event)

    async def text(self, data):
        await self.browser.put({"type": "websocket.receive", "text": json.dumps(data)})

    async def audio(self, data):
        await self.browser.put({"type": "websocket.receive", "bytes": data})

    async def finish(self):
        return await asyncio.wait_for(self.task, TIMEOUT)

    async def stop(self):
        await self.text({"type": "stop"})
        return await self.finish()

    async def close(self):
        if self.task is not None and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)


class LiveSessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.harnesses = []

    async def asyncTearDown(self):
        for harness in self.harnesses:
            await harness.close()

    def harness(self, *args, **kwargs):
        harness = Harness(*args, **kwargs)
        self.harnesses.append(harness)
        return harness.start()

    async def test_session_start_is_strict_and_ready_follows_the_service_session(self):
        h = self.harness()
        start = await h.sent("session.start")
        self.assertEqual(set(start), {"type", "event_id", "session"})
        self.assertRegex(start["event_id"], r"^evt_[0-9a-f]{32}$")
        session = start["session"]
        self.assertEqual(set(session), {"model", "instructions", "audio", "delegation"})
        self.assertEqual(session["model"], "gpt-live-1")
        self.assertEqual(session["audio"], {"output": {"voice": "noeul"}})
        self.assertEqual(session["delegation"], {"type": "client"})
        self.assertIn("Always speak Korean", session["instructions"])
        self.assertIn("Occasionally use brief natural backchannel", session["instructions"])

        described = await h.expect("live_session")
        ready = await h.expect("status", state="ready")
        ids = {"session_id": h.session.session_id, "provider": "webiq"}
        self.assertEqual(described, {
            "type": "live_session", "model": "gpt-live-1", "voice": "noeul",
            "instructions": session["instructions"], "language": "korean", "backchannel": "sometimes",
            "delegation": "client", "session": "sess_1", **ids,
        })
        self.assertEqual(ready, {
            "type": "status", "state": "ready", "connection_mode": "gpt_live",
            "provider_label": PROVIDER_LABELS["webiq"], "agent": {"name": "test-webiq", "version": "2"}, **ids,
        })
        self.assertEqual(h.events[0], {**ready, "state": "connecting"})
        self.assertEqual([event["type"] for event in h.events], ["status", "live_session", "status"])
        self.assertEqual(len(h.connector_calls), 1)
        self.assertIs(h.connector_calls[0][1], h.session.tokens)
        self.assertEqual(await h.stop(), "stopped")

    async def test_selected_voice_language_and_backchannel_reach_the_session(self):
        h = self.harness("bing", options={"live_voice": "marin", "live_language": "none", "live_backchannel": "often"})
        session = (await h.sent("session.start"))["session"]
        self.assertEqual(session["audio"], {"output": {"voice": "marin"}})
        self.assertNotIn("Korean", session["instructions"])
        self.assertNotIn("language the user", session["instructions"])
        self.assertIn("Frequently use brief backchannel", session["instructions"])
        described = await h.expect("live_session")
        self.assertEqual((described["voice"], described["language"], described["backchannel"]), ("marin", "none", "often"))
        self.assertEqual((await h.expect("status", state="ready"))["agent"], {"name": "test-bing", "version": "1"})
        self.assertEqual(await h.stop(), "stopped")

    async def test_audio_is_forwarded_both_ways_and_invalid_frames_are_dropped(self):
        h = await self.harness().ready()
        for frame in (b"", b"\x01", b"\x01\x00\x02\x00"):
            await h.audio(frame)
        appended = await h.sent("session.input_audio.append")
        self.assertEqual(appended, {"type": "session.input_audio.append", "audio": "AQACAA=="})
        for delta in ("", "AQ==", "!!!", None, "AQACAA=="):
            await h.emit(type="session.output_audio.delta", delta=delta, start_ms=100, end_ms=200.5)
        await h.emit(type="session.usage.updated", usage={"seconds": 1.5}, context_window={"usage_ratio": 0.02})
        usage = await h.expect("live_usage")
        self.assertEqual((usage["seconds"], usage["usage_ratio"]), (1.5, 0.02))
        audio = [event for event in h.events if event["type"] == "audio"]
        self.assertEqual([(event["data"], event["start_ms"], event["end_ms"]) for event in audio], [("AQACAA==", 100, 200)])
        self.assertEqual(await h.stop(), "stopped")
        self.assertEqual([event["type"] for event in h.service.sent].count("session.input_audio.append"), 1)

    async def test_audio_before_start_is_dropped_and_oversized_frames_fail(self):
        h = self.harness(service=FakeLive(start=False))
        await h.sent("session.start")
        await h.audio(b"\x01\x00")
        await h.audio(b"\x00" * 48002)
        with self.assertRaises(VoiceProtocolError):
            await h.finish()
        self.assertEqual([event["type"] for event in h.service.sent], ["session.start"])

    async def test_transcripts_are_relayed_by_role(self):
        h = await self.harness().ready()
        await h.emit(type="session.input_transcript.delta", delta="오늘 ", start_ms=0, end_ms=400)
        await h.emit(type="session.output_transcript.delta", delta="네", start_ms="x", end_ms=float("nan"))
        await h.emit(type="session.input_transcript.delta", delta="")
        await h.emit(type="session.input_transcript.delta", delta="날씨")
        await h.expect("live_transcript", delta="날씨")
        ids = {"session_id": h.session.session_id, "provider": "webiq"}
        self.assertEqual([event for event in h.events if event["type"] == "live_transcript"], [
            {"type": "live_transcript", "role": "user", "delta": "오늘 ", "start_ms": 0, "end_ms": 400, **ids},
            {"type": "live_transcript", "role": "assistant", "delta": "네", "start_ms": None, "end_ms": None, **ids},
            {"type": "live_transcript", "role": "user", "delta": "날씨", "start_ms": None, "end_ms": None, **ids},
        ])
        self.assertEqual(await h.stop(), "stopped")

    async def test_delegation_runs_the_agent_and_returns_clean_commentary(self):
        answer = (
            "## 오늘의 주요 뉴스\n- **첫째** 기사【3:0†source】 [연합뉴스](https://news.example/a) 보도입니다. "
            "\ue200cite\ue202turn0news1\ue201 https://news.example/b\n"
            + "추가 설명 문장입니다. " * 80
        )
        calls = {"output": "x" * 7000}
        h = self.harness("webiq", "arrival 20:10", news={"length": "30s"}, answer=lambda provider, text: {
            "answer": answer,
            "citations": [{"url": "https://news.example/a", "title": "A"}, {"url": "javascript:alert(1)"}],
            "tools": [{"name": "news", "arguments": {"query": "주요 뉴스"}, **calls}, "ignored"],
        })
        await h.ready()
        await h.emit(type="session.input_transcript.delta", delta="오늘 ")
        await h.emit(type="session.input_transcript.delta", delta="주요 뉴스 알려줘")
        await h.expect("live_transcript", delta="주요 뉴스 알려줘")
        await h.emit(type="session.delegation.created", offset_ms=1200, delegation={
            "id": "del_1", "type": "delegation", "target": "client",
        })
        await h.emit(type="session.input_transcript.delta", delta=" 요약해서")
        created = await h.expect("delegation", status="created")
        self.assertEqual(created, {
            "type": "delegation", "id": "del_1", "status": "created", "offset_ms": 1200,
            "request": "오늘 주요 뉴스 알려줘 요약해서", "session_id": h.session.session_id, "provider": "webiq",
        })
        completed = await h.expect("delegation", status="completed")
        commentary = await h.sent("session.commentary.append")
        delivered = await h.expect("delegation", status="delivered")

        provider, text = h.agent_calls[0]
        self.assertEqual(provider, "webiq")
        self.assertTrue(text.startswith("오늘 주요 뉴스 알려줘 요약해서\n\n"))
        self.assertIn(news_rules({"length": "30s"}), text)
        self.assertIn("앱에서 전달한 맥락:\narrival 20:10", text)
        self.assertIn("대화 기준시각: ", text)

        self.assertEqual(set(commentary), {"type", "event_id", "delegation_id", "content"})
        self.assertEqual(commentary["delegation_id"], "del_1")
        content = commentary["content"]
        self.assertTrue(content.startswith("오늘의 주요 뉴스 첫째 기사 연합뉴스 보도입니다. 추가 설명 문장입니다."))
        self.assertLessEqual(len(content), MAX_COMMENTARY_CHARS)
        self.assertTrue(content.endswith("."))
        for marker in ("#", "**", "【", "†", "http", "\ue200", "](", "\n"):
            self.assertNotIn(marker, content)

        self.assertEqual(completed["answer"], answer[:2000])
        self.assertEqual(completed["spoken"], content)
        self.assertEqual(completed["citations"], [{"url": "https://news.example/a", "title": "A"}])
        self.assertEqual(completed["tools"], [{"name": "news", "arguments": {"query": "주요 뉴스"}, "output": "x" * 6000}])
        self.assertIsInstance(completed["elapsed_ms"], int)
        self.assertEqual(delivered, {
            "type": "delegation", "id": "del_1", "status": "delivered", "start_ms": 4000, "end_ms": 9000,
            "session_id": h.session.session_id, "provider": "webiq",
        })
        statuses = [event["status"] for event in h.events if event["type"] == "delegation"]
        self.assertEqual(statuses, ["created", "completed", "delivered"])
        self.assertEqual(h.session.commentary, {})
        self.assertEqual(await h.stop(), "stopped")

    async def test_delegation_waits_briefly_for_the_transcript_then_reuses_the_last_request(self):
        h = await self.harness("bing").ready()
        await h.emit(type="session.delegation.created", delegation={"id": "del_1", "target": "client"})
        await asyncio.sleep(0.05)
        await h.emit(type="session.input_transcript.delta", delta="서울 날씨")
        first = await h.expect("delegation", id="del_1", status="created")
        self.assertEqual((first["request"], first["offset_ms"]), ("서울 날씨", None))
        await h.expect("delegation", id="del_1", status="delivered")
        with patch.object(live_module, "_REQUEST_WAIT_SECONDS", 0.05):
            await h.emit(type="session.delegation.created", delegation={"id": "del_2", "target": "client"})
            second = await h.expect("delegation", id="del_2", status="created")
        self.assertEqual(second["request"], "서울 날씨")
        await h.emit(type="session.delegation.created", delegation={"id": "server_task", "target": "server"})
        await h.emit(type="session.delegation.created", delegation={"target": "client"})
        await h.expect("delegation", id="del_2", status="delivered")
        self.assertEqual(await h.stop(), "stopped")
        self.assertEqual({event.get("id") for event in h.events if event["type"] == "delegation"}, {"del_1", "del_2"})
        self.assertEqual([call[0] for call in h.agent_calls], ["bing", "bing"])

    async def test_unknown_request_is_said_explicitly(self):
        with patch.object(live_module, "_REQUEST_WAIT_SECONDS", 0.05):
            h = await self.harness().ready()
            await h.emit(type="session.delegation.created", delegation={"id": "del_1", "target": "client"})
            created = await h.expect("delegation", status="created")
        self.assertEqual(created["request"], "직전 사용자 발화를 확인하지 못했습니다")
        self.assertEqual(await h.stop(), "stopped")

    async def test_failed_delegation_reports_a_safe_message_and_asks_to_retry(self):
        failures = [
            AgentCallError("Foundry Agent가 응답하지 않았습니다 (HTTP 500)."),
            RuntimeError("internal detail that must not leak"),
            {"answer": None},
            {"answer": "【1:0†source】 "},
        ]
        h = await self.harness(answer=lambda provider, text: failures.pop(0)).ready()
        messages = []
        with self.assertLogs("voice_poc.live", "WARNING") as logs:
            for index in range(4):
                await h.emit(type="session.input_transcript.delta", delta=f"질문 {index}")
                await h.emit(type="session.delegation.created", delegation={"id": f"del_{index}", "target": "client"})
                failed = await h.expect("delegation", id=f"del_{index}", status="failed")
                commentary = await h.sent("session.commentary.append")
                self.assertEqual(commentary["delegation_id"], f"del_{index}")
                self.assertEqual(commentary["content"], "검색 결과를 가져오지 못했습니다. 다시 질문해 달라고 안내하세요.")
                await h.expect("delegation", id=f"del_{index}", status="delivered")
                self.assertEqual(set(failed), {"type", "id", "status", "message", "elapsed_ms", "session_id", "provider"})
                messages.append(failed["message"])
        self.assertNotIn("internal detail", "\n".join(logs.output))
        self.assertEqual(messages, [
            "Foundry Agent가 응답하지 않았습니다 (HTTP 500).", "Foundry Agent 검색을 완료하지 못했습니다.",
            "Foundry Agent 응답 형식이 올바르지 않습니다.", "Foundry Agent 답변이 비어 있습니다.",
        ])
        self.assertEqual(await h.stop(), "stopped")

    async def test_text_questions_are_rejected_without_ending_the_session(self):
        h = await self.harness().ready()
        await h.text({"type": "text", "text": "오늘 뉴스"})
        error = await h.expect("error")
        self.assertEqual(error, {
            "type": "error", "code": "live_voice_only", "message": "GPT-Live는 음성으로만 질문할 수 있습니다.",
            "terminal": False, "session_id": h.session.session_id, "provider": "webiq",
        })
        self.assertFalse(h.task.done())
        self.assertEqual(await h.stop(), "stopped")

    async def test_stop_closes_the_service_session_gracefully(self):
        h = await self.harness().ready()
        await h.text({"type": "stop"})
        close = await h.sent("session.close")
        self.assertEqual(set(close), {"type", "event_id"})
        self.assertEqual(await h.finish(), "stopped")
        self.assertEqual(h.events[-1], {
            "type": "live_closed", "reason": "client_requested", "seconds": 3.5,
            "session_id": h.session.session_id, "provider": "webiq",
        })

    async def test_service_close_ends_the_session(self):
        h = await self.harness().ready()
        await h.emit(type="session.closed", reason="max_duration", usage={"seconds": 600})
        self.assertEqual(await h.finish(), "service_closed")
        self.assertEqual((h.events[-1]["type"], h.events[-1]["reason"], h.events[-1]["seconds"]), ("live_closed", "max_duration", 600))
        await asyncio.sleep(0)
        self.assertNotIn("session.close", [event["type"] for event in h.service.sent])

    async def test_service_errors_are_terminal_only_before_the_session_starts(self):
        h = await self.harness().ready()
        await h.emit(type="error", error={"message": "x" * 400, "client_event_id": "evt_1"})
        await h.emit(type="error", error={"code": "Rate-Limited"})
        first = await h.expect("error")
        second = await h.expect("error")
        self.assertEqual((first["code"], first["terminal"]), ("live_error", False))
        self.assertEqual(first["message"], "GPT-Live 오류: " + "x" * 300)
        self.assertEqual((second["code"], second["message"]), ("live_rate_limited", "GPT-Live 서비스 오류가 발생했습니다."))
        self.assertEqual(await h.stop(), "stopped")

        early = Harness(service=FakeLive(start=False))
        self.harnesses.append(early.start())
        await early.sent("session.start")
        await early.emit(type="error", error={"code": "invalid_value", "message": "voice is not supported"})
        with self.assertRaises(LiveServiceError) as caught:
            await early.finish()
        self.assertEqual(caught.exception.code, "live_invalid_value")
        self.assertEqual(str(caught.exception), "GPT-Live 오류: voice is not supported")
        self.assertFalse([event for event in early.events if event["type"] == "error"])

    async def test_service_that_closes_or_stalls_before_start_fails_clearly(self):
        closed = Harness(service=FakeLive(start=False))
        self.harnesses.append(closed.start())
        await closed.sent("session.start")
        await closed.service.events.put(None)
        with self.assertRaises(LiveServiceError) as caught:
            await closed.finish()
        self.assertEqual(caught.exception.code, "live_closed_before_start")

        with patch.object(live_module, "_READY_SECONDS", 0.05):
            stalled = Harness(service=FakeLive(start=False))
            self.harnesses.append(stalled.start())
            with self.assertRaises(LiveServiceError) as caught:
                await stalled.finish()
        self.assertEqual(caught.exception.code, "live_start_timeout")

    async def test_browser_disconnect_cancels_pending_delegations(self):
        blocked = asyncio.Event()

        async def slow(provider, text):
            blocked.set()
            await asyncio.sleep(60)

        h = await self.harness(answer=slow).ready()
        await h.emit(type="session.input_transcript.delta", delta="뉴스")
        await h.emit(type="session.delegation.created", delegation={"id": "del_1", "target": "client"})
        await asyncio.wait_for(blocked.wait(), TIMEOUT)
        background = set(h.session.background)
        self.assertEqual(len(background), 1)
        await h.browser.put({"type": "websocket.disconnect", "code": 1001})
        with self.assertRaises(Exception) as caught:
            await h.finish()
        self.assertEqual(type(caught.exception).__name__, "WebSocketDisconnect")
        self.assertTrue(all(task.done() for task in background))

    def test_constructor_validates_mode_settings_and_news(self):
        def make(provider="webiq", config=None, **kwargs):
            kwargs.setdefault("voice_options", {"connection_mode": "gpt_live"})
            return LiveSession(config or live_settings(), provider, **kwargs)

        self.assertEqual(make().options, live_options())
        with self.assertRaises(VoiceOptionsError):
            make(voice_options={})
        with self.assertRaises(VoiceOptionsError):
            make(voice_options={"connection_mode": "gpt_live", "speech_rate": 1.25})
        with self.assertRaises(VoiceOptionsError):
            make(voice_options={"connection_mode": "gpt_live", "live_voice": "alloy"})
        with self.assertRaises(ConfigError) as caught:
            make(config=live_settings(live_deployment=""))
        self.assertIn("POC_LIVE_DEPLOYMENT", str(caught.exception))
        with self.assertRaises(ConfigError):
            make(config=live_settings(agents={}))
        with self.assertRaises(VoiceProtocolError) as caught:
            make("bing", news={})
        self.assertEqual(caught.exception.code, "news_requires_webiq")
        self.assertEqual(make(news={"count": 3}).news["count"], 3)


class LiveSessionPayloadTests(unittest.TestCase):
    def build(self, news=None, **options):
        return build_live_session(live_options(**options), deployment="gpt-live-1", news=news, now=NOW)

    def test_instructions_follow_language_and_backchannel_options(self):
        korean = self.build()["instructions"].splitlines()
        self.assertTrue(korean[0].startswith("You are a voice assistant in a search comparison demo."))
        self.assertEqual(korean[1], f"Current date and time (Asia/Seoul): {NOW}.")
        self.assertEqual(korean[2], "Always speak Korean (한국어), even if the user speaks another language.")
        self.assertEqual(len(korean), 4)
        follow = self.build(live_language="follow_user", live_backchannel="none")["instructions"]
        self.assertIn("Reply in the language the user speaks.", follow)
        self.assertIn("Do not use backchannel acknowledgements", follow)
        silent = self.build(live_language="none")["instructions"].splitlines()
        self.assertEqual(len(silent), 3)
        self.assertFalse(any("language" in line.lower() or "Korean" in line for line in silent))

    def test_payload_has_only_documented_session_fields(self):
        payload = self.build(live_voice="marin")
        self.assertEqual(payload, {
            "model": "gpt-live-1", "instructions": payload["instructions"],
            "audio": {"output": {"voice": "marin"}}, "delegation": {"type": "client"},
        })
        news = self.build(news={"length": "30s"})["instructions"]
        self.assertIn("news briefing", news)
        self.assertIn("about 30 seconds", news)
        self.assertNotIn("news briefing", self.build()["instructions"])
        with self.assertRaises(VoiceOptionsError):
            build_live_session(validate_options({}, "ko-KR-SunHiNeural"), deployment="gpt-live-1")
        with self.assertRaises(VoiceOptionsError):
            build_live_session(live_options(), deployment=" ")


class AgentResultTests(unittest.TestCase):
    def test_messages_citations_and_tool_calls_are_extracted(self):
        result = agent_result({"output": [
            {"type": "mcp_list_tools", "tools": []},
            {"type": "mcp_call", "name": "news", "arguments": '{"query": "뉴스", "freshness": "Day"}', "output": "[]"},
            {"type": "web_search_call", "id": "ws_1", "status": "completed"},
            {"type": "function_call", "name": "lookup", "call_id": "call_1", "arguments": "not json"},
            {"type": "function_call_output", "call_id": "call_1", "output": {"rows": 2}},
            {"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": " 첫 문단 ", "annotations": [
                    {"type": "url_citation", "url": "https://news.example/a", "title": "A"},
                    {"type": "url_citation", "url": "https://news.example/a", "title": "duplicate"},
                    {"type": "file_citation", "file_id": "file_1"},
                ]},
                {"type": "output_text", "text": "둘째 문단", "annotations": [
                    {"type": "url_citation", "url": "https://news.example/b"},
                ]},
                {"type": "refusal", "refusal": "ignored"},
            ]},
            "ignored",
        ]})
        self.assertEqual(result["answer"], "첫 문단\n\n둘째 문단")
        self.assertEqual(result["citations"], [
            {"url": "https://news.example/a", "title": "A"},
            {"url": "https://news.example/b", "title": "news.example"},
        ])
        self.assertEqual(result["tools"], [
            {"name": "news", "arguments": {"query": "뉴스", "freshness": "Day"}, "output": "[]"},
            {"name": "web_search", "arguments": {}, "output": ""},
            {"name": "lookup", "arguments": "not json", "output": '{"rows": 2}'},
        ])

    def test_empty_or_malformed_results_raise_safe_errors(self):
        for data in (None, [], {}, {"output": []}, {"output": [{"type": "message", "content": [{"text": " "}]}]}):
            with self.subTest(data=data), self.assertRaises(AgentCallError):
                agent_result(data)


class SpokenTextTests(unittest.TestCase):
    def test_markdown_markers_and_urls_are_removed(self):
        answer = (
            "## 요약\n- **첫째** 기사【3:0†source】 [링크](https://a.example) https://b.example/x "
            "\ue200cite\ue202turn0\ue201 `끝`.\n> 인용 ![그림](https://c.example/i.png) | 표 |"
        )
        self.assertEqual(spoken_text(answer), "요약 첫째 기사 링크 끝. 인용 표")

    def test_long_answers_are_cut_at_a_sentence_or_marked(self):
        sentences = spoken_text("가나다라마바사아자차. " * 100)
        self.assertLessEqual(len(sentences), MAX_COMMENTARY_CHARS)
        self.assertTrue(sentences.endswith("차."))
        unbroken = spoken_text("가" * 700)
        self.assertEqual(unbroken, "가" * MAX_COMMENTARY_CHARS + "…")
        self.assertEqual(spoken_text("짧은 답"), "짧은 답")


class FoundryAgentCallerTests(unittest.IsolatedAsyncioTestCase):
    async def call(self, *, status=200, data=None, error=None, provider="webiq"):
        requests = []

        class Response:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def json(self, content_type=None):
                return data

        Response.status = status

        class Http:
            def __init__(self, *, timeout):
                requests.append({"timeout": timeout.total})

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            def post(self, url, *, json, headers):
                if error is not None:
                    raise error
                requests.append({"url": url, "json": json, "headers": headers})
                return Response()

        class Tokens:
            scopes = []

            async def get(self, scope):
                self.scopes.append(scope)
                return "token-for-test"

        tokens = Tokens()
        caller = FoundryAgentCaller(live_settings(), tokens)
        with patch.object(live_module.aiohttp, "ClientSession", Http):
            result = await caller(provider, "오늘 뉴스")
        return result, requests, tokens.scopes

    async def test_agent_runs_through_the_project_responses_endpoint(self):
        result, requests, scopes = await self.call(data={"output": [
            {"type": "message", "content": [{"type": "output_text", "text": "답변"}]},
        ]})
        self.assertEqual(result, {"answer": "답변", "citations": [], "tools": []})
        self.assertEqual(scopes, ["https://ai.azure.com/.default"])
        self.assertEqual(requests[0], {"timeout": 60})
        request = requests[1]
        self.assertEqual(request["url"], "https://agent.example.invalid/api/projects/voice-poc/openai/v1/responses")
        self.assertEqual(request["json"], {
            "input": "오늘 뉴스",
            "agent_reference": {"type": "agent_reference", "name": "test-webiq", "version": "2"},
        })
        self.assertEqual(request["headers"]["Authorization"].split(" "), ["Bearer", "token-for-test"])

    async def test_http_and_network_failures_become_safe_errors(self):
        with self.assertRaises(AgentCallError) as caught:
            await self.call(status=500, data={"error": {"message": "internal"}})
        self.assertEqual(str(caught.exception), "Foundry Agent가 응답하지 않았습니다 (HTTP 500).")
        with self.assertRaises(AgentCallError) as caught:
            await self.call(error=aiohttp.ClientConnectionError("dns failure"))
        self.assertEqual(str(caught.exception), "Foundry Agent에 연결하지 못했습니다.")
        with self.assertRaises(AgentCallError):
            await self.call(provider="other")


if __name__ == "__main__":
    unittest.main()
