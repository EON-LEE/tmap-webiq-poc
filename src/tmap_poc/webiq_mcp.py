"""Resolve the direct WebIQ MCP Voice Live target from the configured Foundry Agent."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from time import monotonic

from tmap_poc.config import ConfigError

_ERROR = "WebIQ 연결 정보를 확인하지 못했습니다. Foundry 프로젝트의 WebIQ 연결과 권한을 확인하세요."
_TTL_SECONDS = 600
_TIMEOUT_SECONDS = 20
_CACHE = {}
_LOCK = asyncio.Lock()


@dataclass(frozen=True)
class WebIQMCPTarget(Mapping):
    server_url: str
    headers: dict[str, str] = field(repr=False)

    def __iter__(self):
        yield "server_url"
        yield "headers"

    def __len__(self):
        return 2

    def __getitem__(self, key):
        if key == "server_url":
            return self.server_url
        if key == "headers":
            return self.headers
        raise KeyError(key)

    def __repr__(self):
        return f"WebIQMCPTarget(server_url={self.server_url!r}, headers=<redacted>)"


def _extract_target(settings, agent):
    from azure.ai.projects import AIProjectClient

    with AIProjectClient(endpoint=settings.project_endpoint, credential=settings.credential()) as client:
        version = client.agents.get_version(agent_name=agent.name, agent_version=agent.version)
        definition = version.as_dict().get("definition") if hasattr(version, "as_dict") else None
        tools = definition.get("tools") if isinstance(definition, dict) else None
        tool = next(
            (
                item for item in tools or []
                if isinstance(item, dict)
                and item.get("type") == "mcp"
                and isinstance(item.get("server_url"), str)
                and isinstance(item.get("project_connection_id"), str)
            ),
            None,
        )
        if tool is None:
            raise ConfigError(_ERROR)
        connection_name = tool["project_connection_id"].rstrip("/").rsplit("/", 1)[-1]
        connection = client.connections.get(name=connection_name, include_credentials=True)
        data = connection.as_dict() if hasattr(connection, "as_dict") else {}
        credentials = data.get("credentials") if isinstance(data, dict) else None
        key = credentials.get("x-apikey") if isinstance(credentials, dict) else None
        if not isinstance(key, str) or not key:
            raise ConfigError(_ERROR)
        return WebIQMCPTarget(tool["server_url"], {"x-apikey": key})


async def resolve_webiq_mcp_target(settings, agent):
    """Return a cached MCP target for WebIQ without exposing credentials in errors."""
    if agent is None:
        raise ConfigError(_ERROR)
    cache_key = (settings.project_endpoint, agent.name, agent.version)
    now = monotonic()
    cached = _CACHE.get(cache_key)
    if cached is not None and now - cached[0] < _TTL_SECONDS:
        return cached[1]
    async with _LOCK:
        now = monotonic()
        cached = _CACHE.get(cache_key)
        if cached is not None and now - cached[0] < _TTL_SECONDS:
            return cached[1]
        try:
            target = await asyncio.wait_for(
                asyncio.to_thread(_extract_target, settings, agent),
                timeout=_TIMEOUT_SECONDS,
            )
        except ConfigError:
            raise
        except Exception as exc:
            raise ConfigError(_ERROR) from exc
        _CACHE[cache_key] = (monotonic(), target)
        return target
