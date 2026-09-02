"""Web IQ provider (https://api.microsoft.ai/v3).

Web IQ is an independent API, not an Azure resource, so it is unaffected by
the subscription used for the model. Authentication is an API key in the
``x-apikey`` header, or an Entra client-credentials token for the
``https://api.microsoft.ai/.default`` scope.

Request and response shapes below follow the published v3 reference
(https://webiq.microsoft.ai/llms-full.txt). Two details matter for this PoC:

* Web results carry no ``snippet`` field at all, so ``contentFormat=passage``
  is mandatory rather than optional. Without it the model receives whole HTML
  documents, which is not what the passage-quality axis is meant to measure.
* ``location`` accepts ``lat:<float>;long:<float>``. Since no places vertical
  exists, this is the only way to give the generic web vertical the geographic
  context that C1 and C2 depend on. An IVI assistant always has GPS, so the
  benchmark should exercise it rather than pretend the query is location-free.
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

#: Per-vertical response envelope key and result cap, from the v3 reference.
VERTICALS = {
    "/search/web": {"envelope": "webResults", "max_results": 50},
    "/search/news": {"envelope": "newsResults", "max_results": 20},
    "/search/videos": {"envelope": "videoResults", "max_results": 30},
    "/search/images": {"envelope": "imageResults", "max_results": 50},
}


class CredentialsMissing(RuntimeError):
    pass


class WebIQProvider:
    name = "webiq"

    def __init__(
        self,
        routing: dict,
        api_key: str | None = None,
        timeout: float = 20.0,
        max_length: int = 4000,
    ):
        self.api_key = api_key or os.environ.get("WEBIQ_API_KEY")
        if not self.api_key:
            raise CredentialsMissing(
                "WEBIQ_API_KEY is not set. Request a profile key at "
                "https://webiq.microsoft.ai/profiles/ and put it in .env "
                "(never commit it)."
            )
        self.routing = routing
        self.timeout = timeout
        self.max_length = max_length

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
        location: tuple[float, float] | None = None,
    ) -> RetrievalResult:
        path = self.endpoint_for(category, qid)
        spec = VERTICALS.get(path, VERTICALS["/search/web"])

        payload: dict = {
            "query": query[:1000],
            "maxResults": min(top_k, spec["max_results"]),
            "language": "ko",
            "region": "KR",
            "contentFormat": "passage",
            "maxLength": self.max_length,
        }
        if location is not None:
            payload["location"] = f"lat:{location[0]:.6f};long:{location[1]:.6f}"

        req = urllib.request.Request(
            f"{BASE_URL}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "host": "api.microsoft.ai",
                "content-type": "application/json",
                "x-apikey": self.api_key,
            },
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return self._failed(query, path, started, f"HTTP {exc.code}: {_body(exc)}")
        except Exception as exc:  # noqa: BLE001 - surfaced in the result, not raised
            return self._failed(query, path, started, f"{type(exc).__name__}: {exc}")
        latency_ms = (time.perf_counter() - started) * 1000

        items = data.get(spec["envelope"]) or []
        rule = self.routing["routing"].get(category, {})
        return RetrievalResult(
            provider=self.name,
            query=query,
            passages=_to_passages(items, top_k),
            retrieval_latency_ms=latency_ms,
            endpoint=path,
            meta={
                "category": category,
                "deviation": rule.get("deviation"),
                "location_used": location is not None,
                # Kept for support tickets and for auditing a specific result.
                "trace_id": data.get("traceId"),
                # Web IQ's own judgement of whether the query needs fresh docs;
                # useful to cross-check against our per-category freshness rule.
                "query_freshness_signal": (data.get("querySignals") or {}).get(
                    "freshness"
                ),
            },
        )

    def _failed(
        self, query: str, path: str, started: float, error: str
    ) -> RetrievalResult:
        return RetrievalResult(
            provider=self.name,
            query=query,
            passages=[],
            retrieval_latency_ms=(time.perf_counter() - started) * 1000,
            endpoint=path,
            error=error,
        )


def _body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", "replace")[:400]
    except Exception:  # noqa: BLE001
        return "<no body>"


def _to_passages(items: list, top_k: int) -> list[Passage]:
    passages: list[Passage] = []
    for rank, item in enumerate(items[:top_k], start=1):
        if not isinstance(item, dict):
            continue
        passages.append(
            Passage(
                url=item.get("url", ""),
                title=item.get("title", ""),
                # News carries both; content is the grounding text, snippet is
                # the terse search-style line. Web carries content only.
                text=item.get("content") or item.get("snippet") or "",
                rank=rank,
                # Coverage is not 100%; empty values are expected and must not
                # be treated as "undated" when scoring freshness.
                published_at=item.get("lastUpdatedAt") or item.get("crawledAt"),
                site=item.get("source"),
                raw=item,
            )
        )
    return passages
