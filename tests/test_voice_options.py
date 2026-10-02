import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

from azure.ai.voicelive.aio import VoiceLiveConnection, connect
from azure.ai.voicelive.models import (
    AudioInputTranscriptionOptions,
    AzureSemanticVadMultilingual,
    AzureStandardVoice,
    OpenAIVoice,
    RequestSession,
)

from tmap_poc.voice_options import (
    VoiceOptionsError,
    build_model_session,
    build_search_session,
    build_session_options,
    option_schema,
    validate_options,
)


DEFAULT_VOICE = "ko-KR-SunHiNeural"
AGENT_CONFIG = {
    "agent_name": "existing-bing",
    "agent_version": "3",
    "project_name": "existing-project",
    "foundry_resource_override": "existing-koreacentral-host",
    "client_id": "00000000-0000-0000-0000-000000000001",
}


class VoiceOptionsTests(unittest.TestCase):
    def session(self, values=None, default_voice=DEFAULT_VOICE):
        chosen = validate_options(values or {}, default_voice)
        if chosen["connection_mode"] in ("model_search", "realtime_agent_tool"):
            return build_search_session(chosen, AGENT_CONFIG).as_dict()
        if chosen["connection_mode"] == "model_tools":
            return build_model_session(chosen).as_dict()
        return build_session_options(chosen).as_dict()

    def test_defaults_match_previous_actual_sdk_payload_exactly(self):
        previous = RequestSession(
            modalities=["text", "audio"],
            input_audio_format="pcm16",
            output_audio_format="pcm16",
            input_audio_sampling_rate=24000,
            input_audio_transcription=AudioInputTranscriptionOptions(
                model="azure-speech", language="ko-KR",
            ),
            voice=AzureStandardVoice(name=DEFAULT_VOICE),
            turn_detection=AzureSemanticVadMultilingual(
                create_response=True, interrupt_response=True,
            ),
        )
        self.assertEqual(self.session(), previous.as_dict())
        self.assertNotIn("rate", self.session()["voice"])
        self.assertEqual(
            self.session()["turn_detection"],
            {"type": "azure_semantic_vad_multilingual", "create_response": True, "interrupt_response": True},
        )

    def test_schema_defaults_round_trip_to_identical_wire(self):
        schema = json.loads(json.dumps(option_schema(DEFAULT_VOICE), allow_nan=False))
        fields = schema["fields"]
        self.assertEqual(schema["mode"], "foundry_agent")
        self.assertEqual({f["key"]: f["default"] for f in fields}, schema["defaults"])
        self.assertEqual(self.session(schema["defaults"]), self.session())
        self.assertEqual(set(schema["defaults"]), set(validate_options({}, DEFAULT_VOICE)))
        self.assertTrue(schema["unavailable_options"][0]["disabled"])
        self.assertEqual(schema["unavailable_options"][0]["requires"], {"connection_mode": "agent"})
        self.assertEqual(schema["unavailable_options"][0]["availability"], "unverified_for_fixed_agent")
        self.assertNotIn("speech_model", schema["defaults"])
        self.assertEqual(schema["fixed_by_mode"]["agent"]["tool_executor"], "Foundry Agent")
        self.assertNotIn("voice_type", schema["fixed"])
        for mode, values in schema["defaults_by_mode"].items():
            self.assertEqual(values["connection_mode"], mode)
            self.assertEqual(values, validate_options(values, DEFAULT_VOICE))

    def test_sdk_allows_model_and_agent_query_without_proving_service_semantics(self):
        manager = connect(
            credential=object(), endpoint="https://voice.example.invalid",
            model="gpt-realtime", agent_name="existing-agent", project_name="existing-project",
        )
        query = parse_qs(urlparse(manager._prepare_url()).query)
        self.assertEqual(query["model"], ["gpt-realtime"])
        self.assertEqual(query["agent-name"], ["existing-agent"])
        self.assertEqual(query["agent-project-name"], ["existing-project"])

    def test_openai_voice_is_real_sdk_schema_but_not_an_enabled_agent_choice(self):
        sdk_payload = RequestSession(voice=OpenAIVoice(name="alloy")).as_dict()
        self.assertEqual(sdk_payload, {"voice": {"type": "openai", "name": "alloy"}})
        with self.assertRaises(VoiceOptionsError):
            validate_options({"voice_type": "openai", "voice_name": "alloy"}, DEFAULT_VOICE)

    def test_schema_is_fresh_and_input_is_not_mutated(self):
        original = {"speech_rate": 1.25}
        normalized = validate_options(original, DEFAULT_VOICE)
        self.assertEqual(original, {"speech_rate": 1.25})
        normalized["transcription_model"] = "changed"
        schema = option_schema(DEFAULT_VOICE)
        schema["fields"][0]["options"].clear()
        schema["defaults"]["transcription_model"] = "changed"
        self.assertEqual(validate_options({}, DEFAULT_VOICE)["transcription_model"], "azure-speech")
        self.assertEqual(len(option_schema(DEFAULT_VOICE)["fields"][0]["options"]), 4)

    def test_arbitrary_server_configured_default_voice_is_preserved(self):
        configured = "en-GB-ServerConfiguredNeural"
        normalized = validate_options({}, configured)
        self.assertEqual(normalized["voice_name"], configured)
        self.assertEqual(self.session(default_voice=configured)["voice"]["name"], configured)
        voices = next(f["options"] for f in option_schema(configured)["fields"] if f["key"] == "voice_name")
        self.assertIn(configured, [v["value"] for v in voices])
        with self.assertRaises(VoiceOptionsError):
            validate_options({"voice_name": configured}, DEFAULT_VOICE)

    def test_tts_family_uses_real_voice_name_and_string_rate_not_model(self):
        for name in (
            "ko-KR-SunHiNeural", "ko-KR-InJoonNeural",
            "ko-KR-SunHi:DragonHDLatestNeural", "ko-KR-Hyunsu:DragonHDLatestNeural",
        ):
            with self.subTest(name=name):
                data = self.session({"voice_name": name, "speech_rate": 1.25})
                self.assertEqual(data["voice"], {"type": "azure-standard", "name": name, "rate": "1.25"})
                self.assertNotIn("tts_model", data)
                self.assertNotIn("model", data)

    def test_mai_transcribe_uses_documented_agent_model_alias_and_korean_code(self):
        self.assertEqual(
            self.session({"transcription_model": "mai-transcribe"})["input_audio_transcription"],
            {"model": "mai-transcribe", "language": "ko"},
        )

    def test_rate_serialization_does_not_round_accepted_input(self):
        rate = 0.5000000000000001
        self.assertEqual(float(self.session({"speech_rate": rate})["voice"]["rate"]), rate)

    def test_semantic_latency_options_use_real_nested_sdk_fields(self):
        data = self.session({
            "silence_duration_ms": 250, "vad_threshold": 0.35,
            "semantic_threshold": "high", "interrupt_response": False,
        })
        self.assertEqual(data["turn_detection"], {
            "type": "azure_semantic_vad_multilingual", "create_response": True,
            "interrupt_response": False, "silence_duration_ms": 250, "threshold": 0.35,
            "end_of_utterance_detection": {
                "model": "semantic_detection_v1_multilingual", "threshold_level": "high",
            },
        })

    def test_normal_vad_uses_only_selected_detection_and_threshold(self):
        data = self.session({
            "turn_detection": "server_vad", "silence_duration_ms": 800,
            "vad_threshold": 0.7, "interrupt_response": False,
        })
        self.assertEqual(data["turn_detection"], {
            "type": "server_vad", "create_response": True, "interrupt_response": False,
            "silence_duration_ms": 800, "threshold": 0.7,
        })

    def test_audio_filters_distinguish_inherit_enabled_and_explicitly_disabled(self):
        default = self.session()
        self.assertNotIn("input_audio_noise_reduction", default)
        self.assertNotIn("input_audio_echo_cancellation", default)
        enabled = self.session({"input_noise_reduction": True, "echo_cancellation": True})
        self.assertEqual(enabled["input_audio_noise_reduction"], {"type": "azure_deep_noise_suppression"})
        self.assertEqual(enabled["input_audio_echo_cancellation"], {"type": "server_echo_cancellation"})
        disabled = self.session({"input_noise_reduction": False, "echo_cancellation": False})
        self.assertIn("input_audio_noise_reduction", disabled)
        self.assertIn("input_audio_echo_cancellation", disabled)
        self.assertIsNone(disabled["input_audio_noise_reduction"])
        self.assertIsNone(disabled["input_audio_echo_cancellation"])

    def test_normalization_accepts_finite_boundaries_and_integral_json_numbers(self):
        for key, low, high in (
            ("speech_rate", 0.5, 1.5), ("silence_duration_ms", 100, 2000),
            ("vad_threshold", 0, 1),
        ):
            for value in (low, high, None):
                with self.subTest(key=key, value=value):
                    result = validate_options({key: value}, DEFAULT_VOICE)
                    self.assertEqual(result[key], value)
        self.assertIsInstance(validate_options({"silence_duration_ms": 500.0}, DEFAULT_VOICE)["silence_duration_ms"], int)

    def test_all_advertised_select_choices_are_accepted_and_serializable(self):
        for field in option_schema(DEFAULT_VOICE)["fields"]:
            for option in field.get("options", []):
                with self.subTest(field=field["key"], value=option["value"]):
                    choices = {
                        **field.get("requires", {}), **option.get("requires", {}),
                        **option.get("implies", {}), field["key"]: option["value"],
                    }
                    choices = {key: value[0] if isinstance(value, list) else value for key, value in choices.items()}
                    json.dumps(self.session(choices), allow_nan=False)

    def test_invalid_mapping_and_untrusted_keys_are_rejected(self):
        for value in (None, [], "", 1, True, {1: "value"}):
            with self.subTest(value=value), self.assertRaises(VoiceOptionsError):
                validate_options(value, DEFAULT_VOICE)
        for key in (
            "model", "speech_model", "tts_model", "agent_model", "voice_type",
            "endpoint", "agent_name", "instructions", "tools", "api_version",
            "input_audio_format", "input_audio_sampling_rate", "channels",
            "reasoning_effort", "interim_response", "temperature", "unknown",
            "agent_config", "agent_version", "project_name", "foundry_resource_override", "client_id",
        ):
            with self.subTest(key=key), self.assertRaises(VoiceOptionsError):
                validate_options({key: "gpt-realtime"}, DEFAULT_VOICE)

    def test_model_mode_transcription_is_explicitly_rejected_in_agent_mode(self):
        for model in ("whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe", "gpt-4o-transcribe-diarize"):
            with self.subTest(model=model), self.assertRaisesRegex(VoiceOptionsError, "Foundry Agent"):
                validate_options({"transcription_model": model}, DEFAULT_VOICE)

    def test_invalid_select_and_boolean_types_are_rejected_without_coercion(self):
        cases = {
            "connection_mode": [None, [], {}, 1, True, "model", "realtime"],
            "transcription_model": [None, [], True, "mai-transcribe-1", "other"],
            "voice_name": [None, {}, 1, "alloy", "sunhi", "not-allowlisted"],
            "turn_detection": [None, [], 1, "semantic_vad", "azure_semantic_vad"],
            "semantic_threshold": [[], {}, 1, True, "default", "auto"],
            "interrupt_response": [None, 0, 1, "false", [], {}],
            "input_noise_reduction": [0, 1, "true", "near_field", {}, []],
            "echo_cancellation": [0, 1, "false", "client", {}, []],
        }
        for key, values in cases.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(VoiceOptionsError):
                    validate_options({key: value}, DEFAULT_VOICE)

    def test_invalid_numeric_values_never_reach_sdk(self):
        common = [False, True, "1", [], {}, float("nan"), float("inf"), float("-inf"), 10 ** 1000]
        invalid = {
            "speech_rate": common + [0.49, 1.51],
            "silence_duration_ms": common + [99, 2001, 500.5],
            "vad_threshold": common + [-0.01, 1.01],
        }
        for key, values in invalid.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(VoiceOptionsError):
                    validate_options({key: value}, DEFAULT_VOICE)

    def test_semantic_option_with_normal_vad_is_not_silently_ignored(self):
        with self.assertRaisesRegex(VoiceOptionsError, "semantic_threshold"):
            validate_options({"turn_detection": "server_vad", "semantic_threshold": "low"}, DEFAULT_VOICE)

    def test_builder_rejects_unknown_options_instead_of_sdk_ignoring_kwargs(self):
        options = validate_options({}, DEFAULT_VOICE)
        options["model"] = "gpt-realtime"
        with self.assertRaises(VoiceOptionsError):
            build_session_options(options)
        for options in (None, {}, []):
            with self.subTest(options=options), self.assertRaises(VoiceOptionsError):
                build_session_options(options)

    def test_session_never_overrides_agent_brains_tools_or_transport(self):
        data = self.session({
            "transcription_model": "mai-transcribe", "speech_rate": 1.4,
            "silence_duration_ms": 150, "input_noise_reduction": True,
        })
        self.assertFalse(set(data) & {"model", "instructions", "tools", "tool_choice", "interim_response"})
        self.assertEqual(data["input_audio_format"], "pcm16")
        self.assertEqual(data["output_audio_format"], "pcm16")
        self.assertEqual(data["input_audio_sampling_rate"], 24000)
        self.assertEqual(data["modalities"], ["text", "audio"])
        self.assertTrue(data["turn_detection"]["create_response"])

    def test_only_supervisor_mode_selects_documented_mode_defaults(self):
        chosen = validate_options({"connection_mode": "realtime_agent_tool"}, DEFAULT_VOICE)
        self.assertEqual(chosen["realtime_model"], "gpt-realtime-mini")
        self.assertEqual(chosen["transcription_model"], "gpt-4o-mini-transcribe")
        self.assertEqual(chosen["voice_name"], DEFAULT_VOICE)
        session = self.session({"connection_mode": "realtime_agent_tool"})
        self.assertEqual(session["input_audio_transcription"], {
            "model": "gpt-4o-mini-transcribe", "language": "ko",
        })
        self.assertNotIn("model", session)
        self.assertNotIn("connection_mode", session)
        self.assertNotIn("realtime_model", session)

    def test_supervisor_has_only_existing_trusted_agent_tool_with_cross_resource_target(self):
        for name, version in (("existing-bing", "3"), ("existing-webiq", "7")):
            with self.subTest(agent=name):
                target = {**AGENT_CONFIG, "agent_name": name, "agent_version": version}
                before = dict(target)
                session = build_search_session(
                    validate_options({"connection_mode": "realtime_agent_tool"}, DEFAULT_VOICE), target,
                ).as_dict()
                self.assertEqual(target, before)
                self.assertEqual(session["tools"], [{
                    "type": "foundry_agent", **target,
                    "agent_context_type": "agent_context", "return_agent_response_directly": True,
                    "description": session["tools"][0]["description"],
                }])
                self.assertIn("web searches", session["tools"][0]["description"])
                self.assertEqual(session["tool_choice"], "auto")
                self.assertIn("For every information-seeking question", session["instructions"])
                self.assertIn("greetings", session["instructions"])
                self.assertNotIn("interim_response", session)

    def test_unverified_direct_agent_model_combination_is_rejected(self):
        for model in ("gpt-realtime", "gpt-realtime-mini", "", False, 0, {}):
            with self.subTest(model=model), self.assertRaises(VoiceOptionsError):
                validate_options({"connection_mode": "agent", "realtime_model": model}, DEFAULT_VOICE)
        self.assertIsNone(validate_options({}, DEFAULT_VOICE)["realtime_model"])

    def test_supervisor_model_allowlist_is_finite_and_does_not_allow_null(self):
        for model in ("gpt-realtime", "gpt-realtime-mini"):
            self.assertEqual(
                validate_options({"connection_mode": "realtime_agent_tool", "realtime_model": model}, DEFAULT_VOICE)["realtime_model"],
                model,
            )
        for model in (None, "", "azure-realtime", "gpt-4.1", False, 0, {}, []):
            with self.subTest(model=model), self.assertRaises(VoiceOptionsError):
                validate_options({"connection_mode": "realtime_agent_tool", "realtime_model": model}, DEFAULT_VOICE)

    def test_transcription_compatibility_is_checked_in_both_modes(self):
        with self.assertRaises(VoiceOptionsError):
            validate_options({
                "connection_mode": "realtime_agent_tool", "transcription_model": "azure-speech",
            }, DEFAULT_VOICE)
        for model in (
            "whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe",
            "gpt-4o-transcribe-diarize", "mai-transcribe",
        ):
            with self.subTest(model=model):
                session = self.session({
                    "connection_mode": "realtime_agent_tool", "transcription_model": model,
                })
                self.assertEqual(session["input_audio_transcription"], {"model": model, "language": "ko"})

    def test_native_openai_voices_require_supervisor_mode_and_no_rate(self):
        for name in ("alloy", "coral", "verse", "marin"):
            voice = f"openai:{name}"
            with self.subTest(voice=voice), self.assertRaises(VoiceOptionsError):
                validate_options({"voice_name": voice}, DEFAULT_VOICE)
            values = {
                "connection_mode": "realtime_agent_tool", "voice_name": voice,
                "return_agent_response_directly": False,
            }
            self.assertEqual(self.session(values)["voice"], {"type": "openai", "name": name})
            for rate in (0.5, 1.0, 1.5):
                with self.subTest(voice=voice, rate=rate), self.assertRaises(VoiceOptionsError):
                    validate_options({**values, "speech_rate": rate}, DEFAULT_VOICE)
        for name in ("openai:unknown", "alloy", "azure-realtime:sunhi"):
            with self.subTest(voice=name), self.assertRaises(VoiceOptionsError):
                validate_options({"connection_mode": "realtime_agent_tool", "voice_name": name}, DEFAULT_VOICE)

    def test_azure_voices_and_rate_still_work_with_supervisor(self):
        for name in (DEFAULT_VOICE, "ko-KR-SunHi:DragonHDLatestNeural"):
            session = self.session({
                "connection_mode": "realtime_agent_tool", "voice_name": name, "speech_rate": 1.15,
            })
            self.assertEqual(session["voice"], {"type": "azure-standard", "name": name, "rate": "1.15"})

    def test_mode_defaults_are_fresh_and_schema_encodes_all_dependencies(self):
        schema = option_schema(DEFAULT_VOICE)
        fields = {field["key"]: field for field in schema["fields"]}
        modes_by_value = {option["value"]: option for option in fields["connection_mode"]["options"]}
        self.assertIn("STT", modes_by_value["agent"]["help"])
        self.assertIn("비용", modes_by_value["realtime_agent_tool"]["help"])
        self.assertEqual(fields["realtime_model"]["requires"], {"connection_mode": "realtime_agent_tool"})
        azure_names = fields["speech_rate"]["requires"]["voice_name"]
        self.assertIn(DEFAULT_VOICE, azure_names)
        self.assertNotIn("openai:alloy", azure_names)
        native = next(option for option in fields["voice_name"]["options"] if option["value"] == "openai:marin")
        self.assertEqual(native["requires"], {"connection_mode": "realtime_agent_tool"}, "offered without a prior Bing change")
        self.assertEqual(native["implies"], {"return_agent_response_directly": False})
        modes = schema["defaults_by_mode"]
        modes["agent"]["transcription_model"] = "changed"
        self.assertEqual(modes["realtime_agent_tool"]["transcription_model"], "gpt-4o-mini-transcribe")
        self.assertEqual(option_schema(DEFAULT_VOICE)["defaults_by_mode"]["agent"]["transcription_model"], "azure-speech")

    def test_native_voice_requires_explicit_realtime_answer_construction(self):
        values = {"connection_mode": "realtime_agent_tool", "voice_name": "openai:coral"}
        with self.assertRaises(VoiceOptionsError):
            validate_options(values, DEFAULT_VOICE)
        for invalid in (None, "false", 0, 1):
            with self.subTest(invalid=invalid), self.assertRaises(VoiceOptionsError):
                validate_options({**values, "return_agent_response_directly": invalid}, DEFAULT_VOICE)
        session = self.session({**values, "return_agent_response_directly": False})
        self.assertFalse(session["tools"][0]["return_agent_response_directly"])
        self.assertIn("Speak the delegated Agent's answer", session["instructions"])
        with self.assertRaises(VoiceOptionsError):
            validate_options({"return_agent_response_directly": True}, DEFAULT_VOICE)

    def test_builders_reject_wrong_modes_and_missing_or_unknown_trusted_target(self):
        direct = validate_options({}, DEFAULT_VOICE)
        supervisor = validate_options({"connection_mode": "realtime_agent_tool"}, DEFAULT_VOICE)
        with self.assertRaises(VoiceOptionsError):
            build_session_options(supervisor)
        with self.assertRaises(VoiceOptionsError):
            build_search_session(direct, AGENT_CONFIG)
        bad_configs = [
            None, [], {}, {"agent_name": "agent"}, {"project_name": "project"},
            {**AGENT_CONFIG, "model": "gpt-realtime"},
            {**AGENT_CONFIG, "authentication_identity_client_id": "wrong-key"},
        ]
        for key in AGENT_CONFIG:
            for value in ("", " ", 1, [], " x", "x\nx", "x" * 257):
                bad_configs.append({**AGENT_CONFIG, key: value})
        for target in bad_configs:
            with self.subTest(target=target), self.assertRaises(VoiceOptionsError):
                build_search_session(supervisor, target)

    def test_same_resource_target_omits_only_optional_none_values(self):
        supervisor = validate_options({"connection_mode": "realtime_agent_tool"}, DEFAULT_VOICE)
        session = build_search_session(supervisor, {
            "agent_name": "same-resource-agent", "project_name": "same-resource-project",
            "agent_version": None, "client_id": None, "foundry_resource_override": None,
        }).as_dict()
        self.assertEqual(session["tools"], [{
            "type": "foundry_agent",
            "agent_name": "same-resource-agent",
            "project_name": "same-resource-project",
            "agent_context_type": "agent_context",
            "return_agent_response_directly": True,
            "description": session["tools"][0]["description"],
        }])


class SearchSessionSerializationTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_sdk_session_update_preserves_documented_raw_agent_tool(self):
        normalized = validate_options({
            "connection_mode": "realtime_agent_tool",
            "realtime_model": "gpt-realtime",
            "voice_name": "openai:coral",
            "return_agent_response_directly": False,
        }, DEFAULT_VOICE)
        session = build_search_session(normalized, AGENT_CONFIG)
        transport = SimpleNamespace(send_str=AsyncMock())
        connection = VoiceLiveConnection(SimpleNamespace(), transport)
        await connection.session.update(session=session)
        event = json.loads(transport.send_str.call_args.args[0])
        self.assertEqual(event["type"], "session.update")
        self.assertEqual(event["session"], session.as_dict())
        self.assertEqual(event["session"]["tools"][0]["foundry_resource_override"], AGENT_CONFIG["foundry_resource_override"])
        self.assertEqual(event["session"]["tools"][0]["client_id"], AGENT_CONFIG["client_id"])
        self.assertEqual(event["session"]["voice"], {"type": "openai", "name": "coral"})


if __name__ == "__main__":
    unittest.main()
