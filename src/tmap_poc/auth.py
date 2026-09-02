"""Entra ID authentication.

Tokens are minted at runtime via the Azure CLI and held in memory only.
Nothing is ever written to disk, because the target resource has local
(API key) auth disabled and bearer tokens are short-lived secrets.
"""

import os
import shutil
import subprocess
import time


def _az_binary():
    return shutil.which("az") or os.path.expanduser("~/.local/bin/az")


class TokenProvider:
    """Caches an Entra bearer token and refreshes it before expiry."""

    def __init__(self, scope, subscription=None, ttl_seconds=2400):
        self.scope = scope
        self.subscription = subscription
        self.ttl_seconds = ttl_seconds
        self._token = None
        self._fetched_at = 0.0

    def get(self, force=False):
        if force or self._token is None or (time.time() - self._fetched_at) > self.ttl_seconds:
            self._token = self._fetch()
            self._fetched_at = time.time()
        return self._token

    def _fetch(self):
        cmd = [_az_binary(), "account", "get-access-token",
               "--resource", self.scope, "-o", "tsv", "--query", "accessToken"]
        if self.subscription:
            cmd[3:3] = ["--subscription", self.subscription]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                "failed to acquire Entra token via az CLI. Run `az login` first.\n"
                + result.stderr.strip()[:500])
        token = result.stdout.strip()
        if not token:
            raise RuntimeError("az returned an empty access token")
        return token

    def auth_header(self, force=False):
        return {"Authorization": f"Bearer {self.get(force=force)}"}
