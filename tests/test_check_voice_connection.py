import base64
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "check_voice_connection", Path(__file__).resolve().parents[1] / "scripts" / "check_voice_connection.py",
)
check_voice_connection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_voice_connection)


class CheckVoiceConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialization_check_does_not_request_inference(self):
        result = {}
        socket = check_voice_connection.CheckSocket(None, result)
        await socket.send_json({"type": "status", "state": "ready"})
        request = json.loads((await socket.receive())["text"])
        self.assertEqual(request, {"type": "stop"})
        self.assertTrue(result["ready"])

    async def test_prompt_mode_submits_exactly_the_requested_text(self):
        socket = check_voice_connection.CheckSocket("test input", {})
        await socket.send_json({"type": "status", "state": "ready"})
        request = json.loads((await socket.receive())["text"])
        self.assertEqual(request, {"type": "text", "text": "test input"})

    async def test_audio_is_counted_not_retained_and_final_replaces_deltas(self):
        result = {"audio_bytes": 0}
        socket = check_voice_connection.CheckSocket(None, result)
        await socket.send_json({"type": "audio", "data": base64.b64encode(b"\x00\x01").decode()})
        await socket.send_json({"type": "transcript", "role": "assistant", "item_id": "i", "text": "part", "final": False})
        await socket.send_json({"type": "transcript", "role": "assistant", "item_id": "i", "text": "whole answer", "final": True})
        self.assertEqual(result, {"audio_bytes": 2})
        self.assertEqual(socket.messages, {"i": "whole answer"})

    async def test_only_agent_and_end_to_end_modes_are_accepted(self):
        for mode in ("model_search", "model_tools"):
            with self.subTest(mode=mode), self.assertRaises(check_voice_connection.VoiceOptionsError):
                await check_voice_connection.check(
                    check_voice_connection.AppSettings(), "bing", None, 1, voice_options={"connection_mode": mode},
                )
        for mode in ("agent", "end_to_end"):
            with self.subTest(mode=mode):
                chosen = check_voice_connection.validate_options({"connection_mode": mode}, "ko-KR-SunHiNeural")
                self.assertEqual(chosen["connection_mode"], mode)


if __name__ == "__main__":
    unittest.main()
