# Voice Live 실행 및 음성 설정

## 화면에서 선택하는 것

기본 화면에는 선택 항목이 없다. 질문하면 WebIQ와 Grounding with Bing이 **항상 같은 설정으로 동시에** 실행된다.
아래 항목은 접힌 **설정** 패널에 있으며 두 엔진에 똑같이 적용된다.

| 항목 | 선택 |
| --- | --- |
| 음성 처리 방식 | Agent 연결(기본) / End-to-end(Realtime) |
| Realtime 모델 | End-to-end의 `gpt-realtime`, `gpt-realtime-mini` |
| STT / 입력 전사 | Agent 연결: Azure Speech·MAI (End-to-end는 모델이 음성을 직접 들어 화면에서 고르지 않음) |
| TTS / 출력 음성 | Azure Neural·DragonHD / End-to-end의 OpenAI native(모델 자체 음성) |
| Bing Agent 답변 전달 | Bing을 Agent로 연결할 때만 적용(API의 `model_search`, Toolbox가 없는 End-to-end). End-to-end 화면에서는 숨김 |
| 지연 관련 설정 | 발화 종료 감지, 무음 대기, 임계값, 끼어들기, 서버 소음·에코 제거 |

**Agent 연결**은 `agent`, **End-to-end**는 `realtime_agent_tool`이다.
공정한 비교에는 Agent 연결을 쓴다. 두 Agent의 모델·지시가 같고 검색 도구만 다르기 때문이다.
End-to-end에서는 **Agent 없이** 음성 모델이 두 검색을 직접 부른다. WebIQ는 선택 모델의 세션 MCP 도구로 연결하고,
Bing은 `TMAP_WEB_SEARCH_TOOLBOX`로 지정한 **Foundry Toolbox의 Bing 기반 Web Search**를 쓴다
(모델이 `web_search` 함수를 부르면 앱 서버가 Toolbox MCP 주소로 검색하고 결과 글과 출처를 모델에 돌려준다).
Toolbox 설정이 없으면 예전처럼 Bing Agent를 `foundry_agent` 도구로 연결한다. API 전용 `model_search`의 Bing도 Agent 연결이다.
STT → LLM → TTS(`model_search`, 텍스트 모델 `gpt-4.1-mini`, `gpt-4.1`, `gpt-4o-mini`, `gpt-5-mini`, `gpt-5`, `gpt-5.6-luna`)와
앱 조작 데모(`model_tools`)는 비교 화면에서 제외했고 API로만 사용할 수 있다.
설정은 연결 중에도 모두 바꿀 수 있다. 바꾸면 진행 중인 비교 연결을 끝내고 다음 질문부터 새 설정으로 연결한다
(음성은 말하기를 다시 누른다). 이전에는 방식·모델 외의 설정이 연결을 중지할 때까지 잠겨 있었다.

**End-to-end에서 알아둘 점**

- End-to-end도 Voice Live다. `model=gpt-realtime-mini`(또는 `gpt-realtime`)로 연결해 모델이 음성을 직접 듣는다.
  기본 설정은 답변 음성만 Azure TTS(SunHi)로 읽는다. OpenAI native 음성을 고르면 모델이 자기 목소리로 말하고,
  Bing Agent 답변 전달이 “선택한 모델이 답변 구성”으로 함께 바뀐다(서비스가 직접 반환과 native 음성 조합을 거부한다).
- End-to-end에는 글자로 바뀐 질문이 없다. 서비스 문서에 따르면 Realtime 모델은 음성을 직접 받고,
  세션의 인식 모델(`input_audio_transcription`)은 따로 받아쓴 참고용 글자라 모델이 이해한 내용과 다를 수 있다.
  그래서 화면은 End-to-end에서 인식 문장을 표시하지 않고 설정에서도 인식 모델을 고르지 않는다(API 기본값만 사용).
  이 받아쓰기가 실패해도 End-to-end 연결은 끊지 않는다. 모델이 실제로 이해한 내용은 두 엔진의 검색어로 보여 준다.
  Agent 연결에서 보이는 “Agent가 받은 질문”은 STT 결과이자 Agent가 실제로 받은 입력이다.
- **Bing 웹 검색을 Toolbox에서 앱 서버가 부르는 이유(2026-09-29 확인).** Grounding with Bing 도구 자체는 Agent 안에서만 쓸 수 있고
  Toolbox에도 넣을 수 없다. 대신 Bing 기반 **Web Search** 도구는 Toolbox에 넣으면 MCP 주소로 노출된다
  (`tools/call web_search {"search_query": ...}` → Bing 근거로 정리한 답변 글 + `url_citation` 출처).
  Voice Live가 이 MCP 주소를 직접 부르게 해 보니 두 가지가 막혔다. Entra 토큰을 `headers.Authorization`에 넣으면
  `string_above_max_length`로 거부되고(별도 `authorization` 필드는 통과), 호출은 완료되지만 Toolbox가 결과를
  MCP `resource` 형식으로 돌려줘 **모델이 받는 결과가 빈 글**이 된다. 그래서 모델에는 `web_search` 함수를 주고
  앱 서버가 같은 Toolbox MCP를 불러 결과 글을 함수 결과로 넘긴다. Agent는 쓰지 않는다.
- **Toolbox Web Search는 느리다.** 앱에서 직접 잰 한 번 검색 시간은 9–14초였다(`search_context_size: low`도 비슷).
  Toolbox 안에서 Bing 결과를 긴 답변 글로 정리하기 때문이다. WebIQ 검색은 0.5–0.7초였다.
- 엔진마다 Realtime 모델 세션이 따로 음성을 듣는다. 같은 음성도 두 모델이 다르게 이해할 수 있어
  WebIQ와 Bing이 서로 다른 질문을 검색할 수 있다. 검색 엔진 비교에는 두 Agent가 같은 인식 글자를 받는 Agent 연결을 쓴다.
- Realtime 모델은 지시와 달리 “잠시만요” 같은 대기 멘트를 먼저 말한 뒤 검색하기도 한다. 화면은 검색 전에 한 말을
  “대기 멘트”로 따로 적고, 응답 시작 시간은 검색 뒤 실제 답변부터 잰다.

**실제 서비스에서 확인한 제약**

- 세션 MCP 도구는 도구 목록(`mcp_list_tools.completed`)이 준비되기 전 질문하면 도구 없이 답한다.
  앱은 목록이 준비된 뒤에만 준비 완료를 알리며, 목록 실패는 대화를 종료하는 오류로 표시한다.
- 검색 호출(`mcp_call`)로 끝난 응답 뒤에는 서비스가 스스로 답하지 않는다. 앱이 검색 결과로 답하라는
  지시와 함께 후속 `response.create`를 보낸다(사용자 발화당 최대 3회). `foundry_agent` 호출 뒤에는 서비스가 이어서 답한다.
- 검색 호출은 그 응답이 끝난(`response.done`) **뒤에** 실행된다(2026-09-29 관측: 응답 종료 11.82초 → 검색 시작 11.83초 → 완료 12.32초).
  바로 후속 요청을 보내면 모델이 결과 없이 “확인하고 있어요, 잠시만요”만 말하고 끝났다.
  앱은 이제 그 검색이 `response.mcp_call.completed`/`failed`로 돌아온 뒤에 후속 요청을 보낸다.
- Realtime 모델은 대기 멘트를 말한 뒤 같은 응답에서 다시 검색할 수 있다. 응답의 마지막 항목으로 후속 요청 여부를 판단하고,
  화면에는 `response_done.followup`으로 알려 그 응답에서 한 말을 대기 멘트로 표시한다.
- WebIQ 세션 도구는 `web`, `news`, `places`, `finance`만 허용한다. 서비스가 알려준 전체 목록은 10개다.
- OpenAI native 음성은 `return_agent_response_directly=true`와 함께 쓰면 거부된다.
  UI에서 **선택 모델이 답변을 다시 정리**를 명시적으로 선택해야 하며 추가 생성 단계가 생긴다.
- Agent에 설명이 없는 경우에도 호출할 수 있도록 tool의 `description`을 서버 코드에서 제공한다.
- Native Realtime의 `item.id`는 최대 32자다. 맥락 메시지도 이 제한을 지킨다.
- 9월 8일에는 기존 두 Agent 실행 구조의 호환 옵션으로 초기화·Agent 위임·오디오 수신을 확인했다.
  사용자 마이크·재생 품질이나 답변 정확도 평가와는 별개의 기능 확인이다.
- 감독 모드의 Voice Live 사용량만으로 위임된 Foundry 모델 비용까지 모두 포함됐다고 보지 않는다.
  기존 실험 결과와 합산하지 않고 모드·선택값을 기록한다.

근거: `results/voice_realtime_initialization_20260908_04.json`,
`results/voice_realtime_agent_call_20260908_01.json`,
`results/voice_realtime_agent_call_20260908_02.json`.
앞선 `_01`~`_03` 초기화 실패 기록도 보존했다. 9월 23일 검색 연결 확인은
[음성 연결 현황](VOICE_STATUS.md#2026-09-23-연결-방식별-검색-도구-연결-확인)에 정리했다.

Verified on **2026-09-08** against Microsoft Learn and the installed
`azure-ai-voicelive==1.3.0` models, and re-checked on **2026-09-23** (still the
latest package and the latest API version `2026-07-15`). The SDK contracts below do not
assure availability in every region. The limited live connection checks are described above separately.

## Four explicitly selected execution architectures

The customer demo compares the same question across connection types and models.
The chat and the API both default to `agent`. The navigation scenario remains available
by choosing "앱 조작 데모" in the header (`model_tools`); it is not a substitute for either live search provider.

| `connection_mode` | Connection URL | Session behavior |
| --- | --- | --- |
| `agent` (default) | Existing `agent-name`, `agent-project-name`, pinned `agent-version`, and trusted cross-resource/auth parameters. **No `model` query.** | Existing Foundry Agent owns reasoning, conversation, and search-tool execution. No supervisor, no session instructions/tools override. |
| `model_search` | `model=<llm_model>`. **No Agent connection queries.** | Azure STT → selected text LLM → Azure TTS. WebIQ: session `mcp` tool (server-resolved key header, `allowed_tools` web/news/places/finance); the selected model searches and answers. Bing: one `foundry_agent` tool to the Bing Agent. |
| `realtime_agent_tool` | `model=gpt-realtime` or `model=gpt-realtime-mini`. **No Agent connection query parameters.** | Native realtime model hears audio and speaks. WebIQ: same direct `mcp` tool. Bing: with `TMAP_WEB_SEARCH_TOOLBOX`, one `web_search` function that the app runs on the Foundry Toolbox's Bing-based Web Search over MCP (no Agent); without it, one `foundry_agent` tool to the Bing Agent. |
| `model_tools` (optional navigation scenario) | `model=<llm_model>`. **No Agent connection queries.** | Voice Live STT → text LLM as the app agent → allowlisted navigation functions → Azure TTS. No Foundry search Agent. |

The WebIQ MCP key is read at session start from the project connection already referenced by the
WebIQ Agent's MCP tool (`agents.get_version` → `project_connection_id` →
`connections.get(include_credentials=True)`), cached in memory for up to 10 minutes and never
written to files, logs, flow events, traces or browser messages. The server identity needs permission
to read that connection's secret. `/api/config` still makes no cloud calls.
No Agent profile, model deployment, resource, role assignment, or additional
search tool is created. Changing the selected model does not modify any Foundry Agent's model or instructions.

The official API documentation describes **model connection** and **Agent
connection** using `model` **or** `agent-name` / `agent-project-name`; the SDK
docstring says Agent mode uses the model associated with the Agent. **This is not
proof of server-enforced mutual exclusion.** SDK 1.3.0's `connect` accepts
`model`, `agent_name`, and `project_name` together, and its `_prepare_url()`
actually includes all three query parameters. An offline test verifies this
without opening a connection.

The **simultaneous direct-Agent + `model` query** remains disabled/informational,
with `availability="unverified_for_fixed_agent"`. The reviewed official documentation
does **not define** whether a simultaneous Agent+model query is rejected, ignored,
overrides the Agent model, or changes the execution architecture. No live
Agent+model experiment was performed. It would be inaccurate to claim either
"the SDK prohibits it", "the service always rejects it", or "the service ignores
the model".

The app never presents simultaneous query parameters as a speech-only model
change. Instead, selecting the supported supervisor architecture explicitly adds
the realtime model. Non-null `realtime_model` in direct mode is rejected rather
than silently ignored.

In fact, the API explicitly documents **`FoundryAgentTool`**:

> This enables a chat-supervisor pattern where a realtime-based chat agent handles
> basic interactions while delegating complex tasks to a more intelligent Foundry agent.

Its wire shape is `tools=[{"type": "foundry_agent", "agent_name": ...,
"project_name": ...}]`. It supports `return_agent_response_directly` (default
`true`; `false` lets the chat model rephrase). Even direct return still has a
realtime supervisor selecting calls. That is a real supported realtime+Agent
architecture, and it is now exposed through `realtime_agent_tool`.
The supervisor instructions permit greetings, farewells, and microphone checks
directly, but route information-seeking questions, factual answers,
recommendations, and context-dependent tasks to the configured Agent.
`tool_choice="auto"` is deliberate: tool use is model-directed, not a
deterministic application guarantee for every utterance.

The service's [region table](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions?tabs=voice-live)
lists both selected realtime models as **Global standard** in `eastus2`.
This confirms documented regional availability, not a specific resource's
access, quota, or a successful live supervisor-tool invocation.

Selecting another existing Foundry Agent LLM would require an explicitly
configured, existing Agent profile; this module does not change profiles or
accept deployment names. The new `model_tools` mode selects a managed Voice Live
LLM directly; it does not override the model of a registered Foundry Agent.

## Model-level app manipulation

The model choices are documented in the [Voice Live model table](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live#supported-models-and-regions).
The [transcription contract](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live-how-to#audio-input-transcription)
supports Azure Speech and MAI with text-based models. Availability for the configured
resource still requires a real connection; SDK serialization alone is not that evidence.

`navigation.py` owns the action contract and session-local state. Its functions are
`open_app`, `search_places`, `preview_route`, `start_navigation`, `add_waypoint`,
`cancel_navigation`, and `get_navigation_state`. These operate on the in-browser
demo and its explicitly illustrative catalog/road network, not the real TMAP app.
Search returns IDs before a destination or waypoint can be selected.

`navigation_voice.py` consumes actual completed model function calls, validates
arguments, runs the shared executor, and publishes a `navigation` state event.
The browser applies that state and sends
`{"type":"navigation_ack","action_id":"<call_id>","revision":1}`.
Only a matching acknowledgement permits an `ok=true` SDK `FunctionCallOutputItem`.
A five-second acknowledgement timeout returns an explicit uncertain outcome; it
does not claim success or undo a state that might already be visible.
Call IDs prevent duplicate execution. Calls are bounded to eight per response and
256 per session, with at most three waypoints in the demo.

The action worker is separate from the cloud receive loop. Interruption cancels
unexecuted commands and suppresses an obsolete spoken continuation, while stop
cancels the worker along with the audio/session tasks. User transcripts are never
parsed as action commands by application code. The selected LLM chooses tools.
Explicit model response requests carry an opaque `ResponseCreateParams.metadata`
request ID. Their originating turn remains tracked until `response.created`
echoes that ID, so barge-in in the intervening window also cancels late app calls.
Cancellation targets that response ID, without cancelling a newer user's response.
An already-terminal cancellation error is only tolerated when its client event ID
matches this application's cancellation request.
The offline UI rehearsal uses snapshots produced by this same executor, with no
STT, LLM, TTS, or cloud calls and no entries in the real conversation.

This mode needs Voice Live endpoint/voice/auth configuration only. It does not
require a Foundry project or search Agent. The legacy `provider` field remains in
the start envelope for compatibility but is not used as a search provider in this mode.

## What can actually change

| Client option | Accepted values / default | Actual SDK and wire field |
| --- | --- | --- |
| `connection_mode` | `agent` (chat and API default), `model_search`, `realtime_agent_tool`, `model_tools` (optional navigation scenario) | Selects connection architecture and session builder; not a session property |
| `llm_model` | `model_search` / `model_tools`: `gpt-4.1-mini` (default), `gpt-4.1`, `gpt-4o-mini`, `gpt-5-mini`, `gpt-5`, `gpt-5.6-luna`. Other modes: **null only** | Connection URL's `model` query in text-model modes; never overrides a Foundry Agent |
| `realtime_model` | Direct: **null only**. Supervisor: `gpt-realtime`, `gpt-realtime-mini` (mode default) | Parent connection URL's `model` query only; never combined with Agent connection queries |
| `return_agent_response_directly` | `agent` / `model_tools`: **null only**. `model_search` / `realtime_agent_tool`: `true` (default, Agent answer spoken as-is) or `false` (selected model rewrites it; required for OpenAI native voices) | `foundry_agent` tool return policy; applies only when Bing is attached through its Agent. WebIQ direct answers are always written by the selected model |
| `transcription_model` | Model/direct Agent: `azure-speech` (default), `mai-transcribe`. Supervisor: GPT/Whisper choices below, or `mai-transcribe`; mode default `gpt-4o-mini-transcribe` | `AudioInputTranscriptionOptions.model` → `input_audio_transcription.model` |
| `voice_name` | Server-configured Azure default; Korean Azure choices in both modes; `openai:*` choices in supervisor only | `AzureStandardVoice` / `OpenAIVoice` → `voice.name` and `voice.type` |
| `speech_rate` | `null` (inherit), numeric **0.5–1.5** for Azure voices. **Null only** for OpenAI native | `AzureStandardVoice.rate`, serialized as a **string**, e.g. `"1.25"` |
| `turn_detection` | `azure_semantic_vad_multilingual` (default), `server_vad` | `AzureSemanticVadMultilingual` / `ServerVad` → `turn_detection.type` |
| `silence_duration_ms` | `null` (inherit), integer **100–2000** | `turn_detection.silence_duration_ms` |
| `vad_threshold` | `null` (inherit), numeric **0–1** | `turn_detection.threshold` |
| `semantic_threshold` | `null` (inherit), `low`, `medium`, `high`; only Azure multilingual semantic VAD | `AzureSemanticDetectionMultilingual.threshold_level` → `turn_detection.end_of_utterance_detection` with `model="semantic_detection_v1_multilingual"` |
| `interrupt_response` | Boolean, **true** by default | `turn_detection.interrupt_response` |
| `input_noise_reduction` | `null` (inherit), `true`, `false` | `input_audio_noise_reduction`: omit, `AudioNoiseReduction(type="azure_deep_noise_suppression")`, explicit JSON `null` |
| `echo_cancellation` | `null` (inherit), `true`, `false` | `input_audio_echo_cancellation`: omit, `AudioEchoCancellation(type="server_echo_cancellation")`, explicit JSON `null` |

The 100–2000 ms silence range is an **application safety range**, not a claimed
service-wide maximum. Number `step` values in the UI schema are presentation
increments, not a claim that the service quantizes values. Fractional milliseconds,
numeric strings, booleans used as numbers, nonfinite values, unknown fields, and
incompatible combinations are rejected; values are never clipped or silently
dropped.

### STT is a model choice, but not every STT model supports Agent mode

Current official Voice Live documentation explicitly allows `azure-speech` and
`mai-transcribe` with agents. Both support Korean. Azure Speech keeps the existing
`language="ko-KR"`; MAI uses its documented `language="ko"` code.

`whisper-1`, `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`, and
`gpt-4o-transcribe-diarize` are documented for the `gpt-realtime` /
`gpt-realtime-mini` model configuration. They are selectable in supervisor mode
and rejected in direct mode. The `2026-07-15` API reference also explicitly lists
`mai-transcribe` for those realtime models, so MAI is available in both modes.
Azure Speech is not listed for these realtime models and is rejected in
supervisor mode. All supervisor transcription choices use the Korean ISO code
`language="ko"`.

In model mode STT feeds the selected text LLM; in direct Agent mode it feeds the
text-based Foundry Agent. A native realtime model instead
**consumes audio directly**; its separate transcription runs asynchronously and
does not replace the model's own audio understanding. This UI setting changes
the real transcript model, but must not be described as changing what the
native model heard.

The SDK 1.3 generated docstring includes the older name `mai-transcribe-1`.
Its `model` field also accepts strings. The current service how-to and API
reference explicitly use **`mai-transcribe`**; that is the sole MAI value exposed
here and verified in `.as_dict()`. The language-support page says this alias
currently defaults to MAI-Transcribe-1.5; this is **not** a version pin or a
MAI-Transcribe-2 selector.

### TTS model family is encoded in the voice name

The curated choices are:

- Azure Neural: `ko-KR-SunHiNeural`, `ko-KR-InJoonNeural`.
- DragonHD: `ko-KR-SunHi:DragonHDLatestNeural`,
  `ko-KR-Hyunsu:DragonHDLatestNeural`.
- OpenAI native, supervisor mode only: `openai:alloy`, `openai:coral`,
  `openai:verse`, `openai:marin`.

The Azure families use **`AzureStandardVoice` / `type="azure-standard"`**. There is no
invented `tts_model` field. UI labels and `family` metadata identify the model
family, not just the speaker. DragonHD names above are explicitly listed in the
official language/voice table; they are not inferred by appending a suffix.
`LatestNeural` follows the service's latest base-model version.

The configured default voice is preserved verbatim, even if it is outside this
curated list. Only that server-supplied name is added to the allowlist; clients
cannot introduce arbitrary voice names, endpoints, custom voice model IDs, or
lexicon URLs.

The how-to currently lists HD availability in southeastasia, centralindia,
swedencentral, westeurope, eastus, eastus2, and westus2. This is informational:
check the current documentation and actual service error for the selected
resource. `OpenAIVoice` (`type="openai"`) exists in the SDK, and the speech
output documentation ties those native voices to the multimodal OpenAI models;
they are therefore exposed only in the explicitly selected supervisor mode.
`RequestSession(voice=OpenAIVoice(name="alloy")).as_dict()` really serializes
`{"voice": {"type": "openai", "name": "alloy"}}`; an offline test confirms it.
The `openai:` prefix is a client selection identifier, removed before setting
`OpenAIVoice.name`. It is not sent as part of the service voice name. The installed
OpenAI voice class has no `rate` field; any non-null `speech_rate`, even `1.0`,
is rejected with native voices rather than dropped.

`RequestSession` has a general **`model`** field and a **`voice`** union, but no
separate **`tts_model`** field. `AzureStandardVoice` has `name`, `rate`,
`temperature`, and other synthesis properties, not a separate TTS `model`
property. The broader API also has custom/personal voice configurations; these
are different provisioned-voice features, not a free Agent-preserving realtime
model override, and are outside this app's allowlist.

### Latency options are not latency promises

- Reducing silence duration can detect a turn end sooner, but can cut off pauses.
- The VAD activation threshold is different from the semantic **end-of-utterance**
  threshold. The latter creates a documented Azure semantic detection object
  only when explicitly selected.
- OpenAI `semantic_vad.eagerness` is a realtime-model-specific control. It is not
  interchangeable with Azure multilingual semantic VAD and is not accepted.
- The SDK documents `interrupt_response` on both `ServerVad` and
  `AzureSemanticVadMultilingual`. The general how-to's interruption row mentions
  only Azure semantic VAD; service confirmation remains authoritative. The
  serialization tests cover both concrete SDK classes.
- Speaking rate affects answer playback, not Agent/search execution time or a
  guaranteed time-to-first-audio.
- Server echo cancellation uses its existing internal playback reference and
  mono defaults. Client-reference echo cancellation would require a different
  stereo capture protocol and is deliberately unavailable. Browser capture
  processing, if enabled separately, is not toggled by these server options.
- Interim responses are not exposed. Static acknowledgments would make “first
  audio” measure acknowledgment latency instead of answer latency; LLM-generated
  interim responses would add another model. Neither is silently enabled.
  However, the approved realtime supervisor itself can speak before its tool
  completes. Measure first supervisor audio and first Agent-answer audio
  separately; a faster greeting is not a faster search answer.

## SDK compatibility and trusted cross-resource Agent targeting

The official API `2026-07-15` documents `FoundryAgentTool`, but the installed
**SDK 1.3.0 does not export a `FoundryAgentTool` class**. It is incorrect to import
that nonexistent class or construct a generic tool with unknown keyword
arguments that might be ignored.

The supported workaround uses the documented **raw tool mapping** inside
`RequestSession.tools`. The installed SDK preserves that mapping through
`RequestSession.as_dict()`, `ClientEventSessionUpdate`, and
`VoiceLiveConnection.send()` to the final JSON passed to the transport.
Tests exercise that complete serialization path without opening a network
connection. No dependency upgrade is required.

`build_realtime_session(normalized, agent_config)` accepts a trusted server-only
mapping with exactly these permitted target fields:

| Field | Requirement / wire behavior |
| --- | --- |
| `agent_name` | Required existing Agent name |
| `project_name` | Required existing Agent project name |
| `agent_version` | Optional; preserve the selected existing Agent's pinned version |
| `foundry_resource_override` | Optional for same-resource use; **must be supplied for this app's East US 2 Voice Live → Korea Central Agent target** |
| `client_id` | Optional identity field documented on `FoundryAgentTool`; map the server-configured Agent authentication identity client ID here when used |

Nonempty strings are required for present values; optional `None` values are
omitted. Unknown keys are rejected. Direct connection names such as
`authentication_identity_client_id` are **not** accepted as tool keys; the
documented tool property is `client_id`.

The builder adds `type="foundry_agent"`,
`agent_context_type="agent_context"`, and
`return_agent_response_directly` from the validated choice, plus a server-provided
tool description. The target is never read from browser
options; browser Agent/project/resource/identity fields are rejected.
The builder cannot infer resource relationships from project names: the runtime
must supply the trusted override whenever the Voice Live and Agent hosts differ.
It must not omit a missing cross-resource override and silently try the Voice
Live host's similarly named project. Existing identity access remains required;
this module does not add role assignments or prove authorization.

## Integration contract

This module owns validation and session configuration only. Runtime and browser
wiring are separate.

```python
from tmap_poc.voice_options import (
    option_schema, validate_options, build_session_options, build_realtime_session, build_model_session,
)

schema = option_schema(settings.voice_name)
# Validate before opening any cloud connection; omit voice_options or send {}
# for existing behavior. An explicit null voice_options object is invalid.
chosen = validate_options(start_message.get("voice_options", {}), settings.voice_name)
if chosen["connection_mode"] == "agent":
    # Parent connects with existing Agent query parameters and NO model query.
    session = build_session_options(chosen)
elif chosen["connection_mode"] == "model_tools":
    # Parent connects with model=chosen["llm_model"], without an Agent target.
    session = build_model_session(chosen)
else:
    # Parent connects with model=chosen["realtime_model"] and NO Agent queries.
    # Target values are server settings, not start_message/browser fields.
    agent = settings.agents[start_message["provider"]]
    session = build_realtime_session(chosen, {
        "agent_name": agent.name,
        "agent_version": agent.version,
        "project_name": settings.project_name,
        "foundry_resource_override": settings.foundry_resource_override or None,
        "client_id": settings.agent_identity_client_id or None,
    })
await connection.session.update(session=session)
```

The agreed API placement is `config.voice_options` for the schema and
`{"type": "start", "provider": ..., "context": ..., "voice_options": {...}}`
for selected session settings. The module accepts the inner mapping and does not
parse the surrounding WebSocket envelope.

`validate_options(mapping, default_voice)` returns a fresh, complete JSON-safe
dictionary. It raises `VoiceOptionsError`, a `ValueError` subclass. The default
voice argument **must come from trusted server settings**, never the client.
`build_session_options(normalized)` accepts only direct mode;
`build_realtime_session(normalized, agent_config)` accepts only supervisor mode;
`build_model_session(normalized)` accepts only model mode.
Each returns an actual `RequestSession`, not an event wrapper. None sets a
session `model`: the parent must apply the mode-specific connection query.
Calling the wrong builder is an error, so supervisor mode cannot accidentally
start without its Agent tool. All builders also reject
unknown keys and invalid values rather than letting generated SDK constructors
ignore them; it relies on the preceding validation to establish which configured
default voice is trusted.

`option_schema(default_voice)` returns:

```text
{
  mode: "foundry_agent",
  supported_modes: ["agent", "realtime_agent_tool", "model_tools"],
  fields: [{key, label, type, default, options?, nullable?, min?, max?, step?,
            placeholder?, requires?, help}],
  defaults: {all writable keys and defaults},
  defaults_by_mode: {
    agent: {full direct-mode defaults},
    realtime_agent_tool: {full supervisor-mode defaults},
    model_tools: {full model-mode defaults}
  },
  fixed: {shared audio transport information},
  fixed_by_mode: {mode-specific tool executor and Agent/data-source information},
  unavailable_options: [{key, label, type, disabled: true,
                          requires: {connection_mode: "agent"},
                          availability: "unverified_for_fixed_agent", options, help}],
  limitations: [human-readable explanations]
}
```

The legacy top-level `mode` identifies the default Agent path;
`connection_mode` is the actual selected architecture. `defaults` still contains
the direct-mode defaults. `defaults_by_mode.realtime_agent_tool` differs in
`connection_mode`, `realtime_model="gpt-realtime-mini"`, and
`transcription_model="gpt-4o-mini-transcribe"`. All other defaults, including the
configured Azure voice, stay the same.
`defaults_by_mode.model_tools` sets `llm_model="gpt-4.1-mini"` and retains the
Azure Speech/default Azure voice settings. `config.model_connection` supplies
model-only readiness/errors, separate from existing search-Agent readiness.

`type` is `select`, `number`, or `boolean`. Select choices are objects with
`value` and `label`; voice choices additionally include `family`. Both fields
and individual select choices can have `requires` conditions. A scalar condition
requires equality; an array condition permits **any of the listed values**.
For example, `speech_rate.requires.voice_name` lists all allowed Azure voice
names, including a configured nonpreset default.
Connection-mode choices also include `help` describing each route and its
additional-model/cost implications. The connection settings summary uses the selected
choice's label and help rather than inferring the architecture from a model name.

When changing modes, reset an incompatible transcription choice, LLM/realtime model,
or voice to the newly selected mode's default. When selecting a native OpenAI
voice, disable/reset `speech_rate` to `null`. Apply these dependencies before
sending the start message; the backend rejects explicitly incompatible choices
instead of silently dropping or translating them. Missing fields use the chosen
mode's defaults, so `{"connection_mode":"realtime_agent_tool"}` is sufficient to
select its documented defaults.

Preserve JSON
types: the audio-filter selects use `null`, `true`, and `false`, **not strings**.
An empty nullable numeric field must become `null`, not zero. The
`semantic_threshold.requires` condition is
`{"turn_detection": "azure_semantic_vad_multilingual"}`; when switching to
`server_vad`, reset it to `null` or omit it. Never submit `fixed`,
`unavailable_options`, or their keys as choices.

An API client can send `"voice_options": {}` **for a new direct-Agent session**. Null/inherit options
omit the corresponding field, so they do not undo settings in an already running
session. Explicit `false` for audio filters deliberately serializes JSON `null`
via the SDK's `RequestSession` null-handling support.
The page uses the schema's direct-Agent defaults for initial selection and full
reset. The navigation scenario (`model_tools`) is excluded from the page; the API
still accepts it. Current-mode defaults keep the selected architecture.
There is no per-conversation settings card or conversation download/recorder.

**Comparison screen (2026-09-28).** One question is sent to both engines at once:
each configured provider gets its own WebSocket session with the same voice options.
Text questions are sent to every ready lane (queued until a connecting lane is ready).
Voice uses one microphone and one AudioWorklet; the same PCM frames go to every ready
lane, so both engines hear the same audio. A lane that fails does not stop the other;
the next text question reconnects only the failed lane.

Each question is one row with an aligned cell per engine. Voice turns are aligned by
order: an engine's first new user item joins the next voice row, so rows stay aligned
when both engines segment the audio the same way; each cell shows its own recognized text.
A cell shows four steps — 질문, 검색, 찾은 결과, 답변 — driven only by received events:
MCP tool lifecycle and arguments (search step and duration), tool output (result count,
finance price/change, place category/hours/coordinates, web/news excerpts with markup
removed), citations (답변 출처), and answer text/audio (답변, response-start and completion
time measured in the browser from when that engine received the question). With Grounding
with Bing in Agent mode no tool events arrive, so the search step is shown as “비공개”
and only service citations are listed. The row header lists both response-start times;
these are single observations, not a benchmark.

Only one engine's audio plays live (WebIQ by default, switchable in the lane bar).
All answer audio is buffered per answer (up to about 65 seconds) for “답변 듣기” replay.
Barge-in stops live playback and replay. A new question can be sent after both engines
finish; an engine that sends nothing for 45 seconds is marked as not answering.
Changing the voice pipeline or its model ends the current comparison; other speech
options are locked while connected.
`/api/config.providers[]` reports `configured`, `errors`, `warnings`,
`readiness_scope="configuration_only"`, and an optional
`agent={name, version, pinned}` reference. These check local configuration,
not Azure connectivity, agent existence, quota, or answer quality. Connection Settings
shows the selected reference and warnings about unpinned or shared agent targets;
the normal chat does not display a per-conversation settings card.

The browser consumes these correlated conversation events:

| Event | Meaning |
| --- | --- |
| `transcript` | Actual user or assistant text. Deltas append; `final=true` replaces the current text. User STT uses its own `item_id`, never the assistant response ID. |
| `citation` | An actual service annotation with `item_id` / `response_id`, URL and title. It may precede text or arrive after it; it is not an invented WebIQ citation. |
| `tool` | Observed tool lifecycle/output. The tool's `id` is not the assistant message's `item_id`; unknown status remains unknown. Raw output is retained in the permanent execution pane. |
| `response_done` | One response ended: `response_id`, `status`, `interrupted`. It does not end the session or establish tool success. |
| `flow` | Additive, allowlisted application-operation or service-event metadata; see the observation contract below. |
| `usage` | Numeric usage returned by Voice Live, associated with its reported response ID. Not a price or guaranteed aggregate of every delegated model. |
| `error` | Terminal API errors include `terminal=true` and available session/provider/response identity. `response_busy` is recoverable and does not close the connection. |

Completion is cached by response ID so source-only responses stop waiting and
late sources do not reopen a completed bubble or disturb another turn. Failed,
incomplete, interrupted and unknown completion states stay explicit. Completion
does not fabricate a final transcript: missing text or an unconfirmed final text
is labeled accordingly. Interrupted responses reject obsolete assistant text,
audio and sources while user transcription remains separate.

### Always-visible API observations

The right pane displays **observations**, not private reasoning or a simulated
sequence of expected steps. Connection preparation is grouped into one card;
input and tool metadata join other records only through explicitly provided
identifiers. Tool IDs, assistant message IDs and response IDs are distinct.
Unknown associations remain unknown. Browser observation times and SDK-client
tool durations are not server-internal search/model latency measurements.

`config.observability` declares `flow_schema_version=1`,
`scope="client_observed"`, `reasoning_content=false` and
`automatic_trace_queries=false`. Each `flow` event carries:

```text
{
  type: "flow",
  stage, status,
  observation: "app_operation" | "service_event",
  operation? | source_event?,
  session_id, provider,
  item_id: string | null,
  response_id: string | null,
  tool_id: string | null,
  data: {allowlisted fields only}
}
```

| Observation | What it establishes | What it does not establish |
| --- | --- | --- |
| Configured connection target | The requested endpoint host, Agent/version or model connection; `search_attachment` (`mcp` or `foundry_agent`) chosen by the server for model pipelines | Agent existence/permissions before connection, or the underlying Agent LLM |
| `session.update`, `conversation.item.create`, `response.create` submissions | The application's SDK operation returned; public request fields were captured. `session.update` may carry a sanitized `search_tool` {type, server_label, server_host, allowed_tools} (never headers, URL query or key). `response.create` with `purpose="tool_followup"` is the app asking for an answer after a tool-only response | Completed service processing or hidden prompt contents |
| `session.created` / `session.updated` | Service-reported session fields | `data.service_model` with `model_scope="voice_live_session"` is not proof of the underlying Agent model |
| VAD start/stop, buffer commit, STT partial/final | Actual voice-input milestones and recognized text keyed by the user's item ID | Text input did not run STT; audio reception alone is not recognized speech |
| MCP catalog | Names actually advertised by the service | That the Agent invoked every listed tool |
| Tool lifecycle/arguments/output | The actual exposed call, public arguments, state and returned data. A `foundry_agent_call` exposes the delegated `input` and the Agent's answer text | Unknown status is not success; incomplete/unparseable or filtered arguments are labeled; a delegated Agent's inner searches are not exposed |
| Response text/citations/completion | Actual answer text, annotations and terminal response state | Citations are not the complete raw retrieval list; response completion is not individual tool success |
| Service audio start/done | Audio generation was observed / ended | Browser playback, physical audibility or successful overall response |
| Browser PCM/playback | Valid PCM bytes received and actual buffer-source scheduling/end events | Physical speaker quality or microphone performance |
| Manually fetched Foundry spans | Collected, access-controlled tracing evidence when configured | Complete coverage, immediate ingestion or inferred missing parent/timing relationships |

Metadata projection excludes authentication/capability values, raw PCM, hidden
instructions/context and whole SDK session/hosted-invocation objects. Tool
arguments use an allowlist and expose filtering/parseability flags. Full MCP
**output** remains available in the received tool JSON; compact UI previews do
not modify that output. The UI does not relabel generic `web_search_call` events
as Bing calls or invent tools from answer citations.

**Provider boundary:** WebIQ's public reference lists web/content tools but does
not promise Finance availability in every connection. Only advertised/called
names are shown; the actual September 21 stock check did return `finance`.
Current Bing documentation says generated search queries can be inspected via
Agents APIs, while raw grounding output is unavailable to developers/end users.
Our Voice Live checks returned citations without those queries or raw result
lists. This is an observation about this route, not a claim that every Bing
integration hides queries. Missing tool events are not classified as search
failure.

Verified references for this contract:
[Voice Live 2026-07-15](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live-api-reference-2026-07-15),
[Agent integration](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-voice-agent-integration),
[WebIQ API/MCP](https://webiq.microsoft.ai/llms-full.txt),
[Bing tools](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/bing-tools),
[Foundry tracing](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup).
Installed SDK 1.3.0 typed/generic event behavior is covered by the flow tests.

Both audio-upload and service-receive loops yield cooperatively after each event.
Buffered async I/O can otherwise complete without yielding and starve peer tasks.
Content-free slow-relay/event-loop warnings support diagnosis; the PCM format,
96,000-byte browser backpressure guard and production timeouts are unchanged.

Submitting a search without a session starts the shared text connection. The
initial command is sent once, only after the service reports ready. A connection
failure or edits made while connecting must not erase the current input draft.
This path does not request a microphone or pretend to run STT.

A separately labeled **current-mode defaults** button can restore
`defaults_by_mode[selected_mode]` without changing the selected architecture.
For supervisor mode, it must still send at least
`{"voice_options":{"connection_mode":"realtime_agent_tool"}}`. Never omit the
mode discriminator merely because it matches that mode's contextual default:
an empty object always selects the global direct-Agent default. Compare the
mode discriminator against the global default, even if other fields are
serialized as deviations from the selected mode's defaults. A conversation/full
reset requires confirmation and restores the global direct-Agent defaults.

The disabled simultaneous-query explanation itself has
`requires={"connection_mode":"agent"}`. Hide it in supervisor mode; it is not a
global prohibition of the approved realtime model selector.

With omitted options or schema defaults, `.as_dict()` matches the previous
session request **exactly**: Korean Azure Speech, configured Azure standard voice
without `rate`, Azure multilingual semantic VAD with only `create_response=True`
and `interrupt_response=True`, text/audio modalities, mono PCM16 at 24 kHz.
No threshold, silence duration, EOU model, filter, or instructions are added.
`create_response=True`, modalities, sample rate, and format are fixed transport
requirements, not user controls.

Session choice validation is not service capability discovery. The runtime
must surface a service rejection as an error (including a safe field/code when
available), explain region/Agent-mode restrictions, and must not report ready or
silently retry with another model. Only `session.updated` confirms service
acceptance. Preserve existing authentication and Agent connection parameters.

The runtime must also honor `chosen["interrupt_response"]` when handling
`input_audio_buffer.speech_started`: do not mark the active response interrupted
or send the browser an `interrupt` playback-clear event when it is false.
Otherwise, a valid service setting would appear ineffective because local code
still drops response audio. Speech timing instrumentation can run independently
of that playback decision.

## Sources

1. [Voice Live API reference 2026-07-15](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live-api-reference-2026-07-15)
   — documented connection shapes, `FoundryAgentTool` chat-supervisor semantics,
   STT compatibility, audio processing, interim responses. It does not define
   simultaneous Agent+model query precedence.
2. [How to use Voice Live](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live-how-to)
   — Agent instructions restriction, VAD controls, STT, TTS `rate`, HD regions.
3. [Foundry Agent quickstart](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live-agents-quickstart)
   — existing Agent owns configuration; Agent-mode voice/VAD/speed configuration.
4. [Voice Live languages](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live-language-support)
   — Korean STT, MAI alias/version, Azure TTS versus OpenAI native speech.
5. [Speech language and voice table](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts)
   and [HD voices](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/high-definition-voices)
   — exact Korean voice names and model-family naming.
6. SDK references:
   [RequestSession](https://learn.microsoft.com/en-us/python/api/azure-ai-voicelive/azure.ai.voicelive.models.requestsession?view=azure-python),
   [AzureStandardVoice](https://learn.microsoft.com/en-us/python/api/azure-ai-voicelive/azure.ai.voicelive.models.azurestandardvoice?view=azure-python),
   [OpenAIVoice](https://learn.microsoft.com/en-us/python/api/azure-ai-voicelive/azure.ai.voicelive.models.openaivoice?view=azure-python),
   [ServerVad](https://learn.microsoft.com/en-us/python/api/azure-ai-voicelive/azure.ai.voicelive.models.servervad?view=azure-python),
   [AzureSemanticVadMultilingual](https://learn.microsoft.com/en-us/python/api/azure-ai-voicelive/azure.ai.voicelive.models.azuresemanticvadmultilingual?view=azure-python),
   [AzureSemanticDetectionMultilingual](https://learn.microsoft.com/en-us/python/api/azure-ai-voicelive/azure.ai.voicelive.models.azuresemanticdetectionmultilingual?view=azure-python).
7. [SDK `aio.connect` reference](https://learn.microsoft.com/en-us/python/api/azure-ai-voicelive/azure.ai.voicelive.aio?view=azure-python#azure-ai-voicelive-aio-connect)
   — documents the model and Agent parameters and the Agent-associated model
   when `model` is omitted. Installed SDK 1.3.0's `aio/_patch.py` additionally
   verifies that `_prepare_url` transmits both when supplied; client behavior is
   not server proof.
8. [Agent integration guide](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-voice-agent-integration)
   — named/versioned Agent configuration and separately configurable speech
   settings; no documented speech-only native-model override for a fixed Agent.
9. [Voice Live regions](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions?tabs=voice-live)
   — East US 2 lists `gpt-realtime`, `gpt-realtime-mini`, and Agent support.

## Offline validation

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_voice_options.py'
```

Tests use the real installed SDK `.as_dict()` and complete
`session.update` → JSON transport serialization without opening a cloud
connection. Direct-mode defaults remain the exact same JSON object.
Cross-resource tool targeting, native TTS, mode-aware validation, and the
documented raw tool workaround are covered.

The parent also separately confirmed direct-mode initialization of MAI +
DragonHD/rate 1.15 and normal VAD/700 ms/interrupt false in
`results/voice_options_initialization_20260908.json`. That initialization
evidence must not be misrepresented as a completed native supervisor-tool
inference. This module work performs no paid calls, provisioning, or dependency
changes.
