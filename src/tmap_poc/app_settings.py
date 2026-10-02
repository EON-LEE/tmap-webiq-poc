"""Explicit application settings; cloud calls are never made on import."""

import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from tmap_poc.config import ConfigError
from tmap_poc.profiles import AgentReference, PROVIDER_LABELS
from tmap_poc.voice_options import CONNECTION_MODES, MODEL_MODE


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
    agents: dict[str, AgentReference] = field(default_factory=dict)
    allowed_origins: tuple[str, ...] = (
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    )

    @classmethod
    def from_env(cls):
        mode = _value("TMAP_AUTH_MODE", "cli")
        if mode not in ("cli", "managed_identity"):
            raise ConfigError("TMAP_AUTH_MODE must be cli or managed_identity")
        agents = {}
        for provider in PROVIDER_LABELS:
            prefix = f"TMAP_{provider.upper()}_AGENT"
            name, version = _value(prefix + "_NAME"), _value(prefix + "_VERSION")
            if version and not name:
                raise ConfigError(f"{prefix}_VERSION requires {prefix}_NAME")
            if name:
                agents[provider] = AgentReference(name, version or None)
        origins = _value(
            "TMAP_ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
        )
        allowed_origins = tuple(part.strip().rstrip("/") for part in origins.split(",") if part.strip())
        for origin in allowed_origins:
            parsed = urlparse(origin)
            if (
                parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.path
                or parsed.query or parsed.fragment
            ):
                raise ConfigError("TMAP_ALLOWED_ORIGINS must contain exact HTTP(S) origins.")
        if not allowed_origins:
            raise ConfigError("TMAP_ALLOWED_ORIGINS must not be empty.")
        toolbox = _value("TMAP_WEB_SEARCH_TOOLBOX")
        if toolbox and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", toolbox):
            raise ConfigError("TMAP_WEB_SEARCH_TOOLBOX must be a Foundry toolbox name.")
        return cls(
            project_endpoint=_https(_value("GWB_PROJECT_ENDPOINT"), "GWB_PROJECT_ENDPOINT"),
            voice_endpoint=_https(_value("TMAP_VOICE_ENDPOINT"), "TMAP_VOICE_ENDPOINT"),
            model=_value("TMAP_POC_MODEL_DEPLOYMENT"),
            subscription=_value("TMAP_POC_AZ_SUBSCRIPTION"),
            auth_mode=mode,
            managed_identity_client_id=_value("AZURE_CLIENT_ID"),
            voice_name=_value("TMAP_VOICE_NAME", "ko-KR-SunHiNeural"),
            foundry_resource_override=_value("TMAP_VOICE_FOUNDRY_RESOURCE_OVERRIDE"),
            agent_identity_client_id=_value("TMAP_VOICE_AGENT_IDENTITY_CLIENT_ID"),
            web_search_toolbox=toolbox,
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
                f"TMAP_{provider.upper()}_AGENT_VERSION is not pinned; the service selects the version."
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

    def problems(self, provider=None, *, voice=True, connection_mode="agent"):
        if connection_mode not in CONNECTION_MODES:
            raise ConfigError("Unknown voice connection mode")
        needs_agent = connection_mode != MODEL_MODE
        errors = []
        if needs_agent and not self.project_name:
            errors.append("GWB_PROJECT_ENDPOINT must identify a Foundry project.")
        if self.auth_mode == "cli" and not self.subscription:
            errors.append("TMAP_POC_AZ_SUBSCRIPTION is required for local CLI authentication.")
        if voice and not self.voice_endpoint:
            errors.append("TMAP_VOICE_ENDPOINT is required for Voice Live.")
        if voice and not self.voice_name:
            errors.append("TMAP_VOICE_NAME must identify the server's default voice.")
        if not voice and not self.model:
            errors.append("TMAP_POC_MODEL_DEPLOYMENT is required.")
        if needs_agent and provider is not None and provider not in self.agents:
            errors.append(f"Configure TMAP_{provider.upper()}_AGENT_NAME first.")
        return errors

    def require(self, provider=None, *, voice=True, connection_mode="agent"):
        if provider is not None and provider not in PROVIDER_LABELS:
            raise ConfigError("Unknown search provider")
        errors = self.problems(provider, voice=voice, connection_mode=connection_mode)
        if errors:
            raise ConfigError(" ".join(errors))

    def credential(self):
        if self.auth_mode == "managed_identity":
            from azure.identity import ManagedIdentityCredential

            kwargs = {"client_id": self.managed_identity_client_id} if self.managed_identity_client_id else {}
            return ManagedIdentityCredential(**kwargs)
        if not self.subscription:
            raise ConfigError("TMAP_POC_AZ_SUBSCRIPTION is required; default subscription is not used.")
        from tmap_poc.auth import AzTokenCredential

        return AzTokenCredential(subscription=self.subscription)
