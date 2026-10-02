"""Translate Voice Live function calls into app actions and confirmed UI results."""

import asyncio
import json
import re
from time import monotonic

from azure.ai.voicelive.models import FunctionCallOutputItem
from opentelemetry.trace import Status, StatusCode

from tmap_poc.navigation import DATA_SOURCE, NavigationError, NavigationState
from tmap_poc.telemetry import span


class NavigationVoice:
    def __init__(self, *, acknowledgement_timeout=5):
        self.state = NavigationState()
        self.acknowledgement_timeout = acknowledgement_timeout
        self.completed = {}
        self.pending_display = None

    def calls(self, response):
        output = response.get("output", [])
        if not isinstance(output, list) or any(not isinstance(item, dict) for item in output):
            raise NavigationError("invalid_tool_call", "모델이 올바른 앱 명령을 반환하지 않았습니다.")
        calls = [item for item in output if item.get("type") == "function_call"]
        if len(calls) > 8:
            raise NavigationError("too_many_calls", "한 번에 너무 많은 앱 동작이 요청되었습니다.")
        for call in calls:
            call_id = call.get("call_id")
            if not isinstance(call_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", call_id):
                raise NavigationError("invalid_tool_call", "앱 명령의 호출 ID가 올바르지 않습니다.")
        return [call for call in calls if call["call_id"] not in self.completed]

    def acknowledge(self, action_id, revision):
        if self.pending_display is not None:
            expected_id, expected_revision, ready = self.pending_display
            if (action_id, revision) == (expected_id, expected_revision):
                ready.set()
                return True
        return action_id in self.completed and self.completed[action_id] == revision

    async def publish(self, socket):
        await socket.send_json({"type": "navigation", "state": self.state.snapshot()})

    async def _execute(self, call, socket, cancelled):
        if cancelled():
            raise NavigationError("interrupted", "새 발화로 이전 앱 명령을 취소했습니다.")
        arguments = call.get("arguments")
        if not isinstance(arguments, str) or len(arguments) > 4000:
            raise NavigationError("invalid_arguments", "앱 명령의 인수가 올바르지 않습니다.")
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise NavigationError("invalid_arguments", "앱 명령에 올바른 JSON 인수가 필요합니다.") from exc
        result = self.state.execute(call.get("name"), arguments)
        ready = asyncio.Event()
        self.pending_display = (call["call_id"], self.state.revision, ready)
        try:
            await socket.send_json({
                "type": "navigation", "action_id": call["call_id"],
                "action": call["name"], "state": result["state"],
            })
            try:
                await asyncio.wait_for(ready.wait(), self.acknowledgement_timeout)
            except TimeoutError as exc:
                raise NavigationError(
                    "display_ack_timeout",
                    "화면 반영을 확인하지 못했습니다. 완료 여부가 불확실하므로 앱 상태를 확인해 주세요.",
                ) from exc
        finally:
            self.pending_display = None
        return {**result, "display_confirmed": True}

    async def dispatch(self, calls, connection, socket, *, cancelled=lambda: False):
        executed = False
        for call in calls:
            call_id = call["call_id"]
            if call_id in self.completed:
                continue
            if len(self.completed) >= 256:
                raise NavigationError("action_limit", "앱 명령이 256건에 도달했습니다. 새 대화를 시작해 주세요.")
            name = call.get("name")
            safe_name = name if isinstance(name, str) and re.fullmatch(r"[a-z_]{1,80}", name) else "unknown_tool"
            started = monotonic()
            await socket.send_json({"type": "activity", "state": "acting"})
            with span(
                f"execute_tool {safe_name}",
                **{
                    "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": safe_name,
                    "gen_ai.tool.call.id": call_id, "app.execution.location": "application",
                    "app.navigation.data_source": DATA_SOURCE,
                },
            ) as current:
                try:
                    result = await self._execute(call, socket, cancelled)
                except NavigationError as exc:
                    result = {
                        "ok": False, "code": exc.code, "message": str(exc),
                        "display_confirmed": False, "state": self.state.snapshot(),
                    }
                    current.set_status(Status(StatusCode.ERROR))
                    current.set_attribute("error.type", exc.code)
                current.set_attribute("app.action.display_confirmed", result["display_confirmed"])
                result["data_source"] = DATA_SOURCE
                self.completed[call_id] = self.state.revision
                await connection.conversation.item.create(item=FunctionCallOutputItem(
                    call_id=call_id, output=json.dumps(result, ensure_ascii=False, allow_nan=False),
                ))
                await socket.send_json({
                    "type": "tool", "kind": "navigation_action", "id": call_id,
                    "name": safe_name, "arguments": call.get("arguments"),
                    "status": "completed" if result["ok"] else "failed", "output": result,
                    "observed_elapsed_ms": round((monotonic() - started) * 1000, 2),
                    "timing_scope": "application_execution_and_display_ack",
                })
                executed = True
        return executed
