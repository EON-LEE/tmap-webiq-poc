"""Citation validity checker (planning doc section 5: citation_dead_rate).

Reads baseline result JSONs, extracts every citation URL, and verifies it with
HTTP HEAD (falling back to GET, since many sites reject HEAD).
"""

import argparse
import glob
import json
import pathlib
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
UA = "Mozilla/5.0 (compatible; TMAP-PoC-CitationCheck/1.0)"


def check(url):
    t0 = time.perf_counter()
    try:
        r = requests.head(url, headers={"User-Agent": UA}, timeout=15, allow_redirects=True)
        if r.status_code in (403, 405, 501) or r.status_code >= 500:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=20,
                             allow_redirects=True, stream=True)
            r.close()
        return {"status": r.status_code, "final_url": r.url,
                "ms": round((time.perf_counter() - t0) * 1000),
                "dead": r.status_code >= 400}
    except requests.RequestException as e:
        return {"status": None, "error": type(e).__name__,
                "ms": round((time.perf_counter() - t0) * 1000), "dead": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default="results/baseline_*.json")
    args = ap.parse_args()

    files = sorted(glob.glob(str(ROOT / args.pattern)))
    if not files:
        raise SystemExit(f"no result files match {args.pattern}")

    seen, rows = {}, []
    for f in files:
        d = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
        for rec in d["records"]:
            for c in (rec.get("parsed") or {}).get("citations") or []:
                url = (c or {}).get("url")
                if not url:
                    continue
                if url not in seen:
                    seen[url] = check(url)
                rows.append({
                    "file": pathlib.Path(f).name, "query_id": rec["query_id"],
                    "category": rec["category"], "repeat": rec["repeat"],
                    "title": c.get("title"), "url": url, "result": seen[url],
                })

    print(f"files={len(files)}  citation instances={len(rows)}  unique urls={len(seen)}\n")
    for url, res in seen.items():
        flag = "DEAD" if res["dead"] else "ok  "
        print(f"  [{flag}] {res.get('status') or res.get('error')}  {url}")

    if rows:
        dead = sum(1 for r in rows if r["result"]["dead"])
        print(f"\ncitation_dead_rate (instances) : {dead}/{len(rows)} = {dead / len(rows) * 100:.1f}%")
        dead_u = sum(1 for r in seen.values() if r["dead"])
        print(f"citation_dead_rate (unique urls): {dead_u}/{len(seen)} = {dead_u / len(seen) * 100:.1f}%")

    out = ROOT / "results" / "citation_check.json"
    out.write_text(json.dumps({"rows": rows, "unique": seen}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    main()
