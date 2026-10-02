import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from tmap_poc.app_settings import AppSettings
from tmap_poc.config import ConfigError
from tmap_poc.profiles import AgentReference
from tmap_poc.voice import VoiceSession
from tmap_poc.voice_options import (
    WEB_SEARCH_FOLLOWUP_INSTRUCTIONS, VoiceOptionsError, build_web_search_session, validate_options,
)
from tmap_poc.web_search import ToolboxWebSearch, WebSearchError, _payload, result_text

DEFAULT_VOICE = "ko-KR-SunHiNeural"
REALTIME = {"connection_mode": "realtime_agent_tool"}


def settings(**overrides):
    return AppSettings(**{
        "project_endpoint": "https://agent.example.invalid/api/projects/demo",
        "voice_endpoint": "https://voice.example.invalid",
        "subscription": "explicit-test-subscription",
        "web_search_toolbox": "demo-web-search",
        "agents": {"bing": AgentReference("test-bing", "1"), "webiq": AgentReference("test-webiq", "2")},
        **overrides,
    })


class WebSearchSettingsTests(unittest.TestCase):
    def test_toolbox_url_comes_from_the_project_and_toolbox_name(self):
        self.assertEqual(
            settings().web_search_toolbox_url,
            "https://agent.example.invalid/api/projects/demo/toolboxes/demo-web-search/mcp?api-version=v1",
        )
        self.assertEqual(settings(web_search_toolbox="").web_search_toolbox_url, "")

    def test_toolbox_name_is_validated_from_the_environment(self):
        import os
        from unittest.mock import patch

        for name in ("bad name", "../x", "x/y"):
            with self.subTest(name=name), patch.dict(os.environ, {"TMAP_WEB_SEARCH_TOOLBOX": name}):
                with self.assertRaises(ConfigError):
                    AppSettings.from_env()
        with patch.dict(os.environ, {"TMAP_WEB_SEARCH_TOOLBOX": "tmap-web-search"}):
            self.assertEqual(AppSettings.from_env().web_search_toolbox, "tmap-web-search")


class WebSearchSessionTests(unittest.TestCase):
    def test_end_to_end_bing_session_offers_only_the_web_search_function(self):
        session = build_web_search_session(validate_options(REALTIME, DEFAULT_VOICE)).as_dict()
        self.assertEqual([tool["type"] for tool in session["tools"]], ["function"])
        self.assertEqual(session["tools"][0]["name"], "web_search")
        self.assertEqual(session["tools"][0]["parameters"]["required"], ["search_query"])
        self.assertIn("web_search 도구", session["instructions"])
        self.assertNotIn("agent", str(session["tools"]).lower())
        with self.assertRaises(VoiceOptionsError):
            build_web_search_session(validate_options({}, DEFAULT_VOICE))

    def test_only_the_end_to_end_bing_lane_runs_the_toolbox(self):
        self.assertIsNotNone(VoiceSession(settings(), "bing", voice_options=REALTIME).web_search)
        self.assertIsNone(VoiceSession(settings(), "webiq", voice_options=REALTIME).web_search)
        self.assertIsNone(VoiceSession(settings(), "bing").web_search)
        self.assertIsNone(VoiceSession(settings(web_search_toolbox=""), "bing", voice_options=REALTIME).web_search)


class ToolboxResultTests(unittest.TestCase):
    def test_embedded_resource_and_citations_become_plain_text(self):
        result = result_text({"content": [{
            "type": "resource",
            "resource": {"uri": "about:web-search-answer", "mimeType": "text/plain", "text": "종가 272,500원"},
            "_meta": {"annotations": [
                {"type": "url_citation", "url": "https://example.com/a", "title": "A", "start_index": 0, "end_index": 3},
                {"type": "url_citation", "url": "https://example.com/a", "title": "A again"},
                {"type": "url_citation", "url": "http://insecure.example.com", "title": "skip"},
            ]},
        }]})
        self.assertEqual(result["text"], "종가 272,500원")
        self.assertEqual(result["citations"], [{"type": "url_citation", "url": "https://example.com/a", "title": "A"}])
        self.assertEqual(result_text({"content": [{"type": "text", "text": "plain"}]})["text"], "plain")
        with self.assertRaises(WebSearchError):
            result_text({"content": []})

    def test_streamable_http_payloads_are_read_as_json_or_events(self):
        self.assertEqual(_payload('{"id": 1}'), {"id": 1})
        self.assertEqual(_payload('event: message\ndata: {"id": 2}\n\n'), {"id": 2})
        self.assertEqual(_payload(""), {})

    def test_missing_toolbox_is_a_configuration_error(self):
        with self.assertRaises(ConfigError):
            ToolboxWebSearch(settings(web_search_toolbox=""))


class WebSearchFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().set_debug(False)
        self.socket = SimpleNamespace(send_json=AsyncMock())
        self.connection = SimpleNamespace(
            session=SimpleNamespace(update=AsyncMock()),
            conversation=SimpleNamespace(item=SimpleNamespace(create=AsyncMock())),
            response=SimpleNamespace(create=AsyncMock(), cancel=AsyncMock()),
        )
        self.session = VoiceSession(settings(), "bing", voice_options=REALTIME)
        self.addCleanup(self.session.tools.close)
        self.session.connection = self.connection
        self.session.connection_opened.set()

    def events(self, kind):
        return [call.args[0] for call in self.socket.send_json.call_args_list if call.args[0]["type"] == kind]

    async def run_worker(self):
        worker = asyncio.create_task(self.session._web_search_worker(self.socket))
        await asyncio.wait_for(self.session.web_search_queue.join(), 5)
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    async def answer_search(self, search):
        self.session.web_search = SimpleNamespace(search=search)
        await self.session.handle_event({"type": "response.done", "response": {
            "id": "r1", "status": "completed", "output": [
                {"type": "message", "role": "assistant", "id": "filler", "content": []},
                {"type": "function_call", "id": "item1", "call_id": "call_1", "name": "web_search",
                 "arguments": '{"search_query": "삼성전자 주가"}'},
            ],
        }}, self.connection, self.socket)
        self.assertTrue(self.events("response_done")[-1]["followup"], "the page waits for the searched answer")
        await self.run_worker()

    async def test_search_result_is_given_to_the_model_and_the_answer_requested(self):
        found = {"text": "종가 272,500원", "citations": [{"type": "url_citation", "url": "https://example.com", "title": "E"}]}
        search = AsyncMock(return_value=found)
        await self.answer_search(search)
        search.assert_awaited_once_with("삼성전자 주가")
        output = self.connection.conversation.item.create.await_args.kwargs["item"]
        self.assertEqual(output.call_id, "call_1")
        self.assertIn("272,500원", output.output)
        tool = self.events("tool")[-1]
        self.assertEqual((tool["kind"], tool["id"], tool["name"], tool["status"]), ("function_call", "item1", "web_search", "completed"))
        self.assertEqual(tool["arguments"], {"search_query": "삼성전자 주가"})
        self.assertEqual(tool["output"], found)
        request = self.connection.response.create.await_args.kwargs["response"]
        self.assertEqual(request.instructions, WEB_SEARCH_FOLLOWUP_INSTRUCTIONS)

    async def test_a_failed_search_still_lets_the_model_answer(self):
        await self.answer_search(AsyncMock(side_effect=WebSearchError("Bing 웹 검색이 응답하지 않았습니다 (HTTP 500).")))
        output = self.connection.conversation.item.create.await_args.kwargs["item"]
        self.assertIn("HTTP 500", output.output)
        self.assertEqual(self.events("tool")[-1]["status"], "failed")
        self.connection.response.create.assert_awaited_once()

    async def test_a_new_question_during_the_search_skips_the_stale_answer(self):
        async def slow(query):
            self.session.response_generation += 1
            return {"text": "old", "citations": []}

        await self.answer_search(slow)
        self.connection.response.create.assert_not_awaited()

    async def test_searches_beyond_three_per_question_report_the_limit(self):
        self.session.tool_followups = 3
        search = AsyncMock()
        await self.answer_search(search)
        search.assert_not_awaited()
        self.assertIn("세 번", self.connection.conversation.item.create.await_args.kwargs["item"].output)


if __name__ == "__main__":
    unittest.main()
