"""Fixture provider: canned passages, no network, no credentials.

Exists so the grounded pipeline (retrieve, synthesise, parse, score) can be
validated before any search vendor key is available, and so specific failure
modes can be reproduced on demand rather than waited for.

The fixtures are fabricated. They are a test harness, never evaluation data.
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import Passage, RetrievalResult

_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "config" / "fixtures.json"


class FixtureProvider:
    name = "fixture"

    def __init__(self, path: Path | None = None):
        data = json.loads((path or _FIXTURE_PATH).read_text(encoding="utf-8"))
        self.fixtures = data["fixtures"]
        self.cases = data.get("_cases", {})

    def retrieve(
        self,
        query: str,
        *,
        category: str,
        top_k: int = 5,
        qid: str | int | None = None,
        location: tuple[float, float] | None = None,
    ) -> RetrievalResult:
        key = str(qid)
        known = key in self.fixtures
        items = self.fixtures.get(key, [])

        passages = [
            Passage(
                url=item["url"],
                title=item["title"],
                text=item["content"],
                rank=rank,
                published_at=item.get("lastUpdatedAt"),
                site=item.get("source"),
                raw=item,
            )
            for rank, item in enumerate(items[:top_k], start=1)
        ]

        return RetrievalResult(
            provider=self.name,
            query=query,
            passages=passages,
            retrieval_latency_ms=0.0,
            endpoint="fixture",
            meta={
                "category": category,
                "synthetic": True,
                "case": self.cases.get(key),
                # Distinguishes "this question has no fixture" from "this
                # question's fixture is deliberately empty" (a retrieval miss).
                "fixture_defined": known,
            },
        )
