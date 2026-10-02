"""Explicit, small Voice Live check using the configured Foundry agents.

Without --prompt this only initializes a session. Supplying --prompt requests
real search/model/audio work. Audio bytes are counted, never written to disk.
"""

import argparse
import asyncio
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import aiohttp
from azure.core.exceptions import AzureError

from tmap_poc.app_settings import AppSettings
from tmap_poc.config import ConfigError, load_dotenv
from tmap_poc.profiles import PROVIDER_LABELS
from tmap_poc.voice import VoiceProtocolError, VoiceServiceError, VoiceSession
from tmap_poc.voice_options import VoiceOptionsError, validate_options


class ProbeSocket:
    def __init__(self, prompt, result):
        self.queue = asyncio.Queue()
        self.prompt = prompt
        self.result = result
        self.messages = {}

    async def receive(self):
        return await self.queue.get()

    async def stop(self):
        await self.queue.put({"type": "websocket.receive", "text": '{"type":"stop"}'})

    async def send_json(self, event):
        kind = event.get("type")
        if kind == "status" and event.get("state") == "ready":
            self.result["ready"] = True
            if self.prompt:
                await self.queue.put({
                    "type": "websocket.receive",
                    "text": json.dumps({"type": "text", "text": self.prompt}),
                })
            else:
                await self.stop()
        elif kind == "audio":
            self.result["audio_bytes"] += len(base64.b64decode(event["data"], validate=True))
        elif kind == "transcript" and event.get("role") == "assistant":
            item = event.get("item_id", "assistant")
            self.messages[item] = (
                event["text"] if event["final"] else self.messages.get(item, "") + event["text"]
            )
        elif kind == "citation":
            self.result["citations"].append({"url": event["url"], "title": event["title"]})
        elif kind == "tool":
            self.result["observed_tools"].append({
                key: event.get(key) for key in ("kind", "name", "status")
            })
        elif kind == "usage":
            self.result["usage"].append(event["usage"])


class ProbeSession(VoiceSession):
    def __init__(self, *args, result, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = result
        self.agent_call_completed = False

    async def handle_event(self, event, connection, socket):
        kind = event.get("type", "unknown")
        counts = self.result["service_events"]
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "error":
            detail = event.get("error") or {}
            self.result["service_error_code"] = detail.get("code")
        if kind == "response.foundry_agent_call.completed":
            self.agent_call_completed = True
            self.result["foundry_agent_call_completed"] = True
            if event.get("agent_response_id"):
                self.result["foundry_agent_response_id"] = event["agent_response_id"]
        if kind == "response.done":
            response = event.get("response") or {}
            self.result["response_status"] = response.get("status")
            error = (response.get("status_details") or {}).get("error") or {}
            if error.get("code"):
                self.result["service_error_code"] = error["code"]
        await super().handle_event(event, connection, socket)
        if kind == "response.done":
            native = self.options.get("connection_mode") == "realtime_agent_tool"
            has_call = any(
                "call" in item.get("type", "") for item in response.get("output", []) if isinstance(item, dict)
            )
            if not native or (
                self.agent_call_completed and not has_call
                and self.result["audio_bytes"] > 0 and bool(socket.messages)
            ):
                await socket.stop()


async def check(settings, provider, prompt, timeout, *, voice_options=None):
    chosen = validate_options({} if voice_options is None else voice_options, settings.voice_name)
    result = {
        "provider": provider, "started_at": datetime.now(timezone.utc).isoformat(),
        "input_mode": "text" if prompt else "session_initialization_only",
        "prompt": prompt, "ready": False, "audio_bytes": 0,
        "microphone_tested": False, "audio_playback_tested": False,
        "answer_quality_evaluated": False,
        "usage_scope": "Client-visible Voice Live responses; delegated Foundry model usage may require separate server traces.",
        "citations": [], "observed_tools": [], "usage": [], "service_events": {},
        "voice_options": chosen,
    }
    started = time.perf_counter()
    socket = ProbeSocket(prompt, result)
    try:
        result["end_reason"] = await asyncio.wait_for(
            ProbeSession(settings, provider, result=result, voice_options=chosen).run(socket), timeout=timeout,
        )
    except (VoiceServiceError, VoiceProtocolError, ConfigError, AzureError, aiohttp.ClientError, TimeoutError) as exc:
        result["error_type"] = type(exc).__name__
    result["assistant_text"] = list(socket.messages.values())
    result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    result["success"] = result["ready"] and not result.get("error_type") and (
        not prompt or (
            result.get("response_status") == "completed"
            and result["audio_bytes"] > 0 and bool(socket.messages)
        )
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--provider", choices=tuple(PROVIDER_LABELS))
    parser.add_argument("--prompt", help="Makes a real paid search/model/audio request.")
    parser.add_argument("--timeout", type=float, default=150)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--voice-options", type=json.loads, default={}, help="JSON object of speech-layer settings.")
    args = parser.parse_args()
    if args.timeout <= 0 or (args.prompt is not None and (not args.prompt.strip() or len(args.prompt) > 4000)):
        parser.error("Use a positive timeout and a nonempty prompt of up to 4000 characters.")
    load_dotenv(args.env_file)
    settings = AppSettings.from_env()
    try:
        chosen = validate_options(args.voice_options, settings.voice_name)
    except VoiceOptionsError as exc:
        parser.error(str(exc))
    providers = [args.provider] if args.provider else list(PROVIDER_LABELS)
    if args.out and args.out.exists():
        parser.error("--out must not overwrite an existing result")
    results = []
    for provider in providers:
        result = asyncio.run(check(settings, provider, args.prompt, args.timeout, voice_options=chosen))
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as output:
            json.dump({"checks": results}, output, ensure_ascii=False, indent=2)
    if not all(result["success"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
