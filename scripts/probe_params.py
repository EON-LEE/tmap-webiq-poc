"""Probe determinism alternatives and reasoning parameters.

The planning document requires temperature=0, which this model rejects. This
script checks what determinism and latency levers remain: seed, reasoning
effort, JSON mode, and the gap between client-observed and server-reported
time-to-first-token.
"""

import json
import pathlib
import sys
import time

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from tmap_poc.auth import TokenProvider          # noqa: E402
from tmap_poc.config import ConfigError, ModelConfig  # noqa: E402

PROMPT = "서울에서 가볼 만한 카페 3곳을 한 줄씩 추천해줘."


def call(cfg, tokens, body):
    headers = tokens.auth_header()
    headers["Content-Type"] = "application/json"
    start = time.perf_counter()
    response = requests.post(cfg.chat_completions_url, headers=headers, json=body, timeout=180)
    return response.status_code, response.json(), (time.perf_counter() - start) * 1000


def probe_seed(cfg, tokens, base):
    print("=== 1) seed determinism (same seed, 3 runs) ===")
    outputs = []
    for i in range(3):
        status, payload, wall_ms = call(cfg, tokens, dict(base, seed=42))
        if status != 200:
            print(f"  run{i}: HTTP {status} {json.dumps(payload, ensure_ascii=False)[:300]}")
            return
        content = payload["choices"][0]["message"]["content"]
        outputs.append(content)
        print(f"  run{i}: {wall_ms:.0f}ms "
              f"fingerprint={payload.get('system_fingerprint')} len={len(content)}")
    print(f"  identical(0==1): {outputs[0] == outputs[1]}  "
          f"identical(0==2): {outputs[0] == outputs[2]}")


def probe_reasoning_effort(cfg, tokens, base):
    print("\n=== 2) reasoning_effort support ===")
    for effort in ["none", "minimal", "low", "medium", "high", "xhigh"]:
        status, payload, wall_ms = call(cfg, tokens, dict(base, reasoning_effort=effort))
        if status != 200:
            message = payload.get("error", payload)
            if isinstance(message, dict):
                message = message.get("message", str(message))
            print(f"  {effort:8s}: HTTP {status} {str(message)[:150]}")
            continue
        usage = payload["usage"]
        checkpoint = usage.get("latency_checkpoint", {})
        print(f"  {effort:8s}: 200 wall={wall_ms:.0f}ms "
              f"reasoning_tok={usage['completion_tokens_details']['reasoning_tokens']} "
              f"engine_ttft={checkpoint.get('engine_ttft_ms')} "
              f"user_ttft={checkpoint.get('user_visible_ttft_ms')} "
              f"service_ttlt={checkpoint.get('service_ttlt_ms')}")


def probe_json_mode(cfg, tokens, base):
    print("\n=== 3) response_format json_object ===")
    body = dict(base, response_format={"type": "json_object"},
                messages=[{"role": "user",
                           "content": PROMPT + ' JSON으로만 답해. {"items":[...]}'}])
    status, payload, wall_ms = call(cfg, tokens, body)
    if status != 200:
        print(f"  HTTP {status}: {json.dumps(payload, ensure_ascii=False)[:300]}")
    else:
        print(f"  200 wall={wall_ms:.0f}ms "
              f"content={payload['choices'][0]['message']['content'][:200]!r}")


def probe_streaming_ttft(cfg, tokens, base):
    """Client-observed TTFT, to cross-check the server-reported value."""
    print("\n=== 4) streaming (TTFT cross-check) ===")
    start = time.perf_counter()
    response = requests.post(cfg.chat_completions_url, headers=tokens.auth_header(),
                             json=dict(base, stream=True), stream=True, timeout=180)
    print(f"  HTTP {response.status_code}")
    if response.status_code != 200:
        return
    for line in response.iter_lines():
        if line and line.startswith(b"data: ") and b"[DONE]" not in line:
            chunk = json.loads(line[6:])
            choices = chunk.get("choices") or []
            if choices and choices[0].get("delta", {}).get("content"):
                print(f"  client-observed TTFT: {(time.perf_counter() - start) * 1000:.0f}ms")
                return
    print("  no content chunk observed")


def main():
    try:
        cfg = ModelConfig.from_env()
    except ConfigError as exc:
        sys.exit(f"config error: {exc}")
    tokens = TokenProvider(cfg.token_scope, cfg.az_subscription)
    base = {"messages": [{"role": "user", "content": PROMPT}],
            "max_completion_tokens": 3000}

    probe_seed(cfg, tokens, base)
    probe_reasoning_effort(cfg, tokens, base)
    probe_json_mode(cfg, tokens, base)
    probe_streaming_ttft(cfg, tokens, base)


if __name__ == "__main__":
    main()
