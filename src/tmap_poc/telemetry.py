"""Local-first tracing without fabricating service-side tool durations."""

from contextlib import contextmanager
import os
import sys

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.trace import Link
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from tmap_poc.config import ConfigError

_provider = None
_mode = "none"
_closed = False

_METADATA = {
    "gen_ai.operation.name", "gen_ai.provider.name", "gen_ai.system",
    "gen_ai.request.model", "gen_ai.response.model", "gen_ai.response.id",
    "gen_ai.agent.name", "gen_ai.agent.id", "gen_ai.agent.version",
    "gen_ai.conversation.id", "gen_ai.tool.name", "gen_ai.tool.type",
    "gen_ai.tool.call.id", "gen_ai.event.type", "gen_ai.event.direction",
    "app.transport", "app.execution.location", "app.observation.source", "app.voice.connection_mode",
    "app.remote_duration_known", "app.tool.kind", "app.tool.item_id",
    "app.timing.scope", "app.tool.observed_elapsed_ms", "app.tool.trace_id", "app.tool.span_id",
    "app.tool.status", "app.foundry.response_id", "app.voice.response_id",
    "app.correlation.source", "error.type", "http.request.method",
    "http.response.status_code", "http.status_code",
    "service.name", "service.version", "telemetry.sdk.name",
    "telemetry.sdk.language", "telemetry.sdk.version",
}


def _metadata(attributes):
    return {
        key: value for key, value in (attributes or {}).items()
        if key in _METADATA
        or (key.startswith("gen_ai.usage.") and isinstance(value, (int, float)))
    }


class MetadataExporter(SpanExporter):
    """Enforce privacy even when an SDK ignores its content-recording opt-out."""

    def __init__(self, delegate):
        self.delegate = delegate

    def export(self, spans):
        sanitized = [
            ReadableSpan(
                name=item.name, context=item.context, parent=item.parent,
                resource=Resource(_metadata(item.resource.attributes), item.resource.schema_url),
                attributes=_metadata(item.attributes),
                events=[Event(e.name, _metadata(e.attributes), e.timestamp) for e in item.events],
                links=[Link(link.context, _metadata(link.attributes)) for link in item.links],
                kind=item.kind, status=Status(item.status.status_code),
                start_time=item.start_time, end_time=item.end_time,
                instrumentation_scope=item.instrumentation_scope,
            )
            for item in spans
        ]
        return self.delegate.export(sanitized)

    def shutdown(self):
        self.delegate.shutdown()

    def force_flush(self, timeout_millis=30000):
        return self.delegate.force_flush(timeout_millis)


def _foundry_connection_string():
    from azure.ai.projects import AIProjectClient
    from azure.core.exceptions import AzureError, ResourceNotFoundError

    from tmap_poc.app_settings import AppSettings

    settings = AppSettings.from_env()
    if not settings.project_endpoint or "/projects/" not in settings.project_endpoint:
        raise ConfigError("Foundry tracing requires GWB_PROJECT_ENDPOINT to identify the current Foundry project.")
    missing = (
        "The current Foundry project has no usable Application Insights connection. "
        "In Foundry, open Agents > Traces > Connect and select an existing Application Insights resource."
    )
    credential = settings.credential()
    try:
        try:
            with AIProjectClient(endpoint=settings.project_endpoint, credential=credential) as project:
                connection = project.telemetry.get_application_insights_connection_string()
        except (ResourceNotFoundError, ValueError):
            raise ConfigError(missing) from None
        except AzureError:
            raise ConfigError(
                "Cannot read the current Foundry project's Application Insights connection. "
                "Check the configured identity's project connection permissions and retry."
            ) from None
    finally:
        close = getattr(credential, "close", None)
        if close is not None:
            close()
    if not isinstance(connection, str) or not connection.strip():
        raise ConfigError(missing)
    return connection.strip()


def configure_tracing():
    global _provider, _mode
    mode = os.environ.get("TMAP_TRACE_EXPORTER", "console").strip().lower()
    if mode not in ("none", "console", "azure", "foundry"):
        raise ConfigError("TMAP_TRACE_EXPORTER must be none, console, azure or foundry.")
    if _closed and mode != "none":
        raise ConfigError("Tracing has shut down; start a new process.")
    if _provider is not None:
        if mode != _mode:
            raise ConfigError("Restart the process to change tracing exporters.")
        return
    if mode == "none":
        return
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    if not isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider):
        raise ConfigError("OpenTelemetry is already configured. Use one tracing setup per process.")
    if mode in ("azure", "foundry"):
        if mode == "azure":
            connection = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
            if not connection:
                raise ConfigError("Azure tracing requires an existing APPLICATIONINSIGHTS_CONNECTION_STRING.")
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
        except ModuleNotFoundError as exc:
            raise ConfigError("Install the Azure exporter with: uv sync --extra azure-tracing") from exc
        if mode == "foundry":
            connection = _foundry_connection_string()
        exporter = AzureMonitorTraceExporter.from_connection_string(
            connection, disable_offline_storage=True,
        )
    else:
        exporter = ConsoleSpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "navigation-voice-agent"}))
    provider.add_span_processor(BatchSpanProcessor(MetadataExporter(exporter)))
    trace.set_tracer_provider(provider)
    _provider, _mode = provider, mode
    os.environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"] = "true"
    from azure.core.settings import settings
    from azure.ai.projects.telemetry import AIProjectInstrumentor
    from azure.ai.voicelive.telemetry import VoiceLiveInstrumentor

    settings.tracing_implementation = "opentelemetry"
    AIProjectInstrumentor().instrument(
        enable_content_recording=False,
        enable_trace_context_propagation=True,
        enable_baggage_propagation=False,
    )
    VoiceLiveInstrumentor().instrument(enable_content_recording=False)


def shutdown_tracing():
    global _closed
    if _provider is not None and not _closed:
        _provider.force_flush(timeout_millis=5000)
        _provider.shutdown()
        _closed = True


def tracer():
    return trace.get_tracer("tmap_poc")


@contextmanager
def span(name, **attributes):
    with tracer().start_as_current_span(
        name, attributes=attributes, record_exception=False, set_status_on_exception=False,
    ) as current:
        try:
            yield current
        finally:
            error = sys.exc_info()[1]
            if error is not None:
                current.set_attribute("error.type", type(error).__name__)
                current.set_status(Status(StatusCode.ERROR))


def trace_id():
    context = trace.get_current_span().get_span_context()
    return f"{context.trace_id:032x}" if context.is_valid else None


def trace_headers():
    headers = {}
    TraceContextTextMapPropagator().inject(headers)
    return headers


def observed_tool(call, *, parent=None):
    current = parent if parent is not None else trace.get_current_span()
    kind = call.get("kind") or call.get("type") or "unknown"
    attributes = {
        "app.tool.kind": kind,
        "app.observation.source": "response_output_item",
        "app.remote_duration_known": False,
    }
    for source, target in (
        ("name", "gen_ai.tool.name"), ("id", "app.tool.item_id"), ("status", "app.tool.status"),
        ("timing_scope", "app.timing.scope"),
        ("trace_id", "app.tool.trace_id"), ("span_id", "app.tool.span_id"),
    ):
        if isinstance(call.get(source), str):
            attributes[target] = call[source]
    if isinstance(call.get("observed_elapsed_ms"), (int, float)):
        attributes["app.tool.observed_elapsed_ms"] = call["observed_elapsed_ms"]
    current.add_event("tool.call.observed", attributes)


@contextmanager
def tool_execution(name):
    with span(
        f"execute_tool {name}",
        **{
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": name,
            "app.execution.location": "client",
        },
    ) as current:
        yield current


def foundry_response_link(agent_response_id, *, parent=None):
    if isinstance(agent_response_id, str) and agent_response_id:
        current = parent if parent is not None else trace.get_current_span()
        current.add_event(
            "foundry.response.correlated",
            {"app.foundry.response_id": agent_response_id, "app.correlation.source": "service_event"},
        )
