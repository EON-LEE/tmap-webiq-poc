import asyncio
import base64
from contextlib import asynccontextmanager
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

from azure.ai.voicelive.aio import VoiceLiveConnection
from azure.ai.voicelive.models import Response, ResponseCreateParams
from fastapi.testclient import TestClient

from tmap_poc.api import create_app
from tmap_poc.app_settings import AppSettings
from tmap_poc.config import ConfigError
from tmap_poc.navigation import NavigationError, NavigationState, demo_configuration, navigation_tools
from tmap_poc.navigation_voice import NavigationVoice
from tmap_poc.voice import VoiceProtocolError, VoiceServiceError, VoiceSession, connection_url, parse_control
from tmap_poc.voice_options import (
    MODEL_CHOICES, MODEL_MODE, VoiceOptionsError, build_model_session, validate_options,
)


def model_settings():
    return AppSettings(voice_endpoint="https://voice.example.invalid", subscription="explicit-test-subscription")


def function_call(name="open_app", arguments=None, call_id="call_one"):
    return {
        "type": "function_call", "call_id": call_id, "name": name,
        "arguments": json.dumps({"app": "navigation"} if arguments is None else arguments),
    }


class NavigationStateTests(unittest.TestCase):
    def setUp(self):
        self.state = NavigationState()

    def open_and_find(self, query="회사"):
        self.state.execute("open_app", {"app": "navigation"})
        return self.state.execute("search_places", {"query": query})["state"]["results"]

    def test_app_launch_is_a_state_change_not_a_fabricated_external_launch(self):
        result = self.state.execute("open_app", {"app": "navigation"})
        self.assertTrue(result["state"]["app_open"])
        self.assertEqual(result["state"]["revision"], 1)
        self.assertEqual(result["state"]["data_source"], "demo_fixture")
        self.assertIn("외부 TMAP 앱 실행은 아닙니다", result["message"])

    def test_search_preview_guidance_waypoint_and_cancel_share_one_state(self):
        place = self.open_and_find()[0]
        preview = self.state.execute("preview_route", {"destination_id": place["id"]})["state"]
        self.assertEqual(preview["phase"], "route_preview")
        self.assertGreater(preview["route"]["distance_km"], 0)
        self.state.execute("start_navigation", {})
        stops = self.state.execute("search_places", {"query": "가는 길 충전소"})["state"]["results"]
        changed = self.state.execute("add_waypoint", {"place_id": stops[0]["id"]})["state"]
        self.assertEqual(changed["phase"], "guiding")
        self.assertEqual(changed["waypoints"][0]["id"], "ev-station")
        self.assertGreater(changed["route"]["distance_km"], preview["route"]["distance_km"])
        self.assertIn(stops[0]["point"], changed["route"]["points"])
        stopped = self.state.execute("cancel_navigation", {})["state"]
        self.assertTrue(stopped["app_open"])
        self.assertEqual(stopped["phase"], "idle")
        self.assertIsNone(stopped["route"])
        self.assertEqual(stopped["waypoints"], [])

    def test_results_support_ordered_followups_without_guessing_unknown_places(self):
        results = self.open_and_find("근처 카페")
        self.assertEqual(len(results), 2)
        self.assertLessEqual(results[0]["distance_km"], results[1]["distance_km"])
        result = self.state.execute("preview_route", {"destination_id": results[1]["id"]})
        self.assertEqual(result["state"]["destination"]["id"], results[1]["id"])
        with self.assertRaisesRegex(NavigationError, "먼저 장소"):
            self.state.execute("preview_route", {"destination_id": "ev-station"})

    def test_unknown_search_is_empty_not_a_fake_recommendation(self):
        self.open_and_find()
        result = self.state.execute("search_places", {"query": "존재하지않는목적지"})
        self.assertEqual(result["state"]["results"], [])
        self.assertIn("실제 장소 검색은 연결되지 않았습니다", result["message"])
        self.assertIsNone(result["state"]["destination"])

    def test_invalid_commands_do_not_mutate_state(self):
        bad = [
            ("execute_shell", {}), ("open_app", {"app": "calculator"}),
            ("open_app", {"app": "navigation", "url": "https://example.invalid"}),
            ("open_app", []), ("search_places", {"query": ""}),
            ("search_places", {"query": False}), ("search_places", {"query": "x" * 81}),
            ("start_navigation", {}), ("cancel_navigation", {}),
        ]
        for name, arguments in bad:
            with self.subTest(name=name, arguments=arguments), self.assertRaises(NavigationError):
                self.state.execute(name, arguments)
            self.assertEqual(self.state.revision, 0)
            self.assertFalse(self.state.app_open)

    def test_duplicate_stops_and_destination_stops_are_rejected(self):
        destination = self.open_and_find()[0]
        self.state.execute("preview_route", {"destination_id": destination["id"]})
        with self.assertRaises(NavigationError):
            self.state.execute("add_waypoint", {"place_id": destination["id"]})
        stops = self.state.execute("search_places", {"query": "카페"})["state"]["results"]
        self.state.execute("add_waypoint", {"place_id": stops[0]["id"]})
        revision = self.state.revision
        with self.assertRaises(NavigationError):
            self.state.execute("add_waypoint", {"place_id": stops[0]["id"]})
        self.assertEqual(self.state.revision, revision)

    def test_snapshots_and_sessions_are_isolated(self):
        place = self.open_and_find()[0]
        result = self.state.execute("preview_route", {"destination_id": place["id"]})
        result["state"]["route"]["points"][0][0] = -1
        result["state"]["destination"]["name"] = "changed"
        self.assertNotEqual(self.state.snapshot()["destination"]["name"], "changed")
        self.assertGreaterEqual(self.state.snapshot()["route"]["points"][0][0], 0)
        self.assertFalse(NavigationState().snapshot()["app_open"])

    def test_rehearsal_is_built_from_the_same_command_executor(self):
        configuration = demo_configuration()
        self.assertFalse(configuration["initial_state"]["app_open"])
        self.assertEqual(len(configuration["rehearsal"]), 5)
        self.assertEqual(configuration["rehearsal"][2]["state"]["phase"], "guiding")
        self.assertEqual(configuration["rehearsal"][3]["state"]["waypoints"][0]["id"], "ev-station")
        self.assertIsNone(configuration["rehearsal"][-1]["state"]["route"])
        json.dumps(configuration, allow_nan=False)
        configuration["rehearsal"].clear()
        self.assertEqual(len(demo_configuration()["rehearsal"]), 5)


class ModelConnectionTests(unittest.TestCase):
    def test_model_mode_needs_no_search_agent_project_or_llm_deployment(self):
        settings = model_settings()
        settings.require("bing", connection_mode=MODEL_MODE)
        with self.assertRaises(ConfigError):
            settings.require("bing")
        options = validate_options({"connection_mode": MODEL_MODE}, settings.voice_name)
        self.assertEqual(options["llm_model"], "gpt-4.1-mini")
        query = parse_qs(urlparse(connection_url(settings, None, voice_options=options)).query)
        self.assertEqual(query["model"], ["gpt-4.1-mini"])
        self.assertNotIn("agent-name", query)
        self.assertNotIn("agent-project-name", query)
        self.assertIsNone(VoiceSession(settings, "bing", voice_options=options).agent)

    def test_model_choices_map_to_real_speech_and_function_fields(self):
        for model in MODEL_CHOICES:
            options = validate_options({"connection_mode": MODEL_MODE, "llm_model": model}, "ko-KR-SunHiNeural")
            data = build_model_session(options).as_dict()
            self.assertEqual(data["tools"], navigation_tools())
            self.assertEqual(data["input_audio_transcription"], {"model": "azure-speech", "language": "ko-KR"})
            self.assertEqual(data["voice"]["type"], "azure-standard")
            self.assertEqual(data["tool_choice"], "auto")
            self.assertNotIn("llm_model", data)
            self.assertNotIn("model", data)
            self.assertIn("never infer that an action succeeded", data["instructions"])

    def test_incompatible_models_and_speech_options_are_not_silently_ignored(self):
        for options in (
            {"llm_model": "gpt-4.1-mini"},
            {"connection_mode": MODEL_MODE, "llm_model": "unknown"},
            {"connection_mode": MODEL_MODE, "llm_model": None},
            {"connection_mode": MODEL_MODE, "llm_model": []},
            {"connection_mode": MODEL_MODE, "realtime_model": "gpt-realtime"},
            {"connection_mode": MODEL_MODE, "transcription_model": "whisper-1"},
            {"connection_mode": MODEL_MODE, "voice_name": "openai:coral"},
            {"connection_mode": MODEL_MODE, "return_agent_response_directly": False},
        ):
            with self.subTest(options=options), self.assertRaises(VoiceOptionsError):
                validate_options(options, "ko-KR-SunHiNeural")

    def test_model_api_capabilities_and_websocket_use_only_model_requirements(self):
        captured = []

        class Session:
            def __init__(self, settings, provider, context, *, voice_options):
                captured.append(voice_options)

            async def run(self, socket):
                return "stopped"

        with TestClient(create_app(model_settings(), voice_factory=Session)) as client:
            data = client.get("/api/config").json()
            self.assertFalse(any(provider["configured"] for provider in data["providers"]))
            self.assertTrue(data["model_connection"]["configured"])
            self.assertEqual(data["model_connection"]["errors"], [])
            self.assertEqual(data["navigation"]["recommended_mode"], MODEL_MODE)
            with client.websocket_connect("/ws/voice", headers={"origin": "http://localhost:8000"}) as socket:
                socket.send_json({"type": "start", "provider": "bing", "voice_options": {"connection_mode": MODEL_MODE}})
                self.assertEqual(socket.receive_json()["state"], "connecting")
                self.assertEqual(socket.receive_json()["type"], "done")
        self.assertEqual(captured[0]["llm_model"], "gpt-4.1-mini")

    def test_display_acknowledgement_has_a_strict_protocol(self):
        good = {"type": "navigation_ack", "action_id": "call_1", "revision": 1}
        self.assertEqual(parse_control(json.dumps(good)), good)
        for changes in (
            {"revision": True}, {"revision": 1.5}, {"revision": -1}, {"revision": 257},
            {"action_id": ""}, {"action_id": []}, {"extra": "untrusted"},
        ):
            with self.subTest(changes=changes), self.assertRaises(VoiceProtocolError):
                parse_control(json.dumps({**good, **changes}))


class NavigationVoiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bridge = NavigationVoice(acknowledgement_timeout=.02)
        self.events = []
        self.auto_ack = True
        self.connection = SimpleNamespace(conversation=SimpleNamespace(item=SimpleNamespace(create=AsyncMock())))

        async def send(event):
            self.events.append(event)
            if self.auto_ack and event["type"] == "navigation" and event.get("action_id"):
                self.assertTrue(self.bridge.acknowledge(event["action_id"], event["state"]["revision"]))

        self.socket = SimpleNamespace(send_json=send)

    def output(self):
        item = self.connection.conversation.item.create.call_args.kwargs["item"].as_dict()
        self.assertEqual(item["type"], "function_call_output")
        return json.loads(item["output"])

    async def test_success_requires_state_application_and_matching_browser_ack(self):
        await self.bridge.dispatch([function_call()], self.connection, self.socket)
        self.assertTrue(self.output()["ok"])
        self.assertTrue(self.output()["display_confirmed"])
        applied = next(event for event in self.events if event["type"] == "navigation")
        self.assertEqual(applied["action_id"], "call_one")
        self.assertTrue(applied["state"]["app_open"])
        self.assertEqual(self.events[-1]["status"], "completed")

    async def test_no_ack_is_uncertain_not_success_or_silent_rollback(self):
        self.auto_ack = False
        await self.bridge.dispatch([function_call()], self.connection, self.socket)
        self.assertFalse(self.output()["ok"])
        self.assertEqual(self.output()["code"], "display_ack_timeout")
        self.assertTrue(self.output()["state"]["app_open"])
        self.assertFalse(self.output()["display_confirmed"])
        self.assertEqual(self.events[-1]["status"], "failed")
        self.assertIsNone(self.bridge.pending_display)

    async def test_wrong_ack_cannot_confirm_an_action(self):
        ready = asyncio.Event()
        self.bridge.pending_display = ("call_expected", 1, ready)
        self.assertFalse(self.bridge.acknowledge("call_other", 1))
        self.assertFalse(self.bridge.acknowledge("call_expected", 0))
        self.assertFalse(ready.is_set())
        self.assertTrue(self.bridge.acknowledge("call_expected", 1))
        self.assertTrue(ready.is_set())

    async def test_duplicate_calls_are_idempotent_and_not_submitted_twice(self):
        call = function_call()
        await self.bridge.dispatch([call, call], self.connection, self.socket)
        self.assertFalse(await self.bridge.dispatch([call], self.connection, self.socket))
        self.assertEqual(self.bridge.state.revision, 1)
        self.connection.conversation.item.create.assert_awaited_once()
        self.assertEqual(self.bridge.calls({"output": [call]}), [])

    async def test_invalid_function_arguments_return_explicit_errors_without_actions(self):
        for index, call in enumerate((
            {**function_call(), "arguments": "{"},
            {**function_call(), "arguments": "x" * 4001},
            function_call("launch_url", {"url": "https://example.invalid"}),
            function_call("open_app", {"app": "terminal"}),
        )):
            call["call_id"] = f"bad_{index}"
            await self.bridge.dispatch([call], self.connection, self.socket)
            self.assertFalse(self.output()["ok"])
            self.assertFalse(self.output()["state"]["app_open"])
        self.assertFalse(any(event["type"] == "navigation" for event in self.events))

    async def test_interruption_prevents_unexecuted_mutations(self):
        await self.bridge.dispatch([function_call()], self.connection, self.socket, cancelled=lambda: True)
        self.assertEqual(self.output()["code"], "interrupted")
        self.assertFalse(self.bridge.state.app_open)
        self.assertFalse(any(event["type"] == "navigation" for event in self.events))

    async def test_sdk_serializes_navigation_contract_and_result_without_losing_fields(self):
        transport = SimpleNamespace(send_str=AsyncMock())
        connection = VoiceLiveConnection(SimpleNamespace(), transport)
        chosen = validate_options({"connection_mode": MODEL_MODE}, "ko-KR-SunHiNeural")
        session = build_model_session(chosen)
        await connection.session.update(session=session)
        self.assertEqual(json.loads(transport.send_str.call_args.args[0])["session"], session.as_dict())
        await self.bridge.dispatch([function_call()], connection, self.socket)
        event = json.loads(transport.send_str.call_args.args[0])
        self.assertEqual(event["type"], "conversation.item.create")
        self.assertEqual(event["item"]["type"], "function_call_output")
        self.assertTrue(json.loads(event["item"]["output"])["display_confirmed"])

    async def test_sdk_preserves_response_correlation_and_targeted_cancellation(self):
        transport = SimpleNamespace(send_str=AsyncMock())
        connection = VoiceLiveConnection(SimpleNamespace(), transport)
        metadata = {"navigation_request": "request_nonce"}
        await connection.response.create(response=ResponseCreateParams(metadata=metadata))
        created = json.loads(transport.send_str.call_args.args[0])
        self.assertEqual(created["response"]["metadata"], metadata)
        self.assertEqual(Response({"id": "response_one", "metadata": metadata}).as_dict()["metadata"], metadata)
        await connection.response.cancel(response_id="response_one", event_id="cancel_nonce")
        cancelled = json.loads(transport.send_str.call_args.args[0])
        self.assertEqual(cancelled["type"], "response.cancel")
        self.assertEqual(cancelled["response_id"], "response_one")
        self.assertEqual(cancelled["event_id"], "cancel_nonce")


class NavigationLoopTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Debug source-stack metadata reads over /mnt/c can exhaust these two-second guards.
        asyncio.get_running_loop().set_debug(False)

    async def setup_loop(self, *, auto_ack=True):
        self.cloud, self.browser = asyncio.Queue(), asyncio.Queue()
        self.ready, self.applied, self.finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        self.response_requested = asyncio.Event()
        self.sent, self.outputs = [], []
        self.session = VoiceSession(model_settings(), "bing", voice_options={"connection_mode": MODEL_MODE})

        async def create_item(*, item):
            data = item.as_dict()
            if data["type"] == "function_call_output":
                self.outputs.append(json.loads(data["output"]))
            elif data.get("id") == self.session.context_id:
                await self.cloud.put({"type": "conversation.item.created", "item": data})

        class Connection:
            session = SimpleNamespace(update=AsyncMock())
            conversation = SimpleNamespace(item=SimpleNamespace(create=create_item))
            response = SimpleNamespace(
                create=AsyncMock(side_effect=lambda **_: self.response_requested.set()), cancel=AsyncMock(),
            )
            input_audio_buffer = SimpleNamespace(append=AsyncMock())

            def __aiter__(inner):
                return inner

            async def __anext__(inner):
                return await self.cloud.get()

        self.connection = Connection()

        @asynccontextmanager
        async def connector(settings, agent, *, voice_options):
            self.assertIsNone(agent)
            self.assertEqual(voice_options["llm_model"], "gpt-4.1-mini")
            yield self.connection

        async def send(event):
            self.sent.append(event)
            if event.get("state") == "ready":
                self.ready.set()
            if event["type"] == "navigation" and event.get("action_id"):
                self.applied.set()
                if auto_ack:
                    await self.send_control({
                        "type": "navigation_ack", "action_id": event["action_id"],
                        "revision": event["state"]["revision"],
                    })
            if event["type"] == "tool":
                self.finished.set()

        self.session.connector = connector
        self.socket = SimpleNamespace(receive=self.browser.get, send_json=send)
        await self.cloud.put({"type": "session.updated"})
        self.task = asyncio.create_task(self.session.run(self.socket))
        self.addAsyncCleanup(self.stop_loop)
        await asyncio.wait_for(self.ready.wait(), 2)

    async def send_control(self, control):
        await self.browser.put({"type": "websocket.receive", "text": json.dumps(control)})

    async def stop_loop(self):
        if not self.task.done():
            await self.send_control({"type": "stop"})
        await asyncio.wait_for(self.task, 2)

    async def request_action(self, calls=None):
        await self.cloud.put({"type": "response.created", "response": {"id": "action_response"}})
        await self.cloud.put({
            "type": "response.done",
            "response": {"id": "action_response", "status": "completed", "output": calls or [function_call()]},
        })

    async def test_audio_and_transcript_do_not_execute_until_the_model_calls_a_tool(self):
        await self.setup_loop()
        pcm = b"\x01\x00" * 10
        await self.browser.put({"type": "websocket.receive", "bytes": pcm})
        await self.session.handle_event({
            "type": "conversation.item.input_audio_transcription.completed",
            "item_id": "heard_1", "transcript": "티맵 켜줘",
        }, self.connection, self.socket)
        self.assertFalse(self.session.navigation.state.app_open)
        user = next(event for event in self.sent if event["type"] == "transcript" and event["role"] == "user")
        self.assertEqual(user["input_mode"], "audio")
        await self.request_action()
        await asyncio.wait_for(self.finished.wait(), 2)
        await self.session.navigation_queue.join()
        self.connection.input_audio_buffer.append.assert_awaited_once_with(audio=base64.b64encode(pcm).decode("ascii"))
        self.assertTrue(self.outputs[0]["display_confirmed"])
        self.connection.response.create.assert_awaited_once()
        self.assertTrue(self.session.navigation.state.app_open)

    async def test_receiving_continues_during_ack_and_barge_in_stops_remaining_calls(self):
        await self.setup_loop(auto_ack=False)
        await self.request_action([
            function_call(), function_call("search_places", {"query": "회사"}, "call_two"),
        ])
        await asyncio.wait_for(self.applied.wait(), 2)
        await self.session.handle_event({"type": "input_audio_buffer.speech_started"}, self.connection, self.socket)
        await self.send_control({"type": "navigation_ack", "action_id": "call_one", "revision": 1})
        await asyncio.wait_for(self.session.navigation_queue.join(), 2)
        self.assertTrue(self.outputs[0]["ok"])
        self.assertEqual(self.outputs[1]["code"], "interrupted")
        self.assertEqual(self.session.navigation.state.results, [])
        self.connection.response.create.assert_not_called()

    async def test_stop_cleans_up_a_pending_app_action_without_claiming_completion(self):
        await self.setup_loop(auto_ack=False)
        await self.request_action()
        await asyncio.wait_for(self.applied.wait(), 2)
        await self.stop_loop()
        self.assertIsNone(self.session.navigation.pending_display)
        self.assertEqual(self.outputs, [])
        self.connection.response.create.assert_not_called()

    async def prepare_pending_continuation(self):
        await self.setup_loop()
        state = self.session.navigation.state
        state.execute("open_app", {"app": "navigation"})
        state.execute("search_places", {"query": "회사"})
        state.execute("preview_route", {"destination_id": "tech-valley"})
        await self.request_action([function_call("get_navigation_state", {}, "read_state")])
        await asyncio.wait_for(self.finished.wait(), 2)
        await self.session.navigation_queue.join()
        self.assertEqual(self.session.navigation_responses, set())
        self.assertIsNone(self.session.active_response)
        self.assertTrue(self.session.response_pending)
        return self.connection.response.create.call_args.kwargs["response"].as_dict()["metadata"]

    async def test_barge_in_before_continuation_created_blocks_late_navigation_and_output(self):
        metadata = await self.prepare_pending_continuation()
        await self.session.handle_event({"type": "input_audio_buffer.speech_started"}, self.connection, self.socket)
        await self.session.handle_event({
            "type": "response.created", "response": {"id": "delayed", "metadata": metadata},
        }, self.connection, self.socket)
        self.assertEqual(self.connection.response.cancel.call_args.kwargs["response_id"], "delayed")
        self.assertIn("delayed", self.session.interrupted)
        await self.session.handle_event({
            "type": "response.audio.delta", "response_id": "delayed", "delta": "AQACAA==",
        }, self.connection, self.socket)
        await self.session.handle_event({
            "type": "response.audio_transcript.done", "response_id": "delayed", "transcript": "stale speech",
        }, self.connection, self.socket)
        await self.session.handle_event({
            "type": "response.done", "response": {
                "id": "delayed", "status": "completed",
                "output": [function_call("start_navigation", {}, "late_start")],
            },
        }, self.connection, self.socket)
        await asyncio.wait_for(self.session.navigation_queue.join(), 2)
        self.assertEqual(self.session.navigation.state.phase, "route_preview")
        self.assertEqual(self.outputs[-1]["code"], "interrupted")
        self.assertFalse(any(event["type"] == "audio" for event in self.sent))
        self.assertFalse(any(event["type"] == "transcript" and event["role"] == "assistant" for event in self.sent))
        self.connection.response.create.assert_awaited_once()
        self.assertEqual(self.session.pending_responses, {})

    async def test_late_continuation_does_not_cancel_or_silence_a_newer_user_response(self):
        metadata = await self.prepare_pending_continuation()
        await self.session.handle_event({"type": "input_audio_buffer.speech_started"}, self.connection, self.socket)
        await self.session.handle_event({
            "type": "response.created", "response": {"id": "new_user_response"},
        }, self.connection, self.socket)
        generation = self.session.response_generation
        self.assertTrue(self.session.pending_responses)
        await self.session.handle_event({
            "type": "response.created", "response": {"id": "delayed", "metadata": metadata},
        }, self.connection, self.socket)
        self.assertEqual(self.session.active_response, "new_user_response")
        self.assertEqual(self.session.response_generation, generation)
        self.assertEqual(self.connection.response.cancel.call_args.kwargs["response_id"], "delayed")
        await self.session.handle_event({
            "type": "response.audio.delta", "response_id": "new_user_response", "delta": "AQACAA==",
        }, self.connection, self.socket)
        self.assertTrue(any(event["type"] == "audio" and event["response_id"] == "new_user_response" for event in self.sent))
        self.assertFalse(any(event["type"] == "interrupt" and event.get("response_id") == "delayed" for event in self.sent))
        cancellation_id = self.connection.response.cancel.call_args.kwargs["event_id"]
        with self.assertLogs("tmap_poc.voice", level="INFO"):
            await self.session.handle_event({
                "type": "error", "error": {"code": "response_cancel_not_active", "event_id": cancellation_id},
            }, self.connection, self.socket)
        with self.assertRaises(VoiceServiceError):
            await self.session.handle_event({
                "type": "error", "error": {"code": "response_cancel_not_active", "event_id": "not_our_request"},
            }, self.connection, self.socket)

    async def test_voice_can_interrupt_a_typed_request_before_its_response_id_exists(self):
        await self.setup_loop()
        await self.send_control({"type": "text", "text": "티맵 켜줘"})
        await asyncio.wait_for(self.response_requested.wait(), 2)
        metadata = self.connection.response.create.call_args.kwargs["response"].as_dict()["metadata"]
        user = next(event for event in self.sent if event["type"] == "transcript" and event["role"] == "user")
        self.assertEqual(user["input_mode"], "text")
        await self.session.handle_event({"type": "input_audio_buffer.speech_started"}, self.connection, self.socket)
        await self.session.handle_event({
            "type": "response.created", "response": {"id": "typed_late", "metadata": metadata},
        }, self.connection, self.socket)
        await self.session.handle_event({
            "type": "response.done", "response": {
                "id": "typed_late", "status": "completed", "output": [function_call()],
            },
        }, self.connection, self.socket)
        await asyncio.wait_for(self.session.navigation_queue.join(), 2)
        self.assertFalse(self.session.navigation.state.app_open)
        self.assertEqual(self.outputs[-1]["code"], "interrupted")


if __name__ == "__main__":
    unittest.main()
