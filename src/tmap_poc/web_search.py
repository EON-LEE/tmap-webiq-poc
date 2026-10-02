"""Call the Bing-based Web Search tool of a Foundry Toolbox over MCP from the app server.

Voice Live's MCP client drops the Toolbox's embedded-resource result, so End-to-end sessions expose a
`web_search` function to the model and the app runs it here, returning plain text the model can read.
"""

import asyncio
import json
from time import time

import aiohttp

from tmap_poc.config import ConfigError

SCOPE = "https://ai.azure.com/.default"
_TIMEOUT_SECONDS = 45
_MAX_ANSWER_CHARS = 6000
_MAX_CITATIONS = 12


class WebSearchError(RuntimeError):
    """The Toolbox search could not return a result; the message is safe to show and to give the model."""


class ToolboxWebSearch:
    def __init__(self, settings, credential=None):
        if not settings.web_search_toolbox_url:
            raise ConfigError("TMAP_WEB_SEARCH_TOOLBOX가 없어 Bing 웹 검색을 사용할 수 없습니다.")
        self.url = settings.web_search_toolbox_url
        self.credential = credential or settings.credential()
        self._token = None

    async def _bearer(self):
        # Reuse the Entra token until five minutes before it expires.
        if self._token is None or self._token.expires_on - 300 < time():
            self._token = await asyncio.to_thread(self.credential.get_token, SCOPE)
        return self._token.token

    async def _rpc(self, http, body, session_id=None):
        headers = {
            "Authorization": f"Bearer {await self._bearer()}",
            "Accept": "application/json, text/event-stream",
        }
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        async with http.post(self.url, json=body, headers=headers) as response:
            text = await response.text()
            if response.status >= 400:
                raise WebSearchError(f"Bing 웹 검색이 응답하지 않았습니다 (HTTP {response.status}).")
            return response.headers.get("Mcp-Session-Id") or session_id, _payload(text)

    async def search(self, query):
        """Return {"text": answer, "citations": [{"type": "url_citation", "url", "title"}]}."""
        timeout = aiohttp.ClientTimeout(total=_TIMEOUT_SECONDS)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as http:
                session_id, _ = await self._rpc(http, {
                    "jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                               "clientInfo": {"name": "tmap-voice-demo", "version": "1"}},
                })
                await self._rpc(http, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session_id)
                _, reply = await self._rpc(http, {
                    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "web_search", "arguments": {"search_query": query}},
                }, session_id)
        except WebSearchError:
            raise
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise WebSearchError("Bing 웹 검색에 연결하지 못했습니다.") from exc
        if not isinstance(reply, dict) or "error" in reply:
            raise WebSearchError("Bing 웹 검색이 오류를 반환했습니다.")
        return result_text(reply.get("result"))


def _payload(text):
    # Streamable HTTP answers with JSON or with server-sent events.
    if not text.strip():
        return {}
    if text.lstrip().startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return {}


def result_text(result):
    """Flatten MCP text and embedded-resource content with its url_citation annotations."""
    texts, citations, seen = [], [], set()
    for item in (result or {}).get("content") or []:
        if not isinstance(item, dict):
            continue
        resource = item.get("resource") if isinstance(item.get("resource"), dict) else {}
        text = item.get("text") if isinstance(item.get("text"), str) else resource.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
        meta = item.get("_meta") if isinstance(item.get("_meta"), dict) else {}
        for note in meta.get("annotations") or []:
            url = note.get("url") if isinstance(note, dict) else None
            if note.get("type") == "url_citation" and isinstance(url, str) and url.startswith("https://") and url not in seen:
                seen.add(url)
                title = note.get("title") if isinstance(note.get("title"), str) else ""
                citations.append({"type": "url_citation", "url": url, "title": title[:200]})
    if not texts:
        raise WebSearchError("Bing 웹 검색 결과가 비어 있습니다.")
    return {"text": "\n\n".join(texts)[:_MAX_ANSWER_CHARS], "citations": citations[:_MAX_CITATIONS]}
