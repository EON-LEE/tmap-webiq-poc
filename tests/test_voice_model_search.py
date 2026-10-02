import asyncio
from contextlib import asynccontextmanager
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from tmap_poc.app_settings import AppSettings
from tmap_poc.config import ConfigError
from tmap_poc.profiles import AgentReference
from tmap_poc.voice import VoiceServiceError, VoiceSession, connection_url
from tmap_poc.voice_options import (
    MODEL_CHOICES, SEARCH_MODE, build_search_session, option_schema, validate_options,
)
from tmap_poc.webiq_mcp import WebIQMCPTarget, resolve_webiq_mcp_target


DEFAULT_VOICE = "ko-KR-SunHiNeural"
AGENT_TARGET = {"agent_name": "bing-agent", "agent_version": "1", "project_name": "demo"}
MCP_TARGET = WebIQMCPTarget("https://api.microsoft.ai/v3/mcp", {"x-apikey": "PRIVATE_KEY"})


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


class ModelSearchOptionsTests(unittest.TestCase):
    def test_schema_declares_public_mode_contract(self):
        schema = option_schema(DEFAULT_VOICE)
        modes = [(option["value"], option["label"], option["help"]) for option in schema["fields"][0]["options"]]
        self.assertEqual([mode[0] for mode in modes], ["agent", SEARCH_MODE, "realtime_agent_tool", "model_tools"])
        self.assertEqual(modes[0][1], "Agent 연결")
        self.assertEqual(modes[1][1], "STT → LLM → TTS")
        self.assertEqual(modes[2][1], "End-to-end")
        self.assertEqual(modes[3][1], "앱 조작 데모")
        self.assertIn("WebIQ는 선택한 모델이 직접 검색", modes[1][2])
        self.assertEqual(MODEL_CHOICES, ("gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-5-mini", "gpt-5", "gpt-5.6-luna"))

    def test_model_search_validation_and_url_use_text_model(self):
        options = validate_options({"connection_mode": SEARCH_MODE, "llm_model": "gpt-5.6-luna"}, DEFAULT_VOICE)
        self.assertEqual(options["return_agent_response_directly"], True)
        self.assertEqual(options["transcription_model"], "azure-speech")
        query = parse_qs(urlparse(connection_url(settings(), settings().agents["webiq"], voice_options=options)).query)
        self.assertEqual(query["model"], ["gpt-5.6-luna"])
        self.assertNotIn("agent-name", query)

    def test_search_builder_supports_mcp_without_exposing_header_in_safe_repr(self):
        session = build_search_session(validate_options({"connection_mode": SEARCH_MODE}, DEFAULT_VOICE), MCP_TARGET).as_dict()
        self.assertEqual(session["tools"][0], {
            "type": "mcp", "server_label": "webiq", "server_url": MCP_TARGET.server_url,
            "headers": {"x-apikey": "PRIVATE_KEY"},
            "allowed_tools": ["web", "news", "places", "finance"],
            "require_approval": "never",
        })
        self.assertIn("language=ko", session["instructions"])
        self.assertNotIn("PRIVATE_KEY", repr(MCP_TARGET))

    def test_search_builder_supports_bing_agent_tool(self):
        session = build_search_session(
            validate_options({"connection_mode": SEARCH_MODE, "return_agent_response_directly": False}, DEFAULT_VOICE),
            AGENT_TARGET,
        ).as_dict()
        self.assertEqual(session["tools"][0]["type"], "foundry_agent")
        self.assertFalse(session["tools"][0]["return_agent_response_directly"])
        self.assertIn("Speak the delegated Agent's answer", session["instructions"])


class ModelSearchFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().set_debug(False)
        self.socket = SimpleNamespace(send_json=AsyncMock())
        self.connection = SimpleNamespace(
            session=SimpleNamespace(update=AsyncMock()),
            conversation=SimpleNamespace(item=SimpleNamespace(create=AsyncMock())),
            response=SimpleNamespace(create=AsyncMock(), cancel=AsyncMock()),
        )

    def events(self, kind=None):
        calls = [call.args[0] for call in self.socket.send_json.call_args_list]
        return [event for event in calls if kind is None or event["type"] == kind]

    async def test_webiq_mcp_flow_metadata_is_sanitized_and_gates_ready(self):
        session = VoiceSession(settings(), "webiq", voice_options={"connection_mode": SEARCH_MODE})
        @asynccontextmanager
        async def connector(*_args, **_kwargs):
            yield self.connection

        session.connector = connector
        with patch("tmap_poc.webiq_mcp.resolve_webiq_mcp_target", new=AsyncMock(return_value=MCP_TARGET)):
            with patch.object(session, "_from_service", new=AsyncMock()):
                await session._serve_cloud(self.socket)
        sent = self.connection.session.update.call_args.kwargs["session"].as_dict()
        self.assertEqual(sent["tools"][0]["headers"], {"x-apikey": "PRIVATE_KEY"})
        request_flow = [event for event in self.events("flow") if event.get("operation") == "session.update"][0]
        self.assertEqual(request_flow["data"]["search_tool"], {
            "type": "mcp", "server_label": "webiq",
            "server_host": "api.microsoft.ai",
            "allowed_tools": ["web", "news", "places", "finance"],
        })
        self.assertNotIn("PRIVATE_KEY", json.dumps(self.events()))
        await session.handle_event({"type": "conversation.item.created", "item": {"id": session.context_id}}, self.connection, self.socket)
        self.assertFalse(session.ready.is_set())
        await session.handle_event({"type": "mcp_list_tools.completed", "item_id": "catalog"}, self.connection, self.socket)
        self.assertTrue(session.ready.is_set())

    async def test_mcp_failure_and_deadline_are_terminal_errors(self):
        session = VoiceSession(settings(), "webiq", voice_options={"connection_mode": SEARCH_MODE})
        session.mcp_tools_required = True
        with self.assertRaisesRegex(VoiceServiceError, "WebIQ 검색 도구"):
            await session.handle_event({"type": "mcp_list_tools.failed", "item_id": "catalog", "error": {"message": "PRIVATE"}}, self.connection, self.socket)
        session = VoiceSession(settings(), "webiq", voice_options={"connection_mode": SEARCH_MODE})
        session.mcp_tools_required = True
        session.connection_opened.set()
        async def timeout(coro, **_kwargs):
            coro.close()
            raise TimeoutError

        with patch("tmap_poc.voice.asyncio.wait_for", new=timeout):
            with self.assertRaisesRegex(VoiceServiceError, "WebIQ 검색 도구"):
                await session._ready_deadline()

    async def test_mcp_tool_only_response_requests_capped_followups(self):
        session = VoiceSession(settings(), "webiq", voice_options={"connection_mode": SEARCH_MODE})
        session.mcp_tools_required = True
        session.connection = self.connection
        current = "r0"
        for index in range(4):
            await session.handle_event({
                "type": "response.done",
                "response": {"id": current, "status": "completed", "output": [
                    {"type": "mcp_call", "id": f"tool{index}", "status": "completed"},
                ]},
            }, self.connection, self.socket)
            if index < 3:
                current = f"followup{index}"
                await session.handle_event({"type": "response.created", "response": {"id": current}}, self.connection, self.socket)
        self.assertEqual(self.connection.response.create.await_count, 3)
        instructions = self.connection.response.create.await_args.kwargs["response"].instructions
        self.assertIn("방금 받은 webiq 도구 결과", instructions, "follow-ups ask for an answer from the tool result")
        self.assertIn("대기 안내는 하지 말고", instructions, "response instructions keep the session's rules")
        followups = [
            event for event in self.events("flow")
            if event.get("operation") == "response.create" and event["data"].get("purpose") == "tool_followup"
        ]
        self.assertEqual(len(followups), 3)
        self.socket.send_json.reset_mock()
        await session.handle_event({
            "type": "response.done",
            "response": {"id": "answer", "status": "completed", "output": [{"type": "message", "role": "assistant", "content": []}]},
        }, self.connection, self.socket)
        self.assertEqual(session.tool_followups, 0)
        await session.handle_event({
            "type": "response.done",
            "response": {"id": "agent", "status": "completed", "output": [{"type": "foundry_agent_call", "id": "a"}]},
        }, self.connection, self.socket)
        self.assertEqual(self.connection.response.create.await_count, 3)

    async def test_spoken_filler_before_a_trailing_mcp_call_still_requests_the_answer(self):
        session = VoiceSession(settings(), "webiq", voice_options={"connection_mode": "realtime_agent_tool"})
        session.mcp_tools_required = True
        session.connection = self.connection
        filler = {"type": "message", "role": "assistant", "id": "filler", "content": []}
        await session.handle_event({"type": "response.done", "response": {
            "id": "r1", "status": "completed", "output": [filler, {"type": "mcp_call", "id": "tool", "status": "completed"}],
        }}, self.connection, self.socket)
        self.assertEqual(self.connection.response.create.await_count, 1)
        self.assertEqual(session.tool_followups, 1, "a filler message does not reset the follow-up cap")
        self.assertTrue(self.events("response_done")[-1]["followup"], "the page is told the answer is still coming")
        await session.handle_event({"type": "response.created", "response": {"id": "r2"}}, self.connection, self.socket)
        await session.handle_event({"type": "response.done", "response": {
            "id": "r2", "status": "completed", "output": [{"type": "mcp_call", "id": "tool2"}, {**filler, "id": "answer"}],
        }}, self.connection, self.socket)
        self.assertEqual(self.connection.response.create.await_count, 1, "a response ending in its answer is complete")
        self.assertEqual(session.tool_followups, 0)
        self.assertFalse(self.events("response_done")[-1]["followup"])

    async def test_answer_is_requested_only_after_the_search_returns(self):
        # Observed 2026-09-29: the MCP call runs after response.done; asking at once answered without the result.
        session = VoiceSession(settings(), "webiq", voice_options={"connection_mode": "realtime_agent_tool"})
        session.mcp_tools_required = True
        session.connection = self.connection
        await session.handle_event({"type": "response.done", "response": {
            "id": "r1", "status": "completed", "output": [{"type": "mcp_call", "id": "search"}],
        }}, self.connection, self.socket)
        self.connection.response.create.assert_not_awaited()
        self.assertTrue(self.events("response_done")[-1]["followup"])
        await session.handle_event({"type": "response.mcp_call.in_progress", "item_id": "search"}, self.connection, self.socket)
        self.connection.response.create.assert_not_awaited()
        await session.handle_event({"type": "response.mcp_call.completed", "item_id": "search"}, self.connection, self.socket)
        self.assertEqual(self.connection.response.create.await_count, 1)

        await session.handle_event({"type": "response.created", "response": {"id": "r2"}}, self.connection, self.socket)
        await session.handle_event({"type": "response.done", "response": {
            "id": "r2", "status": "completed", "output": [{"type": "mcp_call", "id": "again"}],
        }}, self.connection, self.socket)
        await session.handle_event({"type": "input_audio_buffer.committed", "item_id": "next-question"}, self.connection, self.socket)
        await session.handle_event({"type": "response.mcp_call.failed", "item_id": "again"}, self.connection, self.socket)
        self.assertEqual(self.connection.response.create.await_count, 1, "a new question drops the stale follow-up")

        session.followup_after = None
        await session.handle_event({"type": "response.mcp_call.completed", "item_id": "early"}, self.connection, self.socket)
        await session.handle_event({"type": "response.done", "response": {
            "id": "r3", "status": "completed", "output": [{"type": "mcp_call", "id": "early"}],
        }}, self.connection, self.socket)
        self.assertEqual(self.connection.response.create.await_count, 2, "a search that already returned is answered at once")

    async def test_no_mcp_followup_after_interruption_or_active_response(self):
        session = VoiceSession(settings(), "webiq", voice_options={"connection_mode": SEARCH_MODE})
        session.mcp_tools_required = True
        session.connection = self.connection
        session.interrupted.add("old")
        await session.handle_event({"type": "response.done", "response": {
            "id": "old", "status": "completed", "output": [{"type": "mcp_call", "id": "tool"}],
        }}, self.connection, self.socket)
        session.active_response = "other"
        await session.handle_event({"type": "response.done", "response": {
            "id": "different", "status": "completed", "output": [{"type": "mcp_call", "id": "tool2"}],
        }}, self.connection, self.socket)
        self.connection.response.create.assert_not_awaited()


class WebIQResolverTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolver_extracts_and_caches_connection_key_without_printing_it(self):
        class Client:
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                pass
            agents = SimpleNamespace(get_version=MagicMock(return_value=SimpleNamespace(as_dict=lambda: {
                "definition": {"tools": [{
                    "type": "mcp", "server_url": "https://api.microsoft.ai/v3/mcp",
                    "project_connection_id": "/subscriptions/s/resourceGroups/r/providers/Microsoft.CognitiveServices/accounts/a/projects/p/connections/webiq-mcp",
                }]}
            })))
            connections = SimpleNamespace(get=MagicMock(return_value=SimpleNamespace(as_dict=lambda: {
                "credentials": {"type": "CustomKeys", "x-apikey": "PRIVATE_44_CHAR_KEY"}
            })))

        config = settings()
        with patch("tmap_poc.webiq_mcp._CACHE", {}):
            with patch("azure.ai.projects.AIProjectClient", return_value=Client()) as constructor:
                target = await resolve_webiq_mcp_target(config, config.agents["webiq"])
                again = await resolve_webiq_mcp_target(config, config.agents["webiq"])
        constructor.assert_called_once()
        self.assertIs(target, again)
        self.assertEqual(target["headers"], {"x-apikey": "PRIVATE_44_CHAR_KEY"})
        self.assertNotIn("PRIVATE_44_CHAR_KEY", repr(target))

    async def test_resolver_maps_failures_to_safe_korean_error(self):
        with patch("tmap_poc.webiq_mcp._CACHE", {}):
            with patch("azure.ai.projects.AIProjectClient", side_effect=RuntimeError("PRIVATE")):
                with self.assertRaises(ConfigError) as error:
                    await resolve_webiq_mcp_target(settings(), settings().agents["webiq"])
        self.assertIn("WebIQ 연결 정보를", str(error.exception))
        self.assertNotIn("PRIVATE", str(error.exception))


if __name__ == "__main__":
    unittest.main()
