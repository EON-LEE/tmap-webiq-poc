"""Read only this browser's issued trace IDs from the project's telemetry store."""

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import logging
import math
import re
import secrets
import time
from uuid import UUID

import aiohttp
from azure.ai.projects import AIProjectClient
from azure.core.exceptions import AzureError, ResourceNotFoundError

from tmap_poc.config import ConfigError

TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_SPANS = 1000
READ_TIMEOUT = 120
logger = logging.getLogger(__name__)


class TraceReadError(RuntimeError):
    def __init__(self, code, message, status=502):
        super().__init__(message)
        self.code, self.status = code, status


@dataclass
class TraceGrant:
    token_hash: bytes
    expires_at: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    cached_at: float = 0
    cached: dict | None = None


class TraceAccess:
    """Short-lived per-trace capabilities; never accept arbitrary KQL or app IDs."""

    TTL = 4 * 60 * 60
    LIMIT = 128

    def __init__(self, *, clock=time.time):
        self.clock = clock
        self.entries = OrderedDict()

    def _expire(self):
        now = self.clock()
        for key, grant in list(self.entries.items()):
            if grant.expires_at <= now:
                del self.entries[key]

    def issue(self, trace_id):
        if not isinstance(trace_id, str) or not TRACE_ID.fullmatch(trace_id):
            return {}
        self._expire()
        token = secrets.token_urlsafe(32)
        expires = self.clock() + self.TTL
        self.entries[trace_id] = TraceGrant(hashlib.sha256(token.encode()).digest(), expires)
        while len(self.entries) > self.LIMIT:
            self.entries.popitem(last=False)
        return {
            "trace_access_token": token,
            "trace_access_expires_at": datetime.fromtimestamp(expires, timezone.utc).isoformat(),
        }

    def authorize(self, trace_id, token):
        self._expire()
        if not TRACE_ID.fullmatch(trace_id) or not token or len(token) > 128:
            return None
        grant = self.entries.get(trace_id)
        if grant is None or not hmac.compare_digest(grant.token_hash, hashlib.sha256(token.encode()).digest()):
            return None
        return grant


def trace_query(trace_id):
    if not TRACE_ID.fullmatch(trace_id):
        raise ValueError("Invalid trace ID")
    return f"""
union isfuzzy=true requests, dependencies
| where timestamp > ago(1d) and operation_Id == '{trace_id}'
| project id, parent_id=operation_ParentId, name, start_time=timestamp,
    duration_ms=duration, success, role=cloud_RoleName,
    operation=tostring(customDimensions['gen_ai.operation.name']),
    provider=tostring(customDimensions['gen_ai.provider.name']),
    agent_name=tostring(customDimensions['gen_ai.agent.name']),
    model=tostring(customDimensions['gen_ai.request.model']),
    tool_name=tostring(customDimensions['gen_ai.tool.name']),
    input_tokens=todouble(customDimensions['gen_ai.usage.input_tokens']),
    output_tokens=todouble(customDimensions['gen_ai.usage.output_tokens']),
    tool_status=tostring(customDimensions['app.tool.status']),
    timing_scope=tostring(customDimensions['app.timing.scope'])
| extend priority = iff(provider == 'microsoft.foundry'
    or operation in ('invoke_agent', 'execute_tool', 'observe_tool', 'chat', 'generate_content')
    or name == 'navigation.voice.session', 0, 1)
| order by priority asc, start_time asc, id asc
| project-away priority
| take {MAX_SPANS + 1}
""".strip()


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _kind(name, operation):
    if operation == "observe_tool" or name.startswith("observe_tool "):
        return "observation"
    if operation == "invoke_agent" or name.startswith("invoke_agent "):
        return "agent"
    if operation == "execute_tool" or name.startswith("execute_tool "):
        return "tool"
    if operation in ("chat", "generate_content", "inference") or name.startswith(("chat ", "inference ")):
        return "model"
    if name == "navigation.voice.session":
        return "app"
    if operation in ("send", "recv", "connect") or name.startswith(("send ", "recv ", "connect ")):
        return "voice_io"
    return "other"


def normalize_trace(trace_id, payload):
    if not isinstance(payload, dict):
        raise TraceReadError("invalid_query_response", "트레이스 응답 형식을 해석하지 못했습니다.")
    if payload.get("error"):
        raise TraceReadError("partial_query", "트레이스 조회가 일부만 완료됐습니다. 다시 불러와 주세요.")
    tables = payload.get("tables")
    if not isinstance(tables, list) or not tables:
        raise TraceReadError("invalid_query_response", "트레이스 응답 형식을 해석하지 못했습니다.")
    rows = []
    for table in tables:
        if not isinstance(table, dict):
            raise TraceReadError("invalid_query_response", "트레이스 테이블 형식이 올바르지 않습니다.")
        columns = table.get("columns", [])
        if not isinstance(columns, list) or any(not isinstance(column, dict) for column in columns):
            raise TraceReadError("invalid_query_response", "트레이스 열 형식이 올바르지 않습니다.")
        names = [c.get("name") for c in columns]
        if any(not isinstance(name, str) for name in names) or not {"id", "parent_id", "name", "start_time", "duration_ms"} <= set(names):
            raise TraceReadError("invalid_query_response", "트레이스에 필요한 필드가 없습니다.")
        values_list = table.get("rows")
        if not isinstance(values_list, list):
            raise TraceReadError("invalid_query_response", "트레이스 행 형식을 해석하지 못했습니다.")
        for values in values_list:
            if not isinstance(values, list) or len(values) != len(names):
                raise TraceReadError("invalid_query_response", "트레이스 행 형식을 해석하지 못했습니다.")
            rows.append(dict(zip(names, values)))
    spans, seen = [], set()
    for row in rows[:MAX_SPANS]:
        if not isinstance(row["id"], str) or not row["id"] or not isinstance(row["name"], str):
            raise TraceReadError("invalid_query_response", "트레이스의 식별자가 올바르지 않습니다.")
        try:
            start = datetime.fromisoformat(row["start_time"].replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError):
            raise TraceReadError("invalid_query_response", "트레이스의 시각을 해석하지 못했습니다.") from None
        if start.tzinfo is None:
            raise TraceReadError("invalid_query_response", "트레이스의 시간대가 없습니다.")
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        operation = row.get("operation") or ""
        kind = _kind(row["name"], operation)
        origin = (
            "client" if row.get("role") == "navigation-voice-agent"
            else "foundry" if row.get("provider") == "microsoft.foundry"
            else "unknown"
        )
        success = str(row.get("success", "")).lower()
        tool_status = row.get("tool_status")
        status = (
            "error" if success == "false" or tool_status == "failed"
            else "unknown" if tool_status in ("incomplete", "cancelled")
            else "ok" if success == "true" or tool_status == "completed"
            else "unknown"
        )
        attributes = {
            key: row[key][:512] for key in ("tool_name", "agent_name", "model", "operation", "timing_scope")
            if isinstance(row.get(key), str) and row[key]
        }
        for key in ("input_tokens", "output_tokens"):
            value = _number(row.get(key))
            if value is not None:
                attributes[key] = value
        parent = row.get("parent_id")
        spans.append({
            "id": row["id"], "parent_id": parent if isinstance(parent, str) and parent else None,
            "name": row["name"][:512], "start_time": start.isoformat(timespec="milliseconds"),
            "duration_ms": _number(row["duration_ms"]), "status": status,
            "kind": kind, "origin": origin, "attributes": attributes,
        })
    return {
        "trace_id": trace_id, "status": "ready" if spans else "pending",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "foundry_application_insights", "spans": spans,
        "truncated": len(rows) > MAX_SPANS,
    }


class FoundryTraceReader:
    def __init__(self, settings):
        self.settings = settings
        self._application_id = None
        self._credential = None
        self._initialization = None
        self._token_task = None
        self._closed = False
        self._query_slots = asyncio.Semaphore(2)

    @staticmethod
    def _observe_completion(task):
        if not task.cancelled() and task.exception() is not None:
            logger.warning("Trace authentication worker failed (%s)", type(task.exception()).__name__)

    @staticmethod
    def _failed(task):
        return task is not None and task.done() and (task.cancelled() or task.exception() is not None)

    def _worker(self, function, *args):
        task = asyncio.create_task(asyncio.to_thread(function, *args))
        task.add_done_callback(self._observe_completion)
        return task

    async def _query_token(self):
        if self._closed:
            raise TraceReadError("trace_closed", "트레이스 조회 서비스가 종료 중입니다.", 503)
        if self._application_id is None:
            if self._initialization is None or self._failed(self._initialization):
                self._initialization = self._worker(self._resolve_project)
            self._application_id = await asyncio.shield(self._initialization)
        if self._closed:
            raise TraceReadError("trace_closed", "트레이스 조회 서비스가 종료 중입니다.", 503)
        task = self._token_task
        expired = (
            task is not None and task.done() and not self._failed(task)
            and getattr(task.result(), "expires_on", 0) <= time.time() + 30
        )
        if task is None or self._failed(task) or expired:
            self._token_task = self._worker(
                self._credential.get_token, "https://api.applicationinsights.io/.default",
            )
        return await asyncio.shield(self._token_task)

    def _resolve_project(self):
        if self._credential is None:
            self._credential = self.settings.credential()
        with AIProjectClient(
            endpoint=self.settings.project_endpoint, credential=self._credential,
            connection_timeout=10, read_timeout=20, retry_total=0,
        ) as project:
            connection = project.telemetry.get_application_insights_connection_string()
        if not isinstance(connection, str) or not connection.strip():
            raise TraceReadError("trace_not_configured", "프로젝트의 Application Insights 연결을 확인해 주세요.", 503)
        fields = dict(part.split("=", 1) for part in connection.split(";") if "=" in part)
        app_id = next((value.strip() for key, value in fields.items() if key.lower() == "applicationid"), "")
        try:
            return str(UUID(app_id))
        except ValueError:
            raise TraceReadError(
                "missing_application_id", "연결된 Application Insights의 Application ID를 확인해 주세요.", 503,
            ) from None

    async def read(self, trace_id):
        query = trace_query(trace_id)
        try:
            async with asyncio.timeout(READ_TIMEOUT), self._query_slots:
                token = await self._query_token()
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                    async with session.post(
                        f"https://api.applicationinsights.io/v1/apps/{self._application_id}/query",
                        headers={"Authorization": f"Bearer {token.token}"},
                        json={"query": query},
                    ) as response:
                        if response.status in (401, 403):
                            raise TraceReadError(
                                "trace_permission", "Application Insights 트레이스 조회 권한이 필요합니다.", 403,
                            )
                        if response.status == 429:
                            raise TraceReadError("trace_rate_limit", "조회가 많습니다. 잠시 후 다시 불러와 주세요.", 429)
                        if response.status != 200:
                            raise TraceReadError("trace_query_failed", "트레이스 저장소에서 조회하지 못했습니다.")
                        payload = await response.json()
                return normalize_trace(trace_id, payload)
        except ResourceNotFoundError:
            raise TraceReadError(
                "trace_not_configured", "Foundry 프로젝트에서 Agents → Traces → Connect를 먼저 설정하세요.", 503,
            ) from None
        except (ConfigError, AzureError, RuntimeError) as exc:
            if isinstance(exc, TraceReadError):
                raise
            raise TraceReadError(
                "trace_credentials", "트레이스 조회 인증 또는 프로젝트 연결을 확인해 주세요.", 503,
            ) from None
        except (aiohttp.ClientError, TimeoutError, ValueError):
            raise TraceReadError("trace_unavailable", "트레이스를 불러오지 못했습니다. 연결 상태를 확인하세요.") from None

    async def close(self):
        self._closed = True
        tasks = [task for task in (self._initialization, self._token_task) if task is not None]
        if tasks:
            await asyncio.gather(*(asyncio.shield(task) for task in tasks), return_exceptions=True)
        close = getattr(self._credential, "close", None)
        if close is not None:
            await asyncio.to_thread(close)


class TraceSocket:
    def __init__(self, socket, access):
        self.socket, self.access = socket, access

    async def receive(self):
        return await self.socket.receive()

    async def send_json(self, event):
        if event.get("type") == "trace":
            event = {**event, **self.access.issue(event.get("trace_id"))}
        await self.socket.send_json(event)
