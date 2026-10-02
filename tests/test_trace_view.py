import asyncio
from datetime import datetime, timezone
import json
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

from tmap_poc.api import create_app
from tmap_poc.app_settings import AppSettings
from tmap_poc.profiles import AgentReference
from tmap_poc.trace_view import (
    FoundryTraceReader, MAX_SPANS, TraceAccess, TraceReadError, normalize_trace, trace_query,
)

TRACE_A = "a" * 32
TRACE_B = "b" * 32
COLUMNS = [
    "id", "parent_id", "name", "start_time", "duration_ms", "success", "role",
    "operation", "provider", "agent_name", "model", "tool_name", "input_tokens",
    "output_tokens", "tool_status", "timing_scope", "secret_content",
]


def payload(rows=None):
    return {"tables": [{
        "name": "PrimaryResult", "columns": [{"name": n} for n in COLUMNS],
        "rows": rows if rows is not None else [
            ["agent", "missing-parent", "invoke_agent example", "2026-09-08T00:00:00.0012345Z",
             3000, "True", "responsesapi", "invoke_agent", "microsoft.foundry", "example",
             "model", "", 100, 50, "", "", "private prompt"],
            ["tool", "agent", "execute_tool web", "2026-09-08T00:00:01Z",
             500.5, "True", "responsesapi", "execute_tool", "microsoft.foundry", "example",
             "", "web", None, None, "", "", "private tool output"],
            ["observer", None, "observe_tool web", "2026-09-08T00:00:01Z",
             800, "True", "navigation-voice-agent", "observe_tool", "", "", "", "web",
             None, None, "completed", "client_observed_lifecycle", "private data"],
        ],
    }]}


def app_settings():
    return AppSettings(
        project_endpoint="https://example.invalid/api/projects/test",
        voice_endpoint="https://voice.invalid",
        subscription="explicit-test",
        agents={"bing": AgentReference("b", "1"), "webiq": AgentReference("w", "1")},
    )


class AccessTests(unittest.TestCase):
    def test_only_issued_trace_and_matching_capability_can_be_read(self):
        access = TraceAccess()
        first, second = access.issue(TRACE_A), access.issue(TRACE_B)
        self.assertIsNotNone(access.authorize(TRACE_A, first["trace_access_token"]))
        self.assertIsNone(access.authorize(TRACE_B, first["trace_access_token"]))
        self.assertIsNone(access.authorize(TRACE_A, ""))
        self.assertIsNone(access.authorize("c" * 32, second["trace_access_token"]))
        self.assertNotIn(first["trace_access_token"], repr(access.entries))

    def test_access_expires_and_registry_is_bounded(self):
        now = [1000]
        access = TraceAccess(clock=lambda: now[0])
        grant = access.issue(TRACE_A)
        now[0] += access.TTL
        self.assertIsNone(access.authorize(TRACE_A, grant["trace_access_token"]))
        for value in range(access.LIMIT + 10):
            access.issue(f"{value:032x}")
        self.assertEqual(len(access.entries), access.LIMIT)

    def test_invalid_id_never_enters_query_or_registry(self):
        access = TraceAccess()
        for bad in ("", "a" * 31, "A" * 32, "a';union *", "../traces"):
            with self.subTest(bad=bad):
                self.assertEqual(access.issue(bad), {})
                with self.assertRaises(ValueError):
                    trace_query(bad)


class NormalizationTests(unittest.TestCase):
    def test_native_parentage_timing_and_client_observation_remain_distinct(self):
        result = normalize_trace(TRACE_A, payload())
        self.assertEqual(result["status"], "ready")
        agent, tool, observer = result["spans"]
        self.assertEqual(tool["parent_id"], agent["id"])
        self.assertEqual(agent["parent_id"], "missing-parent")
        self.assertEqual(tool["duration_ms"], 500.5)
        self.assertEqual(tool["origin"], "foundry")
        self.assertEqual(observer["origin"], "client")
        self.assertEqual(observer["kind"], "observation")
        self.assertEqual(observer["attributes"]["timing_scope"], "client_observed_lifecycle")
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("private", json.dumps(result))

    def test_missing_duration_and_cancelled_status_are_not_success(self):
        table = payload()
        row = table["tables"][0]["rows"][0]
        row[COLUMNS.index("duration_ms")] = None
        row[COLUMNS.index("tool_status")] = "cancelled"
        result = normalize_trace(TRACE_A, table)["spans"][0]
        self.assertIsNone(result["duration_ms"])
        self.assertEqual(result["status"], "unknown")

    def test_no_rows_is_ingestion_pending_not_failure(self):
        result = normalize_trace(TRACE_A, payload([]))
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["spans"], [])
        self.assertFalse(result["truncated"])

    def test_nonfinite_and_negative_metrics_are_not_rendered_as_measured(self):
        for bad in (float("nan"), float("inf"), -1, True):
            table = payload()
            row = table["tables"][0]["rows"][0]
            row[COLUMNS.index("duration_ms")] = bad
            row[COLUMNS.index("input_tokens")] = bad
            result = normalize_trace(TRACE_A, table)["spans"][0]
            self.assertIsNone(result["duration_ms"])
            self.assertNotIn("input_tokens", result["attributes"])

    def test_truncation_is_explicit(self):
        row = payload()["tables"][0]["rows"][0]
        rows = [[str(i), *row[1:]] for i in range(MAX_SPANS + 1)]
        result = normalize_trace(TRACE_A, payload(rows))
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["spans"]), MAX_SPANS)

    def test_invalid_and_partial_responses_surface_errors(self):
        for data in (None, [], {}, {"error": {"code": "PartialError"}, "tables": []}, {"tables": [None]}, payload([["wrong"]])):
            with self.subTest(data=data):
                with self.assertRaises(TraceReadError):
                    normalize_trace(TRACE_A, data)

    def test_unlabelled_sdk_receive_spans_are_classified_as_voice_io(self):
        table = payload()
        row = table["tables"][0]["rows"][0]
        row[COLUMNS.index("name")] = "recv"
        row[COLUMNS.index("operation")] = "recv"
        self.assertEqual(normalize_trace(TRACE_A, table)["spans"][0]["kind"], "voice_io")


class TraceApiTests(unittest.TestCase):
    def setUp(self):
        self.reader = SimpleNamespace(
            read=AsyncMock(return_value=normalize_trace(TRACE_A, payload())),
            close=AsyncMock(),
        )

        class FakeVoice:
            def __init__(self, settings, provider, context):
                self.id = TRACE_A if provider == "bing" else TRACE_B

            async def run(self, socket):
                await socket.send_json({"type": "trace", "trace_id": self.id, "session_id": "session"})
                return "stopped"

        self.client = TestClient(create_app(
            app_settings(), voice_factory=FakeVoice, trace_reader=self.reader,
        ))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.reader.close.assert_awaited_once()

    def issue(self, provider="bing"):
        with self.client.websocket_connect("/ws/voice", headers={"origin": "http://localhost:8000"}) as ws:
            ws.send_json({"type": "start", "provider": provider})
            self.assertEqual(ws.receive_json()["state"], "connecting")
            grant = ws.receive_json()
            self.assertEqual(ws.receive_json()["type"], "done")
        return grant

    def test_same_browser_can_read_after_voice_stops_and_repeat_reads_are_cached(self):
        grant = self.issue()
        headers = {"X-Trace-Access": grant["trace_access_token"]}
        for _ in range(2):
            response = self.client.get(f"/api/traces/{TRACE_A}", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertNotIn(grant["trace_access_token"], response.text)
        self.reader.read.assert_awaited_once_with(TRACE_A)

    def test_unknown_wrong_and_cross_trace_tokens_cannot_trigger_a_query(self):
        first, second = self.issue(), self.issue("webiq")
        for trace_id, token in (
            (TRACE_A, ""), (TRACE_A, "wrong"), (TRACE_B, first["trace_access_token"]),
            ("c" * 32, second["trace_access_token"]),
        ):
            response = self.client.get(f"/api/traces/{trace_id}", headers={"X-Trace-Access": token})
            self.assertEqual(response.status_code, 404)
        self.reader.read.assert_not_called()

    def test_permission_errors_stay_errors_and_do_not_get_cached(self):
        grant = self.issue()
        self.reader.read.side_effect = TraceReadError("trace_permission", "permission required", 403)
        for _ in range(2):
            response = self.client.get(
                f"/api/traces/{TRACE_A}", headers={"X-Trace-Access": grant["trace_access_token"]},
            )
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["error"]["code"], "trace_permission")
        self.assertEqual(self.reader.read.await_count, 2)

    def test_trace_access_capability_is_not_in_public_configuration(self):
        grant = self.issue()
        response = self.client.get("/api/config")
        self.assertTrue(response.json()["tracing"]["embedded_enabled"])
        self.assertNotIn(grant["trace_access_token"], response.text)


class ReaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_waiting_for_query_slots_is_inside_the_deadline(self):
        reader = FoundryTraceReader(app_settings())
        await reader._query_slots.acquire()
        await reader._query_slots.acquire()
        try:
            with patch("tmap_poc.trace_view.READ_TIMEOUT", 0.02):
                with self.assertRaises(TraceReadError):
                    await asyncio.wait_for(reader.read(TRACE_A), 0.5)
            self.assertIsNone(reader._initialization)
        finally:
            reader._query_slots.release()
            reader._query_slots.release()
            await reader.close()

    async def test_cancelled_waiters_share_one_worker_and_close_drains_it(self):
        reader = FoundryTraceReader(app_settings())
        entered, release = threading.Event(), threading.Event()
        closed = Mock()
        calls = []

        def resolve():
            calls.append(1)
            reader._credential = SimpleNamespace(close=closed)
            entered.set()
            release.wait(2)
            return "00000000-0000-0000-0000-000000000001"

        close_task = None
        try:
            with patch.object(reader, "_resolve_project", side_effect=resolve):
                first = asyncio.create_task(reader.read(TRACE_A))
                for _ in range(100):
                    if entered.is_set():
                        break
                    await asyncio.sleep(0.001)
                self.assertTrue(entered.is_set())
                first.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await first
                for _ in range(4):
                    waiter = asyncio.create_task(reader.read(TRACE_A))
                    await asyncio.sleep(0)
                    waiter.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await waiter
                self.assertEqual(len(calls), 1)
                self.assertFalse(reader._initialization.cancelled())
                close_task = asyncio.create_task(reader.close())
                await asyncio.sleep(0.01)
                closed.assert_not_called()
                self.assertFalse(close_task.done())
                release.set()
                await close_task
                closed.assert_called_once_with()
        finally:
            release.set()
            if close_task is not None:
                await close_task
            else:
                await reader.close()

    async def test_query_is_fixed_to_the_configured_application_and_safe_projection(self):
        response = AsyncMock()
        response.status = 200
        response.json.return_value = payload()
        manager = AsyncMock()
        manager.__aenter__.return_value = response
        http = AsyncMock()
        http.post = Mock(return_value=manager)
        session = AsyncMock()
        session.__aenter__.return_value = http
        reader = FoundryTraceReader(app_settings())
        reader._application_id = "00000000-0000-0000-0000-000000000001"
        reader._credential = SimpleNamespace(get_token=Mock(return_value=SimpleNamespace(token="not-returned")))
        with patch("tmap_poc.trace_view.aiohttp.ClientSession", return_value=session):
            result = await reader.read(TRACE_A)
        args, kwargs = http.post.call_args
        self.assertTrue(args[0].endswith(reader._application_id + "/query"))
        self.assertIn(f"operation_Id == '{TRACE_A}'", kwargs["json"]["query"])
        self.assertNotIn("gen_ai.input.messages", kwargs["json"]["query"])
        self.assertNotIn("not-returned", json.dumps(result))

    async def test_invalid_trace_id_prevents_configuration_lookup(self):
        reader = FoundryTraceReader(app_settings())
        with patch.object(reader, "_resolve_project") as resolve:
            with self.assertRaises(ValueError):
                await reader.read("bad'; union *")
            resolve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
