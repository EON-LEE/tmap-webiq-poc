"""Client-observed MCP lifecycles, never inferred remote execution intervals."""

from collections import OrderedDict
from dataclasses import dataclass, field
from time import monotonic

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import Status, StatusCode

from tmap_poc import telemetry
from tmap_poc.runtime import public_call


@dataclass
class _Call:
    updated: float
    item: dict = field(default_factory=lambda: {"type": "mcp_call"})
    metadata: dict = field(default_factory=dict)
    span: object = None
    started: float | None = None
    terminal: bool = False
    final: bool = False
    response_id: str | None = None


class ToolLifecycle:
    MAX_AGE = 900
    MAX_CALLS = 256

    def __init__(self, parent=None, *, clock=monotonic):
        self.parent = parent
        self.clock = clock
        self.calls = OrderedDict()
        self.retired = OrderedDict()

    def _finish(self, call, status, *, error=None, measured=False):
        call.terminal = True
        call.metadata["status"] = status
        if measured and call.started is not None:
            call.metadata.update(
                observed_elapsed_ms=max(0, (self.clock() - call.started) * 1000),
                timing_scope="client_observed_lifecycle",
            )
        if call.span is not None:
            call.span.set_attribute("app.tool.status", status)
            if measured and call.started is not None:
                call.span.set_attribute("app.tool.observed_elapsed_ms", call.metadata["observed_elapsed_ms"])
            if error:
                call.span.set_attribute("error.type", error)
                call.span.set_status(Status(StatusCode.ERROR))
            call.span.end()
            call.span = None

    def _retire(self, item_id, now):
        self.calls.pop(item_id, None)
        self.retired[item_id] = now
        while len(self.retired) > self.MAX_CALLS:
            self.retired.popitem(last=False)

    def expire(self):
        now = self.clock()
        for item_id, at in list(self.retired.items()):
            if now - at >= self.MAX_AGE:
                del self.retired[item_id]
        for item_id, call in list(self.calls.items()):
            if now - call.updated >= self.MAX_AGE:
                if not call.terminal:
                    self._finish(call, "incomplete", error="lifecycle_expired")
                self._retire(item_id, now)

    def close(self, status="incomplete", error="session_closed", *, response_id=None):
        for item_id, call in list(self.calls.items()):
            if response_id is None or call.response_id == response_id:
                if not call.terminal:
                    self._finish(call, status, error=error)
                self._retire(item_id, self.clock())
        if response_id is None:
            self.retired.clear()

    def summary(self, item_id):
        """Return only already-observed call metadata, without changing its lifecycle."""
        call = self.calls.get(item_id)
        if call is None:
            return None
        return {
            **public_call(call.item), **call.metadata,
            "response_id": call.response_id,
        }

    def observe(self, event):
        self.expire()
        kind = event.get("type", "")
        item = event.get("item")
        item = item if isinstance(item, dict) else {}
        is_output = kind in ("response.output_item.added", "response.output_item.done")
        if is_output and item.get("type") != "mcp_call":
            if kind == "response.output_item.done" and "call" in item.get("type", ""):
                call = public_call(item)
                if self.parent is not None:
                    telemetry.observed_tool(call, parent=self.parent)
                return call
            return None
        if not is_output and kind not in (
            "response.mcp_call.in_progress", "response.mcp_call.completed",
            "response.mcp_call.failed", "response.mcp_call_arguments.done",
        ):
            return None
        item_id = item.get("id") if is_output else event.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            if kind == "response.output_item.done":
                call = public_call(item)
                if self.parent is not None:
                    telemetry.observed_tool(call, parent=self.parent)
                return call
            return None
        if item_id in self.retired:
            return None
        now = self.clock()
        if item_id not in self.calls:
            if len(self.calls) >= self.MAX_CALLS:
                oldest, previous = next(iter(self.calls.items()))
                if not previous.terminal:
                    self._finish(previous, "incomplete", error="lifecycle_capacity")
                self._retire(oldest, now)
            self.calls[item_id] = _Call(now)
        call = self.calls[item_id]
        response_id = event.get("response_id")
        if isinstance(response_id, str) and response_id:
            if call.response_id is not None and call.response_id != response_id:
                return None
            call.response_id = response_id
        call.updated = now
        self.calls.move_to_end(item_id)
        call.item["id"] = item_id
        payload = item if is_output else event
        for key in ("name", "arguments", "call_id"):
            value = payload.get(key)
            if isinstance(value, str) and value and len(value) <= 65536:
                call.item[key] = value
        attributes = {
            "gen_ai.operation.name": "observe_tool",
            "gen_ai.tool.type": "mcp",
            "app.tool.kind": "mcp_call",
            "app.tool.item_id": item_id,
            "app.execution.location": "service",
            "app.observation.source": "voice_live_tool_events",
            "app.remote_duration_known": False,
            "app.timing.scope": "client_observed_lifecycle",
        }
        for source, target in (("name", "gen_ai.tool.name"), ("call_id", "gen_ai.tool.call.id")):
            if call.item.get(source):
                attributes[target] = call.item[source]
        if call.response_id:
            attributes["app.voice.response_id"] = call.response_id
        name = f"observe_tool {call.item.get('name') or 'mcp'}"
        if kind == "response.mcp_call.in_progress" and call.started is None and not call.terminal and not call.final:
            call.started = now
            if self.parent is not None and self.parent.get_span_context().is_valid:
                call.span = telemetry.tracer().start_span(
                    name, context=trace.set_span_in_context(self.parent, Context()),
                    attributes={**attributes, "app.tool.status": "in_progress"},
                )
                context = call.span.get_span_context()
                if context.is_valid:
                    call.metadata.update(trace_id=f"{context.trace_id:032x}", span_id=f"{context.span_id:016x}")
        if call.span is not None:
            call.span.update_name(name)
            call.span.set_attributes(attributes)
        if kind in ("response.mcp_call.completed", "response.mcp_call.failed") and not call.terminal:
            failed = kind.endswith(".failed")
            self._finish(call, "failed" if failed else "completed", error="tool_failed" if failed else None, measured=True)
            if call.final:
                self._retire(item_id, now)
                return {"id": item_id, "kind": "mcp_call", **call.metadata}
        if kind == "response.output_item.done":
            call.final = True
            result = public_call({**call.item, **{key: value for key, value in item.items() if value is not None}})
            if not result["name"]:
                result["name"] = call.item.get("name")
            result.update(call.metadata)
            call.item.pop("arguments", None)
            if self.parent is not None:
                telemetry.observed_tool(result, parent=self.parent)
            # A final item is not a lifecycle terminal event; leave any open span open.
            if call.terminal or call.started is None:
                self._retire(item_id, now)
            return result
        return None
