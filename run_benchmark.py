"""Benchmark runner. The search layer is the only variable.

Every path shares one model, one system prompt and one synthesis prompt, so a
score difference between runs is attributable to retrieval and nothing else.

Setup:
  cp config/runtime.example.env .env   # then fill it in
  az login

Usage:
  python3 run_benchmark.py --provider null    --category C7 --repeats 3
  python3 run_benchmark.py --provider fixture --ids 1,13,56,57,60
  python3 run_benchmark.py --provider webiq   --category C1 --location 37.5045,127.0490
"""

import argparse
import datetime as dt
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from tmap_poc.auth import TokenProvider  # noqa: E402
from tmap_poc.config import ConfigError, ModelConfig  # noqa: E402
from tmap_poc.model import (  # noqa: E402
    audit_citations,
    call_model,
    extract_latency,
    extract_usage,
    parse_answer,
)
from tmap_poc.prompts import build_messages  # noqa: E402
from tmap_poc.search import PASSAGE_PROVIDERS, get_provider  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent
KST = dt.timezone(dt.timedelta(hours=9))


def select_queries(args):
    queryset = json.loads(
        (ROOT / "config" / "queryset.json").read_text(encoding="utf-8")
    )
    if args.ids:
        wanted = [int(x) for x in args.ids.split(",")]
        by_id = {q["id"]: q for q in queryset["queries"]}
        return [by_id[i] for i in wanted if i in by_id]
    return [q for q in queryset["queries"] if q["category"] == args.category]


def retrieve(provider, query, location):
    """Call the provider, tolerating the ones with a narrower signature."""
    kwargs = {"category": query["category"], "top_k": 5}
    try:
        return provider.retrieve(
            query["text"], qid=query["id"], location=location, **kwargs
        )
    except TypeError:
        return provider.retrieve(query["text"], **kwargs)


def summarize(records, grounded):
    parsed = [r for r in records if r.get("parse_ok")]
    print(f"\n=== summary ({len(parsed)}/{len(records)} parsed) ===")
    if not parsed:
        return

    refusals = sum(
        1 for r in parsed if r["parsed"].get("insufficient_evidence") is True
    )
    print(f"insufficient_evidence=true : {refusals}/{len(parsed)}")

    by_query = {}
    for record in parsed:
        by_query.setdefault(record["query_id"], []).append(record)
    for query_id, group in sorted(by_query.items()):
        refused = sum(
            1 for r in group if r["parsed"].get("insufficient_evidence") is True
        )
        outside = sum(len(r["citation_audit"].get("out_of_passage_set") or []) for r in group)
        note = f"  fabricated-citations={outside}" if grounded and outside else ""
        print(f"  q{query_id}: {refused}/{len(group)} refused{note}")

    if grounded:
        checked = [r for r in parsed if r["citation_audit"]["checked"]]
        total = sum(r["citation_audit"]["count"] for r in checked)
        outside = sum(
            len(r["citation_audit"]["out_of_passage_set"]) for r in checked
        )
        if total:
            print(
                f"citations outside passage set : {outside}/{total} "
                f"({outside / total * 100:.0f}%)"
            )
        retrieval = [
            r["retrieval_latency_ms"] for r in parsed if r["retrieval_latency_ms"]
        ]
        if retrieval:
            print(
                f"retrieval ms   : p50={statistics.median(retrieval):.0f} "
                f"max={max(retrieval):.0f}"
            )

    e2e = [r["client_e2e_ms"] for r in parsed]
    print(
        f"client e2e ms  : p50={statistics.median(e2e):.0f} "
        f"min={min(e2e):.0f} max={max(e2e):.0f}"
    )
    ttft = [
        r["server_latency"]["user_visible_ttft_ms"]
        for r in parsed
        if r.get("server_latency", {}).get("user_visible_ttft_ms") is not None
    ]
    if ttft:
        print(f"server ttft ms : p50={statistics.median(ttft):.0f} max={max(ttft)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="null", choices=list(PASSAGE_PROVIDERS))
    parser.add_argument("--category", default="C7")
    parser.add_argument("--ids", default=None, help="comma-separated ids, overrides --category")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--reasoning-effort", default="low",
                        choices=["none", "low", "medium", "high", "xhigh"])
    parser.add_argument("--max-completion-tokens", type=int, default=4000)
    parser.add_argument("--json-mode", action="store_true")
    parser.add_argument("--location", default=None, help="lat,long for geo-aware search")
    parser.add_argument("--label", default=None)
    args = parser.parse_args()

    try:
        cfg = ModelConfig.from_env()
    except ConfigError as exc:
        sys.exit(f"config error: {exc}")

    try:
        provider = get_provider(args.provider)
    except Exception as exc:
        sys.exit(f"provider '{args.provider}' unavailable:\n{exc}")

    location = None
    if args.location:
        lat, _, lon = args.location.partition(",")
        location = (float(lat), float(lon))

    grounded = args.provider != "null"
    tokens = TokenProvider(cfg.token_scope, cfg.az_subscription)
    queries = select_queries(args)
    if not queries:
        sys.exit("no queries selected")

    started = dt.datetime.now(KST)
    label = args.label or f"{args.provider}_{args.ids or args.category}"
    print(f"provider={args.provider}  deployment={cfg.deployment}  "
          f"reasoning_effort={args.reasoning_effort}  queries={len(queries)}  "
          f"repeats={args.repeats}  location={location}")
    print("temperature: NOT SET (model rejects values other than the default)")
    print(f"started {started.isoformat()}\n")

    records = []
    for query in queries:
        retrieval = retrieve(provider, query, location)
        if retrieval.error:
            print(f"  q{query['id']}: RETRIEVAL FAILED {retrieval.error[:160]}")
        allowed = retrieval.allowed_urls()

        for repeat in range(1, args.repeats + 1):
            now_kst = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
            messages = build_messages(
                query["text"], now_kst, retrieval.passages, grounded
            )
            status, text, wall_ms = call_model(
                cfg, tokens, messages, args.reasoning_effort,
                args.max_completion_tokens, args.json_mode,
            )

            record = {
                "provider": args.provider,
                "query_id": query["id"], "category": query["category"],
                "query": query["text"], "trap": query.get("trap"),
                "repeat": repeat, "now_kst": now_kst,
                "http_status": status, "client_e2e_ms": round(wall_ms, 1),
                "reasoning_effort": args.reasoning_effort,
                "retrieval_latency_ms": round(retrieval.retrieval_latency_ms, 1),
                "retrieval_endpoint": retrieval.endpoint,
                "retrieval_error": retrieval.error,
                "passage_count": len(retrieval.passages),
                "retrieval_meta": retrieval.meta,
            }

            if status != 200:
                record["error"] = text[:800]
                record["parse_ok"] = False
                print(f"  q{query['id']} r{repeat}: HTTP {status} {text[:200]}")
            else:
                payload = json.loads(text)
                choice = payload["choices"][0]
                content = choice["message"].get("content")
                record["raw_content"] = content
                record["finish_reason"] = choice.get("finish_reason")
                record["usage"] = extract_usage(payload)
                record["server_latency"] = extract_latency(payload)

                parsed, parse_error = parse_answer(content)
                record["parse_ok"] = parsed is not None
                record["parse_error"] = parse_error
                record["parsed"] = parsed
                record["citation_audit"] = (
                    audit_citations(parsed, allowed, grounded)
                    if parsed else {"checked": False, "count": 0,
                                    "in_passage_set": None,
                                    "out_of_passage_set": None}
                )

                if parsed:
                    audit = record["citation_audit"]
                    bad = len(audit.get("out_of_passage_set") or [])
                    flag = f" FABRICATED_CIT={bad}" if bad else ""
                    print(f"  q{query['id']} r{repeat}: "
                          f"insufficient={str(parsed.get('insufficient_evidence')):5s} "
                          f"conf={parsed.get('confidence')} cits={audit['count']}{flag} "
                          f"psg={len(retrieval.passages)} e2e={wall_ms:.0f}ms")
                    print(f"          {str(parsed.get('answer', ''))[:76]}")
                else:
                    print(f"  q{query['id']} r{repeat}: PARSE FAIL ({parse_error})")
            records.append(record)

    outdir = ROOT / "results"
    outdir.mkdir(exist_ok=True)
    outfile = outdir / f"{label}_{started.strftime('%Y%m%d_%H%M%S')}.json"
    outfile.write_text(json.dumps({
        "run": {
            "provider": args.provider,
            "grounded": grounded,
            "model": cfg.describe(),
            "reasoning_effort": args.reasoning_effort,
            "json_mode": args.json_mode,
            "max_completion_tokens": args.max_completion_tokens,
            "location": location,
            "temperature": "unsupported (model rejects values other than the default)",
            "seed_determinism": "unavailable (verified: same seed produced different outputs)",
            "started_kst": started.isoformat(),
            "repeats": args.repeats,
        },
        "records": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    summarize(records, grounded)
    print(f"\nsaved -> {outfile}")


if __name__ == "__main__":
    main()
