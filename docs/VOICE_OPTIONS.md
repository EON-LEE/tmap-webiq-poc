# 음성 설정

오른쪽 위 **설정** 패널의 값은 두 엔진에 똑같이 적용된다. 값을 바꾸면 진행 중인 비교 연결을 끝내고
다음 질문부터 새 설정을 쓴다(음성은 말하기를 다시 누른다).

## 방식

| 방식 | `connection_mode` | 흐름 | 쓰임 |
| --- | --- | --- | --- |
| Agent 연결(기본) | `agent` | STT → Foundry Agent → TTS. 두 Agent는 같은 모델·지시를 쓰고 검색 도구만 다르다 | 검색 엔진 공정 비교 |
| End-to-end | `realtime_agent_tool` | Realtime 모델이 음성을 직접 듣고 말한다. WebIQ는 세션 MCP 도구, Bing은 앱 서버가 부르는 Toolbox Web Search(없으면 Bing Agent)를 쓴다 | 응답 속도 확인 |

## 항목

| 항목 | 선택 | 적용 범위 |
| --- | --- | --- |
| Realtime 모델 | `gpt-realtime`, `gpt-realtime-mini` | End-to-end |
| STT | Azure Speech(기본), MAI Transcribe(preview) | Agent 연결. End-to-end는 모델이 직접 듣는다 |
| TTS 음성 | Azure Neural·DragonHD 한국어 음성. End-to-end는 OpenAI native 음성도 고를 수 있다 | 둘 다 |
| TTS 말하기 속도 | 0.5–1.5배 | Azure 음성 |
| 발화 종료 감지 | Azure 다국어 Semantic VAD(기본), Server VAD | 둘 다 |
| 지연 관련 | 무음 대기(100–2000 ms), VAD 임계값(0–1), 의미 기반 종료 임계값, 말로 답변 끊기, 서버 소음 억제, 서버 에코 제거 | 둘 다 |

빈 숫자와 "기존 서비스 설정 유지"는 서비스 기본값을 쓴다. 지연 설정은 발화 감지·재생 설정이며
검색이나 추론 시간을 줄이지 않는다.

## 서비스에서 확인한 제약

- End-to-end는 엔진마다 모델이 음성을 따로 듣는다. 같은 말도 두 엔진이 다르게 이해할 수 있어, 엔진 비교에는 Agent 연결을 쓴다.
- End-to-end 자막은 별도 인식 모델이 만들어 모델이 이해한 내용과 다를 수 있다. 그래서 화면에 표시하지 않는다.
- 세션 MCP 도구는 도구 목록이 준비되기 전에 질문하면 도구 없이 답한다. 앱은 목록이 준비된 뒤에 준비 완료를 알린다.
- MCP 검색으로 끝난 응답 뒤에는 서비스가 스스로 답하지 않는다. 앱은 검색 결과가 온 뒤 후속 응답을 요청한다(발화당 최대 3회).
- WebIQ 세션 도구는 `web`, `news`, `places`, `finance`만 허용한다.
- Voice Live가 Toolbox Web Search를 직접 부르면 결과가 빈 글이 된다. 그래서 앱 서버가 대신 호출한다. 검색 한 번에 9–14초 걸렸다(WebIQ 0.5–0.7초).
- End-to-end에서 Bing이 Bing Agent로 연결되면 Agent 답변을 그대로 전달한다. OpenAI native 음성은 이 직접 전달과
  함께 쓸 수 없어, native 음성을 고르면 선택한 모델이 답변을 다시 구성한다(API 값 `return_agent_response_directly`).
- WebIQ 키는 세션을 시작할 때 프로젝트 연결에서 읽어 서버 메모리에만 최대 10분 둔다. 브라우저, 로그, trace에는 보내지 않는다.

## WebSocket API

브라우저와 같은 Origin에서 `/ws/voice`로 연결한다. Azure 배포에서는 Microsoft Entra 로그인이 필요하다.

| 방향 | 메시지 |
| --- | --- |
| 클라이언트 → 서버 | `{"type": "start", "provider": "webiq" 또는 "bing", "context": "", "voice_options": {...}}`, `{"type": "text", "text": "..."}`, PCM16 24 kHz 모노 바이너리 프레임, `{"type": "stop"}` |
| 서버 → 클라이언트 | `status`, `activity`, `transcript`, `flow`, `tool`, `citation`, `audio`, `usage`, `response_done`, `interrupt`, `error`, `done` |

- `voice_options`를 빼면 Agent 연결 기본값을 쓴다. 모르는 키, 지원하지 않는 모드나 값은 오류로 거부한다.
- 질문과 앱 맥락은 각각 4,000자 이내, 오디오 프레임은 48,000바이트 이내다.
- 프로세스당 동시 세션은 4개다. 비교 화면은 질문마다 두 세션을 쓴다.
- `/api/config`는 클라우드를 호출하지 않는다. 엔진별 설정 상태와 선택 가능한 음성 설정을 돌려준다.
