"""Web IQ provider (https://api.microsoft.ai/v3).

Web IQ is an independent API, not an Azure resource, so it is unaffected by
the subscription used for the model. Authentication is an API key in the
``x-apikey`` header, or an Entra client-credentials token for the
``https://api.microsoft.ai/.default`` scope.

The request shape below follows the published v3 surface but has NOT been
executed against a live profile yet, because no key has been issued. The
first successful call must be treated as a verification step, not a given.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from .base import Passage, RetrievalResult

BASE_URL = "https://api.microsoft.ai/v3"
DOCS_URL = "https://webiq.microsoft.ai/llms-full.txt"


class CredentialsMissing(RuntimeError):
    pass


class WebIQProvider:
    name = "webiq"

    def __init__(self, routing: dict, api_key: str | None = None, timeout: float = 20.0):
        self.api_key = api_key or os.environ.get("WEBIQ_API_KEY")
        if not self.api_key:
            raise CredentialsMissing(
                "WEBIQ_API_KEY is not set. Request a profile key at "
                "https://webiq.microsoft.ai/profiles/ and put it in .env "
                "(never commit it)."
            )
        self.routing = routing
        self.timeout = timeout

    def endpoint_for(self, category: str, qid: str | int | None = None) -> str:
        rule = self.routing["routing"].get(category, {})
        exceptions = rule.get("exceptions", {})
        if qid is not None and str(qid) in exceptions:
            return exceptions[str(qid)]["actual"]
        return rule.get("actual", "/search/web")

    def retrieve(
        self,
        query: str,
        *,
        category: str,
        top_k: int = 5,
        qid: str | int | None = None,
    ) -> RetrievalResult:
        path = self.endpoint_for(category, qid)
        url = f"{BASE_URL}{path}"
        payload = {
            "query": query,
            "count": top_k,
            "language": "ko",
            "region": "KR",
            "contentFormat": "passage",
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-apikey": self.api_key,
            },
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            return RetrievalResult(
                provider=self.name,
                query=query,
                passages=[],
                retrieval_latency_ms=(time.perf_counter() - started) * 1000,
                endpoint=path,
                error=f"HTTP {exc.code}: {detail}",
            )
        except Exception as exc:  # noqa: BLE001 - surfaced in the result, not raised
            return RetrievalResult(
                provider=self.name,
                query=query,
                passages=[],
                retrieval_latency_ms=(time.perf_counter() - started) * 1000,
                endpoint=path,
                error=f"{type(exc).__name__}: {exc}",
            )
        latency_ms = (time.perf_counter() - started) * 1000

        return RetrievalResult(
            provider=self.name,
            query=query,
            passages=_parse_passages(data, top_k),
            retrieval_latency_ms=latency_ms,
            endpoint=path,
            meta={
                "category": category,
                "deviation": self.routing["routing"].get(category, {}).get("deviation"),
            },
        )


def _parse_passages(data: dict, top_k: int) -> list[Passage]:
    """Tolerant parse.

    The exact envelope is unverified, so several plausible container keys are
    tried instead of assuming one. If none match, an empty list is returned
    and the raw response is preserved by the caller for inspection.
    """
    items = None
    for key in ("results", "value", "webPages", "data", "items"):
        node = data.get(key)
        if isinstance(node, dict):
            node = node.get("value") or node.get("results")
        if isinstance(node, list):
            items = node
            break
    if items is None:
        return []

    passages: list[Passage] = []
    for rank, item in enumerate(items[:top_k], start=1):
        if not isinstance(item, dict):
            continue
        passages.append(
            Passage(
                url=item.get("url") or item.get("link") or "",
                title=item.get("name") or item.get("title") or "",
                text=(
                    item.get("passage")
                    or item.get("snippet")
                    or item.get("description")
                    or item.get("text")
                    or ""
                ),
                rank=rank,
                published_at=item.get("datePublished") or item.get("publishedAt"),
                site=item.get("siteName") or item.get("displayUrl"),
                raw=item,
            )
        )
    return passages
