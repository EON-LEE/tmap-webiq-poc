"""Run in a fresh process; the only transport is an in-memory SDK fake."""

import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
from azure.core.settings import settings
from azure.ai.voicelive.aio import VoiceLiveConnection
from azure.ai.voicelive.telemetry import VoiceLiveInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tmap_poc.telemetry import MetadataExporter

PRIVATE = "PRIVATE_TRANSCRIPT_OFFLINE_SENTINEL"


async def main():
    raw, safe = InMemorySpanExporter(), InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(raw))
    provider.add_span_processor(SimpleSpanProcessor(MetadataExporter(safe)))
    trace.set_tracer_provider(provider)
    settings.tracing_implementation = "opentelemetry"
    os.environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"] = "true"
    instrumentor = VoiceLiveInstrumentor()
    instrumentor.instrument(enable_content_recording=False)
    event = {
        "type": "response.audio_transcript.done", "event_id": "event-test",
        "response_id": "voice-response-test", "item_id": "item-test",
        "output_index": 0, "content_index": 0, "transcript": PRIVATE,
    }
    transport = SimpleNamespace(receive=AsyncMock(return_value=aiohttp.WSMessage(
        aiohttp.WSMsgType.TEXT, json.dumps(event), None,
    )))
    connection = VoiceLiveConnection(SimpleNamespace(close=AsyncMock()), transport)
    try:
        with provider.get_tracer("offline").start_as_current_span("offline.voice"):
            await connection.recv()
        raw_spans, safe_spans = raw.get_finished_spans(), safe.get_finished_spans()
        assert len(raw_spans) >= 2
        assert len(raw_spans) == len(safe_spans)
        assert PRIVATE not in "\n".join(s.to_json() for s in safe_spans)
        print(json.dumps({
            "spans_preserved": len(safe_spans),
            "sdk_content_optout_enabled": not instrumentor.is_content_recording_enabled(),
            "sdk_completed_transcript_detected": PRIVATE in "\n".join(s.to_json() for s in raw_spans),
            "private_content_exported": False,
        }))
    finally:
        instrumentor.uninstrument()
        provider.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
