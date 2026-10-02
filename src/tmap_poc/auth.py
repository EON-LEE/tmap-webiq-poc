"""Entra ID authentication.

Tokens are minted at runtime via the Azure CLI and held in memory only.
Nothing is ever written to disk, because the target resource has local
(API key) auth disabled and bearer tokens are short-lived secrets.
"""

import json
import os
import shutil
import subprocess
import time


def _az_binary():
    """Azure CLI used for local tokens. TMAP_AZ_BINARY pins it explicitly."""
    explicit = os.environ.get("TMAP_AZ_BINARY", "").strip()
    if explicit:
        return explicit
    linux = os.path.expanduser("~/.local/bin/az")
    found = shutil.which("az")
    # Under WSL, PATH also lists the Windows CLI (/mnt/c/...), whose login is separate from the Linux one.
    if found and found.startswith("/mnt/") and os.path.exists(linux):
        return linux
    return found or linux


class TokenProvider:
    """Caches an Entra bearer token and refreshes it before expiry."""

    #: Refresh this long before the token's real expiry. Entra tokens last
    #: about an hour, and a matrix run that straddled the boundary died with
    #: every remaining cell failing to publish, so the margin is generous.
    SKEW_SECONDS = 300

    def __init__(self, scope, subscription=None, ttl_seconds=2400):
        self.scope = scope
        self.subscription = subscription
        self.ttl_seconds = ttl_seconds
        self._token = None
        self._expires_at = 0.0

    def get(self, force=False):
        if force or self._token is None or time.time() >= self._expires_at:
            self._token, self._expires_at = self._fetch()
        return self._token

    @property
    def expires_at(self):
        """Real expiry, minus the refresh margin."""
        return self._expires_at

    def _fetch(self):
        """Return ``(token, refresh_deadline)``.

        The expiry is read from the CLI rather than assumed. Assuming a fixed
        lifetime is what let a stale token be reused: the cached value looked
        fresh to us long after Entra had stopped honouring it.
        """
        cmd = [_az_binary(), "account", "get-access-token",
               "--resource", self.scope, "-o", "json"]
        if self.subscription:
            cmd[3:3] = ["--subscription", self.subscription]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Azure CLI token acquisition timed out.") from exc
        if result.returncode != 0:
            raise RuntimeError(
                "failed to acquire Entra token via az CLI. Run `az login` first.\n"
                + result.stderr.strip()[:500])
        try:
            payload = json.loads(result.stdout)
        except ValueError:
            raise RuntimeError("az returned an unparseable token response")
        token = (payload.get("accessToken") or "").strip()
        if not token:
            raise RuntimeError("az returned an empty access token")
        try:
            expiry = float(payload["expires_on"])
        except (KeyError, TypeError, ValueError):
            expiry = time.time() + self.ttl_seconds
        return token, expiry - self.SKEW_SECONDS

    def auth_header(self, force=False):
        return {"Authorization": f"Bearer {self.get(force=force)}"}


class AzTokenCredential:
    """Adapts TokenProvider to the azure-core TokenCredential protocol.

    The Azure SDKs ship AzureCliCredential, but it resolves `az` from PATH,
    which is not populated in non-login WSL shells, and it cannot be pinned to
    a subscription. Reusing TokenProvider keeps a single auth path and keeps
    the subscription pin that stops calls landing in someone else's tenant.
    """

    def __init__(self, subscription=None):
        self._providers = {}
        self.subscription = subscription

    def get_token(self, *scopes, **kwargs):
        from azure.core.credentials import AccessToken

        resource = scopes[0]
        if resource.endswith("/.default"):
            resource = resource[: -len("/.default")]
        provider = self._providers.get(resource)
        if provider is None:
            provider = TokenProvider(resource, subscription=self.subscription)
            self._providers[resource] = provider
        token = provider.get()
        #: Report the token's real expiry. Reporting a fixed now+ttl on every
        #: call made the SDK hold a token well past the point Entra stopped
        #: accepting it, which killed a matrix run an hour in: arm A finished,
        #: then all eight remaining cells failed to publish as unauthorised.
        return AccessToken(token, int(provider.expires_at))
