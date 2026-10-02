import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from azure.ai.voicelive.models import (
    ServerEvent, ServerEventResponseMcpCallArgumentsDone,
    ServerEventResponseMcpCallCompleted, ServerEventResponseMcpCallInProgress,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from starlette.websockets import WebSocketDisconnect

from tmap_poc import telemetry
from tmap_poc.profiles import AgentReference
from tmap_poc.tool_spans import ToolLifecycle
from tmap_poc.voice import VoiceSession
from tests.test_voice_app import settings


class ToolLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.exporter = InMemorySpanExporter()
        self.provider = TracerProvider()
        self.provider.add_span_processor(SimpleSpanProcessor(telemetry.MetadataExporter(self.exporter)))
        self.tracer = self.provider.get_tracer("lifecycle-tests")
        self.patch = patch("tmap_poc.telemetry.tracer", return_value=self.tracer)
        self.patch.start()
        self.root = self.tracer.start_span("navigation.voice.session")
        self.now = 100
        self.tools = ToolLifecycle(self.root, clock=lambda: self.now)

    def tearDown(self):
        self.tools.close()
        self.root.end()
        self.patch.stop()
        self.provider.shutdown()

    def observe(self, kind, **fields):
        return self.tools.observe({
            "type": kind, "item_id": "item-1", "output_index": 0, **fields,
        })

    def added(self, *, item_id="item-1", response_id="voice-1", name="finance"):
        self.observe("response.output_item.added", response_id=response_id, item={
            "type": "mcp_call", "id": item_id, "name": name,
            "arguments": '{"query":"PRIVATE_ARGUMENTS"}',
        })

    def final(self, **fields):
        return self.observe("response.output_item.done", response_id="voice-1", item={
            "type": "mcp_call", "id": "item-1", "output": "PRIVATE_OUTPUT", **fields,
        })

    def test_completed_child_uses_actual_lifecycle_and_explicit_session_parent(self):
        self.added()
        self.assertFalse(self.exporter.get_finished_spans())
        with self.tracer.start_as_current_span("unrelated"):
            self.observe("response.mcp_call.in_progress")
        self.now += 0.250
        self.observe("response.mcp_call.completed")
        result = self.final()
        child = self.exporter.get_finished_spans()[-1]
        self.assertEqual(child.name, "observe_tool finance")
        self.assertEqual(child.parent.span_id, self.root.get_span_context().span_id)
        self.assertEqual(child.context.trace_id, self.root.get_span_context().trace_id)
        self.assertEqual(child.attributes["app.execution.location"], "service")
        self.assertEqual(child.attributes["app.observation.source"], "voice_live_tool_events")
        self.assertEqual(child.attributes["app.timing.scope"], "client_observed_lifecycle")
        self.assertFalse(child.attributes["app.remote_duration_known"])
        self.assertEqual(child.attributes["app.voice.response_id"], "voice-1")
        self.assertNotIn("app.foundry.response_id", child.attributes)
        self.assertNotIn("gen_ai.tool.call.id", child.attributes)
        self.assertEqual(child.attributes["app.tool.item_id"], "item-1")
        self.assertEqual(child.attributes["app.tool.status"], "completed")
        self.assertEqual(result["name"], "finance")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["observed_elapsed_ms"], 250)
        self.assertEqual(result["timing_scope"], "client_observed_lifecycle")
        self.assertEqual(result["trace_id"], f"{child.context.trace_id:032x}")
        self.assertEqual(result["span_id"], f"{child.context.span_id:016x}")
        self.assertNotIn("PRIVATE", child.to_json())
        self.assertFalse(self.tools.calls)
        self.assertEqual(self.root.events[-1].name, "tool.call.observed")

    def test_failure_event_sets_safe_error_without_service_message(self):
        self.added()
        self.observe("response.mcp_call.in_progress")
        self.now += 1
        self.observe("response.mcp_call.failed", error={"message": "PRIVATE_FAILURE"})
        result = self.final(status="completed")
        child = self.exporter.get_finished_spans()[0]
        self.assertEqual(child.status.status_code.name, "ERROR")
        self.assertEqual(child.attributes["error.type"], "tool_failed")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["observed_elapsed_ms"], 1000)
        self.assertNotIn("PRIVATE", child.to_json())

    def test_only_final_item_is_an_observation_not_a_span(self):
        result = self.final(name="finance")
        self.assertFalse(self.exporter.get_finished_spans())
        self.assertIsNone(result["status"])
        self.assertNotIn("observed_elapsed_ms", result)
        self.assertNotIn("span_id", result)
        self.assertEqual(self.root.events[-1].attributes["gen_ai.tool.name"], "finance")
        self.assertFalse(self.tools.calls)

    def test_completed_without_start_enriches_status_but_no_duration(self):
        self.observe("response.mcp_call.completed")
        result = self.final(name="finance")
        self.assertEqual(result["status"], "completed")
        self.assertNotIn("observed_elapsed_ms", result)
        self.assertFalse(self.exporter.get_finished_spans())
        self.observe("response.mcp_call.in_progress")
        self.assertFalse(self.tools.calls)

    def test_final_before_start_is_not_reinterpreted_as_an_execution(self):
        self.final(name="finance")
        self.observe("response.mcp_call.in_progress")
        self.observe("response.mcp_call.completed")
        self.assertFalse(self.exporter.get_finished_spans())
        self.assertFalse(self.tools.calls)

    def test_output_done_does_not_end_open_span(self):
        self.added()
        self.observe("response.mcp_call.in_progress")
        first = self.final()
        self.assertNotIn("observed_elapsed_ms", first)
        self.assertNotIn("arguments", self.tools.calls["item-1"].item)
        self.assertFalse(self.exporter.get_finished_spans())
        self.now += 2
        update = self.observe("response.mcp_call.completed")
        self.assertEqual(update["id"], first["id"])
        self.assertEqual(update["status"], "completed")
        self.assertEqual(update["observed_elapsed_ms"], 2000)
        self.assertNotIn("output", update)
        self.assertFalse(self.tools.calls)

    def test_terminal_before_start_is_not_reopened(self):
        self.observe("response.mcp_call.failed")
        self.observe("response.mcp_call.in_progress")
        self.added()
        result = self.final()
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("observed_elapsed_ms", result)
        self.assertFalse(self.exporter.get_finished_spans())

    def test_name_arriving_after_start_updates_span_before_completion(self):
        self.observe("response.mcp_call.in_progress")
        self.observe(
            "response.mcp_call_arguments.done", name="finance", response_id="voice-1",
            arguments='{"query":"PRIVATE_QUERY"}', call_id="actual-call-id",
        )
        self.observe("response.mcp_call.completed")
        result = self.final()
        child = self.exporter.get_finished_spans()[0]
        self.assertEqual(child.name, "observe_tool finance")
        self.assertEqual(child.attributes["gen_ai.tool.call.id"], "actual-call-id")
        self.assertEqual(result["arguments"], {"query": "PRIVATE_QUERY"})
        self.assertNotIn("PRIVATE_QUERY", child.to_json())

    def test_name_only_on_final_after_terminal_does_not_invent_or_extend_span(self):
        self.observe("response.mcp_call.in_progress")
        self.observe("response.mcp_call.completed")
        child = self.exporter.get_finished_spans()[0]
        ended = child.end_time
        result = self.final(name="finance")
        self.assertEqual(child.name, "observe_tool mcp")
        self.assertEqual(child.end_time, ended)
        self.assertEqual(result["name"], "finance")
        observation = self.root.events[-1]
        self.assertEqual(observation.attributes["gen_ai.tool.name"], "finance")
        self.assertEqual(observation.attributes["app.tool.span_id"], result["span_id"])

    def test_ids_are_required_and_conflicting_responses_do_not_merge(self):
        self.observe("response.mcp_call.in_progress", item_id=None, response_id="voice-1")
        self.assertFalse(self.tools.calls)
        self.added()
        self.observe("response.mcp_call.in_progress", response_id="voice-2")
        self.assertIsNone(self.tools.calls["item-1"].started)
        self.observe("response.mcp_call.in_progress")
        self.observe("response.mcp_call.failed", item_id="other")
        self.assertFalse(self.exporter.get_finished_spans())
        self.observe("response.mcp_call.completed")
        self.assertEqual(self.final()["status"], "completed")
        self.assertEqual(self.exporter.get_finished_spans()[0].attributes["app.voice.response_id"], "voice-1")

    def test_duplicate_service_events_do_not_create_or_extend_spans(self):
        self.added()
        self.observe("response.mcp_call.in_progress")
        self.now += 1
        self.observe("response.mcp_call.in_progress")
        self.observe("response.mcp_call.completed")
        self.observe("response.mcp_call.completed")
        result = self.final()
        self.observe("response.mcp_call.in_progress")
        self.observe("response.mcp_call.failed")
        self.assertIsNone(self.final())
        self.assertEqual(result["observed_elapsed_ms"], 1000)
        self.assertEqual(len(self.exporter.get_finished_spans()), 1)

    def test_no_parent_does_not_create_a_detached_or_ambient_span(self):
        tools = ToolLifecycle()
        with self.tracer.start_as_current_span("not-the-session"):
            tools.observe({"type": "response.mcp_call.in_progress", "item_id": "i"})
            tools.observe({"type": "response.mcp_call.completed", "item_id": "i"})
        self.assertEqual(len(self.exporter.get_finished_spans()), 1)
        tools.close()

    def test_concurrent_sessions_with_same_service_ids_remain_separate(self):
        other_parent = self.tracer.start_span("other-session")
        other = ToolLifecycle(other_parent)
        self.added()
        self.observe("response.mcp_call.in_progress")
        other.observe({"type": "response.mcp_call.in_progress", "item_id": "item-1", "name": "web"})
        other.observe({"type": "response.mcp_call.failed", "item_id": "item-1"})
        self.observe("response.mcp_call.completed")
        first, second = self.exporter.get_finished_spans()
        self.assertEqual(first.parent.span_id, other_parent.get_span_context().span_id)
        self.assertEqual(second.parent.span_id, self.root.get_span_context().span_id)
        self.assertNotEqual(first.context.trace_id, second.context.trace_id)
        other.close()
        other_parent.end()

    def test_cancelled_or_incomplete_lifecycle_has_no_completed_duration(self):
        for status, error in (("cancelled", "session_stopped"), ("incomplete", "session_timeout")):
            with self.subTest(status=status):
                tools = ToolLifecycle(self.root)
                tools.observe({"type": "response.mcp_call.in_progress", "item_id": "i"})
                tools.close(status, error)
                child = self.exporter.get_finished_spans()[-1]
                self.assertEqual(child.attributes["app.tool.status"], status)
                self.assertEqual(child.attributes["error.type"], error)
                self.assertEqual(child.status.status_code.name, "ERROR")
                self.assertNotIn("app.tool.observed_elapsed_ms", child.attributes)
                self.assertFalse(tools.calls)
                self.assertFalse(tools.retired)

    def test_idle_expiration_and_capacity_bound_cache(self):
        self.observe("response.mcp_call.in_progress")
        self.now += 900
        self.tools.expire()
        expired = self.exporter.get_finished_spans()[0]
        self.assertEqual(expired.attributes["app.tool.status"], "incomplete")
        self.assertEqual(expired.attributes["error.type"], "lifecycle_expired")
        self.assertFalse(self.tools.calls)
        self.tools.MAX_CALLS = 2
        for index in range(6):
            self.observe("response.mcp_call.in_progress", item_id=f"i-{index}")
        self.assertEqual(len(self.tools.calls), 2)
        self.assertLessEqual(len(self.tools.retired), 2)
        self.assertEqual(self.exporter.get_finished_spans()[-1].attributes["error.type"], "lifecycle_capacity")

    def test_final_item_can_supply_name_while_real_lifecycle_is_still_open(self):
        self.observe("response.mcp_call.in_progress")
        self.final(name="finance")
        self.observe("response.mcp_call.completed")
        self.assertEqual(self.exporter.get_finished_spans()[0].name, "observe_tool finance")

    def test_installed_sdk_fields_and_unknown_fields_are_preserved(self):
        start = ServerEventResponseMcpCallInProgress(item_id="item-1", output_index=0)
        self.assertNotIn("response_id", start.as_dict())
        self.tools.observe(start.as_dict())
        args = ServerEventResponseMcpCallArgumentsDone({
            "type": "response.mcp_call_arguments.done", "item_id": "item-1",
            "response_id": "voice-1", "output_index": 0, "name": "finance",
            "arguments": '{"query":"PRIVATE_QUERY"}',
        })
        self.tools.observe(args.as_dict())
        self.tools.observe(ServerEventResponseMcpCallCompleted(item_id="item-1", output_index=0).as_dict())
        self.assertEqual(self.final()["name"], "finance")
        generic = ServerEvent({"type": "response.foundry_agent_call.completed", "agent_response_id": "foundry-1"})
        self.assertEqual(generic.as_dict()["agent_response_id"], "foundry-1")


class VoiceToolLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_exports_selected_agent_without_inventing_unpinned_version(self):
        for version in ("2", None):
            with self.subTest(version=version):
                exporter = InMemorySpanExporter()
                provider = TracerProvider()
                provider.add_span_processor(SimpleSpanProcessor(telemetry.MetadataExporter(exporter)))
                session = VoiceSession(settings(), "webiq")
                session.agent = AgentReference("actual-selected-agent", version)
                socket = SimpleNamespace(send_json=AsyncMock())
                with patch("tmap_poc.telemetry.tracer", return_value=provider.get_tracer("agent-tests")):
                    with patch.object(session, "_run", new=AsyncMock(return_value="service_closed")):
                        await session.run(socket)
                parent = exporter.get_finished_spans()[0]
                self.assertEqual(parent.attributes["gen_ai.agent.name"], "actual-selected-agent")
                if version:
                    self.assertEqual(parent.attributes["gen_ai.agent.version"], version)
                else:
                    self.assertNotIn("gen_ai.agent.version", parent.attributes)
                self.assertNotIn("gen_ai.agent.id", parent.attributes)
                provider.shutdown()

    async def test_response_done_is_not_a_substitute_for_a_tool_terminal(self):
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        session = VoiceSession(settings(), "webiq")
        socket = SimpleNamespace(send_json=AsyncMock())
        with patch("tmap_poc.telemetry.tracer", return_value=provider.get_tracer("voice-tests")):
            with telemetry.span("navigation.voice.session") as parent:
                session.trace_span = parent
                session.tools.parent = parent
                for event in (
                    {"type": "response.output_item.added", "response_id": "voice-1", "item": {
                        "type": "mcp_call", "id": "i", "name": "finance",
                    }},
                    {"type": "response.mcp_call.in_progress", "item_id": "i"},
                    {"type": "response.done", "response": {"id": "voice-1", "status": "completed"}},
                ):
                    await session.handle_event(event, None, socket)
                self.assertFalse(exporter.get_finished_spans())
                await session.handle_event({
                    "type": "response.mcp_call.completed", "item_id": "i",
                }, None, socket)
        child, _parent = exporter.get_finished_spans()
        self.assertEqual(child.attributes["app.tool.status"], "completed")
        self.assertIn("app.tool.observed_elapsed_ms", child.attributes)
        session.tools.close()
        provider.shutdown()

    async def test_active_voice_response_is_not_used_as_an_unreported_tool_id(self):
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        session = VoiceSession(settings(), "webiq")
        socket = SimpleNamespace(send_json=AsyncMock())
        with patch("tmap_poc.telemetry.tracer", return_value=provider.get_tracer("voice-tests")):
            with telemetry.span("navigation.voice.session") as parent:
                session.trace_span = parent
                session.tools.parent = parent
                for event in (
                    {"type": "response.created", "response": {"id": "ambient-response"}},
                    {"type": "response.mcp_call.in_progress", "item_id": "i"},
                    {"type": "response.mcp_call.completed", "item_id": "i"},
                    {"type": "response.output_item.done", "item": {
                        "type": "mcp_call", "id": "i", "name": "finance",
                    }},
                ):
                    await session.handle_event(event, None, socket)
        child, _parent = exporter.get_finished_spans()
        self.assertNotIn("app.voice.response_id", child.attributes)
        self.assertNotIn("app.foundry.response_id", child.attributes)
        self.assertNotIn("gen_ai.response.id", child.attributes)
        provider.shutdown()

    async def test_all_session_exit_paths_close_open_tools_before_parent(self):
        for mode in ("stop", "disconnect", "timeout", "closed", "cancel"):
            with self.subTest(mode=mode):
                exporter = InMemorySpanExporter()
                provider = TracerProvider()
                provider.add_span_processor(SimpleSpanProcessor(exporter))
                session = VoiceSession(settings(), "webiq")
                socket = SimpleNamespace(send_json=AsyncMock())

                async def run(_socket):
                    await session.handle_event({
                        "type": "response.mcp_call.in_progress", "item_id": "i", "name": "finance",
                    }, None, socket)
                    if mode == "stop":
                        session.stop_requested = True
                        return "stopped"
                    if mode == "disconnect":
                        raise WebSocketDisconnect()
                    if mode == "timeout":
                        raise TimeoutError()
                    if mode == "cancel":
                        raise asyncio.CancelledError()
                    return "service_closed"

                with patch("tmap_poc.telemetry.tracer", return_value=provider.get_tracer("voice-tests")):
                    with patch.object(session, "_run", side_effect=run):
                        if mode in ("stop", "closed"):
                            await session.run(socket)
                        else:
                            expected = {"disconnect": WebSocketDisconnect, "timeout": TimeoutError, "cancel": asyncio.CancelledError}[mode]
                            with self.assertRaises(expected):
                                await session.run(socket)
                child, parent = exporter.get_finished_spans()
                self.assertEqual(child.parent.span_id, parent.context.span_id)
                self.assertLessEqual(child.end_time, parent.end_time)
                self.assertEqual(child.status.status_code.name, "ERROR")
                self.assertEqual(child.attributes["app.tool.status"], "incomplete" if mode in ("closed", "timeout") else "cancelled")
                self.assertFalse(session.tools.calls)
                provider.shutdown()

    async def test_forwarded_tool_keeps_lifecycle_status_and_distinct_foundry_id(self):
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        events = [
            {"type": "response.created", "response": {"id": "unrelated-active-response"}},
            {"type": "response.mcp_call.in_progress", "item_id": "i"},
            {"type": "response.output_item.added", "response_id": "voice-1", "item": {
                "type": "mcp_call", "id": "i", "name": "finance",
            }},
            {"type": "response.mcp_call.completed", "item_id": "i"},
            {"type": "response.output_item.done", "response_id": "voice-1", "item": {
                "type": "mcp_call", "id": "i", "name": "finance", "output": "PRIVATE_OUTPUT",
            }},
            {"type": "response.foundry_agent_call.completed", "agent_response_id": "foundry-1"},
        ]

        class Connection:
            session = SimpleNamespace(update=AsyncMock())

            def __aiter__(self):
                async def stream():
                    for event in events:
                        yield ServerEvent(event)
                return stream()

        @asynccontextmanager
        async def connector(*_args):
            yield Connection()

        session = VoiceSession(settings(), "webiq", connector=connector)
        socket = SimpleNamespace(send_json=AsyncMock(), receive=asyncio.Queue().get)
        with patch("tmap_poc.telemetry.tracer", return_value=provider.get_tracer("voice-tests")):
            self.assertEqual(await session.run(socket), "service_closed")
        tool = [entry.args[0] for entry in socket.send_json.call_args_list if entry.args[0]["type"] == "tool"][0]
        self.assertEqual(tool["status"], "completed")
        self.assertIn("observed_elapsed_ms", tool)
        child, parent = exporter.get_finished_spans()
        self.assertEqual(child.attributes["app.voice.response_id"], "voice-1")
        self.assertNotIn("app.foundry.response_id", child.attributes)
        correlated = [event for event in parent.events if event.name == "foundry.response.correlated"][0]
        self.assertEqual(correlated.attributes["app.foundry.response_id"], "foundry-1")
        self.assertNotIn("PRIVATE_OUTPUT", parent.to_json())
        provider.shutdown()


if __name__ == "__main__":
    unittest.main()
