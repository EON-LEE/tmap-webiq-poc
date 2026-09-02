"""Probe the model deployment: auth, temperature acceptance, latency_checkpoint shape.

Establishes which of the planning document's fixed variables are actually
achievable on this model. Run once per new deployment.
"""

import json
import pathlib
import sys
import time

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from tmap_poc.auth import TokenProvider          # noqa: E402
from tmap_poc.config import ConfigError, ModelConfig  # noqa: E402


def call(cfg, tokens, body):
    headers = tokens.auth_header()
    headers["Content-Type"] = "application/json"
    start = time.perf_counter()
    response = requests.post(cfg.chat_completions_url, headers=headers, json=body, timeout=120)
    return response.status_code, response.text, (time.perf_counter() - start) * 1000


def main():
    try:
        cfg = ModelConfig.from_env()
    except ConfigError as exc:
        sys.exit(f"config error: {exc}")
    tokens = TokenProvider(cfg.token_scope, cfg.az_subscription)
    print(f"deployment={cfg.deployment} api_version={cfg.api_version}\n")

    base = {
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_completion_tokens": 2000,
    }
    cases = [
        ("no temperature", dict(base)),
        ("temperature=0", dict(base, temperature=0)),
        ("temperature=1", dict(base, temperature=1)),
        ("top_p=1 seed=42", dict(base, top_p=1, seed=42)),
    ]

    for name, body in cases:
        status, text, wall_ms = call(cfg, tokens, body)
        print(f"--- {name} -> HTTP {status} ({wall_ms:.0f} ms wall)")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            print(text[:500] + "\n")
            continue
        if status != 200:
            print(json.dumps(payload.get("error", payload), ensure_ascii=False)[:600])
        else:
            print(f"    content: {payload['choices'][0]['message'].get('content')!r}")
            print(f"    usage: {json.dumps(payload.get('usage', {}), ensure_ascii=False)}")
            print(f"    top-level keys: {list(payload.keys())}")
        print()


if __name__ == "__main__":
    main()
