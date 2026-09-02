"""Grounding with Bing path.

This provider deliberately does NOT implement the ``SearchProvider``
interface. Grounding with Bing performs retrieval and generation inside one
service, so it cannot hand back passages and its retrieval latency cannot be
isolated. It is modelled as an ``AnswerProvider`` and compared on the reduced
metric set declared in ``DirectAnswer.UNAVAILABLE_METRICS``.

Consequence for the report: a score gap between this path and the passage
based paths cannot be attributed to search quality alone, because the model
and the internal prompt also differ. That confound must be stated wherever
this path is compared.

Not provisioned. Enabling it requires, in the eonlee subscription only:
  1. register the ``Microsoft.Bing`` resource provider (currently NotRegistered)
  2. create a ``Microsoft.Bing/accounts`` resource of kind ``Bing.Grounding``
  3. connect it to an Azure AI Foundry project and expose it as an agent tool

Steps 2 and 3 create billable resources, so they must not be executed without
explicit approval.
"""

from __future__ import annotations

import os

from .base import DirectAnswer  # noqa: F401  (re-exported for callers)


class NotProvisioned(RuntimeError):
    pass


PROVISIONING_STEPS = (
    "az provider register --namespace Microsoft.Bing "
    "--subscription ME-MngEnvMCAP277524-eonlee-1",
    "create a Microsoft.Bing/accounts resource of kind Bing.Grounding (billable)",
    "attach it to a Foundry project and set GWB_PROJECT_ENDPOINT / GWB_CONNECTION_ID",
)


class GroundingWithBingProvider:
    name = "gwb"

    def __init__(self) -> None:
        endpoint = os.environ.get("GWB_PROJECT_ENDPOINT")
        connection = os.environ.get("GWB_CONNECTION_ID")
        if not endpoint or not connection:
            raise NotProvisioned(
                "Grounding with Bing is not provisioned. Required steps:\n  - "
                + "\n  - ".join(PROVISIONING_STEPS)
            )
        self.endpoint = endpoint
        self.connection = connection

    def answer(self, query: str, *, category: str) -> DirectAnswer:
        raise NotProvisioned(
            "Client not implemented. Implement against the live agent once the "
            "resource exists, so the request shape is verified rather than assumed."
        )
