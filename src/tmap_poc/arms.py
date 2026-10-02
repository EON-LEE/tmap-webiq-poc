"""The three arms: same agent, different search tool.

The previous benchmark compared a hand-wired Web IQ pipeline against a
Grounding with Bing *agent*, which is not a tool comparison. A routing table
in the repo picked the vertical, retrieval was forced on every question, the
utterance went to the API verbatim and exactly one search was ever issued --
all decisions the Bing arm had to make for itself, and pay for. Here the
agent makes them on every arm and only the ``tools`` array changes.

``A`` bing_grounding, resolved inside the service.
``B`` Web IQ over MCP, called by the service.
``C`` Web IQ over MCP, called by this process via function calling.

B and C hit the same MCP endpoint with the same arguments, so a difference
between them is integration overhead rather than search quality -- which is
the only way to attribute a gap to the right cause. C additionally shows what
client-side control buys: it is the one arm where a query policy can be
*enforced* rather than merely requested.

Verticals are not restricted. The published reference lists five tools and no
Places or Finance; the live server exposes ten including both, and an agent
given the choice reached for ``places`` unprompted. Letting the agent choose
is what turns vertical routing into a measured behaviour instead of an
assumption baked into a config file.
"""

from __future__ import annotations

import json
import os
import time

import requests

MCP_URL = "https://api.microsoft.ai/v3/mcp"

#: Query-taking verticals exposed by the live MCP server. ``browse`` is listed
#: separately because it takes a URL rather than a query.
VERTICALS = ("web", "news", "places", "finance", "sonic",
             "videos", "images", "sports", "autosuggest")

_VERTICAL_HELP = """검색할 버티컬:
- web: 일반 웹 검색. 무엇을 쓸지 애매하면 이것.
- news: 뉴스 기사. 최근 14일 이내 결과만 반환됨.
- places: 장소·매장 정보(주소, 영업시간, 전화번호, 좌표).
- finance: 주가·환율·지수 등 금융 상품 시세.
- sonic: 여러 버티컬을 섞어 랭킹한 검색.
- videos / images / sports / autosuggest: 각 이름에 해당하는 검색."""

FUNCTION_TOOLS = [
    {
        "type": "function",
        "name": "web_search",
        "description": "웹에서 최신 정보를 검색합니다. 답변에 필요한 근거를 얻으려면 이 도구를 사용하세요.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색어"},
                "vertical": {"type": "string", "enum": list(VERTICALS),
                             "description": _VERTICAL_HELP},
                "language": {"type": "string", "description": "언어 코드. 한국어는 ko."},
                "region": {"type": "string", "description": "지역 코드. 한국은 KR."},
            },
            "required": ["query", "vertical"],
        },
    },
    {
        "type": "function",
        "name": "browse",
        "description": "특정 URL의 본문을 가져옵니다. 검색 결과의 링크를 더 자세히 확인할 때 사용하세요.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "가져올 페이지 URL"}},
            "required": ["url"],
        },
    },
]


def tools_for(arm: str):
    if arm == "A":
        return [{
            "type": "bing_grounding",
            "bing_grounding": {"search_configurations": [{
                "project_connection_id": os.environ["GWB_CONNECTION_ID"],
                "market": "ko-KR", "set_lang": "ko", "count": 5,
            }]},
        }]
    if arm == "B":
        return [{
            "type": "mcp",
            "server_label": "webiq",
            "server_url": MCP_URL,
            "project_connection_id": os.environ["WEBIQ_CONNECTION_ID"],
            "require_approval": "never",
        }]
    if arm == "C":
        return list(FUNCTION_TOOLS)
    raise ValueError(f"unknown arm {arm!r}")


ARM_LABELS = {
    "A": "GwB (서비스 내장)",
    "B": "Web IQ / MCP (서비스 호출)",
    "C": "Web IQ / 함수 (클라이언트 호출)",
}


class WebIQMCP:
    """Direct MCP client for arm C.

    Pooled deliberately. An unpooled client opens a fresh TCP+TLS connection
    per call, measured at roughly 2.1s of setup on this network, which is
    larger than the search itself and would be charged to arm C alone --
    reproducing the exact artefact that previously biased the comparison.
    """

    def __init__(self, api_key=None, timeout=45):
        self._key = api_key or os.environ["WEBIQ_API_KEY"]
        self._timeout = timeout
        self._session = requests.Session()
        self._id = 0

    def call(self, tool: str, arguments: dict):
        """Returns ``(payload, elapsed_ms, error)``."""
        from tmap_poc.telemetry import tool_execution

        with tool_execution(f"webiq.{tool}") as span:
            result = self._call(tool, arguments)
            if result[2] is not None:
                from opentelemetry.trace import Status, StatusCode

                span.set_status(Status(StatusCode.ERROR))
            return result

    def _call(self, tool: str, arguments: dict):
        self._id += 1
        started = time.perf_counter()
        try:
            response = self._session.post(
                MCP_URL,
                headers={"content-type": "application/json",
                         "accept": "application/json, text/event-stream",
                         "x-apikey": self._key},
                json={"jsonrpc": "2.0", "method": "tools/call",
                      "params": {"name": tool, "arguments": arguments},
                      "id": self._id},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            return None, (time.perf_counter() - started) * 1000, str(exc)[:200]
        elapsed = (time.perf_counter() - started) * 1000

        if response.status_code >= 400:
            return None, elapsed, f"HTTP {response.status_code}"
        body = response.text
        if "data:" in body[:200]:
            for line in body.splitlines():
                if line.startswith("data: "):
                    body = line[6:]
                    break
        try:
            payload = json.loads(body)
        except ValueError:
            return None, elapsed, f"HTTP {response.status_code}: {body[:200]}"
        if "error" in payload:
            return None, elapsed, json.dumps(payload["error"], ensure_ascii=False)[:300]
        return payload.get("result"), elapsed, None

    def execute(self, name: str, arguments: dict):
        """Run one agent-issued function call and return text for the model."""
        if name == "browse":
            tool, args = "browse", {"url": arguments.get("url", "")}
        else:
            tool = arguments.get("vertical") or "web"
            if tool not in VERTICALS:
                tool = "web"
            args = {"query": arguments.get("query", ""),
                    "language": arguments.get("language") or "ko",
                    "region": arguments.get("region") or "KR"}
        result, elapsed, error = self.call(tool, args)
        if error:
            return f"검색 실패: {error}", tool, elapsed, error
        content = (result or {}).get("structuredContent") or result or {}
        return (json.dumps(content, ensure_ascii=False)[:60000],
                tool, elapsed, None)
