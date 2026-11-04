"""Allowlisted Voice Live model, Agent, and speech settings."""

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
import math
from zoneinfo import ZoneInfo

from azure.ai.voicelive.models import (
    AudioEchoCancellation,
    AudioInputTranscriptionOptions,
    AudioNoiseReduction,
    AzureSemanticDetectionMultilingual,
    AzureSemanticVadMultilingual,
    AzureStandardVoice,
    OpenAIVoice,
    RequestSession,
    ServerVad,
)

from voice_poc.news import validate_news


class VoiceOptionsError(ValueError):
    """A session option is invalid or unavailable with the configured Agent."""


_VOICES = (
    ("ko-KR-SunHiNeural", "Azure Neural · SunHi (한국어, 여성)", "azure-neural"),
    ("ko-KR-InJoonNeural", "Azure Neural · InJoon (한국어, 남성)", "azure-neural"),
    (
        "ko-KR-SunHi:DragonHDLatestNeural",
        "DragonHD · SunHi (한국어, 여성; 지역 제한)",
        "dragon-hd",
    ),
    (
        "ko-KR-Hyunsu:DragonHDLatestNeural",
        "DragonHD · Hyunsu (한국어, 남성; 지역 제한)",
        "dragon-hd",
    ),
)
_SEMANTIC_VAD = "azure_semantic_vad_multilingual"
_END_TO_END = "end_to_end"
_GPT_LIVE = "gpt_live"
_REALTIME_MODELS = ("gpt-realtime", "gpt-realtime-mini")
CONNECTION_MODES = ("agent", _END_TO_END, _GPT_LIVE)
_VOICE_LIVE_MODES = ("agent", _END_TO_END)
_OPENAI_VOICES = ("alloy", "coral", "verse", "marin")
_END_TO_END_TRANSCRIPTION = (
    "whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe",
    "gpt-4o-transcribe-diarize",
)
_DEFAULTS = {
    "connection_mode": "agent",
    "realtime_model": None,
    "return_agent_response_directly": None,
    "transcription_model": "azure-speech",
    "turn_detection": _SEMANTIC_VAD,
    "speech_rate": None,
    "silence_duration_ms": None,
    "vad_threshold": None,
    "semantic_threshold": None,
    "interrupt_response": True,
    "input_noise_reduction": None,
    "echo_cancellation": None,
    "live_voice": "noeul",
    "live_language": "korean",
    "live_backchannel": "sometimes",
}
_LIVE_CHOICES = {
    "live_voice": ("noeul", "marin"),
    "live_language": ("korean", "follow_user", "none"),
    "live_backchannel": ("none", "sometimes", "often"),
}
# Voice Live session settings; GPT-Live has its own voice and turn handling.
_VOICE_LIVE_KEYS = (
    *(key for key in _DEFAULTS if key != "connection_mode" and key not in _LIVE_CHOICES), "voice_name",
)
_LIVE_PERSONA = (
    "You are a voice assistant in a search comparison demo. "
    "When the user asks for information that needs current facts or a web/news search, "
    "delegate the work instead of guessing; while waiting say a very short natural acknowledgement. "
    "When delegated results arrive, speak them naturally and concisely, mention sources when given."
)
_LIVE_LANGUAGE = {
    "korean": "Always speak Korean (한국어), even if the user speaks another language.",
    "follow_user": "Reply in the language the user speaks.",
    "none": None,
}
_LIVE_BACKCHANNEL = {
    "none": "Do not use backchannel acknowledgements while the user is speaking.",
    "sometimes": "Occasionally use brief natural backchannel acknowledgements (like 네, 음) while the user is speaking.",
    "often": "Frequently use brief backchannel acknowledgements while the user is speaking.",
}
_LIVE_NEWS_LENGTH = {"30s": "about 30 seconds", "60s": "about one minute", "free": "no fixed length, but stay brief"}
_NUMBERS = {
    "speech_rate": (0.5, 1.5, 0.05),
    "silence_duration_ms": (100, 2000, 50),
    "vad_threshold": (0.0, 1.0, 0.05),
}
_AGENT_LIMITATION = (
    "Agent 연결은 기존 Foundry Agent를 그대로 사용합니다. End-to-end는 별도 Realtime 모델 비용이 들고 "
    "실행 구조가 다릅니다. model과 Agent 연결 쿼리를 함께 보내는 조합은 사용하지 않습니다."
)
_AGENT_TOOL_DESCRIPTION = (
    "A Korean voice information assistant. Use it for web searches, current facts, "
    "news, prices, opening hours, events and place information. "
    "Include relevant application context and the user's question."
)
_BING_SEARCH_INSTRUCTIONS = (
    "You are a Korean voice supervisor connected to one existing Foundry Agent tool. "
    "You may answer greetings, farewells, and microphone checks directly. "
    "For every information-seeking question, search, recommendation, factual answer, or task "
    "using the supplied application context, call the configured foundry_agent tool. "
    "Do not answer those questions from your own knowledge or invent search results. "
    "Pass the user's full request in their own words, including what they asked the Agent to do; do not shorten it to keywords. "
    "Include relevant user-provided application context and conversation details "
    "in the request to the Agent. The Agent owns retrieval and information-task reasoning. "
    "Return its answer directly; do not replace it with a separate factual answer. "
    "If the tool fails, say that the request could not be completed rather than guessing. "
    "Use Korean unless the user asks for another language."
)
_WEBIQ_SEARCH_INSTRUCTIONS = (
    "당신은 한국어 음성 비서입니다. 최신 사실, 장소, 뉴스, 금융, 영업 정보는 webiq 도구로 확인하세요. "
    "도구 호출에는 가능한 한 language=ko, region=KR을 사용하세요. "
    "'잠시만요', '찾고 있습니다' 같은 대기 안내는 하지 말고, 도구 결과를 받으면 바로 답하세요. "
    "핵심 답부터 짧은 한국어 구어체 두세 문장으로 말하세요. "
    "URL, JSON, 내부 도구 이름은 소리 내어 읽지 마세요. 확인하지 못한 내용은 확인하지 못했다고 말하고 지어내지 마세요."
)
# Response-level instructions replace the session's for that response, so the follow-up repeats them.
WEBIQ_FOLLOWUP_INSTRUCTIONS = _WEBIQ_SEARCH_INSTRUCTIONS + (
    " 지금은 방금 받은 webiq 도구 결과로 사용자 질문에 답할 차례입니다. 결과가 질문에 답하기에 부족할 때만 한 번 더 검색하세요."
)
_WEBIQ_ALLOWED_TOOLS = ["web", "news", "places", "finance"]
_WEB_SEARCH_INSTRUCTIONS = (
    "당신은 한국어 음성 비서입니다. 최신 사실, 장소, 뉴스, 금융, 영업 정보는 web_search 도구로 확인하세요. "
    "검색어는 사용자의 질문을 한국어로 구체적으로 적으세요. "
    "'잠시만요', '찾고 있습니다' 같은 대기 안내는 하지 말고, 도구 결과를 받으면 바로 답하세요. "
    "핵심 답부터 짧은 한국어 구어체 두세 문장으로 말하세요. "
    "URL, 출처 표기, 표, 내부 도구 이름은 소리 내어 읽지 마세요. 확인하지 못한 내용은 확인하지 못했다고 말하고 지어내지 마세요."
)
WEB_SEARCH_FOLLOWUP_INSTRUCTIONS = _WEB_SEARCH_INSTRUCTIONS + (
    " 지금은 방금 받은 web_search 도구 결과로 사용자 질문에 답할 차례입니다. 결과가 질문에 답하기에 부족할 때만 한 번 더 검색하세요."
)
# Instructions for the answer the app requests after a search result arrives.
FOLLOWUP_INSTRUCTIONS = {"webiq": WEBIQ_FOLLOWUP_INSTRUCTIONS, "web_search": WEB_SEARCH_FOLLOWUP_INSTRUCTIONS}
WEB_SEARCH_FUNCTION = {
    "type": "function",
    "name": "web_search",
    "description": (
        "Search the public web with Bing (Foundry Web Search) for current facts, news, stock prices, places, "
        "opening hours, parking and charging information."
    ),
    "parameters": {
        "type": "object",
        "properties": {"search_query": {"type": "string", "minLength": 1, "maxLength": 200,
                                        "description": "The user's question as a specific Korean search query."}},
        "required": ["search_query"],
        "additionalProperties": False,
    },
}


def _default_values(default_voice):
    if not isinstance(default_voice, str) or not default_voice.strip():
        raise VoiceOptionsError("서버 기본 음성 이름이 필요합니다.")
    return {**_DEFAULTS, "voice_name": default_voice}


def _mode_defaults(default_voice, mode):
    defaults = _default_values(default_voice)
    if mode == _END_TO_END:
        defaults.update(
            connection_mode=mode,
            realtime_model="gpt-realtime-mini",
            transcription_model="gpt-4o-mini-transcribe",
            return_agent_response_directly=True,
        )
    elif mode == _GPT_LIVE:
        defaults["connection_mode"] = mode
    return defaults


def _same(value, default):
    return type(value) is type(default) and value == default


def option_schema(default_voice):
    """Return JSON-safe UI fields; null optional values inherit service settings."""
    defaults = _default_values(default_voice)
    voices = [
        {"value": name, "label": label, "family": family}
        for name, label, family in _VOICES
    ]
    if default_voice not in {voice["value"] for voice in voices}:
        voices.insert(0, {
            "value": default_voice,
            "label": f"서버 설정 기본 음성 · {default_voice}",
            "family": "server-configured",
        })
    azure_voice_names = [voice["value"] for voice in voices]
    # Selecting a native voice also switches Bing's delivery; validation still requires the explicit pair.
    voices.extend({
        "value": f"openai:{name}", "label": f"OpenAI native · {name}",
        "family": "openai", "requires": {"connection_mode": _END_TO_END},
        "implies": {"return_agent_response_directly": False},
    } for name in _OPENAI_VOICES)
    fields = [
        {
            "key": "connection_mode", "label": "실행 구조", "type": "select",
            "options": [
                {
                    "value": "agent", "label": "Agent 연결",
                    "help": "STT → 기존 Foundry Agent(검색 도구 포함) → TTS. 답변 모델은 Agent에 지정된 모델입니다.",
                },
                {
                    "value": _END_TO_END, "label": "End-to-end",
                    "help": "Realtime 모델이 음성을 직접 듣고 말합니다. WebIQ는 모델이 MCP로 직접 검색하고, Bing은 Foundry Toolbox 웹 검색(없으면 Bing Agent)을 사용합니다. 별도 Realtime 비용이 발생합니다.",
                },
                {
                    "value": _GPT_LIVE, "label": "GPT-Live",
                    "help": "Azure OpenAI GPT-Live가 음성을 직접 듣고 말하며, 검색은 클라이언트 위임으로 기존 WebIQ / Bing Agent에 맡깁니다. 음성으로만 질문할 수 있고 별도 GPT-Live 비용이 발생합니다.",
                },
            ],
        },
        {
            "key": "realtime_model", "label": "Realtime 모델", "type": "select",
            "nullable": True, "requires": {"connection_mode": _END_TO_END},
            "options": [
                {
                    "value": None, "label": "직접 Agent 모드: 추가 모델 없음",
                    "requires": {"connection_mode": ["agent"]},
                },
                *[
                    {
                        "value": model, "label": model,
                        "requires": {"connection_mode": _END_TO_END},
                    }
                    for model in _REALTIME_MODELS
                ],
            ],
            "help": "End-to-end에서만 실제 model 연결 쿼리에 적용합니다. 기존 Foundry Agent의 모델/버전은 변경하지 않습니다.",
        },
        {
            "key": "return_agent_response_directly", "label": "Agent 답변 전달 방식",
            "type": "select", "nullable": True, "requires": {"connection_mode": [_END_TO_END]},
            "options": [
                {"value": None, "label": "Agent 연결에서는 사용하지 않음", "requires": {"connection_mode": ["agent"]}},
                {
                    "value": True, "label": "Agent 답변 직접 사용 · Azure TTS",
                    "requires": {"connection_mode": [_END_TO_END], "voice_name": azure_voice_names},
                },
                {
                    "value": False, "label": "선택한 모델이 답변 구성 · OpenAI 음성 사용 가능",
                    "requires": {"connection_mode": [_END_TO_END]},
                },
            ],
            "help": "Bing Agent 도구에만 적용됩니다. WebIQ 직접 검색 답변은 항상 선택한 모델이 작성합니다. OpenAI native 음성은 직접 반환과 함께 사용할 수 없습니다.",
        },
        {
            "key": "transcription_model", "label": "STT 모델", "type": "select",
            "options": [
                {
                    "value": "azure-speech", "label": "Azure Speech · 한국어",
                    "requires": {"connection_mode": ["agent"]},
                },
                {"value": "mai-transcribe", "label": "MAI Transcribe · 한국어 (preview)"},
                *[
                    {
                        "value": model, "label": model,
                        "requires": {"connection_mode": _END_TO_END},
                    }
                    for model in _END_TO_END_TRANSCRIPTION
                ],
            ],
            "help": "직접 Agent 모드에서는 LLM에 전달하는 STT입니다. Realtime에서는 모델이 음성을 직접 이해하며 별도 전사 모델을 선택하는 것입니다.",
        },
        {
            "key": "voice_name", "label": "TTS 모델 계열 / 음성", "type": "select",
            "options": voices,
            "help": "Neural/DragonHD는 Azure voice.name, OpenAI native는 End-to-end의 voice.type=openai로 적용합니다.",
        },
        {
            "key": "turn_detection", "label": "발화 종료 감지", "type": "select",
            "options": [
                {"value": _SEMANTIC_VAD, "label": "Azure 다국어 Semantic VAD"},
                {"value": "server_vad", "label": "Server VAD · 음량 / 무음 기준"},
            ],
            "help": "한국어 지원 Azure Semantic VAD 또는 일반 VAD. OpenAI semantic_vad와 다릅니다.",
        },
        {
            "key": "speech_rate", "label": "TTS 말하기 속도", "type": "number",
            "requires": {"voice_name": azure_voice_names},
            "placeholder": "기본 속도 (1.0)",
            "help": "Azure 음성만 0.5–1.5배 지원합니다. OpenAI native에서는 null이어야 합니다. 추론이나 첫 음성 지연을 보장하지 않습니다.",
        },
        {
            "key": "silence_duration_ms", "label": "발화 종료 무음 대기 (ms)", "type": "number",
            "placeholder": "서비스 기본값 (문서: 500 ms)",
            "help": "짧으면 종료 판단이 빨라지지만 말 중간에 잘릴 수 있습니다. 앱 허용 범위: 100–2000 ms.",
        },
        {
            "key": "vad_threshold", "label": "VAD 음성 감지 임계값", "type": "number",
            "placeholder": "서비스 기본값 (문서: 0.5)",
            "help": "0–1. 높을수록 음성으로 판단하는 데 더 높은 신뢰도가 필요합니다.",
        },
        {
            "key": "semantic_threshold", "label": "의미 기반 발화 종료 임계값", "type": "select",
            "nullable": True,
            "options": [
                {"value": None, "label": "기존 서비스 설정 유지"},
                {"value": "low", "label": "low"},
                {"value": "medium", "label": "medium"},
                {"value": "high", "label": "high"},
            ],
            "requires": {"turn_detection": _SEMANTIC_VAD},
            "help": "Azure 다국어 end_of_utterance_detection.threshold_level. 기본 선택은 추가 설정을 보내지 않습니다.",
        },
        {
            "key": "interrupt_response", "label": "말로 답변 끊기 (barge-in)", "type": "boolean",
            "help": "사용자 발화로 진행 중인 답변을 중단할 수 있습니다.",
        },
    ]
    for key, label, help_text in (
        (
            "input_noise_reduction", "서버 소음 억제",
            "azure_deep_noise_suppression. 브라우저의 마이크 소음 억제와 별개입니다.",
        ),
        (
            "echo_cancellation", "서버 에코 제거",
            "server_echo_cancellation. 모노 입력과 서버 재생 참조를 사용하며 클라이언트 참조 / 스테레오는 사용하지 않습니다.",
        ),
    ):
        fields.append({
            "key": key, "label": label, "type": "select", "nullable": True,
            "options": [
                {"value": None, "label": "기존 서비스 설정 유지"},
                {"value": True, "label": "켜기"},
                {"value": False, "label": "끄기"},
            ],
            "help": help_text,
        })
    for field in fields[1:]:
        # Voice Live settings do not apply to GPT-Live; narrower mode requirements are kept.
        field["requires"] = {"connection_mode": list(_VOICE_LIVE_MODES), **field.get("requires", {})}
    fields.extend([
        {
            "key": "live_voice", "label": "GPT-Live 음성", "type": "select",
            "requires": {"connection_mode": _GPT_LIVE},
            "options": [
                {"value": "noeul", "label": "Noeul", "help": "한국어 권장 음성. Azure 지원 여부는 진단으로 확인합니다."},
                {"value": "marin", "label": "Marin", "help": "GPT-Live 기본값(영어)."},
            ],
            "help": "session.start의 audio.output.voice입니다. 세션을 시작한 뒤에는 바꿀 수 없습니다.",
        },
        {
            "key": "live_language", "label": "GPT-Live 답변 언어", "type": "select",
            "requires": {"connection_mode": _GPT_LIVE},
            "options": [
                {"value": "korean", "label": "항상 한국어"},
                {"value": "follow_user", "label": "사용자 언어 따라가기"},
                {"value": "none", "label": "지시 없음"},
            ],
            "help": "instructions에 넣는 언어 지시입니다. '지시 없음'은 언어 문장을 넣지 않아 모델 기본 동작을 확인합니다.",
        },
        {
            "key": "live_backchannel", "label": "GPT-Live 맞장구", "type": "select",
            "requires": {"connection_mode": _GPT_LIVE},
            "options": [
                {"value": "none", "label": "없음"},
                {"value": "sometimes", "label": "가끔"},
                {"value": "often", "label": "자주"},
            ],
            "help": "사용자가 말하는 동안 '네', '음' 같은 짧은 반응을 얼마나 할지 instructions로 요청합니다.",
        },
    ])
    for field in fields:
        key = field["key"]
        field["default"] = defaults[key]
        if key in _NUMBERS:
            minimum, maximum, step = _NUMBERS[key]
            field.update(min=minimum, max=maximum, step=step, nullable=True)
    return {
        "supported_modes": list(CONNECTION_MODES),
        "fields": fields,
        "defaults": defaults,
        "defaults_by_mode": {
            mode: _mode_defaults(default_voice, mode) for mode in CONNECTION_MODES
        },
        "fixed": {
            "modalities": ["text", "audio"],
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_sampling_rate": 24000,
            "channels": 1,
        },
        "fixed_by_mode": {
            "agent": {"tool_executor": "Foundry Agent", "agent_model": "기존 Agent에 설정된 모델"},
            _END_TO_END: {"tool_executor": "WebIQ MCP와 Bing 웹 검색", "model": "선택한 Realtime 모델"},
            _GPT_LIVE: {
                "tool_executor": "Foundry Agent (클라이언트 위임)", "model": "GPT-Live 배포", "input": "음성 전용",
            },
        },
    }


def validate_options(mapping, default_voice):
    """Validate client choices without coercion; return a fresh complete dict."""
    defaults = _default_values(default_voice)
    if not isinstance(mapping, Mapping):
        raise VoiceOptionsError("음성 options는 JSON 객체여야 합니다.")
    if any(not isinstance(key, str) for key in mapping):
        raise VoiceOptionsError("음성 options 키는 문자열이어야 합니다.")
    unknown = set(mapping) - set(defaults)
    if unknown:
        if unknown & {"model", "speech_model", "tts_model", "agent_model", "voice_type"}:
            raise VoiceOptionsError(
                "model / speech_model / tts_model / agent_model / voice_type은 변경할 수 없습니다. "
                + _AGENT_LIMITATION
            )
        raise VoiceOptionsError("지원하지 않는 음성 option 키가 있습니다.")
    mode = mapping.get("connection_mode", "agent")
    if not isinstance(mode, str) or mode not in CONNECTION_MODES:
        raise VoiceOptionsError("지원하지 않는 connection_mode입니다.")
    result = {**_mode_defaults(default_voice, mode), **mapping}
    for key, allowed in _LIVE_CHOICES.items():
        if not isinstance(result[key], str) or result[key] not in allowed:
            raise VoiceOptionsError(f"{key}는 {', '.join(allowed)} 중 하나여야 합니다.")
    if mode == _GPT_LIVE:
        live_defaults = _mode_defaults(default_voice, mode)
        changed = sorted(key for key in _VOICE_LIVE_KEYS if not _same(result[key], live_defaults[key]))
        if changed:
            raise VoiceOptionsError(
                "GPT-Live에서는 Voice Live 설정을 바꿀 수 없습니다: " + ", ".join(changed)
                + ". live_voice, live_language, live_backchannel만 설정하세요."
            )
        return result
    if any(not _same(result[key], _DEFAULTS[key]) for key in _LIVE_CHOICES):
        raise VoiceOptionsError("live_voice, live_language, live_backchannel은 gpt_live 모드에서만 설정할 수 있습니다.")
    realtime_model = result["realtime_model"]
    if mode != _END_TO_END:
        if realtime_model is not None:
            raise VoiceOptionsError("realtime_model은 end_to_end 모드에서만 지정할 수 있습니다.")
    elif not isinstance(realtime_model, str) or realtime_model not in _REALTIME_MODELS:
        raise VoiceOptionsError("End-to-end의 realtime_model은 gpt-realtime 또는 gpt-realtime-mini여야 합니다.")
    direct_return = result["return_agent_response_directly"]
    if mode != _END_TO_END:
        if direct_return is not None:
            raise VoiceOptionsError("Agent 답변 전달 방식은 end_to_end 모드 전용입니다.")
    elif type(direct_return) is not bool:
        raise VoiceOptionsError("return_agent_response_directly는 true 또는 false여야 합니다.")
    stt = result["transcription_model"]
    allowed_stt = (
        ("azure-speech", "mai-transcribe")
        if mode != _END_TO_END else (*_END_TO_END_TRANSCRIPTION, "mai-transcribe")
    )
    if not isinstance(stt, str) or stt not in allowed_stt:
        if mode == "agent" and isinstance(stt, str) and stt in _END_TO_END_TRANSCRIPTION:
            raise VoiceOptionsError(
                "Whisper / GPT 전사는 End-to-end 전용입니다. "
                "Agent 연결에서는 azure-speech 또는 mai-transcribe를 선택하세요."
            )
        raise VoiceOptionsError("현재 connection_mode에서 지원하지 않는 transcription_model입니다.")
    voice = result["voice_name"]
    native_voices = {f"openai:{name}" for name in _OPENAI_VOICES}
    allowed_voices = {default_voice, *(v[0] for v in _VOICES)}
    if mode == _END_TO_END:
        allowed_voices.update(native_voices)
    if not isinstance(voice, str) or voice not in allowed_voices:
        raise VoiceOptionsError("voice_name은 현재 실행 구조에서 허용된 음성 또는 서버 기본 음성이어야 합니다.")
    if voice in native_voices and mode != _END_TO_END:
        raise VoiceOptionsError("OpenAI native 음성은 end_to_end 모드에서만 사용할 수 있습니다.")
    if voice in native_voices and direct_return:
        raise VoiceOptionsError("OpenAI native 음성은 Agent 직접 반환과 함께 사용할 수 없습니다. 답변 구성 방식을 선택하세요.")
    vad = result["turn_detection"]
    if not isinstance(vad, str) or vad not in (_SEMANTIC_VAD, "server_vad"):
        raise VoiceOptionsError(
            "turn_detection은 azure_semantic_vad_multilingual 또는 server_vad여야 합니다."
        )
    for key, (minimum, maximum, _) in _NUMBERS.items():
        value = result[key]
        if value is None:
            continue
        if type(value) not in (int, float) or not minimum <= value <= maximum or not math.isfinite(value):
            raise VoiceOptionsError(f"{key}는 {minimum}–{maximum} 범위의 유한한 숫자여야 합니다.")
        if key == "silence_duration_ms":
            if int(value) != value:
                raise VoiceOptionsError("silence_duration_ms는 정수 밀리초여야 합니다.")
            result[key] = int(value)
        else:
            result[key] = float(value)
    if voice in native_voices and result["speech_rate"] is not None:
        raise VoiceOptionsError("OpenAI native 음성은 speech_rate를 지원하지 않습니다. null로 초기화하세요.")
    for key in ("interrupt_response", "input_noise_reduction", "echo_cancellation"):
        value = result[key]
        if value is None and key != "interrupt_response":
            continue
        if type(value) is not bool:
            raise VoiceOptionsError(f"{key}는 true 또는 false여야 합니다.")
    semantic = result["semantic_threshold"]
    if semantic is not None:
        if not isinstance(semantic, str) or semantic not in ("low", "medium", "high"):
            raise VoiceOptionsError("semantic_threshold는 low, medium, high 또는 null이어야 합니다.")
        if vad != _SEMANTIC_VAD:
            raise VoiceOptionsError("semantic_threshold는 Azure 다국어 Semantic VAD에서만 설정할 수 있습니다.")
    return result


def _builder_options(normalized):
    if not isinstance(normalized, Mapping) or "voice_name" not in normalized:
        raise VoiceOptionsError("validate_options의 결과가 필요합니다.")
    # The caller's validation establishes which configured default voice is trusted.
    return validate_options(normalized, normalized["voice_name"])


def _speech_session(options):
    voice_kwargs = {"name": options["voice_name"]}
    if options["speech_rate"] is not None:
        voice_kwargs["rate"] = str(options["speech_rate"])
    voice = (
        OpenAIVoice(name=options["voice_name"].split(":", 1)[1])
        if options["voice_name"] in {f"openai:{name}" for name in _OPENAI_VOICES}
        else AzureStandardVoice(**voice_kwargs)
    )
    turn_kwargs = {
        "create_response": True,
        "interrupt_response": options["interrupt_response"],
    }
    for source, target in (
        ("silence_duration_ms", "silence_duration_ms"),
        ("vad_threshold", "threshold"),
    ):
        if options[source] is not None:
            turn_kwargs[target] = options[source]
    if options["semantic_threshold"] is not None:
        turn_kwargs["end_of_utterance_detection"] = AzureSemanticDetectionMultilingual(
            threshold_level=options["semantic_threshold"],
        )
    turn_class = AzureSemanticVadMultilingual if options["turn_detection"] == _SEMANTIC_VAD else ServerVad
    kwargs = {
        "modalities": ["text", "audio"],
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "input_audio_sampling_rate": 24000,
        "input_audio_transcription": AudioInputTranscriptionOptions(
            model=options["transcription_model"],
            language="ko-KR" if options["transcription_model"] == "azure-speech" else "ko",
        ),
        "voice": voice,
        "turn_detection": turn_class(**turn_kwargs),
    }
    if options["input_noise_reduction"] is not None:
        kwargs["input_audio_noise_reduction"] = (
            AudioNoiseReduction(type="azure_deep_noise_suppression")
            if options["input_noise_reduction"] else None
        )
    if options["echo_cancellation"] is not None:
        kwargs["input_audio_echo_cancellation"] = (
            AudioEchoCancellation(type="server_echo_cancellation")
            if options["echo_cancellation"] else None
        )
    return RequestSession(**kwargs)


def build_agent_session(normalized):
    """Build the Agent-mode RequestSession; never set model/tools."""
    options = _builder_options(normalized)
    if options["connection_mode"] != "agent":
        raise VoiceOptionsError("선택한 실행 구조에 맞는 세션 빌더를 사용하세요.")
    return _speech_session(options)


def _validated_agent_target(agent_config):
    """Return a trusted foundry_agent tool target supplied by the server."""
    allowed = {
        "agent_name", "agent_version", "project_name", "foundry_resource_override", "client_id",
    }
    if not isinstance(agent_config, Mapping) or set(agent_config) - allowed:
        raise VoiceOptionsError("서버 Agent 설정에 지원하지 않는 필드가 있습니다.")
    target = {}
    for key in allowed:
        value = agent_config.get(key)
        if value is None and key not in ("agent_name", "project_name"):
            continue
        if (
            not isinstance(value, str) or not value.strip() or len(value) > 256
            or value != value.strip() or any(ord(character) < 32 for character in value)
        ):
            raise VoiceOptionsError(f"서버 Agent 설정의 {key} 값이 올바르지 않습니다.")
        target[key] = value
    return target


def _validated_mcp_target(mcp_config):
    allowed = {"server_url", "headers"}
    if not isinstance(mcp_config, Mapping) or set(mcp_config) - allowed:
        raise VoiceOptionsError("서버 MCP 설정에 지원하지 않는 필드가 있습니다.")
    server_url = mcp_config.get("server_url")
    if not isinstance(server_url, str) or not server_url.strip() or server_url != server_url.strip():
        raise VoiceOptionsError("서버 MCP URL이 올바르지 않습니다.")
    from urllib.parse import urlparse

    parsed = urlparse(server_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise VoiceOptionsError("서버 MCP URL은 https여야 합니다.")
    headers = mcp_config.get("headers")
    if not isinstance(headers, Mapping) or not headers:
        raise VoiceOptionsError("서버 MCP 헤더가 올바르지 않습니다.")
    safe_headers = {}
    for key, value in headers.items():
        if (
            not isinstance(key, str) or not isinstance(value, str)
            or not key.strip() or key != key.strip()
            or not value or any(ord(character) < 32 for character in key + value)
        ):
            raise VoiceOptionsError("서버 MCP 헤더가 올바르지 않습니다.")
        safe_headers[key] = value
    return {"server_url": server_url, "headers": safe_headers}


def build_end_to_end_web_search_session(normalized):
    """End-to-end Bing lane: the model calls a web_search function that the app runs on the Foundry Toolbox."""
    options = _builder_options(normalized)
    if options["connection_mode"] != _END_TO_END:
        raise VoiceOptionsError("build_end_to_end_web_search_session은 end_to_end 모드 전용입니다.")
    session = _speech_session(options)
    session.tools = [dict(WEB_SEARCH_FUNCTION, parameters=deepcopy(WEB_SEARCH_FUNCTION["parameters"]))]
    session.instructions = _WEB_SEARCH_INSTRUCTIONS
    session.tool_choice = "auto"
    return session


def build_end_to_end_session(normalized, target):
    """Build End-to-end settings with a foundry_agent or MCP target."""
    options = _builder_options(normalized)
    if options["connection_mode"] != _END_TO_END:
        raise VoiceOptionsError("build_end_to_end_session은 end_to_end 모드 전용입니다.")
    # SDK 1.3 lacks this class; the documented API tool mapping is preserved losslessly.
    if isinstance(target, Mapping) and "server_url" in target:
        mcp = _validated_mcp_target(target)
        tool = {
            "type": "mcp",
            "server_label": "webiq",
            "server_url": mcp["server_url"],
            "headers": mcp["headers"],
            "allowed_tools": list(_WEBIQ_ALLOWED_TOOLS),
            "require_approval": "never",
        }
        instructions = _WEBIQ_SEARCH_INSTRUCTIONS
    else:
        agent_target = _validated_agent_target(target)
        tool = {
            "type": "foundry_agent",
            **agent_target,
            "agent_context_type": "agent_context",
            "return_agent_response_directly": options["return_agent_response_directly"],
            "description": _AGENT_TOOL_DESCRIPTION,
        }
        instructions = _BING_SEARCH_INSTRUCTIONS
        if not options["return_agent_response_directly"]:
            instructions = _BING_SEARCH_INSTRUCTIONS.replace(
                "Return its answer directly; do not replace it with a separate factual answer.",
                "Speak the delegated Agent's answer, preserving its facts and uncertainties. Do not add new facts.",
            )
    session = _speech_session(options)
    session.tools = [tool]
    session.instructions = instructions
    session.tool_choice = "auto"
    return session


def build_live_session(normalized, *, deployment, news=None, now=None):
    """Build the strict GPT-Live session.start payload; instructions are English on purpose."""
    if not isinstance(normalized, Mapping) or "voice_name" not in normalized:
        raise VoiceOptionsError("validate_options의 결과가 필요합니다.")
    options = validate_options(normalized, normalized["voice_name"])
    if options["connection_mode"] != _GPT_LIVE:
        raise VoiceOptionsError("build_live_session은 gpt_live 모드 전용입니다.")
    if not isinstance(deployment, str) or not deployment.strip():
        raise VoiceOptionsError("GPT-Live 배포 이름이 필요합니다.")
    news = validate_news(news)
    now = now or datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    lines = [_LIVE_PERSONA, f"Current date and time (Asia/Seoul): {now}."]
    if _LIVE_LANGUAGE[options["live_language"]]:
        lines.append(_LIVE_LANGUAGE[options["live_language"]])
    lines.append(_LIVE_BACKCHANNEL[options["live_backchannel"]])
    if news is not None:
        lines.append(
            "This is a news briefing. The search agent applies the news briefing rules; "
            f"keep the spoken briefing to {_LIVE_NEWS_LENGTH[news['length']]}."
        )
    return {
        "model": deployment,
        "instructions": "\n".join(lines),
        "audio": {"output": {"voice": options["live_voice"]}},
        "delegation": {"type": "client"},
    }
