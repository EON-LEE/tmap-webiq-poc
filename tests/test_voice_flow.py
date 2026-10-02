import asyncio
import base64
from contextlib import asynccontextmanager
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from azure.ai.voicelive.models import (
    ServerEvent, ServerEventResponseMcpCallArgumentsDone,
    ServerEventResponseMcpCallCompleted, ServerEventResponseMcpCallInProgress,
    ServerEventSessionCreated,
)
from fastapi.testclient import TestClient

from tmap_poc.api import create_app
from tmap_poc.app_settings import AppSettings
from tmap_poc.voice import VoiceServiceError, VoiceSession
from tmap_poc.voice_options import MODEL_MODE
from tests.test_voice_conversation import settings


class FlowConfigTests(unittest.TestCase):
    def test_config_declares_observation_scope_without_calling_cloud(self):
        with patch.object(AppSettings, "credential", side_effect=AssertionError("No cloud queries")):
            with TestClient(create_app(settings())) as client:
                data = client.get("/api/config").json()
        self.assertEqual(data["observability"], {
            "flow_schema_version": 1, "scope": "client_observed",
            "reasoning_content": False, "automatic_trace_queries": False,
        })
        self.assertTrue(all(provider["readiness_scope"] == "configuration_only" for provider in data["providers"]))

    def test_terminal_error_keeps_actual_source_event_without_private_details(self):
        class FailedSession:
            session_id = "session"

            def __init__(self, *_args):
                pass

            async def run(self, _socket):
                raise VoiceServiceError(
                    "응답 실패", {"code": "tool_failed", "message": "PRIVATE_MESSAGE"},
                    response_id="response", source_event="response.done",
                )

        with TestClient(create_app(settings(), voice_factory=FailedSession)) as client:
            with client.websocket_connect("/ws/voice", headers={"origin": "http://localhost:8000"}) as socket:
                socket.send_json({"type": "start", "provider": "bing"})
                socket.receive_json()
                event = socket.receive_json()
        self.assertEqual(event["source_event"], "response.done")
        self.assertEqual(event["response_id"], "response")
        self.assertNotIn("PRIVATE_MESSAGE", json.dumps(event))


class VoiceFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().set_debug(False)
        self.session = VoiceSession(settings(), "webiq", "PRIVATE_APP_CONTEXT")
        self.socket = SimpleNamespace(send_json=AsyncMock())
        self.connection = SimpleNamespace(
            session=SimpleNamespace(update=AsyncMock()),
            conversation=SimpleNamespace(item=SimpleNamespace(create=AsyncMock())),
            response=SimpleNamespace(create=AsyncMock(), cancel=AsyncMock()),
            input_audio_buffer=SimpleNamespace(append=AsyncMock()),
        )
        self.addCleanup(self.session.tools.close)

    async def event(self, kind, **fields):
        await self.session.handle_event({"type": kind, **fields}, self.connection, self.socket)

    def sent(self, kind=None):
        events = [call.args[0] for call in self.socket.send_json.call_args_list]
        return [event for event in events if kind is None or event["type"] == kind]

    def flows(self, *, stage=None, operation=None):
        return [
            event for event in self.sent("flow")
            if (stage is None or event["stage"] == stage)
            and (operation is None or event.get("operation") == operation)
        ]

    async def browser(self, *messages):
        queue = asyncio.Queue()
        for message in messages:
            await queue.put({"type": "websocket.receive", **message})
        self.socket.receive = queue.get
        self.session.ready.set()
        await self.session._from_browser(self.connection, self.socket)

    async def serve(self):
        @asynccontextmanager
        async def connector(*_args, **_kwargs):
            yield self.connection

        self.session.connector = connector
        with patch.object(self.session, "_from_service", new=AsyncMock()):
            await self.session._serve_cloud(self.socket)

    async def test_connection_target_is_configuration_not_deployed_agent_model(self):
        await self.serve()
        target, connected = self.flows(stage="connection")
        self.assertEqual(target["data"]["target_scope"], "configured")
        self.assertEqual(target["data"]["agent"], {"name": "test-webiq", "version": "2"})
        self.assertEqual(target["data"]["project_name"], "demo")
        self.assertEqual(target["data"]["api_version"], "2026-07-15")
        self.assertNotIn("requested_model", target["data"])
        self.assertNotIn("service_model", target["data"])
        self.assertEqual(connected["status"], "connected")
        self.assertEqual(target["observation"], "app_operation")
        self.assertEqual(target["provider"], "webiq")
        self.assertEqual(target["session_id"], self.session.session_id)

    async def test_supervisor_target_and_session_request_keep_only_safe_actual_settings(self):
        config = settings(
            foundry_resource_override="different-resource",
            agent_identity_client_id="PRIVATE_IDENTITY",
        )
        self.session = VoiceSession(config, "bing", voice_options={
            "connection_mode": "realtime_agent_tool", "realtime_model": "gpt-realtime-mini",
        })
        self.addCleanup(self.session.tools.close)
        await self.serve()
        target = self.flows(stage="connection")[0]["data"]
        self.assertEqual(target["requested_model"], "gpt-realtime-mini")
        self.assertEqual(target["foundry_resource_override"], "different-resource")
        request = self.flows(operation="session.update")[0]
        sent = self.connection.session.update.call_args.kwargs["session"].as_dict()
        self.assertEqual(request["data"]["agent_tool"]["agent_name"], sent["tools"][0]["agent_name"])
        self.assertEqual(request["data"]["voice"], sent["voice"])
        self.assertNotIn("instructions", request["data"])
        self.assertNotIn("PRIVATE_IDENTITY", json.dumps(self.flows()))

    async def test_navigation_target_remains_providerless_and_not_a_foundry_agent(self):
        self.session = VoiceSession(settings(), "bing", voice_options={"connection_mode": MODEL_MODE})
        self.addCleanup(self.session.tools.close)
        await self.serve()
        target = self.flows(stage="connection")[0]
        self.assertIsNone(target["provider"])
        self.assertEqual(target["data"]["requested_model"], self.session.options["llm_model"])
        self.assertNotIn("agent", target["data"])
        self.assertNotIn("agent_tool", self.flows(operation="session.update")[0]["data"])

    async def test_failed_session_update_is_not_reported_as_sent(self):
        self.connection.session.update.side_effect = RuntimeError("test failure")
        with self.assertRaisesRegex(RuntimeError, "test failure"):
            await self.serve()
        self.assertEqual(self.flows(operation="session.update"), [])
        self.assertEqual([event["status"] for event in self.flows(stage="connection")], ["connecting", "connected"])

    async def test_session_model_is_service_reported_voice_live_scope_and_payload_is_allowlisted(self):
        event = ServerEventSessionCreated({
            "type": "session.created",
            "session": {
                "id": "service-session", "model": "service-reported-model", "expires_at": 1800000000,
                "voice": {"type": "azure-standard", "name": "ko-KR-SunHiNeural", "secret": "PRIVATE_VOICE"},
                "instructions": "PRIVATE_PROMPT", "metadata": {"trace_access": "PRIVATE_CAPABILITY"},
                "tools": [{"headers": {"Authorization": "PRIVATE_CREDENTIAL"}}],
                "agent": {"authentication_identity_client_id": "PRIVATE_IDENTITY"},
            },
        })
        await self.session.handle_event(event.as_dict(), self.connection, self.socket)
        flow = self.flows()[0]
        self.assertEqual(flow["source_event"], "session.created")
        self.assertEqual(flow["data"]["service_model"], "service-reported-model")
        self.assertEqual(flow["data"]["model_scope"], "voice_live_session")
        self.assertEqual(flow["data"]["service_session_id"], "service-session")
        self.assertEqual(flow["session_id"], self.session.session_id)
        self.assertNotIn("PRIVATE", json.dumps(flow))

    async def test_missing_service_model_is_not_filled_from_configuration(self):
        await self.event("session.created", session={"id": "service"})
        self.assertNotIn("service_model", self.flows()[0]["data"])
        await self.event("session.created", session={"model": None})
        self.assertNotIn("model_scope", self.flows()[-1]["data"])

    async def test_context_submission_does_not_publish_hidden_context_or_prompts(self):
        await self.event("session.updated", session={"instructions": "PRIVATE_SERVICE_PROMPT"})
        sent = self.connection.conversation.item.create.call_args.kwargs["item"].as_dict()
        self.assertIn("PRIVATE_APP_CONTEXT", sent["content"][0]["text"])
        flow = self.flows(operation="conversation.item.create")[0]
        self.assertEqual(flow["item_id"], self.session.context_id)
        self.assertEqual(flow["data"], {"purpose": "app_context", "role": "user", "content_omitted": True})
        self.assertNotIn("PRIVATE", json.dumps(self.sent()))

    async def test_typed_input_and_sdk_operations_are_reported_in_actual_call_order(self):
        order = []

        async def send(event):
            if event["type"] == "flow":
                order.append((event.get("operation"), event["status"]))

        async def create_item(**_kwargs):
            order.append(("sdk.item.create", "returned"))

        async def create_response(**_kwargs):
            order.append(("sdk.response.create", "returned"))

        self.socket.send_json.side_effect = send
        self.connection.conversation.item.create.side_effect = create_item
        self.connection.response.create.side_effect = create_response
        await self.browser({"text": json.dumps({"type": "text", "text": "삼성전자 주식 찾아줘"})}, {"text": '{"type":"stop"}'})
        self.assertEqual(order, [
            ("browser.text", "received"), ("sdk.item.create", "returned"),
            ("conversation.item.create", "sent"), ("sdk.response.create", "returned"),
            ("response.create", "requested"),
        ])
        received = self.flows(operation="browser.text")[0]
        submitted = self.flows(operation="conversation.item.create")[0]
        created = self.connection.conversation.item.create.call_args.kwargs["item"].as_dict()
        self.assertIsNone(received["item_id"])
        self.assertEqual(submitted["item_id"], created["id"])
        self.assertEqual(submitted["data"]["text"], created["content"][0]["text"])
        self.assertIsNone(self.flows(operation="response.create")[0]["response_id"])

    async def test_failed_item_create_does_not_claim_sdk_submission_or_response_request(self):
        self.connection.conversation.item.create.side_effect = RuntimeError("test failure")
        with self.assertRaisesRegex(RuntimeError, "test failure"):
            await self.browser({"text": '{"type":"text","text":"question"}'})
        self.assertEqual(len(self.flows(operation="browser.text")), 1)
        self.assertEqual(self.flows(operation="conversation.item.create"), [])
        self.assertEqual(self.flows(operation="response.create"), [])
        self.connection.response.create.assert_not_awaited()

    async def test_failed_response_create_does_not_claim_response_requested(self):
        self.connection.response.create.side_effect = RuntimeError("test failure")
        with self.assertRaisesRegex(RuntimeError, "test failure"):
            await self.browser({"text": '{"type":"text","text":"question"}'})
        self.assertEqual(len(self.flows(operation="conversation.item.create")), 1)
        self.assertEqual(self.flows(operation="response.create"), [])

    async def test_busy_input_is_observed_but_not_forwarded_or_correlated_to_active_response(self):
        self.session.active_response = "busy-response"
        await self.browser({"text": '{"type":"text","text":"question"}'}, {"text": '{"type":"stop"}'})
        self.connection.conversation.item.create.assert_not_awaited()
        self.assertIsNone(self.flows(operation="browser.text")[0]["response_id"])
        self.assertEqual(self.flows(operation="conversation.item.create"), [])
        self.assertEqual(self.sent("error")[0]["code"], "response_busy")

    async def test_audio_upload_has_only_first_frame_milestones_and_no_pcm_content(self):
        frame = b"PRIVATE_PCM_DATA" * 300
        await self.browser(*[{"bytes": frame} for _ in range(5)], {"text": '{"type":"stop"}'})
        self.assertEqual(self.connection.input_audio_buffer.append.await_count, 5)
        for call in self.connection.input_audio_buffer.append.call_args_list:
            self.assertEqual(base64.b64decode(call.kwargs["audio"]), frame)
        self.assertEqual(len(self.flows()), 2)
        self.assertEqual(self.flows(operation="browser.audio")[0]["data"]["first_frame_bytes"], len(frame))
        self.assertEqual(len(self.flows(operation="input_audio_buffer.append")), 1)
        self.assertNotIn(base64.b64encode(frame).decode("ascii"), json.dumps(self.flows()))
        self.assertTrue(all(event["response_id"] is None for event in self.flows()))

    async def test_failed_audio_upload_is_not_reported_as_sent(self):
        self.connection.input_audio_buffer.append.side_effect = RuntimeError("test failure")
        with self.assertRaisesRegex(RuntimeError, "test failure"):
            await self.browser({"bytes": b"\x00\x00" * 2400})
        self.assertEqual(len(self.flows(operation="browser.audio")), 1)
        self.assertEqual(self.flows(operation="input_audio_buffer.append"), [])

    async def test_vad_commit_and_transcription_keep_user_ids_without_response_guessing(self):
        self.session.active_response = "unrelated-answer"
        await self.event("input_audio_buffer.speech_started", item_id="heard", audio_start_ms=123)
        await self.event("input_audio_buffer.speech_stopped", item_id="heard", audio_end_ms=456)
        await self.event("input_audio_buffer.committed", item_id="heard", previous_item_id="previous")
        await self.event(
            "conversation.item.input_audio_transcription.completed",
            item_id="heard", transcript="삼성전자 주식 찾아줘",
        )
        flows = self.flows()
        self.assertEqual([event["status"] for event in flows], ["started", "stopped", "committed"])
        self.assertEqual([event["data"] for event in flows], [
            {"audio_start_ms": 123}, {"audio_end_ms": 456}, {"previous_item_id": "previous"},
        ])
        self.assertTrue(all(event["item_id"] == "heard" and event["response_id"] is None for event in flows))
        self.assertEqual(self.sent("transcript")[-1]["source_event"], "conversation.item.input_audio_transcription.completed")
        self.assertEqual(self.flows(operation="response.create"), [])

    async def test_user_item_acceptance_does_not_echo_the_service_content(self):
        await self.event("conversation.item.created", item={
            "type": "message", "id": "user", "role": "user",
            "content": [{"type": "input_text", "text": "PRIVATE_ECHO"}],
        })
        self.assertEqual(self.flows()[0]["status"], "accepted")
        self.assertEqual(self.flows()[0]["item_id"], "user")
        self.assertNotIn("PRIVATE_ECHO", json.dumps(self.flows()))

    async def test_response_creation_and_completion_do_not_claim_tool_execution(self):
        await self.event("response.created", response={"id": "response", "status": "in_progress"})
        await self.event("response.done", response={"id": "response", "status": "completed"})
        self.assertEqual(self.flows(stage="response")[0]["response_id"], "response")
        self.assertEqual(self.flows(stage="response")[0]["data"], {"status": "in_progress"})
        self.assertEqual(self.sent("response_done")[0]["source_event"], "response.done")
        self.assertEqual(self.flows(stage="tool"), [])
        self.assertEqual(self.sent("tool"), [])

    async def test_mcp_progress_and_arguments_precede_output_and_keep_actual_correlation(self):
        await self.event("response.output_item.added", response_id="response", item={
            "type": "mcp_call", "id": "tool", "name": "web",
        })
        events = [
            ServerEventResponseMcpCallInProgress(item_id="tool", output_index=0),
            ServerEventResponseMcpCallArgumentsDone({
                "type": "response.mcp_call_arguments.done", "item_id": "tool", "response_id": "response",
                "output_index": 0, "arguments": '{"query":"삼성전자 주식","maxResults":5}',
            }),
            ServerEventResponseMcpCallCompleted(item_id="tool", output_index=0),
        ]
        for event in events:
            await self.session.handle_event(event.as_dict(), self.connection, self.socket)
        self.assertEqual(self.sent("tool"), [])
        self.assertEqual([event["status"] for event in self.flows(stage="tool")], [
            "announced", "in_progress", "arguments_ready", "completed",
        ])
        args = self.flows(stage="tool")[2]
        self.assertEqual(args["data"]["arguments"], {"query": "삼성전자 주식", "maxResults": 5})
        self.assertEqual(args["data"]["name"], "web")
        self.assertTrue(all(
            event["tool_id"] == "tool" and event["item_id"] is None and event["response_id"] == "response"
            for event in self.flows(stage="tool")
        ))
        output = '{"structuredContent":{"webResults":[{"url":"https://example.invalid","title":"fixture"}]}}'
        await self.event("response.output_item.done", response_id="response", item={
            "type": "mcp_call", "id": "tool", "output": output,
        })
        self.assertEqual(self.sent("tool")[0]["output"], output)
        self.assertEqual(self.sent("tool")[0]["status"], "completed")
        self.assertEqual(self.sent("tool")[0]["source_event"], "response.output_item.done")
        self.assertNotIn(output, json.dumps(self.flows()))
        self.assertEqual(self.sent("citation"), [])

    async def test_unknown_tool_response_and_status_are_not_filled_from_active_response(self):
        self.session.active_response = "unrelated"
        await self.event("response.mcp_call.in_progress", item_id="tool")
        self.assertIsNone(self.flows(stage="tool")[0]["response_id"])
        await self.event("response.output_item.done", item={
            "type": "mcp_call", "id": "tool", "output": "actual output",
        })
        self.assertIsNone(self.sent("tool")[0]["status"])
        self.assertIsNone(self.sent("tool")[0]["response_id"])
        self.assertNotIn("name", self.flows(stage="tool")[0]["data"])
        self.assertEqual(self.flows(stage="tool")[-1]["status"], "output_observed")

    async def test_tool_summary_reads_metadata_without_ending_or_creating_a_call(self):
        self.assertIsNone(self.session.tools.summary("unknown"))
        await self.event("response.output_item.added", response_id="response", item={
            "type": "mcp_call", "id": "tool", "name": "web", "arguments": '{"query":"question"}',
        })
        summary = self.session.tools.summary("tool")
        self.assertEqual(summary["name"], "web")
        self.assertEqual(summary["response_id"], "response")
        self.assertIsNone(summary["status"])
        self.assertIn("tool", self.session.tools.calls)
        self.assertNotIn("tool", self.session.tools.retired)

    async def test_foundry_response_id_is_separate_from_voice_response_id(self):
        event = ServerEvent({
            "type": "response.foundry_agent_call.completed", "item_id": "tool",
            "agent_response_id": "foundry-response", "reasoning": "PRIVATE_REASONING",
        })
        self.session.active_response = "unrelated"
        await self.session.handle_event(event.as_dict(), self.connection, self.socket)
        flow = self.flows(stage="tool")[0]
        self.assertEqual(flow["data"]["agent_response_id"], "foundry-response")
        self.assertIsNone(flow["response_id"])
        self.assertEqual(flow["tool_id"], "tool")
        self.assertIsNone(flow["item_id"])
        self.assertNotIn("PRIVATE_REASONING", json.dumps(flow))

    async def test_foundry_agent_call_exposes_delegated_input_and_keeps_output(self):
        await self.event("response.output_item.done", response_id="response", item={
            "id": "agent-call", "type": "foundry_agent_call", "name": "test-bing",
            "arguments": json.dumps({"input": "삼성전자 주식 가격", "trace_access": "PRIVATE"}),
            "output": "Agent answer text",
        })
        tool = self.sent("tool")[0]
        self.assertEqual(tool["kind"], "foundry_agent_call")
        self.assertEqual(tool["arguments"], {"input": "삼성전자 주식 가격"})
        self.assertEqual(tool["output"], "Agent answer text")
        flow = self.flows(stage="tool")[0]
        self.assertEqual(flow["data"]["arguments"], {"input": "삼성전자 주식 가격"})
        self.assertEqual(flow["status"], "output_observed")
        self.assertNotIn("PRIVATE", json.dumps(self.sent()))

    async def test_argument_allowlist_drops_nested_private_values_unknown_fields_and_credentials(self):
        await self.event("response.mcp_call_arguments.done", item_id="tool", arguments=json.dumps({
            "query": "삼성전자 주식", "input": "빙 Agent에게 묻기", "region": "KR", "maxResults": 5,
            "location": {"Authorization": "PRIVATE_NESTED"},
            "headers": {"Authorization": "PRIVATE_HEADER"}, "trace_access": "PRIVATE_CAPABILITY",
            "reasoning": "PRIVATE_REASONING", "url": "https://example.invalid?api_key=PRIVATE_KEY",
            "maxLength": 10**200, "count": float("nan"),
        }))
        data = self.flows(stage="tool")[0]["data"]
        self.assertEqual(data["arguments"], {
            "query": "삼성전자 주식", "input": "빙 Agent에게 묻기", "region": "KR", "maxResults": 5,
        })
        self.assertTrue(data["arguments_filtered"])
        self.assertTrue(data["arguments_observed"])
        self.assertNotIn("PRIVATE", json.dumps(self.flows()))

    async def test_unparseable_arguments_are_not_exposed_or_described_as_empty_arguments(self):
        for index, arguments in enumerate(("PRIVATE_BAD_JSON", '["PRIVATE_ARRAY"]', "PRIVATE_" * 10000, None)):
            await self.event("response.mcp_call_arguments.done", item_id=f"tool-{index}", arguments=arguments)
            data = self.flows(stage="tool")[-1]["data"]
            self.assertEqual(data["arguments_observed"], arguments is not None)
            self.assertFalse(data["arguments_parseable"])
            self.assertNotIn("arguments", data)
        self.assertNotIn("PRIVATE", json.dumps(self.flows()))

    async def test_argument_urls_never_expose_trace_access_credentials(self):
        for index, url in enumerate((
            "https://example.invalid?trace_access_token=PRIVATE_CAPABILITY",
            "https://example.invalid?X-Trace-Access=PRIVATE_CAPABILITY",
            "https://example.invalid#trace%5Faccess%5Ftoken=PRIVATE_CAPABILITY",
        )):
            with self.subTest(url=url):
                await self.event("response.mcp_call_arguments.done", item_id=f"tool-{index}",
                                 arguments=json.dumps({"url": url, "query": "public question"}))
                data = self.flows(stage="tool")[-1]["data"]
                self.assertEqual(data["arguments"], {"query": "public question"})
                self.assertTrue(data["arguments_filtered"])
        self.assertNotIn("PRIVATE", json.dumps(self.flows()))

    async def test_final_tool_arguments_are_filtered_but_raw_output_is_unchanged(self):
        await self.event("response.output_item.done", item={
            "type": "mcp_call", "id": "tool", "name": "web",
            "arguments": '{"query":{"auth":"PRIVATE_NESTED"},"region":"KR"}',
            "output": {"structuredContent": {"webResults": []}},
        })
        tool = self.sent("tool")[0]
        self.assertEqual(tool["arguments"], {"region": "KR"})
        self.assertEqual(tool["output"], {"structuredContent": {"webResults": []}})
        self.assertNotIn("PRIVATE", json.dumps(self.sent()))

    async def test_mcp_discovery_exposes_actual_names_not_private_schemas_or_headers(self):
        await self.event("mcp_list_tools.completed", item_id="catalog")
        await self.event("conversation.item.created", item={
            "type": "mcp_list_tools", "id": "catalog", "server_label": "reported-server",
            "tools": [{"name": "web", "description": "PRIVATE_PROMPT", "input_schema": {"secret": "PRIVATE_SCHEMA"}}],
            "headers": {"Authorization": "PRIVATE_HEADER"},
        })
        flow = self.flows(stage="tool_discovery")[-1]
        self.assertEqual(flow["data"]["tools"], ["web"])
        self.assertEqual(flow["data"]["server_label"], "reported-server")
        self.assertEqual(flow["tool_id"], "catalog")
        self.assertEqual(self.flows(stage="tool"), [])
        self.assertNotIn("PRIVATE", json.dumps(self.flows()))

    async def test_citations_do_not_fabricate_bing_queries_tools_or_duplicate_sources(self):
        self.session = VoiceSession(settings(), "bing")
        self.addCleanup(self.session.tools.close)
        annotation = {"type": "url_citation", "url": "https://example.invalid/source", "title": "Fixture source"}
        for _ in range(2):
            await self.event(
                "response.output_text.annotation.added",
                response_id="response", item_id="message", annotation=annotation,
            )
        self.assertEqual(len(self.sent("citation")), 1)
        self.assertEqual(self.sent("citation")[0]["provider"], "bing")
        self.assertEqual(self.flows(stage="tool"), [])
        self.assertEqual(self.sent("tool"), [])

    async def test_supported_generic_web_search_event_is_not_renamed_bing(self):
        await self.event("response.web_search_call.searching", item_id="search")
        flow = self.flows(stage="tool")[0]
        self.assertEqual(flow["data"]["kind"], "web_search_call")
        self.assertEqual(flow["status"], "searching")
        self.assertNotIn("name", flow["data"])
        self.assertNotIn("arguments", flow["data"])
        self.assertIsNone(flow["response_id"])

    async def test_duplicate_tool_and_audio_milestones_are_not_repeated(self):
        for _ in range(5):
            await self.event("response.mcp_call.in_progress", item_id="tool", response_id="response")
            await self.event("response.audio.delta", item_id="message", response_id="response", delta="AAAA")
        self.assertEqual(len(self.flows(stage="tool")), 1)
        self.assertEqual(len(self.flows(stage="audio")), 1)
        self.assertEqual(len(self.sent("audio")), 5)

    async def test_legacy_active_response_fallback_does_not_become_reported_flow_correlation(self):
        self.session.active_response = "active"
        await self.event("response.audio.delta", item_id="message", delta="AAAA")
        await self.event("response.audio.done", item_id="message")
        self.assertEqual(self.sent("audio")[0]["response_id"], "active")
        self.assertTrue(all(flow["response_id"] is None for flow in self.flows(stage="audio")))
        self.assertNotIn("message", self.session.item_responses)

    async def test_audio_done_is_generation_boundary_not_response_success_or_playback(self):
        await self.event("response.audio.done", response_id="response", item_id="message")
        flow = self.flows(stage="audio")[0]
        self.assertEqual(flow["status"], "done")
        self.assertEqual(flow["data"], {"scope": "service_audio_generation"})
        self.assertEqual(self.sent("response_done"), [])
        self.assertEqual(self.sent("tool"), [])

    async def test_interrupted_response_emits_no_new_tool_audio_or_source_flows(self):
        await self.event("response.output_item.added", response_id="old", item={
            "type": "mcp_call", "id": "tool", "name": "web",
        })
        self.session.interrupted.add("old")
        self.socket.send_json.reset_mock()
        await self.event("response.mcp_call.completed", item_id="tool")
        await self.event("response.mcp_call_arguments.done", item_id="tool", arguments='{"query":"late"}')
        await self.event("response.output_item.done", item={
            "type": "mcp_call", "id": "tool", "output": "late",
        })
        await self.event("response.audio.delta", response_id="old", item_id="message", delta="AAAA")
        await self.event("response.audio.done", response_id="old", item_id="message")
        await self.event("response.output_text.annotation.added", response_id="old", annotation={
            "url": "https://example.invalid/late",
        })
        self.assertEqual(self.sent(), [])

    async def test_conflicting_service_item_response_mapping_is_not_reassigned(self):
        await self.event("response.mcp_call.in_progress", item_id="tool", response_id="first")
        self.socket.send_json.reset_mock()
        await self.event("response.mcp_call.completed", item_id="tool", response_id="other")
        self.assertEqual(self.sent(), [])
        self.assertEqual(self.session.item_responses["tool"], "first")

    async def test_late_response_created_cannot_reactivate_a_completed_or_interrupted_response(self):
        self.session.completed_responses.add("completed")
        self.session.interrupted.add("interrupted")
        self.session.active_response = "current"
        for response_id in ("completed", "interrupted"):
            await self.event("response.created", response={"id": response_id})
        self.assertEqual(self.sent(), [])
        self.assertEqual(self.session.active_response, "current")

    async def test_stopped_and_closed_sessions_do_not_emit_late_flow_events(self):
        self.session.stop_requested = True
        await self.event("session.created", session={"model": "late"})
        self.session.stop_requested = False
        self.session.closed.set()
        await self.event("response.created", response={"id": "late"})
        self.assertEqual(self.sent(), [])

    async def test_warning_preserves_safe_codes_without_echoing_service_message(self):
        await self.event("warning", warning={
            "code": "voice_warning", "param": "voice.name",
            "message": "PRIVATE_CONTENT", "event_id": "PRIVATE_EVENT",
        })
        self.assertEqual(self.flows()[0]["data"], {"code": "voice_warning", "param": "voice.name"})
        self.assertNotIn("PRIVATE", json.dumps(self.flows()))

    async def test_stt_error_preserves_actual_source_without_assistant_response_inference(self):
        self.session.active_response = "unrelated"
        with self.assertRaises(VoiceServiceError) as result:
            await self.event(
                "conversation.item.input_audio_transcription.failed", item_id="heard",
                error={"code": "transcription_failed", "message": "PRIVATE_FAILURE"},
            )
        self.assertEqual(result.exception.source_event, "conversation.item.input_audio_transcription.failed")
        self.assertEqual(result.exception.item_id, "heard")
        self.assertIsNone(result.exception.response_id)
        self.assertNotIn("PRIVATE", str(result.exception))

    async def test_caption_failure_does_not_end_a_realtime_session(self):
        realtime = VoiceSession(settings(), "webiq", "PRIVATE_APP_CONTEXT", voice_options={"connection_mode": "realtime_agent_tool"})
        self.addCleanup(realtime.tools.close)
        with self.assertLogs("tmap_poc.voice", level="WARNING"):
            await realtime.handle_event({
                "type": "conversation.item.input_audio_transcription.failed", "item_id": "heard",
                "error": {"code": "transcription_failed", "message": "PRIVATE_FAILURE"},
            }, self.connection, self.socket)

    async def test_hosted_invocation_and_reasoning_payloads_are_not_forwarded_raw(self):
        await self.event("response.invocation.delta", item_id="hosted", delta={
            "type": "response.reasoning.delta", "delta": "PRIVATE_REASONING",
            "headers": {"Authorization": "PRIVATE_TOKEN"},
        })
        self.assertEqual(self.sent(), [])


if __name__ == "__main__":
    unittest.main()
