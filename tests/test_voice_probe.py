import base64
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "check_voice_connection", Path(__file__).resolve().parents[1] / "scripts" / "check_voice_connection.py",
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class VoiceProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialization_check_does_not_request_inference(self):
        result = {}
        socket = probe.ProbeSocket(None, result)
        await socket.send_json({"type": "status", "state": "ready"})
        request = json.loads((await socket.receive())["text"])
        self.assertEqual(request, {"type": "stop"})
        self.assertTrue(result["ready"])

    async def test_prompt_mode_submits_exactly_the_requested_text(self):
        socket = probe.ProbeSocket("test input", {})
        await socket.send_json({"type": "status", "state": "ready"})
        request = json.loads((await socket.receive())["text"])
        self.assertEqual(request, {"type": "text", "text": "test input"})

    async def test_audio_is_counted_not_retained_and_final_replaces_deltas(self):
        result = {"audio_bytes": 0}
        socket = probe.ProbeSocket(None, result)
        await socket.send_json({"type": "audio", "data": base64.b64encode(b"\x00\x01").decode()})
        await socket.send_json({"type": "transcript", "role": "assistant", "item_id": "i", "text": "part", "final": False})
        await socket.send_json({"type": "transcript", "role": "assistant", "item_id": "i", "text": "whole answer", "final": True})
        self.assertEqual(result, {"audio_bytes": 2})
        self.assertEqual(socket.messages, {"i": "whole answer"})


if __name__ == "__main__":
    unittest.main()
