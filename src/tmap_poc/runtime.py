"""Shared streaming Foundry Agent runtime, extracted from the paired runner.

Callers own configuration and client creation, including disabling SDK retries.
The explicit retry retains every attempt and includes backoff in wall time.
"""

from __future__ import annotations

import json
import time

from openai import APIError
from opentelemetry.trace import Status, StatusCode

from tmap_poc.serialization import citation_links, parse_answer
from tmap_poc.telemetry import observed_tool, span


def public_call(item):
    if isinstance(item, dict):
        data = item
    elif hasattr(item, "model_dump"):
        data = item.model_dump(mode="json", exclude_none=True)
    elif hasattr(item, "as_dict"):
        data = item.as_dict()
    else:
        raise TypeError("Expected a dict or SDK tool-call model")
    if not isinstance(data, dict):
        raise TypeError("Tool-call model must serialize to a dict")
    arguments = data.get("arguments", {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {"unparsed": arguments}
    if not isinstance(arguments, dict):
        arguments = {}
    allowed = (
        "query", "q", "url", "language", "region", "vertical", "maxResults",
        "contentFormat", "maxLength", "location", "input",
    )
    return {
        "id": data.get("id"),
        "kind": data.get("type"),
        "name": data.get("name"),
        "arguments": {k: v for k, v in arguments.items() if k in allowed},
        "output": data.get("output"),
        "status": data.get("status"),
    }


def one_attempt(
    openai, agent, model, message, timeout, *, answer_format="json",
    max_output_tokens=1600,
):
    if answer_format not in ("json", "text"):
        raise ValueError("answer_format must be 'json' or 'text'")
    started = time.perf_counter()
    text, usage, status, failure, ttft = "", None, None, None, None
    calls, annotations = {}, []
    response_id = None
    try:
        with openai.responses.create(
            model=model,
            input=message,
            extra_body={"agent_reference": {
                "type": "agent_reference", "name": agent["name"],
                "version": agent["version"],
            }},
            stream=True,
            max_output_tokens=max_output_tokens,
            timeout=timeout,
        ) as stream:
            for event in stream:
                elapsed = (time.perf_counter() - started) * 1000
                if elapsed > timeout * 1000:
                    failure = {"code": "client_deadline"}
                    break
                if event.type == "response.output_text.delta":
                    if event.delta:
                        if ttft is None:
                            ttft = elapsed
                        text += event.delta
                elif event.type == "response.output_text.annotation.added":
                    annotation = event.annotation
                    annotations.append(
                        annotation.model_dump(mode="json")
                        if hasattr(annotation, "model_dump") else annotation
                    )
                elif event.type == "response.output_item.done":
                    item = event.item
                    if item.type.endswith("_call") or item.type == "function_call":
                        call = public_call(item)
                        key = call["id"] or str(len(calls))
                        if key not in calls:
                            observed_tool(call)
                        calls[key] = call
                elif event.type in (
                    "response.completed", "response.failed", "response.incomplete"
                ):
                    response = event.response
                    response_id, status = response.id, response.status
                    if response.usage is not None:
                        usage = response.usage.model_dump(mode="json")
                    if event.type != "response.completed":
                        error = getattr(response, "error", None)
                        failure = {"code": getattr(error, "code", event.type)}
                elif event.type == "error":
                    failure = {"code": getattr(event, "code", "stream_error")}
    except APIError as exc:
        failure = {
            "code": type(exc).__name__,
            "http_status": getattr(exc, "status_code", None),
        }
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            detail = body.get("error", body)
            if isinstance(detail, dict):
                failure["service_code"] = detail.get("code")
                failure["parameter"] = detail.get("param")
                if failure["http_status"] == 400:
                    print(f"Request rejected: {detail.get('message', '')}", flush=True)
    if status != "completed" and failure is None:
        failure = {"code": "stream_ended_without_completion"}
    if answer_format == "text":
        parsed = {"answer": text, "citations": citation_links(annotations)} if text.strip() else None
        parse_error = None if parsed is not None else "empty content"
    else:
        parsed, parse_error = parse_answer(text)
        if parse_error is None and (
            not isinstance(parsed, dict) or not isinstance(parsed.get("answer"), str)
            or not isinstance(parsed.get("citations"), list)
        ):
            parse_error = "invalid_answer_schema"
    return {
        "response_id": response_id,
        "status": status,
        "error": failure,
        "ttft_ms": round(ttft, 2) if ttft is not None else None,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "raw_answer": text,
        "parsed": parsed,
        "parse_error": parse_error,
        "usage": usage,
        "tool_calls": list(calls.values()),
        "annotations": annotations,
    }


def run_question(
    openai, agent, model, message, *, answer_format="json", max_output_tokens=1600,
):
    with span("navigation.text.request", **{
        "app.transport": "foundry_responses", "gen_ai.request.model": model,
        "gen_ai.agent.name": agent["name"],
    }) as current:
        result = _run_question(
            openai, agent, model, message,
            answer_format=answer_format, max_output_tokens=max_output_tokens,
        )
        if not result["completed"] or result["parse_error"]:
            current.set_attribute("error.type", "response_or_format_failure")
            current.set_status(Status(StatusCode.ERROR))
        return result


def _run_question(
    openai, agent, model, message, *, answer_format="json", max_output_tokens=1600,
):
    started = time.perf_counter()
    attempts = []
    for index in range(2):
        offset = (time.perf_counter() - started) * 1000
        attempt = one_attempt(
            openai, agent, model, message, timeout=120,
            answer_format=answer_format, max_output_tokens=max_output_tokens,
        )
        attempt["offset_ms"] = round(offset, 2)
        attempts.append(attempt)
        error = attempt["error"]
        if error is None:
            break
        retryable = (
            error.get("http_status") in (429, 500, 502, 503, 504)
            or error.get("code") in ("APIConnectionError", "APITimeoutError")
        )
        if not retryable or index == 1:
            break
        time.sleep(15)
    final = attempts[-1]
    completed = final["error"] is None
    return {
        "attempts": attempts,
        "completed": completed,
        "ttft_ms": (
            round(final["offset_ms"] + final["ttft_ms"], 2)
            if completed and final["ttft_ms"] is not None else None
        ),
        "completion_ms": round((time.perf_counter() - started) * 1000, 2),
        "parsed": final["parsed"],
        "parse_error": final["parse_error"],
        "raw_answer": final["raw_answer"],
    }
