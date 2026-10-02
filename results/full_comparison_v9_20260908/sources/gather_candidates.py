"""Extract URL leads from completed trials; these leads are not evidence."""
import json
from pathlib import Path
import re
from urllib.parse import quote

OUT = Path(__file__).resolve().parent
rows = [json.loads(x) for x in (OUT.parent / "runs.jsonl").read_text().splitlines()]
urls = {}
for row in rows:
    if row["endpoint"] not in ("places", "news", "finance", "videos", "browse"):
        continue
    leads = [c["url"] for c in row["citations"] if c.get("url")]
    for call in row.get("tool_calls", []):
        if call.get("name") in ("web", "news", "videos", "browse"):
            try:
                data, _ = json.JSONDecoder().raw_decode(call.get("output", ""))
            except (ValueError, TypeError):
                continue
            def walk(value):
                if isinstance(value, dict):
                    for k, v in value.items():
                        if k in ("url", "contentUrl", "webSearchUrl", "hostPageUrl") and isinstance(v, str):
                            yield v
                        elif isinstance(v, (dict, list)):
                            yield from walk(v)
                elif isinstance(value, list):
                    for v in value:
                        yield from walk(v)
            leads.extend(list(walk(data))[:5])
    for index, url in enumerate(dict.fromkeys(leads)):
        if not url.startswith(("https://", "http://")) or "bing.com" in url or "bing.net" in url:
            continue
        if re.search(r"\.(?:jpg|jpeg|png|gif|webp|mp4)(?:[?&#]|$)", url, re.I):
            continue
        if "blog.naver.com" in url and "m.blog.naver.com" not in url:
            url = url.replace("blog.naver.com", "m.blog.naver.com")
        key = f"{row['id']}-{row['condition']}-{index}"
        if not (OUT / f"{key}.json").exists():
            urls[key] = url
        if "youtube.com/watch" in url or "youtu.be/" in url:
            okey = key + "-oembed"
            if not (OUT / f"{okey}.json").exists():
                urls[okey] = "https://www.youtube.com/oembed?url=" + quote(url, safe="") + "&format=json"
(OUT / "candidate_urls.json").write_text(json.dumps(urls, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"{len(rows)} completed records; {len(urls)} new public URL leads")
