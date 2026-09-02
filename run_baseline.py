"""No-search baseline runner.

Runs the common system prompt against the model under test with NO retrieval
layer. This is the `null` search path: it establishes the hallucination floor
(does the model emit insufficient_evidence=true when it has no grounding?) and
the model-only latency, so that retrieval latency can be isolated once a real
search layer is attached.

Setup:
  cp config/runtime.example.env .env   # then fill it in
  az login

Usage:
  python3 run_baseline.py --category C7 --repeats 3
  python3 run_baseline.py --category C7 --repeats 3 --reasoning-effort high
  python3 run_baseline.py --ids 56,57 --repeats 1 --json-mode
"""

import argparse
import datetime as dt
import json
import pathlib
import statistics
import sys
import time

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from tmap_poc.auth import TokenProvider          # noqa: E402
from tmap_poc.config import ConfigError, ModelConfig  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent
KST = dt.timezone(dt.timedelta(hours=9))

# Verbatim from the planning document, section 2. Identical across all paths.
SYSTEM_PROMPT = """당신은 차량 내 음성 어시스턴트입니다. 운전 중 사용자가 음성으로 질문하며,
답변은 TTS로 읽힙니다.

[답변 규칙]
- 2~3문장, 40단어 이내. 운전 중 청취 가능한 길이로.
- 숫자·시간·가격은 구체적으로. 모호한 표현("최근", "곧") 금지.
- 정보의 기준 시점을 반드시 포함 (예: "9월 2일 기준").
- 근거가 불충분하면 추측하지 말고 "확인되지 않습니다"라고 답할 것.
- 목록이 필요하면 최대 3개까지만.

[출력 형식 — JSON만 반환]
{
  "answer": "음성으로 읽힐 답변 문장",
  "as_of": "정보 기준 시점 (YYYY-MM-DD 또는 YYYY-MM-DD HH:mm)",
  "confidence": "high | medium | low",
  "citations": [
    {"title": "출처 제목", "url": "출처 URL", "published": "발행일 또는 null"}
  ],
  "insufficient_evidence": true | false
}"""

# The null path has no <search_results> block; everything else matches the
# synthesis prompt used by the Web IQ / EXA paths.
USER_TEMPLATE = """질문: {query}
현재 시각: {now_kst}"""


def call_model(cfg, tokens, messages, reasoning_effort, max_completion_tokens, json_mode):
    body = {
        "messages": messages,
        "max_completion_tokens": max_completion_tokens,
        "reasoning_effort": reasoning_effort,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    for attempt in range(2):
        headers = tokens.auth_header(force=(attempt == 1))
        headers["Content-Type"] = "application/json"
        start = time.perf_counter()
        response = requests.post(cfg.chat_completions_url, headers=headers,
                                 json=body, timeout=180)
        wall_ms = (time.perf_counter() - start) * 1000
        if response.status_code == 401 and attempt == 0:
            continue
        return response.status_code, response.text, wall_ms
    return response.status_code, response.text, wall_ms


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
        return json.loads(text[start:end + 1]), None
    except json.JSONDecodeError as exc:
        return None, f"json decode error: {exc}"


def select_queries(args):
    queryset = json.loads((ROOT / "config" / "queryset.json").read_text(encoding="utf-8"))
    if args.ids:
        wanted = {int(x) for x in args.ids.split(",")}
        return [q for q in queryset["queries"] if q["id"] in wanted]
    return [q for q in queryset["queries"] if q["category"] == args.category]


def summarize(records):
    parsed = [r for r in records if r.get("parse_ok")]
    print(f"\n=== summary ({len(parsed)}/{len(records)} parsed) ===")
    if not parsed:
        return
    refusals = sum(1 for r in parsed if r["parsed"].get("insufficient_evidence") is True)
    print(f"insufficient_evidence=true : {refusals}/{len(parsed)} "
          f"({refusals / len(parsed) * 100:.0f}%)")

    by_query = {}
    for record in parsed:
        by_query.setdefault(record["query_id"], []).append(
            record["parsed"].get("insufficient_evidence") is True)
    for query_id, values in sorted(by_query.items()):
        print(f"  q{query_id}: {sum(values)}/{len(values)} refused")

    e2e = [r["client_e2e_ms"] for r in parsed]
    print(f"client e2e ms  : p50={statistics.median(e2e):.0f} "
          f"min={min(e2e):.0f} max={max(e2e):.0f}")
    ttft = [r["server_latency"]["user_visible_ttft_ms"] for r in parsed
            if r.get("server_latency", {}).get("user_visible_ttft_ms") is not None]
    if ttft:
        print(f"server ttft ms : p50={statistics.median(ttft):.0f} "
              f"min={min(ttft)} max={max(ttft)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default="C7")
    parser.add_argument("--ids", default=None,
                        help="comma-separated query ids, overrides --category")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--reasoning-effort", default="low",
                        choices=["none", "low", "medium", "high", "xhigh"])
    parser.add_argument("--max-completion-tokens", type=int, default=4000)
    parser.add_argument("--json-mode", action="store_true",
                        help="enforce response_format=json_object")
    parser.add_argument("--label", default=None)
    args = parser.parse_args()

    try:
        cfg = ModelConfig.from_env()
    except ConfigError as exc:
        sys.exit(f"config error: {exc}")

    tokens = TokenProvider(cfg.token_scope, cfg.az_subscription)
    queries = select_queries(args)
    if not queries:
        sys.exit("no queries selected")

    started = dt.datetime.now(KST)
    label = args.label or f"nosearch_{args.ids or args.category}_{args.reasoning_effort}"
    print(f"path=NO-SEARCH BASELINE  deployment={cfg.deployment}  "
          f"reasoning_effort={args.reasoning_effort}  json_mode={args.json_mode}  "
          f"queries={len(queries)}  repeats={args.repeats}")
    print("temperature: NOT SET (model rejects any value other than the default)")
    print(f"started {started.isoformat()}\n")

    records = []
    for query in queries:
        for repeat in range(1, args.repeats + 1):
            now_kst = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(
                    query=query["text"], now_kst=now_kst)},
            ]
            status, text, wall_ms = call_model(
                cfg, tokens, messages, args.reasoning_effort,
                args.max_completion_tokens, args.json_mode)

            record = {
                "query_id": query["id"], "category": query["category"],
                "query": query["text"], "trap": query.get("trap"),
                "repeat": repeat, "now_kst": now_kst,
                "http_status": status, "client_e2e_ms": round(wall_ms, 1),
                "reasoning_effort": args.reasoning_effort, "json_mode": args.json_mode,
                "retrieval_latency_ms": None,  # null search path
            }

            if status != 200:
                record["error"] = text[:800]
                record["parse_ok"] = False
                print(f"  q{query['id']} r{repeat}: HTTP {status} {text[:200]}")
            else:
                payload = json.loads(text)
                choice = payload["choices"][0]
                content = choice["message"].get("content")
                usage = payload.get("usage", {})
                checkpoint = usage.get("latency_checkpoint", {})
                record["raw_content"] = content
                record["finish_reason"] = choice.get("finish_reason")
                record["usage"] = {
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "reasoning_tokens": usage.get(
                        "completion_tokens_details", {}).get("reasoning_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                }
                record["server_latency"] = {
                    key: checkpoint.get(key) for key in (
                        "engine_ttft_ms", "user_visible_ttft_ms", "service_ttft_ms",
                        "engine_ttlt_ms", "service_ttlt_ms", "pre_inference_ms")
                }
                parsed, parse_error = parse_answer(content)
                record["parse_ok"] = parsed is not None
                record["parse_error"] = parse_error
                record["parsed"] = parsed
                if parsed:
                    citations = parsed.get("citations") or []
                    print(f"  q{query['id']} r{repeat}: "
                          f"insufficient={str(parsed.get('insufficient_evidence')):5s} "
                          f"conf={parsed.get('confidence')} cits={len(citations)} "
                          f"ttft={checkpoint.get('user_visible_ttft_ms')}ms e2e={wall_ms:.0f}ms")
                    print(f"          answer: {str(parsed.get('answer', ''))[:70]}")
                else:
                    print(f"  q{query['id']} r{repeat}: PARSE FAIL ({parse_error}) "
                          f"finish={record['finish_reason']} e2e={wall_ms:.0f}ms")
            records.append(record)

    outdir = ROOT / "results"
    outdir.mkdir(exist_ok=True)
    outfile = outdir / f"baseline_{label}_{started.strftime('%Y%m%d_%H%M%S')}.json"
    outfile.write_text(json.dumps({
        "run": {
            "path": "no_search_baseline",
            "model": cfg.describe(),
            "reasoning_effort": args.reasoning_effort,
            "json_mode": args.json_mode,
            "max_completion_tokens": args.max_completion_tokens,
            "temperature": "unsupported (model rejects values other than the default)",
            "seed_determinism": "unavailable (verified: same seed produced different outputs)",
            "started_kst": started.isoformat(),
            "repeats": args.repeats,
        },
        "records": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    summarize(records)
    print(f"\nsaved -> {outfile}")


if __name__ == "__main__":
    main()
