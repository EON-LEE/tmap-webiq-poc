"""Search layer registry.

``null``, ``webiq`` and ``exa`` are passage providers sharing one interface.
``gwb`` is deliberately separate; see ``gwb.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import (
    AnswerProvider,
    DirectAnswer,
    Passage,
    RetrievalResult,
    SearchProvider,
)
from .null import NullProvider

__all__ = [
    "AnswerProvider",
    "DirectAnswer",
    "Passage",
    "RetrievalResult",
    "SearchProvider",
    "NullProvider",
    "PASSAGE_PROVIDERS",
    "ANSWER_PROVIDERS",
    "get_provider",
    "load_routing",
]

PASSAGE_PROVIDERS = ("null", "fixture", "webiq", "exa")
ANSWER_PROVIDERS = ("gwb",)

_ROUTING_PATH = Path(__file__).resolve().parents[3] / "config" / "routing.json"


def load_routing(path: Path | None = None) -> dict:
    return json.loads((path or _ROUTING_PATH).read_text(encoding="utf-8"))


def get_provider(name: str):
    """Construct a provider. Raises if its credentials are absent."""
    if name == "null":
        return NullProvider()
    if name == "fixture":
        from .fixture import FixtureProvider

        return FixtureProvider()
    if name == "webiq":
        from .webiq import WebIQProvider

        return WebIQProvider(routing=load_routing())
    if name == "exa":
        from .exa import ExaProvider

        return ExaProvider()
    if name == "gwb":
        from .gwb import GroundingWithBingProvider

        return GroundingWithBingProvider()
    raise ValueError(
        f"unknown provider {name!r}; expected one of "
        f"{PASSAGE_PROVIDERS + ANSWER_PROVIDERS}"
    )
