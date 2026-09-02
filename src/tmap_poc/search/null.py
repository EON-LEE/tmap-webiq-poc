"""No-search control path.

Returns zero passages so the model must answer from parametric knowledge
alone. This is the baseline every grounded path is measured against.
"""

from __future__ import annotations

from .base import RetrievalResult


class NullProvider:
    name = "null"

    def retrieve(self, query: str, *, category: str, top_k: int = 0) -> RetrievalResult:
        return RetrievalResult(
            provider=self.name,
            query=query,
            passages=[],
            retrieval_latency_ms=0.0,
            endpoint=None,
            meta={"category": category, "note": "no search layer"},
        )
