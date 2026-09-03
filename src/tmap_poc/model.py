"""Model call and output parsing.

Shared by every path so that only the search layer differs between runs.
"""

from __future__ import annotations

import json
import time

import requests

#: Server-side latency fields exposed by the deployment. Collected verbatim
#: because client-observed timing and these values disagree by more than 4x,
#: and both must be reported until that is explained.
LATENCY_FIELDS = (
    "engine_ttft_ms",
    "user_visible_ttft_ms",
    "service_ttft_ms",
    "engine_ttlt_ms",
    "service_ttlt_ms",
    "pre_inference_ms",
)


def call_model(
    cfg,
    tokens,
    messages,
    reasoning_effort: str,
    max_completion_tokens: int,
    json_mode: bool = False,
    timeout: float = 180,
):
    """Returns (status, body_text, client_wall_ms). Retries once on 401."""
    body = {
        "messages": messages,
        "max_completion_tokens": max_completion_tokens,
        "reasoning_effort": reasoning_effort,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    status, text, wall_ms = None, "", 0.0
    for attempt in range(2):
        headers = tokens.auth_header(force=(attempt == 1))
        headers["Content-Type"] = "application/json"
        start = time.perf_counter()
        response = requests.post(
            cfg.chat_completions_url, headers=headers, json=body, timeout=timeout
        )
        wall_ms = (time.perf_counter() - start) * 1000
        status, text = response.status_code, response.text
        if status == 401 and attempt == 0:
            continue
        break
    return status, text, wall_ms


def parse_answer(content):
    """Tolerant parse of the model's JSON output contract."""
    if not content:
        return None, "empty content"
    text = content.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) > 1:
            text = parts[1]
            if text.lstrip().lower().startswith("json"):
                text = text.lstrip()[4:]
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None, "no JSON object found"
    try:
        return json.loads(text[start : end + 1]), None
    except json.JSONDecodeError as exc:
        return None, f"json decode error: {exc}"


def extract_usage(payload: dict) -> dict:
    usage = payload.get("usage", {})
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": usage.get("completion_tokens_details", {}).get(
            "reasoning_tokens"
        ),
        "total_tokens": usage.get("total_tokens"),
    }


def extract_latency(payload: dict) -> dict:
    checkpoint = payload.get("usage", {}).get("latency_checkpoint", {})
    return {field: checkpoint.get(field) for field in LATENCY_FIELDS}


def audit_citations(parsed: dict, allowed_urls: set[str], grounded: bool) -> dict:
    """Check citations against the passage set actually supplied.

    The no-search baseline showed the model inventing plausible deep links, so
    a citation resolving is not enough. On a grounded path every cited URL must
    trace back to a passage we provided; anything else is fabricated
    attribution even if the URL happens to be live.
    """
    citations = parsed.get("citations") or []
    urls = [c.get("url") for c in citations if isinstance(c, dict) and c.get("url")]
    if not grounded:
        return {
            "count": len(urls),
            "in_passage_set": None,
            "out_of_passage_set": None,
            "checked": False,
        }
    outside = [u for u in urls if u not in allowed_urls]
    return {
        "count": len(urls),
        "in_passage_set": len(urls) - len(outside),
        "out_of_passage_set": outside,
        "checked": True,
    }
