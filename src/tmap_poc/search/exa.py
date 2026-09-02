"""EXA provider (https://api.exa.ai).

EXA returns documents with optional extracted text, which maps cleanly onto
the passage interface. Requires a self-issued key from exa.ai.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from .base import Passage, RetrievalResult

SEARCH_URL = "https://api.exa.ai/search"


class CredentialsMissing(RuntimeError):
    pass


class ExaProvider:
    name = "exa"

    def __init__(self, api_key: str | None = None, timeout: float = 20.0):
        self.api_key = api_key or os.environ.get("EXA_API_KEY")
        if not self.api_key:
            raise CredentialsMissing(
                "EXA_API_KEY is not set. Issue a key at https://exa.ai and put "
                "it in .env (never commit it)."
            )
        self.timeout = timeout

    def retrieve(
        self,
        query: str,
        *,
        category: str,
        top_k: int = 5,
        start_published_date: str | None = None,
    ) -> RetrievalResult:
        payload: dict = {
            "query": query,
            "numResults": top_k,
            "type": "auto",
            "contents": {"text": {"maxCharacters": 1200}},
        }
        if start_published_date:
            payload["startPublishedDate"] = start_published_date

        req = urllib.request.Request(
            SEARCH_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-api-key": self.api_key},
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
                endpoint="/search",
                error=f"HTTP {exc.code}: {detail}",
            )
        except Exception as exc:  # noqa: BLE001
            return RetrievalResult(
                provider=self.name,
                query=query,
                passages=[],
                retrieval_latency_ms=(time.perf_counter() - started) * 1000,
                endpoint="/search",
                error=f"{type(exc).__name__}: {exc}",
            )
        latency_ms = (time.perf_counter() - started) * 1000

        passages = [
            Passage(
                url=item.get("url", ""),
                title=item.get("title") or "",
                text=(item.get("text") or "")[:1200],
                rank=rank,
                published_at=item.get("publishedDate"),
                site=item.get("author"),
                raw=item,
            )
            for rank, item in enumerate(data.get("results", [])[:top_k], start=1)
        ]

        return RetrievalResult(
            provider=self.name,
            query=query,
            passages=passages,
            retrieval_latency_ms=latency_ms,
            endpoint="/search",
            meta={"category": category, "search_type": data.get("resolvedSearchType")},
        )
