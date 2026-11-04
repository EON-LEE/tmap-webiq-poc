"""Application settings read from the environment or a local `.env` file.

Nothing environment-specific (endpoints, subscription, agent names) is hardcoded, and no cloud
call is made on import. See config/runtime.example.env.
"""

import os
import pathlib
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from voice_poc.agents import AgentReference, PROVIDER_LABELS

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


def _value(name, default=""):
    value = os.environ.get(name, default).strip()
    return "" if "<" in value else value


def _https(value, name):
    if value:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ConfigError(f"{name} must be an HTTPS endpoint without credentials")
        if parsed.query or parsed.fragment:
            raise ConfigError(f"{name} must not contain a query or fragment")
    return value.rstrip("/")


@dataclass(frozen=True)
class AppSettings:
    project_endpoint: str = ""
    voice_endpoint: str = ""
    model: str = ""
    subscription: str = ""
    auth_mode: str = "cli"
    managed_identity_client_id: str = ""
    voice_name: str = "ko-KR-SunHiNeural"
    foundry_resource_override: str = ""
    agent_identity_client_id: str = ""
    # Foundry Toolbox that exposes the Bing-based Web Search tool over MCP for End-to-end sessions.
    web_search_toolbox: str = ""
    # Azure OpenAI GPT-Live deployment for the optional gpt_live mode; empty disables it.
    live_endpoint: str = ""
    live_deployment: str = ""
    agents: dict[str, AgentReference] = field(default_factory=dict)
    allowed_origins: tuple[str, ...] = (
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    )

    @classmethod
    def from_env(cls):
        mode = _value("POC_AUTH_MODE", "cli")
        if mode not in ("cli", "managed_identity"):
            raise ConfigError("POC_AUTH_MODE must be cli or managed_identity")
        agents = {}
        for provider in PROVIDER_LABELS:
            prefix = f"POC_{provider.upper()}_AGENT"
            name, version = _value(prefix + "_NAME"), _value(prefix + "_VERSION")
            if version and not name:
                raise ConfigError(f"{prefix}_VERSION requires {prefix}_NAME")
            if name:
                agents[provider] = AgentReference(name, version or None)
        origins = _value(
            "POC_ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
        )
        allowed_origins = tuple(part.strip().rstrip("/") for part in origins.split(",") if part.strip())
        for origin in allowed_origins:
            parsed = urlparse(origin)
            if (
                parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.path
                or parsed.query or parsed.fragment
            ):
                raise ConfigError("POC_ALLOWED_ORIGINS must contain exact HTTP(S) origins.")
        if not allowed_origins:
            raise ConfigError("POC_ALLOWED_ORIGINS must not be empty.")
        toolbox = _value("POC_WEB_SEARCH_TOOLBOX")
        if toolbox and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", toolbox):
            raise ConfigError("POC_WEB_SEARCH_TOOLBOX must be a Foundry toolbox name.")
        live_deployment = _value("POC_LIVE_DEPLOYMENT")
        if live_deployment and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", live_deployment):
            raise ConfigError("POC_LIVE_DEPLOYMENT must be a model deployment name.")
        return cls(
            project_endpoint=_https(_value("FOUNDRY_PROJECT_ENDPOINT"), "FOUNDRY_PROJECT_ENDPOINT"),
            voice_endpoint=_https(_value("POC_VOICE_ENDPOINT"), "POC_VOICE_ENDPOINT"),
            model=_value("POC_MODEL_DEPLOYMENT"),
            subscription=_value("POC_AZ_SUBSCRIPTION"),
            auth_mode=mode,
            managed_identity_client_id=_value("AZURE_CLIENT_ID"),
            voice_name=_value("POC_VOICE_NAME", "ko-KR-SunHiNeural"),
            foundry_resource_override=_value("POC_VOICE_FOUNDRY_RESOURCE_OVERRIDE"),
            agent_identity_client_id=_value("POC_VOICE_AGENT_IDENTITY_CLIENT_ID"),
            web_search_toolbox=toolbox,
            live_endpoint=_https(_value("POC_LIVE_ENDPOINT"), "POC_LIVE_ENDPOINT"),
            live_deployment=live_deployment,
            agents=agents,
            allowed_origins=allowed_origins,
        )

    @property
    def project_name(self):
        path = urlparse(self.project_endpoint).path.rstrip("/")
        if "/projects/" not in path:
            return ""
        name = path.rsplit("/projects/", 1)[-1]
        return name if "/" not in name else ""

    @property
    def web_search_toolbox_url(self):
        if not self.web_search_toolbox or not self.project_name:
            return ""
        return f"{self.project_endpoint}/toolboxes/{self.web_search_toolbox}/mcp?api-version=v1"

    def provider_config(self, provider):
        if provider not in PROVIDER_LABELS:
            raise ConfigError("Unknown search provider")
        agent = self.agents.get(provider)
        errors = self.problems(provider)
        warnings = []
        if agent is not None and not agent.version:
            warnings.append(
                f"POC_{provider.upper()}_AGENT_VERSION is not pinned; the service selects the version."
            )
        if agent is not None and any(
            other != provider and reference == agent
            for other, reference in self.agents.items()
        ):
            warnings.append(
                "Both providers reference the same Agent. Check the Agent's actual search tools before comparing providers."
            )
        return {
            "id": provider,
            "label": PROVIDER_LABELS[provider],
            "configured": not errors,
            "errors": errors,
            "warnings": warnings,
            "readiness_scope": "configuration_only",
            "agent": (
                {"name": agent.name, "version": agent.version, "pinned": bool(agent.version)}
                if agent is not None else None
            ),
        }

    def problems(self, provider=None, *, voice=True):
        errors = []
        if not self.project_name:
            errors.append("FOUNDRY_PROJECT_ENDPOINT must identify a Foundry project.")
        if self.auth_mode == "cli" and not self.subscription:
            errors.append("POC_AZ_SUBSCRIPTION is required for local CLI authentication.")
        if voice and not self.voice_endpoint:
            errors.append("POC_VOICE_ENDPOINT is required for Voice Live.")
        if voice and not self.voice_name:
            errors.append("POC_VOICE_NAME must identify the server's default voice.")
        if not voice and not self.model:
            errors.append("POC_MODEL_DEPLOYMENT is required.")
        if provider is not None and provider not in self.agents:
            errors.append(f"Configure POC_{provider.upper()}_AGENT_NAME first.")
        return errors

    def require(self, provider=None, *, voice=True):
        if provider is not None and provider not in PROVIDER_LABELS:
            raise ConfigError("Unknown search provider")
        errors = self.problems(provider, voice=voice)
        if errors:
            raise ConfigError(" ".join(errors))

    def live_problems(self):
        """GPT-Live is optional, so its settings are not part of problems()."""
        if self.live_endpoint and self.live_deployment:
            return []
        return ["GPT-Live 배포가 설정되지 않았습니다. POC_LIVE_ENDPOINT와 POC_LIVE_DEPLOYMENT를 확인하세요."]

    def require_live(self):
        errors = self.live_problems()
        if errors:
            raise ConfigError(" ".join(errors))

    @property
    def live_url(self):
        if not self.live_endpoint:
            return ""
        parsed = urlparse(self.live_endpoint)
        return f"wss://{parsed.netloc}{parsed.path}/openai/v1/live/sessions"

    def credential(self):
        if self.auth_mode == "managed_identity":
            from azure.identity import ManagedIdentityCredential

            kwargs = {"client_id": self.managed_identity_client_id} if self.managed_identity_client_id else {}
            return ManagedIdentityCredential(**kwargs)
        if not self.subscription:
            raise ConfigError("POC_AZ_SUBSCRIPTION is required; default subscription is not used.")
        from voice_poc.auth import AzTokenCredential

        return AzTokenCredential(subscription=self.subscription)
