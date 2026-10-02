"""Fetch public references only; no Azure SDK, credentials or model calls."""
import concurrent.futures
import datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import urllib.request

OUT = Path(__file__).resolve().parent


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def fetch(item):
    key, url = item
    result = {"id": key, "url": url, "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "method": "Independent unauthenticated public HTTP GET", "images_used": False}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/json"})
        with urllib.request.urlopen(request, timeout=35) as response:
            if response.headers.get_content_type().startswith(("image/", "video/", "audio/")):
                result.update(http_status=response.status, final_url=response.url,
                              skipped_media_body=True, content_type=response.headers.get_content_type())
                (OUT / f"{key}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                print(key, "media body skipped", flush=True)
                return result
            raw = response.read(6_000_000)
            encoding = response.headers.get_content_charset() or "utf-8"
            body = raw.decode(encoding, errors="replace")
            if "\ufffd" in body[:4000]:
                match = re.search(r'charset=["\']?([\w-]+)', body[:4000], re.I)
                if match:
                    body = raw.decode(match[1], errors="replace")
            parser = Text()
            parser.feed(body)
            text = "\n".join(parser.parts)
            result.update(http_status=response.status, final_url=response.url,
                          content_sha256=hashlib.sha256(raw).hexdigest(), content_bytes=len(raw),
                          text=text, links=re.findall(r'href=["\']([^"\']+)', body))
            if "youtube.com/watch" in url:
                for field in ("title", "author", "lengthSeconds", "shortDescription", "channelId"):
                    match = re.search(r'"' + field + r'":("(?:\\.|[^"\\])*")', body)
                    if match:
                        result[field] = json.loads(match[1])
            if "youtube.com/results" in url:
                match = re.search(r'var ytInitialData = (\{.*?\});', body)
                if match:
                    def videos(value):
                        if isinstance(value, dict):
                            if "videoRenderer" in value:
                                yield value["videoRenderer"]
                            for child in value.values():
                                yield from videos(child)
                        elif isinstance(value, list):
                            for child in value:
                                yield from videos(child)
                    result["videos"] = list(videos(json.loads(match[1])))[:12]
    except Exception as exc:
        result["error"] = str(exc)
    (OUT / f"{key}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(key, result.get("http_status", result.get("error")), len(result.get("text", "")), flush=True)
    return result


if __name__ == "__main__":
    items = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(fetch, items.items()))
