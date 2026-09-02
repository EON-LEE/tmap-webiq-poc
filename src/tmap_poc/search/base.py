"""Search provider interface.

Design principle: for the Web IQ and EXA paths, the search layer is the *only*
thing that varies. Both return normalized passages that are fed into the same
model with the same system prompt.

Grounding with Bing does not fit this shape. It performs retrieval and
generation inside one opaque service, so it cannot return passages and its
retrieval latency cannot be separated. It is therefore modelled as an
``AnswerProvider`` (see ``gwb.py``) and compared on the reduced metric set.
This asymmetry is a reportable limitation, not an implementation detail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Passage:
    """One retrieved snippet, normalized across providers."""

    url: str
    title: str
    text: str
    rank: int
    published_at: str | None = None
    site: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_raw: bool = False) -> dict[str, Any]:
        out = {
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "rank": self.rank,
            "published_at": self.published_at,
            "site": self.site,
        }
        if include_raw:
            out["raw"] = self.raw
        return out


@dataclass
class RetrievalResult:
    """Outcome of one retrieval call, with the latency isolated."""

    provider: str
    query: str
    passages: list[Passage]
    retrieval_latency_ms: float
    endpoint: str | None = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self, include_raw: bool = False) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "query": self.query,
            "endpoint": self.endpoint,
            "retrieval_latency_ms": self.retrieval_latency_ms,
            "passage_count": len(self.passages),
            "passages": [p.to_dict(include_raw) for p in self.passages],
            "error": self.error,
            "meta": self.meta,
        }

    def allowed_urls(self) -> set[str]:
        """URLs the model is permitted to cite.

        The baseline run showed the model inventing plausible-looking deep
        links, so the judge must check citations against this set rather than
        only checking that a URL resolves.
        """
        return {p.url for p in self.passages}


class SearchProvider(Protocol):
    """Returns passages. Generation happens downstream, under our control."""

    name: str

    def retrieve(self, query: str, *, category: str, top_k: int) -> RetrievalResult:
        ...


@dataclass
class DirectAnswer:
    """A provider that answers directly, without exposing passages."""

    provider: str
    query: str
    answer_text: str
    citations: list[str]
    e2e_latency_ms: float
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    #: Metrics that cannot be computed for this shape of provider.
    UNAVAILABLE_METRICS = (
        "retrieval_latency_ms",
        "generation_latency_ms",
        "citation_in_passage_set",
        "controlled_model",
        "controlled_prompt",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "query": self.query,
            "answer_text": self.answer_text,
            "citations": self.citations,
            "e2e_latency_ms": self.e2e_latency_ms,
            "error": self.error,
            "unavailable_metrics": list(self.UNAVAILABLE_METRICS),
            "meta": self.meta,
        }


class AnswerProvider(Protocol):
    """Retrieval and generation are fused and cannot be separated."""

    name: str

    def answer(self, query: str, *, category: str) -> DirectAnswer:
        ...
