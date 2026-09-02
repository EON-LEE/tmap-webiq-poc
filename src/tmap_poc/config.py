"""Runtime configuration.

Everything environment-specific (endpoint, deployment, subscription) is read
from the environment or a local `.env`, never hardcoded, so that no resource
or subscription identifiers land in version control.
"""

import os
import pathlib
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    pass


def load_dotenv(path=None):
    """Minimal .env loader. Existing environment variables win."""
    p = pathlib.Path(path) if path else ROOT / ".env"
    if not p.exists():
        return False
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value
    return True


def _require(name):
    value = os.environ.get(name, "").strip()
    if not value or value.startswith("<"):
        raise ConfigError(
            f"environment variable {name} is not set. "
            f"Copy config/runtime.example.env to .env and fill it in."
        )
    return value


@dataclass(frozen=True)
class ModelConfig:
    """The model under test. Held identical across every search path."""

    endpoint: str
    deployment: str
    api_version: str
    az_subscription: str | None
    token_scope: str = "https://cognitiveservices.azure.com"

    @classmethod
    def from_env(cls):
        load_dotenv()
        subscription = os.environ.get("TMAP_POC_AZ_SUBSCRIPTION", "").strip()
        if subscription.startswith("<"):
            subscription = ""
        return cls(
            endpoint=_require("TMAP_POC_MODEL_ENDPOINT").rstrip("/"),
            deployment=_require("TMAP_POC_MODEL_DEPLOYMENT"),
            api_version=os.environ.get("TMAP_POC_MODEL_API_VERSION", "2025-01-01-preview"),
            az_subscription=subscription or None,
        )

    @property
    def chat_completions_url(self):
        return (f"{self.endpoint}/openai/deployments/{self.deployment}"
                f"/chat/completions?api-version={self.api_version}")

    def describe(self):
        """Redacted description safe to print into logs and result files."""
        host = self.endpoint.split("://")[-1].split(".")[0]
        return {
            "resource": host[:4] + "***" if len(host) > 4 else "***",
            "deployment": self.deployment,
            "api_version": self.api_version,
        }
