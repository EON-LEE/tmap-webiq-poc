import asyncio
from contextlib import asynccontextmanager
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tmap_poc.api import create_app
from tmap_poc.app_settings import AppSettings
from tmap_poc.cli import prepare_agents, verified_profiles
from tmap_poc.config import ConfigError
from tmap_poc.profiles import AgentReference, NAVIGATION_INSTRUCTIONS, agent_definition
from tmap_poc.voice_options import VoiceOptionsError
from tmap_poc.voice import (
    VoiceProtocolError, VoiceServiceError, VoiceSession, connection_url, parse_control,
)

# Debug stack collection over a WSL/Windows mount is not transport latency.
SESSION_TEST_TIMEOUT = 10


def settings():
    return AppSettings(
        project_endpoint="https://agent.example.invalid/api/projects/navigation",
        voice_endpoint="https://voice.example.invalid",
        model="test-model", subscription="explicit-test-subscription",
        agents={
            "bing": AgentReference("test-bing", "1"),
            "webiq": AgentReference("test-webiq", "2"),
        },
    )


class SettingsTests(unittest.TestCase):
    def test_missing_subscription_is_not_defaulted(self):
        with patch.dict(os.environ, {}, clear=True):
            config = AppSettings.from_env()
            with self.assertRaises(ConfigError):
                config.credential()
            self.assertIn("TMAP_POC_AZ_SUBSCRIPTION", " ".join(config.problems()))

    def test_managed_identity_requires_no_subscription(self):
        config = AppSettings(auth_mode="managed_identity")
        with patch("azure.identity.ManagedIdentityCredential") as constructor:
            self.assertIs(config.credential(), constructor.return_value)
            constructor.assert_called_once_with()

    def test_settings_do_not_expose_environment_values_in_config_errors(self):
        with patch.dict(os.environ, {"TMAP_VOICE_ENDPOINT": "https://user:secret@example.invalid"}, clear=True):
            with self.assertRaises(ConfigError) as error:
                AppSettings.from_env()
            self.assertNotIn("secret", str(error.exception))

    def test_exact_origins_required(self):
        for origin in ("*", "https://example.invalid/path", "https://u:p@example.invalid"):
            with self.subTest(origin=origin), patch.dict(os.environ, {"TMAP_ALLOWED_ORIGINS": origin}, clear=True):
                with self.assertRaises(ConfigError):
                    AppSettings.from_env()

    def test_prepare_defaults_to_no_client_creation(self):
        with patch.dict(os.environ, {"GWB_CONNECTION_ID": "bing-test", "WEBIQ_CONNECTION_ID": "webiq-test"}):
            with patch("azure.ai.projects.AIProjectClient") as client:
                prepare_agents(settings(), "example", False)
                client.assert_not_called()

    def test_profiles_share_instructions_not_tools(self):
        with patch.dict(os.environ, {"GWB_CONNECTION_ID": "bing-test", "WEBIQ_CONNECTION_ID": "webiq-test"}):
            bing = agent_definition("bing", "test-model")
            webiq = agent_definition("webiq", "test-model")
        for field in ("instructions", "model", "reasoning", "kind"):
            self.assertEqual(bing[field], webiq[field])
        self.assertEqual(bing["tools"][0]["type"], "bing_grounding")
        self.assertEqual(webiq["tools"][0]["type"], "mcp")
        self.assertNotIn('{"answer":', NAVIGATION_INSTRUCTIONS)

    def test_comparison_rejects_unmatched_agent_instructions(self):
        project = SimpleNamespace(agents=SimpleNamespace(
            get_version=lambda *_: SimpleNamespace(definition=SimpleNamespace(as_dict=lambda: {
                "model": "test-model", "instructions": "different", "tools": [],
            }))
        ))
        with self.assertRaises(ConfigError):
            verified_profiles(project, settings())

    def test_voice_url_pins_agent_not_direct_model(self):
        config = settings()
        url = urlparse(connection_url(config, config.agents["webiq"]))
        query = parse_qs(url.query)
        self.assertEqual(url.scheme, "wss")
        self.assertEqual(query["agent-name"], ["test-webiq"])
        self.assertEqual(query["agent-project-name"], ["navigation"])
        self.assertEqual(query["agent-version"], ["2"])
        self.assertNotIn("model", query)
        self.assertNotIn("api-key", query)
        self.assertNotIn("conversation-id", query)


class ProtocolTests(unittest.TestCase):
    def test_invalid_messages_are_rejected(self):
        invalid = [
            "null", "[]", "{", '{"type":[]}', '{"type":"start","provider":"unknown"}',
            '{"type":"text","text":""}', '{"type":"stop","endpoint":"override"}',
            json.dumps({"type": "start", "provider": "bing", "context": "x" * 4001}),
        ]
        for message in invalid:
            with self.subTest(message=message[:60]):
                with self.assertRaises(VoiceProtocolError):
                    parse_control(message)

    def test_valid_start_preserves_context(self):
        message = {"type": "start", "provider": "bing", "context": "destination example"}
        self.assertEqual(parse_control(json.dumps(message)), message)


class ApiTests(unittest.TestCase):
    def test_unconfigured_page_makes_no_cloud_calls(self):
        with TestClient(create_app(AppSettings())) as client:
            self.assertEqual(client.get("/healthz").json(), {"status": "ok"})
            data = client.get("/api/config").json()
        self.assertFalse(any(p["configured"] for p in data["providers"]))
        self.assertTrue(data["errors"])
        self.assertNotIn("endpoint", data)

    def test_empty_server_voice_reports_configuration_error_instead_of_crashing(self):
        with TestClient(create_app(AppSettings(voice_name=""))) as client:
            response = client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["voice_options"])
        self.assertTrue(any("TMAP_VOICE_NAME" in item for item in response.json()["errors"]))

    def test_browser_origin_is_required(self):
        with TestClient(create_app(settings())) as client:
            with self.assertRaises(WebSocketDisconnect):
                with client.websocket_connect("/ws/voice", headers={"origin": "https://other.invalid"}):
                    pass

    def test_start_uses_selected_provider_context(self):
        captured = {}

        class FakeSession:
            def __init__(self, config, provider, context):
                captured.update(provider=provider, context=context, config=config)

            async def run(self, socket):
                await socket.send_json({"type": "status", "state": "ready"})
                return "stopped"

        with TestClient(create_app(settings(), voice_factory=FakeSession)) as client:
            with client.websocket_connect("/ws/voice", headers={"origin": "http://localhost:8000"}) as ws:
                ws.send_json({"type": "start", "provider": "webiq", "context": "arrival 20:10"})
                self.assertEqual(ws.receive_json()["state"], "connecting")
                self.assertEqual(ws.receive_json()["state"], "ready")
                self.assertEqual(ws.receive_json()["type"], "done")
        self.assertEqual(captured["provider"], "webiq")
        self.assertEqual(captured["context"], "arrival 20:10")

    def test_unconfigured_start_surfaces_error(self):
        with TestClient(create_app(AppSettings())) as client:
            with client.websocket_connect("/ws/voice", headers={"origin": "http://localhost:8000"}) as ws:
                ws.send_json({"type": "start", "provider": "bing"})
                result = ws.receive_json()
        self.assertEqual(result["type"], "error")
        self.assertEqual(result["code"], "ConfigError")

    def test_selected_options_reach_voice_session_and_unknown_models_do_not(self):
        calls = []

        class FakeSession:
            def __init__(self, config, provider, context, *, voice_options):
                calls.append(voice_options)

            async def run(self, socket):
                return "stopped"

        with TestClient(create_app(settings(), voice_factory=FakeSession)) as client:
            with client.websocket_connect("/ws/voice", headers={"origin": "http://localhost:8000"}) as ws:
                ws.send_json({"type": "start", "provider": "bing", "voice_options": {
                    "transcription_model": "mai-transcribe", "speech_rate": 1.25,
                    "interrupt_response": False,
                }})
                self.assertEqual(ws.receive_json()["state"], "connecting")
                self.assertEqual(ws.receive_json()["type"], "done")
            with client.websocket_connect("/ws/voice", headers={"origin": "http://localhost:8000"}) as ws:
                ws.send_json({"type": "start", "provider": "bing", "voice_options": {"model": "gpt-realtime"}})
                self.assertEqual(ws.receive_json()["code"], "VoiceOptionsError")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["transcription_model"], "mai-transcribe")
        self.assertEqual(calls[0]["speech_rate"], 1.25)
        self.assertFalse(calls[0]["interrupt_response"])


class VoiceEventsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = VoiceSession(settings(), "bing", "arrival 20:10")
        self.socket = SimpleNamespace(send_json=AsyncMock())
        self.connection = SimpleNamespace(
            conversation=SimpleNamespace(item=SimpleNamespace(create=AsyncMock())),
        )

    async def event(self, **data):
        await self.session.handle_event(data, self.connection, self.socket)

    async def test_each_session_has_new_ids_and_only_its_own_context(self):
        fresh = VoiceSession(settings(), "bing", "")
        self.assertNotEqual(fresh.session_id, self.session.session_id)
        self.assertNotEqual(fresh.context_id, self.session.context_id)
        self.assertLessEqual(len(fresh.context_id), 32)
        await fresh.handle_event({"type": "session.updated"}, self.connection, self.socket)
        item = self.connection.conversation.item.create.call_args.kwargs["item"].as_dict()
        self.assertNotIn("arrival 20:10", item["content"][0]["text"])
        self.assertNotIn("conversation-id", parse_qs(urlparse(connection_url(settings(), fresh.agent)).query))

    async def test_realtime_route_uses_model_query_and_pinned_agent_tool(self):
        options = {"connection_mode": "realtime_agent_tool", "realtime_model": "gpt-realtime-mini"}
        session = VoiceSession(settings(), "webiq", voice_options=options)
        query = parse_qs(urlparse(connection_url(settings(), session.agent, voice_options=options)).query)
        self.assertEqual(query["model"], ["gpt-realtime-mini"])
        self.assertNotIn("agent-name", query)
        self.assertNotIn("agent-project-name", query)
        self.assertLessEqual(len(session.context_id), 32)

    async def test_realtime_runtime_sends_trusted_agent_target_with_selected_model_route(self):
        captured = {}
        events = asyncio.Queue()
        browser = asyncio.Queue()

        async def create_item(*, item):
            await events.put({"type": "conversation.item.created", "item": {"id": item.as_dict()["id"]}})

        class Connection:
            session = SimpleNamespace(update=AsyncMock())
            conversation = SimpleNamespace(item=SimpleNamespace(create=create_item))

            def __aiter__(self):
                return self

            async def __anext__(self):
                return await events.get()

        connection = Connection()

        @asynccontextmanager
        async def connector(config, agent, *, voice_options):
            captured.update(agent=agent, options=voice_options)
            yield connection

        async def send(event):
            if event.get("state") == "ready":
                await browser.put({"type": "websocket.receive", "text": '{"type":"stop"}'})

        socket = SimpleNamespace(receive=browser.get, send_json=send)
        await events.put({"type": "session.updated"})
        session = VoiceSession(settings(), "bing", connector=connector, voice_options={
            "connection_mode": "realtime_agent_tool", "realtime_model": "gpt-realtime",
            "voice_name": "openai:coral", "return_agent_response_directly": False,
        })
        self.assertEqual(await asyncio.wait_for(session.run(socket), SESSION_TEST_TIMEOUT), "stopped")
        sent = connection.session.update.call_args.kwargs["session"].as_dict()
        self.assertEqual(captured["options"]["realtime_model"], "gpt-realtime")
        self.assertEqual(sent["tools"][0]["agent_name"], settings().agents["bing"].name)
        self.assertEqual(sent["tools"][0]["agent_version"], "1")
        self.assertFalse(sent["tools"][0]["return_agent_response_directly"])
        self.assertEqual(sent["voice"], {"type": "openai", "name": "coral"})
        self.assertNotIn("model", sent)

    async def test_ready_waits_for_context_ack(self):
        await self.event(type="session.updated")
        self.assertFalse(self.session.ready.is_set())
        item = self.connection.conversation.item.create.call_args.kwargs["item"].as_dict()
        self.assertEqual(item["role"], "user")
        self.assertIn("arrival 20:10", item["content"][0]["text"])
        await self.event(type="conversation.item.created", item={"id": self.session.context_id})
        self.assertTrue(self.session.ready.is_set())

    async def test_interruption_drops_old_audio(self):
        await self.event(type="response.created", response={"id": "old"})
        await self.event(type="input_audio_buffer.speech_started")
        await self.event(type="response.audio.delta", response_id="old", delta="AAAA")
        events = [call.args[0] for call in self.socket.send_json.call_args_list]
        self.assertEqual([
            event["type"] for event in events if event["type"] not in ("activity", "flow")
        ], ["interrupt"])
        await self.event(type="response.created", response={"id": "new"})
        await self.event(type="response.audio.delta", response_id="new", delta="AAAA")
        self.assertEqual(self.socket.send_json.call_args.args[0]["type"], "audio")

    async def test_disabled_interruption_does_not_silence_the_playing_response(self):
        self.session = VoiceSession(settings(), "bing", voice_options={"interrupt_response": False})
        await self.event(type="response.created", response={"id": "active"})
        await self.event(type="input_audio_buffer.speech_started")
        self.assertFalse(any(call.args[0]["type"] in ("audio", "interrupt") for call in self.socket.send_json.call_args_list))
        await self.event(type="response.audio.delta", response_id="active", delta="AAAA")
        self.assertEqual(self.socket.send_json.call_args.args[0]["type"], "audio")

    async def test_invalid_options_fail_before_connection_attempt(self):
        connector = AsyncMock()
        with self.assertRaises(VoiceOptionsError):
            VoiceSession(settings(), "bing", connector=connector, voice_options={"voice_name": "untrusted"})
        connector.assert_not_called()

    async def test_safe_parameter_diagnostics_exclude_service_message_content(self):
        with self.assertRaises(VoiceServiceError) as error:
            await self.event(type="error", error={
                "code": "invalid_value", "param": "session.voice",
                "message": "private diagnostic details",
            })
        self.assertIn("code=invalid_value", str(error.exception))
        self.assertIn("parameter=session.voice", str(error.exception))
        self.assertNotIn("private diagnostic", str(error.exception))

    async def test_text_and_audio_transcripts_are_not_duplicated(self):
        await self.event(type="response.created", response={"id": "r"})
        await self.event(type="response.text.done", item_id="i", text="hello")
        await self.event(type="response.audio_transcript.done", item_id="i", transcript="hello")
        await self.event(type="response.done", response={"id": "r", "status": "completed"})
        transcripts = [c.args[0] for c in self.socket.send_json.call_args_list if c.args[0]["type"] == "transcript"]
        self.assertEqual(len(transcripts), 1)

    async def test_citations_are_actual_safe_annotations(self):
        await self.event(type="response.audio_transcript.annotation.added", annotation={"url": "javascript:alert(1)"})
        self.socket.send_json.assert_not_called()
        await self.event(
            type="response.audio_transcript.annotation.added", item_id="i",
            annotation={"type": "url_citation", "url": "https://example.invalid/source", "title": "Source"},
        )
        self.assertEqual(self.socket.send_json.call_args.args[0]["type"], "citation")

    async def test_usage_is_voice_meter_not_model_estimate(self):
        usage = {"input_tokens": 20, "output_tokens": 30}
        await self.event(type="response.done", response={"id": "r", "status": "completed", "usage": usage})
        result = next(
            call.args[0] for call in self.socket.send_json.call_args_list
            if call.args[0]["type"] == "usage"
        )
        self.assertEqual(result["source"], "voice_live")
        self.assertEqual(result["usage"], usage)

    async def test_service_error_is_not_success(self):
        with self.assertRaises(VoiceServiceError):
            await self.event(type="error", error={"message": "contains private diagnostics"})

    async def test_typed_requests_wait_for_the_first_response(self):
        self.session.ready.set()
        queue = asyncio.Queue()
        for control in (
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
            {"type": "stop"},
        ):
            await queue.put({"type": "websocket.receive", "text": json.dumps(control)})
        self.socket.receive = queue.get
        self.connection.response = SimpleNamespace(create=AsyncMock(), cancel=AsyncMock())
        await self.session._from_browser(self.connection, self.socket)
        self.connection.response.create.assert_awaited_once()
        self.connection.response.cancel.assert_awaited_once()
        errors = [c.args[0] for c in self.socket.send_json.call_args_list if c.args[0]["type"] == "error"]
        self.assertEqual(errors[0]["code"], "response_busy")

    async def test_invalid_audio_is_not_forwarded(self):
        self.session.ready.set()
        self.socket.receive = AsyncMock(return_value={"type": "websocket.receive", "bytes": b"x"})
        self.connection.input_audio_buffer = SimpleNamespace(append=AsyncMock())
        with self.assertRaises(VoiceProtocolError):
            await self.session._from_browser(self.connection, self.socket)
        self.connection.input_audio_buffer.append.assert_not_called()

    async def test_stop_cancels_pending_connection_setup(self):
        started, cancelled = asyncio.Event(), asyncio.Event()

        @asynccontextmanager
        async def connector(config, reference):
            try:
                started.set()
                await asyncio.Event().wait()
                yield None
            finally:
                cancelled.set()

        async def receive():
            await started.wait()
            return {"type": "websocket.receive", "text": '{"type":"stop"}'}

        socket = SimpleNamespace(receive=receive, send_json=AsyncMock())
        session = VoiceSession(settings(), "bing", connector=connector)
        self.assertEqual(await asyncio.wait_for(session.run(socket), SESSION_TEST_TIMEOUT), "stopped")
        self.assertTrue(cancelled.is_set())

    async def test_ready_deadline_starts_after_authentication_and_connection(self):
        original = asyncio.wait_for
        with patch("tmap_poc.voice.asyncio.wait_for", new=AsyncMock(wraps=original)) as wait:
            task = asyncio.create_task(self.session._ready_deadline())
            await asyncio.sleep(0)
            wait.assert_not_called()
            self.session.connection_opened.set()
            await asyncio.sleep(0)
            self.assertEqual(wait.call_args.kwargs["timeout"], 30)
            self.session.ready.set()
            self.session.closed.set()
            await task

    async def test_stop_closes_connection_and_background_readers(self):
        service_events = asyncio.Queue()
        browser_events = asyncio.Queue()
        captured = {"closed": False}

        async def create_item(*, item):
            await service_events.put({"type": "conversation.item.created", "item": {"id": item.as_dict()["id"]}})

        class Connection:
            session = SimpleNamespace(update=AsyncMock())
            conversation = SimpleNamespace(item=SimpleNamespace(create=create_item))
            response = SimpleNamespace(cancel=AsyncMock())

            def __aiter__(self):
                return self

            async def __anext__(self):
                return await service_events.get()

        connection = Connection()

        @asynccontextmanager
        async def connector(config, reference):
            try:
                yield connection
            finally:
                captured["closed"] = True

        async def send_json(event):
            if event.get("state") == "ready":
                await browser_events.put({"type": "websocket.receive", "text": '{"type":"stop"}'})

        socket = SimpleNamespace(receive=browser_events.get, send_json=send_json)
        await service_events.put({"type": "session.updated"})
        session = VoiceSession(settings(), "webiq", connector=connector)
        result = await asyncio.wait_for(session.run(socket), timeout=SESSION_TEST_TIMEOUT)
        self.assertEqual(result, "stopped")
        self.assertTrue(captured["closed"])
        config = connection.session.update.call_args.kwargs["session"].as_dict()
        self.assertEqual(config["input_audio_sampling_rate"], 24000)
        self.assertNotIn("instructions", config)


if __name__ == "__main__":
    unittest.main()
