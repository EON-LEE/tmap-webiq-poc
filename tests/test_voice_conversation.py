import asyncio
import base64
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from tmap_poc.api import create_app
from tmap_poc.app_settings import AppSettings
from tmap_poc.profiles import AgentReference
from tmap_poc.voice import VoiceServiceError, VoiceSession
from tmap_poc.voice_options import MODEL_MODE


def settings(**overrides):
    return AppSettings(**{
        "project_endpoint": "https://agent.example.invalid/api/projects/demo",
        "voice_endpoint": "https://voice.example.invalid",
        "subscription": "explicit-test-subscription",
        "agents": {
            "bing": AgentReference("test-bing", "1"),
            "webiq": AgentReference("test-webiq", "2"),
        },
        **overrides,
    })


class ProviderReadinessTests(unittest.TestCase):
    def test_existing_config_reports_per_provider_problems_without_cloud_calls(self):
        config = settings(agents={"bing": AgentReference("test-bing", "1")})
        with patch.object(AppSettings, "credential", side_effect=AssertionError("No cloud checks")):
            with TestClient(create_app(config)) as client:
                response = client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        data = response.json()
        bing, webiq = data["providers"]
        self.assertEqual(data["errors"], [])
        self.assertTrue(bing["configured"])
        self.assertEqual(bing["readiness_scope"], "configuration_only")
        self.assertEqual(bing["agent"], {"name": "test-bing", "version": "1", "pinned": True})
        self.assertFalse(webiq["configured"])
        self.assertIn("TMAP_WEBIQ_AGENT_NAME", " ".join(webiq["errors"]))
        self.assertIsNone(webiq["agent"])
        self.assertEqual(bing["label"], "Grounding with Bing")
        self.assertEqual(webiq["label"], "WebIQ")

    def test_unpinned_or_duplicate_agents_are_not_described_as_verified(self):
        reference = AgentReference("shared")
        config = settings(agents={"bing": reference, "webiq": reference})
        for provider in ("bing", "webiq"):
            result = config.provider_config(provider)
            self.assertTrue(result["configured"])
            self.assertFalse(result["agent"]["pinned"])
            self.assertIsNone(result["agent"]["version"])
            self.assertEqual(len(result["warnings"]), 2)
            self.assertIn("same Agent", " ".join(result["warnings"]))
            self.assertEqual(result["readiness_scope"], "configuration_only")

    def test_incomplete_project_paths_do_not_appear_ready(self):
        for path in ("/api/projects", "/api/projects/", "/api/projects/demo/extra"):
            with self.subTest(path=path):
                config = settings(project_endpoint="https://agent.example.invalid" + path)
                self.assertEqual(config.project_name, "")
                self.assertIn("GWB_PROJECT_ENDPOINT", " ".join(config.problems("bing")))
                self.assertEqual(config.problems(connection_mode=MODEL_MODE), [])
        self.assertEqual(settings().project_name, "demo")

    def test_terminal_api_error_preserves_known_response_correlation(self):
        class FailedSession:
            session_id = "test-session"

            def __init__(self, *_args):
                pass

            async def run(self, _socket):
                raise VoiceServiceError(
                    "응답 실패", {"code": "tool_failed", "message": "PRIVATE"},
                    response_id="failed-response",
                )

        with TestClient(create_app(settings(), voice_factory=FailedSession)) as client:
            with client.websocket_connect("/ws/voice", headers={"origin": "http://localhost:8000"}) as socket:
                socket.send_json({"type": "start", "provider": "webiq"})
                self.assertEqual(socket.receive_json()["state"], "connecting")
                event = socket.receive_json()
        self.assertEqual(event["type"], "error")
        self.assertTrue(event["terminal"])
        self.assertEqual(event["session_id"], "test-session")
        self.assertEqual(event["provider"], "webiq")
        self.assertEqual(event["response_id"], "failed-response")
        self.assertNotIn("item_id", event)
        self.assertNotIn("PRIVATE", event["message"])

    def test_terminal_stt_error_keeps_user_item_without_inventing_response_id(self):
        class FailedSession:
            session_id = "test-session"

            def __init__(self, *_args):
                pass

            async def run(self, _socket):
                raise VoiceServiceError("STT 실패", item_id="user-item")

        with TestClient(create_app(settings(), voice_factory=FailedSession)) as client:
            with client.websocket_connect("/ws/voice", headers={"origin": "http://localhost:8000"}) as socket:
                socket.send_json({"type": "start", "provider": "bing"})
                socket.receive_json()
                event = socket.receive_json()
        self.assertTrue(event["terminal"])
        self.assertEqual(event["item_id"], "user-item")
        self.assertNotIn("response_id", event)


class ConversationEventsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = VoiceSession(settings(), "webiq")
        self.socket = SimpleNamespace(send_json=AsyncMock())
        self.connection = SimpleNamespace(
            conversation=SimpleNamespace(item=SimpleNamespace(create=AsyncMock())),
            response=SimpleNamespace(create=AsyncMock(), cancel=AsyncMock()),
        )
        self.addCleanup(self.session.tools.close)

    async def event(self, kind, **fields):
        await self.session.handle_event({"type": kind, **fields}, self.connection, self.socket)

    def sent(self, kind, role=None):
        events = [call.args[0] for call in self.socket.send_json.call_args_list]
        return [
            event for event in events
            if event["type"] == kind and (role is None or event.get("role") == role)
        ]

    async def test_speech_placeholder_preserves_order_when_stt_finishes_after_answer(self):
        await self.event("input_audio_buffer.speech_started", item_id="user-one")
        await self.event("input_audio_buffer.speech_stopped", item_id="user-one")
        await self.event("input_audio_buffer.committed", item_id="user-one")
        await self.event("response.created", response={"id": "answer-one"})
        await self.event("response.audio_transcript.done", item_id="assistant-one", transcript="검색 답변")
        await self.event("response.done", response={"id": "answer-one", "status": "completed"})
        await self.event("response.created", response={"id": "answer-two"})
        await self.event(
            "conversation.item.input_audio_transcription.completed",
            item_id="user-one", transcript="영업시간 알려 줘",
        )
        transcripts = self.sent("transcript")
        self.assertEqual([event["role"] for event in transcripts], ["user", "assistant", "user"])
        self.assertEqual(transcripts[0]["text"], "")
        self.assertFalse(transcripts[0]["final"])
        self.assertEqual(transcripts[-1]["item_id"], "user-one")
        self.assertEqual(transcripts[-1]["input_mode"], "audio")
        self.assertNotIn("response_id", transcripts[-1])
        self.assertEqual(self.session.active_response, "answer-two")

    async def test_stt_deltas_and_authoritative_final_are_correlated_without_duplicates(self):
        for delta in ("광명", " 영업"):
            await self.event(
                "conversation.item.input_audio_transcription.delta", item_id="heard", delta=delta,
            )
        await self.event(
            "conversation.item.input_audio_transcription.completed",
            item_id="heard", transcript="광명점 영업시간",
        )
        await self.event(
            "conversation.item.input_audio_transcription.delta", item_id="heard", delta="late",
        )
        await self.event(
            "conversation.item.input_audio_transcription.completed",
            item_id="heard", transcript="광명점 영업시간",
        )
        events = self.sent("transcript", "user")
        self.assertEqual([event["text"] for event in events], ["광명", " 영업", "광명점 영업시간"])
        self.assertEqual([event["final"] for event in events], [False, False, True])
        self.assertEqual({event["item_id"] for event in events}, {"heard"})
        self.assertEqual({event["provider"] for event in events}, {"webiq"})
        self.assertEqual({event["session_id"] for event in events}, {self.session.session_id})

    async def test_unidentified_or_context_stt_never_becomes_an_assistant_turn(self):
        await self.event("response.created", response={"id": "assistant-response"})
        for item_id in (None, "", self.session.context_id):
            await self.event(
                "conversation.item.input_audio_transcription.completed",
                item_id=item_id, transcript="not a correlated user item",
            )
        self.assertEqual(self.sent("transcript"), [])

    async def test_stt_error_is_actionable_without_exposing_private_service_details(self):
        with self.assertRaises(VoiceServiceError) as error:
            await self.event(
                "conversation.item.input_audio_transcription.failed",
                item_id="heard",
                error={"code": "transcription_failed", "message": "PRIVATE_SERVICE_DETAILS"},
            )
        self.assertIn("STT", str(error.exception))
        self.assertIn("transcription_failed", str(error.exception))
        self.assertNotIn("PRIVATE_SERVICE_DETAILS", str(error.exception))
        self.assertEqual(error.exception.item_id, "heard")
        self.assertIsNone(error.exception.response_id)

    async def test_text_only_answer_streams_before_response_done(self):
        await self.event("response.created", response={"id": "answer"})
        await self.event("response.text.delta", item_id="message", delta="검색 ")
        await self.event("response.text.delta", item_id="message", delta="결과")
        events = self.sent("transcript", "assistant")
        self.assertEqual([event["text"] for event in events], ["검색 ", "결과"])
        self.assertTrue(all(not event["final"] for event in events))
        self.assertTrue(all(event["response_id"] == "answer" for event in events))
        await self.event("response.done", response={"id": "answer", "status": "completed"})
        self.assertEqual(self.sent("transcript")[-1]["text"], "검색 결과")
        self.assertTrue(self.sent("transcript")[-1]["final"])

    async def test_text_and_audio_use_one_message_without_concatenating_both_channels(self):
        await self.event("response.text.delta", response_id="answer", item_id="message", delta="검색 ")
        await self.event("response.audio_transcript.delta", response_id="answer", item_id="message", delta="음성 ")
        await self.event("response.text.done", response_id="answer", item_id="message", text="검색 결과")
        await self.event(
            "response.audio_transcript.done",
            response_id="answer", item_id="message", transcript="음성 검색 결과",
        )
        await self.event("response.text.done", response_id="answer", item_id="message", text="late text")
        events = self.sent("transcript", "assistant")
        self.assertEqual([event["text"] for event in events], ["검색 ", "검색 결과", "음성 검색 결과"])
        self.assertEqual({event["item_id"] for event in events}, {"message"})
        self.assertTrue(events[-1]["final"])

    async def test_identical_audio_final_deduplicates_and_takes_precedence_over_late_text(self):
        await self.event("response.text.done", response_id="answer", item_id="message", text="같은 답변")
        await self.event(
            "response.audio_transcript.done",
            response_id="answer", item_id="message", transcript="같은 답변",
        )
        await self.event("response.text.done", response_id="answer", item_id="message", text="late text")
        self.assertEqual(len(self.sent("transcript")), 1)

    async def test_final_message_content_is_used_when_streamed_text_is_not_provided(self):
        await self.event("response.done", response={
            "id": "answer", "status": "completed", "output": [{
                "id": "message", "type": "message", "role": "assistant",
                "content": [{"type": "text", "text": "관측된 "}, {"type": "text", "text": "답변"}],
            }],
        })
        events = self.sent("transcript", "assistant")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["text"], "관측된 답변")
        self.assertEqual(events[0]["response_id"], "answer")

    async def test_failed_response_does_not_mark_partial_text_as_final(self):
        await self.event("response.text.delta", response_id="answer", item_id="message", delta="partial")
        with self.assertRaises(VoiceServiceError) as error:
            await self.event("response.done", response={"id": "answer", "status": "failed"})
        self.assertEqual(len(self.sent("transcript")), 1)
        self.assertFalse(self.sent("transcript")[0]["final"])
        self.assertEqual(error.exception.response_id, "answer")
        self.assertEqual(self.sent("response_done")[0]["status"], "failed")

    async def test_actual_annotation_channels_deduplicate_sources_and_keep_response_identity(self):
        citation = {"type": "url_citation", "url": "https://source.example.invalid/page", "title": "Source"}
        for kind in ("response.audio_transcript.annotation.added", "response.output_text.annotation.added"):
            await self.event(kind, response_id="answer", item_id="message", annotation=citation)
        await self.event(
            "response.content_part.done", response_id="answer", item_id="message",
            part={"type": "text", "text": "답변", "annotations": [citation]},
        )
        await self.event("response.done", response={
            "id": "answer", "status": "completed", "output": [{
                "id": "message", "type": "message", "role": "assistant",
                "content": [{"type": "text", "text": "답변", "annotations": [
                    citation, {"url": "javascript:alert(1)"}, {"url": "https://user:password@example.invalid"},
                ]}],
            }],
        })
        events = self.sent("citation")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "annotation")
        self.assertEqual(events[0]["url"], citation["url"])
        self.assertEqual(events[0]["response_id"], "answer")
        self.assertEqual(events[0]["provider"], "webiq")

    async def test_prose_links_and_raw_webiq_results_are_not_invented_citations(self):
        output = json.dumps({"structuredResponse": {"webResults": [{
            "title": "Observed result", "url": "https://result.example.invalid", "snippet": "Observed excerpt",
        }]}})
        await self.event("response.created", response={"id": "answer"})
        await self.event(
            "response.output_item.done", response_id="answer",
            item={"id": "tool", "type": "mcp_call", "name": "web", "output": output},
        )
        await self.event(
            "response.text.done", response_id="answer", item_id="message",
            text="모델이 쓴 [링크](https://answer.example.invalid)는 annotation이 아닙니다.",
        )
        tool = self.sent("tool")[0]
        self.assertEqual(tool["output"], output)
        self.assertIsNone(tool["status"])
        self.assertEqual(tool["kind"], "mcp_call")
        self.assertEqual(tool["response_id"], "answer")
        self.assertNotIn("item_id", tool)
        self.assertEqual(self.sent("citation"), [])

    async def test_tool_response_identity_remains_unknown_without_service_correlation(self):
        await self.event("response.created", response={"id": "ambient"})
        await self.event("response.output_item.done", item={
            "id": "tool", "type": "foundry_agent_call", "name": "test-bing",
        })
        event = self.sent("tool")[0]
        self.assertIsNone(event["response_id"])
        self.assertIsNone(event["status"])
        self.assertEqual(event["kind"], "foundry_agent_call")
        self.assertEqual(self.sent("citation"), [])

    async def test_interrupted_tool_and_citations_do_not_leak_into_the_next_turn(self):
        await self.event("response.created", response={"id": "old"})
        await self.event("response.output_item.added", response_id="old", item={
            "id": "old-tool", "type": "mcp_call", "name": "web",
        })
        await self.event("input_audio_buffer.speech_started", item_id="new-user")
        await self.event("response.created", response={"id": "new"})
        await self.event("response.output_item.done", item={
            "id": "old-tool", "type": "mcp_call", "name": "web", "output": "old result",
        })
        await self.event(
            "response.audio_transcript.annotation.added", response_id="old", item_id="old-message",
            annotation={"url": "https://old.example.invalid"},
        )
        await self.event("response.text.done", response_id="old", item_id="old-message", text="old text")
        await self.event("response.done", response={"id": "old", "status": "failed"})
        self.assertEqual(self.sent("tool"), [])
        self.assertEqual(self.sent("citation"), [])
        self.assertEqual(self.sent("transcript", "assistant"), [])
        self.assertEqual(self.session.active_response, "new")
        self.assertEqual(self.sent("response_done")[0]["response_id"], "old")
        self.assertTrue(self.sent("response_done")[0]["interrupted"])

    async def test_response_done_finishes_source_only_response_without_ending_session(self):
        await self.event("response.created", response={"id": "source-only"})
        await self.event(
            "response.audio_transcript.annotation.added",
            response_id="source-only", item_id="message",
            annotation={"url": "https://source.example.invalid"},
        )
        await self.event("response.done", response={"id": "source-only", "status": "completed"})
        event = self.sent("response_done")[0]
        self.assertEqual(event["response_id"], "source-only")
        self.assertEqual(event["status"], "completed")
        self.assertEqual(event["session_id"], self.session.session_id)
        self.assertEqual(event["provider"], "webiq")
        self.assertFalse(event["interrupted"])
        self.assertEqual(self.sent("transcript", "assistant"), [])
        self.assertEqual(self.sent("done"), [])
        self.assertFalse(self.session.closed.is_set())
        await self.event("response.created", response={"id": "next"})
        self.assertEqual(self.session.active_response, "next")

    async def test_response_done_follows_actual_final_text_and_citations(self):
        await self.event("response.done", response={
            "id": "answer", "status": "completed", "output": [{
                "id": "message", "type": "message", "role": "assistant", "content": [{
                    "type": "text", "text": "답변",
                    "annotations": [{"url": "https://source.example.invalid"}],
                }],
            }],
        })
        events = [call.args[0] for call in self.socket.send_json.call_args_list]
        self.assertEqual([event["type"] for event in events], ["citation", "transcript", "response_done"])
        self.assertEqual(events[0]["item_id"], "message")
        self.assertTrue(all(event["response_id"] == "answer" for event in events))

    async def test_response_done_does_not_turn_unknown_tool_status_into_success(self):
        await self.event("response.output_item.done", response_id="answer", item={
            "id": "tool-id", "type": "mcp_call", "name": "web", "output": '{"webResults":[]}',
        })
        await self.event("response.done", response={"id": "answer", "status": "completed"})
        self.assertEqual(len(self.sent("tool")), 1)
        self.assertIsNone(self.sent("tool")[0]["status"])
        self.assertNotIn("item_id", self.sent("tool")[0])
        self.assertEqual(self.sent("response_done")[0]["status"], "completed")

    async def test_response_error_preserves_safe_details_and_actual_response_id(self):
        await self.event("response.created", response={"id": "answer"})
        with self.assertRaises(VoiceServiceError) as error:
            await self.event("response.done", response={
                "id": "answer", "status": "failed",
                "status_details": {"error": {"code": "tool_failed", "message": "PRIVATE"}},
            })
        self.assertIsNone(self.session.active_response)
        self.assertEqual(error.exception.response_id, "answer")
        self.assertIn("code=tool_failed", str(error.exception))
        self.assertNotIn("PRIVATE", str(error.exception))

    async def test_session_error_does_not_borrow_unrelated_active_response_id(self):
        await self.event("response.created", response={"id": "ambient"})
        with self.assertRaises(VoiceServiceError) as error:
            await self.event("error", error={"code": "session_error"})
        self.assertIsNone(error.exception.response_id)

    async def test_finished_response_deltas_are_dropped_but_delayed_actual_sources_keep_old_id(self):
        await self.event("response.text.done", response_id="old", item_id="message", text="old answer")
        await self.event("response.done", response={"id": "old", "status": "completed"})
        await self.event("response.created", response={"id": "new"})
        await self.event("response.text.delta", item_id="message", delta="late text")
        await self.event("response.audio.delta", response_id="old", delta="AAAA")
        await self.event(
            "response.audio_transcript.annotation.added", item_id="message",
            annotation={"url": "https://old.example.invalid"},
        )
        self.assertEqual(len(self.sent("transcript")), 1)
        self.assertEqual(self.sent("audio"), [])
        self.assertEqual(self.sent("citation")[0]["response_id"], "old")

    async def test_mismatched_response_cannot_reassign_an_existing_item(self):
        await self.event("response.text.delta", response_id="first", item_id="message", delta="first")
        await self.event("response.text.done", response_id="other", item_id="message", text="wrong")
        self.assertEqual(len(self.sent("transcript")), 1)
        self.assertEqual(self.session.item_responses["message"], "first")

    async def test_ready_identifies_actual_selected_provider_and_pinned_agent_in_both_modes(self):
        for mode in ("agent", "realtime_agent_tool"):
            for provider in ("bing", "webiq"):
                with self.subTest(mode=mode, provider=provider):
                    session = VoiceSession(settings(), provider, voice_options={"connection_mode": mode})
                    socket = SimpleNamespace(send_json=AsyncMock())
                    await session.handle_event(
                        {"type": "conversation.item.created", "item": {"id": session.context_id}},
                        self.connection, socket,
                    )
                    event = socket.send_json.call_args.args[0]
                    self.assertEqual(event["provider"], provider)
                    self.assertEqual(event["connection_mode"], mode)
                    self.assertEqual(event["agent"]["name"], settings().agents[provider].name)
                    self.assertEqual(event["agent"]["version"], settings().agents[provider].version)
                    self.assertTrue(event["agent"]["pinned"])

    async def test_model_tools_does_not_claim_to_be_either_search_provider(self):
        self.session = VoiceSession(settings(), "bing", voice_options={"connection_mode": MODEL_MODE})
        await self.event("response.text.done", response_id="answer", item_id="message", text="앱 답변")
        self.assertIsNone(self.sent("transcript")[0]["provider"])

    async def test_ready_keeps_the_session_agent_even_if_available_configuration_changes(self):
        self.session.settings.agents["webiq"] = AgentReference("different-agent", "99")
        await self.event("conversation.item.created", item={"id": self.session.context_id})
        ready = self.sent("status")[0]
        self.assertEqual(ready["agent"], {"name": "test-webiq", "version": "2", "pinned": True})

    async def test_stopped_or_closed_sessions_ignore_late_cloud_events(self):
        for state in ("stop", "closed"):
            with self.subTest(state=state):
                if state == "stop":
                    self.session.stop_requested = True
                else:
                    self.session.stop_requested = False
                    self.session.closed.set()
                await self.event("response.text.done", response_id="answer", item_id="message", text="late")
                await self.event(
                    "conversation.item.input_audio_transcription.completed",
                    item_id="heard", transcript="late",
                )
        self.assertEqual(self.sent("transcript"), [])

    async def test_typed_transcript_uses_the_actual_submitted_item_and_is_not_labeled_stt(self):
        self.session.ready.set()
        queue = asyncio.Queue()
        for control in ({"type": "text", "text": "검색해 줘"}, {"type": "stop"}):
            await queue.put({"type": "websocket.receive", "text": json.dumps(control)})
        self.socket.receive = queue.get
        await self.session._from_browser(self.connection, self.socket)
        submitted = self.connection.conversation.item.create.call_args.kwargs["item"].as_dict()
        transcript = self.sent("transcript", "user")[0]
        self.assertEqual(transcript["item_id"], submitted["id"])
        self.assertLessEqual(len(submitted["id"]), 32)
        self.assertEqual(transcript["input_mode"], "text")
        self.assertTrue(transcript["final"])

    async def test_buffered_service_events_yield_to_browser_reader(self):
        order = []

        class Connection:
            def __aiter__(self):
                async def events():
                    for index in range(5):
                        yield {
                            "type": "response.text.delta", "response_id": "answer",
                            "item_id": "message", "delta": str(index),
                        }
                return events()

        async def send(event):
            order.append(("service", event["text"]))

        async def browser_reader():
            order.append(("browser", "received"))

        peer = asyncio.create_task(browser_reader())
        await self.session._from_service(Connection(), SimpleNamespace(send_json=send))
        await peer
        self.assertLess(order.index(("browser", "received")), order.index(("service", "4")))

    async def test_buffered_browser_audio_yields_to_service_reader_without_dropping_frames(self):
        order = []
        frames = [bytes([index, 0]) * 2400 for index in range(5)]
        queue = asyncio.Queue()
        for frame in frames:
            await queue.put({"type": "websocket.receive", "bytes": frame})
        await queue.put({"type": "websocket.receive", "text": '{"type":"stop"}'})

        async def append(*, audio):
            order.append(("audio", audio))

        async def service_reader():
            order.append(("service", "received"))

        self.session.ready.set()
        self.connection.input_audio_buffer = SimpleNamespace(append=append)
        self.socket.receive = queue.get
        peer = asyncio.create_task(service_reader())
        await self.session._from_browser(self.connection, self.socket)
        await peer
        sent = [data for kind, data in order if kind == "audio"]
        self.assertEqual([base64.b64decode(data) for data in sent], frames)
        self.assertLess(order.index(("service", "received")), order.index(("audio", sent[-1])))

    async def test_slow_browser_send_diagnostic_does_not_log_content(self):
        with patch("tmap_poc.voice.monotonic", side_effect=[0, 1]):
            with self.assertLogs("tmap_poc.voice", level="WARNING") as captured:
                await self.session._send(self.socket, {
                    "type": "tool", "output": "PRIVATE_SEARCH_OUTPUT",
                })
        message = " ".join(captured.output)
        self.assertIn("Slow Voice browser send", message)
        self.assertIn("wall_ms=1000", message)
        self.assertNotIn("PRIVATE_SEARCH_OUTPUT", message)

    async def test_slow_audio_upload_is_measured_without_logging_audio(self):
        self.session.ready.set()
        self.connection.input_audio_buffer = SimpleNamespace(append=AsyncMock())
        queue = asyncio.Queue()
        audio = b"PRIVATE_AUDIO_12"
        await queue.put({"type": "websocket.receive", "bytes": audio})
        await queue.put({"type": "websocket.receive", "text": '{"type":"stop"}'})
        self.socket.receive = queue.get
        with patch("tmap_poc.voice.monotonic", side_effect=[0, 0, 0, 1, 1, 1]):
            with self.assertLogs("tmap_poc.voice", level="WARNING") as captured:
                await self.session._from_browser(self.connection, self.socket)
        message = " ".join(captured.output)
        self.assertIn("Slow Voice audio upload", message)
        self.assertIn("wall_ms=1000", message)
        self.assertNotIn("PRIVATE_AUDIO", message)
        self.assertNotIn(base64.b64encode(audio).decode("ascii"), message)

    async def test_event_loop_monitor_reports_lag_and_remains_cancellable(self):
        with patch("tmap_poc.voice.monotonic", side_effect=[0, 1]):
            with patch("tmap_poc.voice.asyncio.sleep", new=AsyncMock(side_effect=[None, asyncio.CancelledError])):
                with self.assertLogs("tmap_poc.voice", level="WARNING") as captured:
                    with self.assertRaises(asyncio.CancelledError):
                        await self.session._monitor_event_loop()
        self.assertIn("Voice event-loop lag", captured.output[0])
        self.assertIn("lag_ms=900", captured.output[0])


if __name__ == "__main__":
    unittest.main()
