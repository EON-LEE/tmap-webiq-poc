from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Link, Status, StatusCode

from tmap_poc import telemetry
from tmap_poc.arms import WebIQMCP
from tmap_poc.config import ConfigError


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.exporter = InMemorySpanExporter()
        self.provider = TracerProvider()
        self.provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.tracer = self.provider.get_tracer("offline-tests")
        self.patch = patch("tmap_poc.telemetry.tracer", return_value=self.tracer)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.provider.shutdown()

    def test_remote_observation_is_event_not_invented_execution_span(self):
        with telemetry.span("request"):
            telemetry.observed_tool({
                "kind": "mcp_call", "id": "item-1", "name": "web", "status": "completed",
                "arguments": {"query": "private question"}, "output": "private result",
            })
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].events[0].name, "tool.call.observed")
        self.assertFalse(spans[0].events[0].attributes["app.remote_duration_known"])
        serialized = spans[0].to_json()
        self.assertNotIn("private question", serialized)
        self.assertNotIn("private result", serialized)

    def test_actual_client_execution_gets_child_span(self):
        with telemetry.span("request") as parent:
            with telemetry.tool_execution("webiq.web"):
                pass
        child, root = self.exporter.get_finished_spans()
        self.assertEqual(child.name, "execute_tool webiq.web")
        self.assertEqual(child.parent.span_id, parent.get_span_context().span_id)
        self.assertEqual(child.attributes["app.execution.location"], "client")
        self.assertGreaterEqual(child.end_time, child.start_time)
        self.assertEqual(root.name, "request")

    def test_http_tool_failure_is_not_a_successful_trace(self):
        client = WebIQMCP(api_key="offline-test-key")
        client._session.post = Mock(return_value=SimpleNamespace(
            status_code=401, text='{"message":"unauthorized"}',
        ))
        try:
            payload, _, error = client.call("web", {"query": "offline"})
        finally:
            client._session.close()
        self.assertIsNone(payload)
        self.assertEqual(error, "HTTP 401")
        recorded = self.exporter.get_finished_spans()[0]
        self.assertEqual(recorded.status.status_code.name, "ERROR")

    def test_exception_messages_are_not_exported_by_application_span(self):
        with self.assertRaises(ValueError):
            with telemetry.span("request"):
                raise ValueError("private diagnostic text")
        span = self.exporter.get_finished_spans()[0]
        self.assertEqual(span.attributes["error.type"], "ValueError")
        self.assertNotIn("private diagnostic text", span.to_json())

    def test_trace_context_contains_no_baggage_or_token(self):
        with telemetry.span("request"):
            headers = telemetry.trace_headers()
            self.assertEqual(len(telemetry.trace_id()), 32)
            self.assertEqual(set(headers), {"traceparent"})

    def test_voice_and_foundry_ids_remain_distinct(self):
        with telemetry.span("voice") as span:
            telemetry.foundry_response_link("foundry-response", parent=span)
        event = self.exporter.get_finished_spans()[0].events[0]
        self.assertEqual(event.attributes["app.foundry.response_id"], "foundry-response")
        self.assertNotIn("app.voice.response_id", event.attributes)

    def test_missing_azure_export_configuration_fails_explicitly(self):
        with patch.dict(os.environ, {"TMAP_TRACE_EXPORTER": "azure"}, clear=True):
            with self.assertRaises(ConfigError):
                telemetry.configure_tracing()

    def test_existing_exporter_cannot_bypass_metadata_guard(self):
        with patch.dict(os.environ, {"TMAP_TRACE_EXPORTER": "console"}, clear=True):
            with patch.object(telemetry.trace, "get_tracer_provider", return_value=self.provider):
                with self.assertRaisesRegex(ConfigError, "already configured"):
                    telemetry.configure_tracing()

    def test_actual_sdk_receive_path_is_redacted(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("sdk_trace_probe.py"))],
            check=True, text=True, capture_output=True,
        )
        observation = json.loads(result.stdout)
        self.assertTrue(observation["sdk_content_optout_enabled"])
        self.assertFalse(observation["private_content_exported"])
        self.assertGreaterEqual(observation["spans_preserved"], 2)

    def test_metadata_exporter_keeps_lifecycle_metadata_but_not_private_content(self):
        safe = InMemorySpanExporter()
        provider = TracerProvider(resource=Resource({
            "service.name": "navigation-voice-agent", "private.resource": "PRIVATE_RESOURCE",
        }))
        provider.add_span_processor(SimpleSpanProcessor(telemetry.MetadataExporter(safe)))
        attributes = {
            "gen_ai.tool.name": "finance", "app.tool.status": "failed",
            "app.execution.location": "service", "app.remote_duration_known": False,
            "app.observation.source": "voice_live_tool_events",
            "app.timing.scope": "client_observed_lifecycle", "app.tool.observed_elapsed_ms": 123.5,
            "app.tool.span_id": "0000000000000001", "error.type": "tool_failed",
            "gen_ai.tool.call.arguments": "PRIVATE_ARGUMENTS",
            "gen_ai.tool.call.result": "PRIVATE_RESULT",
            "gen_ai.input.messages": "PRIVATE_MESSAGES",
            "gen_ai.output.messages": "PRIVATE_OUTPUT",
            "exception.message": "PRIVATE_EXCEPTION",
            "exception.stacktrace": "PRIVATE_STACK",
        }
        with self.tracer.start_as_current_span("parent") as parent:
            with provider.get_tracer("privacy-test").start_as_current_span(
                "observe_tool finance", attributes=attributes,
                links=[Link(parent.get_span_context(), attributes)],
            ) as child:
                child.add_event("tool.call.observed", attributes)
                child.set_status(Status(StatusCode.ERROR, "PRIVATE_DESCRIPTION"))
        recorded = safe.get_finished_spans()[0]
        self.assertEqual(recorded.status.status_code, StatusCode.ERROR)
        self.assertEqual(recorded.attributes["app.tool.observed_elapsed_ms"], 123.5)
        self.assertEqual(recorded.events[0].attributes["app.timing.scope"], "client_observed_lifecycle")
        self.assertEqual(recorded.links[0].attributes["app.tool.status"], "failed")
        self.assertNotIn("PRIVATE", recorded.to_json())
        provider.shutdown()


class FoundryTracingTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"TMAP_TRACE_EXPORTER": "foundry"}, clear=True))
        for name, value in (("_provider", None), ("_mode", "none"), ("_closed", False)):
            self.stack.enter_context(patch.object(telemetry, name, value))
        self.stack.enter_context(patch.object(
            telemetry.trace, "get_tracer_provider", return_value=telemetry.trace.ProxyTracerProvider(),
        ))
        self.install = self.stack.enter_context(patch.object(telemetry.trace, "set_tracer_provider"))
        self.provider = self.stack.enter_context(patch("opentelemetry.sdk.trace.TracerProvider"))
        self.batch = self.stack.enter_context(patch("opentelemetry.sdk.trace.export.BatchSpanProcessor"))
        self.console = self.stack.enter_context(patch("opentelemetry.sdk.trace.export.ConsoleSpanExporter"))
        self.azure = Mock()
        self.stack.enter_context(patch.dict(sys.modules, {
            "azure.monitor.opentelemetry.exporter": SimpleNamespace(AzureMonitorTraceExporter=self.azure),
        }))
        self.app_settings = self.stack.enter_context(patch("tmap_poc.app_settings.AppSettings.from_env"))
        self.config = self.app_settings.return_value
        self.config.project_endpoint = "https://example.invalid/api/projects/current"
        self.credential = self.config.credential.return_value
        self.client = self.stack.enter_context(patch("azure.ai.projects.AIProjectClient"))
        self.project = self.client.return_value.__enter__.return_value
        self.lookup = self.project.telemetry.get_application_insights_connection_string
        self.lookup.return_value = "offline-project-connection"
        self.project_instrumentor = self.stack.enter_context(patch("azure.ai.projects.telemetry.AIProjectInstrumentor"))
        self.voice_instrumentor = self.stack.enter_context(patch("azure.ai.voicelive.telemetry.VoiceLiveInstrumentor"))
        self.stack.enter_context(patch("azure.core.settings.settings", SimpleNamespace()))

    def test_foundry_uses_only_current_project_and_metadata_guard_before_instrumenting(self):
        order = []
        self.lookup.side_effect = lambda: order.append("lookup") or "offline-project-connection"
        self.project_instrumentor.return_value.instrument.side_effect = lambda **_kwargs: order.append("instrument")
        os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = "different-explicit-azure-connection"
        telemetry.configure_tracing()
        self.app_settings.assert_called_once_with()
        self.config.credential.assert_called_once_with()
        self.client.assert_called_once_with(
            endpoint="https://example.invalid/api/projects/current", credential=self.credential,
        )
        self.lookup.assert_called_once_with()
        self.client.return_value.__exit__.assert_called_once()
        self.credential.close.assert_called_once_with()
        self.azure.from_connection_string.assert_called_once_with(
            "offline-project-connection", disable_offline_storage=True,
        )
        guarded = self.batch.call_args.args[0]
        self.assertIsInstance(guarded, telemetry.MetadataExporter)
        self.assertIs(guarded.delegate, self.azure.from_connection_string.return_value)
        self.assertEqual(order, ["lookup", "instrument"])
        self.assertEqual(os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"], "different-explicit-azure-connection")
        self.assertNotIn("offline-project-connection", os.environ.values())
        self.project_instrumentor.return_value.instrument.assert_called_once_with(
            enable_content_recording=False, enable_trace_context_propagation=True,
            enable_baggage_propagation=False,
        )
        self.voice_instrumentor.return_value.instrument.assert_called_once_with(enable_content_recording=False)
        self.console.assert_not_called()
        self.assertEqual(telemetry._mode, "foundry")

    def test_foundry_is_idempotent_and_rejects_exporter_changes(self):
        telemetry.configure_tracing()
        telemetry.configure_tracing()
        self.lookup.assert_called_once_with()
        self.install.assert_called_once()
        os.environ["TMAP_TRACE_EXPORTER"] = "azure"
        with self.assertRaisesRegex(ConfigError, "Restart"):
            telemetry.configure_tracing()
        self.azure.from_connection_string.assert_called_once()

    def test_missing_connection_is_explicit_and_never_falls_back(self):
        self.lookup.side_effect = ResourceNotFoundError("PRIVATE_SERVICE_DIAGNOSTIC")
        os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = "not-a-foundry-fallback"
        with self.assertRaisesRegex(ConfigError, "Agents > Traces > Connect") as error:
            telemetry.configure_tracing()
        self.assertNotIn("PRIVATE", str(error.exception))
        self.client.return_value.__exit__.assert_called_once()
        self.credential.close.assert_called_once_with()
        self.azure.from_connection_string.assert_not_called()
        self.console.assert_not_called()
        self.provider.assert_not_called()
        self.project_instrumentor.assert_not_called()
        self.voice_instrumentor.assert_not_called()
        self.assertIsNone(telemetry._provider)

    def test_empty_or_invalid_project_connections_fail_explicitly(self):
        for connection in (None, "", "   ", 42):
            with self.subTest(connection=connection):
                self.lookup.return_value = connection
                with self.assertRaisesRegex(ConfigError, "Agents > Traces > Connect"):
                    telemetry.configure_tracing()
        self.lookup.side_effect = ValueError("PRIVATE_MALFORMED_CREDENTIAL")
        with self.assertRaisesRegex(ConfigError, "Agents > Traces > Connect"):
            telemetry.configure_tracing()
        self.assertEqual(self.credential.close.call_count, 5)
        self.azure.from_connection_string.assert_not_called()
        self.install.assert_not_called()

    def test_project_access_failure_is_safe_and_closes_clients(self):
        self.lookup.side_effect = HttpResponseError("PRIVATE_DENIED")
        with self.assertRaisesRegex(ConfigError, "permissions") as error:
            telemetry.configure_tracing()
        self.assertNotIn("PRIVATE", str(error.exception))
        self.client.return_value.__exit__.assert_called_once()
        self.credential.close.assert_called_once_with()
        self.install.assert_not_called()

    def test_missing_project_endpoint_fails_before_acquiring_credentials(self):
        self.config.project_endpoint = ""
        with self.assertRaisesRegex(ConfigError, "GWB_PROJECT_ENDPOINT"):
            telemetry.configure_tracing()
        self.config.credential.assert_not_called()
        self.client.assert_not_called()

    def test_client_construction_failure_still_closes_credential(self):
        self.client.side_effect = ValueError("PRIVATE_INVALID_CLIENT")
        with self.assertRaises(ConfigError):
            telemetry.configure_tracing()
        self.credential.close.assert_called_once_with()
        self.install.assert_not_called()

    def test_cli_credential_without_close_is_supported(self):
        self.config.credential.return_value = SimpleNamespace(get_token=Mock())
        telemetry.configure_tracing()
        self.lookup.assert_called_once_with()

    def test_explicit_azure_mode_still_uses_only_environment_connection(self):
        os.environ.update(TMAP_TRACE_EXPORTER="azure", APPLICATIONINSIGHTS_CONNECTION_STRING="offline-explicit-connection")
        telemetry.configure_tracing()
        self.azure.from_connection_string.assert_called_once_with(
            "offline-explicit-connection", disable_offline_storage=True,
        )
        self.app_settings.assert_not_called()
        self.client.assert_not_called()

    def test_console_remains_default_and_none_does_no_lookup(self):
        os.environ["TMAP_TRACE_EXPORTER"] = "none"
        telemetry.configure_tracing()
        self.provider.assert_not_called()
        del os.environ["TMAP_TRACE_EXPORTER"]
        telemetry.configure_tracing()
        self.console.assert_called_once_with()
        self.app_settings.assert_not_called()
        self.client.assert_not_called()
        self.azure.from_connection_string.assert_not_called()

    def test_shutdown_is_idempotent_and_requires_restart(self):
        telemetry.configure_tracing()
        telemetry.shutdown_tracing()
        telemetry.shutdown_tracing()
        self.provider.return_value.force_flush.assert_called_once_with(timeout_millis=5000)
        self.provider.return_value.shutdown.assert_called_once_with()
        with self.assertRaisesRegex(ConfigError, "shut down"):
            telemetry.configure_tracing()
        self.lookup.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
