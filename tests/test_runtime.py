import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tmap_poc import runtime

AGENT = {"name": "test-agent", "version": "1"}
USAGE = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120,
         "input_tokens_details": {"cached_tokens": 10, "cache_write_tokens": 5}}


class SDKValue(SimpleNamespace):
    def model_dump(self, **kwargs):
        return vars(self).copy()


class Clock:
    def __init__(self):
        self.value, self.sleeps = 0, []

    def perf_counter(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += seconds


class FakeStream:
    def __init__(self, events, clock):
        self.events, self.clock = events, clock

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        for event in self.events:
            self.clock.value += .25
            yield event


class FakeSDK:
    def __init__(self, outcomes, clock):
        self.outcomes, self.clock, self.calls = list(outcomes), clock, []
        self.responses = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeStream(outcome, self.clock)


class FakeAPIError(Exception):
    def __init__(self, status=429):
        self.status_code = status
        self.body = {"error": {"code": "test_service_error", "param": "test_parameter"}}


def events(text, status="completed", error=None, usage=USAGE, response_id="resp"):
    return [
        SDKValue(type="response.output_text.delta", delta=text),
        SDKValue(type=f"response.{status}", response=SDKValue(
            id=response_id, status=status, usage=SDKValue(**usage) if usage else None,
            error=SDKValue(code=error) if error else None,
        )),
    ]


class RuntimeTests(unittest.TestCase):
    def run_fake(self, outcomes, **kwargs):
        clock = Clock()
        client = FakeSDK(outcomes, clock)
        with patch.object(runtime, "time", clock), patch.object(runtime, "APIError", FakeAPIError):
            result = runtime.run_question(client, AGENT, "test-model", "app context", **kwargs)
        return result, client, clock

    def test_default_json_schema_raw_tools_and_usage_are_preserved(self):
        raw = '\n```json\n{"answer":"안내","citations":[]}\n```\n'
        args = {"query": "공식 안내", "contentFormat": "passage", "maxLength": 1200,
                "location": "lat:37.0;long:127.0", "maxResults": 5, "api_key": "not-recorded"}
        tool = SDKValue(id="call", type="mcp_call", name="web",
                        arguments=json.dumps(args), output="x" * 70001, status="completed")
        annotation = {"type": "url_citation", "url": "https://example.invalid"}
        stream = [
            SDKValue(type="response.output_item.done", item=tool),
            SDKValue(type="response.output_item.done", item=tool),
            SDKValue(type="response.output_text.annotation.added", annotation=SDKValue(**annotation)),
            *events(raw),
        ]
        result, client, clock = self.run_fake([stream])
        self.assertEqual(set(result), {
            "attempts", "completed", "ttft_ms", "completion_ms", "parsed", "parse_error", "raw_answer",
        })
        self.assertEqual(result["raw_answer"], raw)
        self.assertEqual(result["parsed"], {"answer": "안내", "citations": []})
        self.assertIsNone(result["parse_error"])
        attempt = result["attempts"][0]
        self.assertEqual(attempt["usage"], USAGE)
        self.assertEqual(attempt["response_id"], "resp")
        self.assertEqual(attempt["annotations"], [annotation])
        self.assertEqual(len(attempt["tool_calls"]), 1)
        self.assertEqual(attempt["tool_calls"][0]["output"], tool.output)
        self.assertEqual(attempt["tool_calls"][0]["arguments"], {k: v for k, v in args.items() if k != "api_key"})
        self.assertEqual(client.calls, [{
            "model": "test-model", "input": "app context", "stream": True, "timeout": 120,
            "max_output_tokens": 1600,
            "extra_body": {"agent_reference": {"type": "agent_reference", **AGENT}},
        }])
        self.assertEqual(clock.sleeps, [])

    def test_text_mode_preserves_exact_text_without_another_model_call(self):
        text = '  바로 안내합니다. {"not": "an output contract"}\n'
        result, client, _ = self.run_fake([events(text)], answer_format="text", max_output_tokens=600)
        self.assertEqual(result["raw_answer"], text)
        self.assertEqual(result["parsed"], {"answer": text, "citations": []})
        self.assertIsNone(result["parse_error"])
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["max_output_tokens"], 600)

    def test_text_mode_retains_only_actual_safe_citations(self):
        annotation = {"type": "url_citation", "url": "https://example.invalid/source", "title": "Source"}
        stream = [
            SDKValue(type="response.output_text.annotation.added", annotation=SDKValue(**annotation)),
            SDKValue(type="response.output_text.annotation.added", annotation={"url": "javascript:bad"}),
            *events("spoken answer"),
        ]
        result, _, _ = self.run_fake([stream], answer_format="text")
        self.assertEqual(result["parsed"]["citations"], [{"url": annotation["url"], "title": "Source"}])
        self.assertEqual(len(result["attempts"][0]["annotations"]), 2)

    def test_output_validation_does_not_change_legacy_completion_semantics(self):
        for text, mode, error in (
            ("not json", "json", "no JSON object found"),
            ('{"answer":1,"citations":[]}', "json", "invalid_answer_schema"),
            ('{"answer":"ok","citations":{}}', "json", "invalid_answer_schema"),
            ("", "text", "empty content"),
            (" \n ", "text", "empty content"),
        ):
            with self.subTest(text=text, mode=mode):
                result, _, _ = self.run_fake([events(text)], answer_format=mode)
                self.assertTrue(result["completed"])
                self.assertEqual(result["parse_error"], error)
                self.assertEqual(result["raw_answer"], text)

    def test_retry_preserves_both_usages_partial_text_and_backoff_timing(self):
        second_usage = {**USAGE, "input_tokens": 200, "total_tokens": 220}
        result, client, clock = self.run_fake([
            events("partial", "failed", "APITimeoutError", response_id="failed"),
            events("ready", usage=second_usage, response_id="succeeded"),
        ], answer_format="text")
        first, second = result["attempts"]
        self.assertEqual([a["usage"] for a in result["attempts"]], [USAGE, second_usage])
        self.assertEqual(first["raw_answer"], "partial")
        self.assertEqual([a["response_id"] for a in result["attempts"]], ["failed", "succeeded"])
        self.assertEqual(first["error"], {"code": "APITimeoutError"})
        self.assertEqual(second["offset_ms"], 15500)
        self.assertEqual(result["completion_ms"], 16000)
        self.assertEqual(result["ttft_ms"], 15750)
        self.assertEqual(clock.sleeps, [15])
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(result["parsed"], {"answer": "ready", "citations": []})

    def test_http_retry_is_bounded_and_missing_usage_stays_missing(self):
        for outcomes, attempts, completed in (
            ([FakeAPIError(), events("ready")], 2, True),
            ([FakeAPIError(), FakeAPIError(), events("unused")], 2, False),
            ([FakeAPIError(403), events("unused")], 1, False),
        ):
            with self.subTest(attempts=attempts, completed=completed):
                result, client, clock = self.run_fake(outcomes, answer_format="text")
                self.assertEqual(len(client.calls), attempts)
                self.assertEqual(result["completed"], completed)
                self.assertIsNone(result["attempts"][0]["usage"])
                self.assertEqual(result["attempts"][0]["error"]["service_code"], "test_service_error")
                self.assertEqual(clock.sleeps, [15] if attempts == 2 else [])
                if not completed:
                    self.assertIsNone(result["ttft_ms"])

    def test_nontransient_stream_failure_retains_usage_without_retry(self):
        result, client, clock = self.run_fake([events("partial", "failed", "tool_error")])
        self.assertFalse(result["completed"])
        self.assertEqual(result["attempts"][0]["usage"], USAGE)
        self.assertEqual(result["attempts"][0]["raw_answer"], "partial")
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(clock.sleeps, [])

    def test_deadline_and_missing_terminal_event_are_recorded(self):
        clock = Clock()
        client = FakeSDK([events("late")], clock)
        with patch.object(runtime, "time", clock):
            attempt = runtime.one_attempt(client, AGENT, "test-model", "context", .1)
        self.assertEqual(attempt["error"], {"code": "client_deadline"})
        result, _, _ = self.run_fake([[events("partial")[0]]], answer_format="text")
        self.assertEqual(result["attempts"][0]["error"], {"code": "stream_ended_without_completion"})

    def test_invalid_arguments_and_answer_format_do_not_trigger_calls(self):
        for arguments in ("not json", "[]", None):
            self.assertEqual(runtime.public_call(SDKValue(type="mcp_call", arguments=arguments))["arguments"], {})
        client = FakeSDK([], Clock())
        with self.assertRaises(ValueError):
            runtime.run_question(client, AGENT, "model", "context", answer_format="xml")
        self.assertEqual(client.calls, [])

    def test_public_call_accepts_dict_and_both_sdk_model_shapes(self):
        class AzureValue(SimpleNamespace):
            def as_dict(self):
                return vars(self).copy()

        safe_args = {"query": "안내", "contentFormat": "passage", "maxLength": 1200,
                     "location": "lat:37.0;long:127.0"}
        private = {"headers": {"Authorization": "private-header"},
                   "project_connection_id": "private-connection"}
        output = {"webResults": [{"url": "https://example.invalid", "content": "source"}]}
        expected = {"id": "call", "kind": "mcp_call", "name": "web",
                    "arguments": safe_args, "output": output, "status": "completed"}
        for arguments in ({**safe_args, **private}, json.dumps({**safe_args, **private})):
            data = {"id": "call", "type": "mcp_call", "name": "web",
                    "arguments": arguments, "output": output, "status": "completed", **private}
            for item in (data, SDKValue(**data), AzureValue(**data)):
                with self.subTest(item_type=type(item).__name__, arguments_type=type(arguments).__name__):
                    result = runtime.public_call(item)
                    self.assertEqual(result, expected)
                    self.assertNotIn("private-header", json.dumps(result))
                    self.assertNotIn("private-connection", json.dumps(result))
            self.assertIn("headers", data)
            if isinstance(arguments, dict):
                self.assertIn("headers", arguments)

    def test_public_call_rejects_unsupported_serialization(self):
        for item in (object(), SimpleNamespace(as_dict=lambda: [])):
            with self.subTest(item_type=type(item).__name__), self.assertRaises(TypeError):
                runtime.public_call(item)


if __name__ == "__main__":
    unittest.main()
