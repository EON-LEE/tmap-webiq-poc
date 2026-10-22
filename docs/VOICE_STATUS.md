# 음성 연결 검증 기록

실제 서비스로 확인한 결과를 최신순으로 적는다. 각 확인은 1회 관측이며 성능 벤치마크가 아니다.
정확성 비교는 [V9 보고서](REPORT.md)를 따른다. 근거 JSON은 `results/`에 있다.

## 2026-10-22: 미사용 기능 삭제, 한 명령 배포 검증

- 화면에서 쓰지 않는 기능을 삭제했다: 앱 조작 데모(`model_tools`), STT → LLM → TTS(`model_search`),
  서버 trace 조회(`/api/traces`), `tmap compare`. 남은 방식은 Agent 연결과 End-to-end다.
- `scripts/provision.py --apply`로 새 리소스 그룹에 환경 전체를 만들었다. `gpt-6-luna` 할당량이 모두 사용 중이라
  시험 모델은 `gpt-5-mini`(용량 300)였다. 약 20분이 걸렸고, 그중 인프라 배포가 15분 51초였다(대부분 Container Apps 환경 생성).
- 로그인 토큰으로 호출한 `/api/config`는 두 엔진 모두 설정 완료였고, 로그인 없는 요청은 차단됐다.

| "삼성전자 주식의 최근 정보…" | WebIQ | Grounding with Bing |
| --- | --- | --- |
| Agent 연결 | `finance` 검색, 첫 음성 4.98초, TTS 1,729,800바이트 | 첫 시도는 `gpt-5-mini` Agent가 검색 없이 "검색해도 될까요?"라고 되물었다. 재시도에서 인용 1개, TTS 783,000바이트 |
| End-to-end | `finance` 검색, 첫 음성 1.95초, TTS 984,000바이트 | Toolbox `web_search`, 첫 음성 21.93초, TTS 847,800바이트 |

- 같은 명령을 다시 실행하자 2.4분 만에 끝났다. Agent 버전, Toolbox, 로그인 앱과 비밀값을 재사용했고 리비전은 바뀌지 않았다.
- 시험 환경은 확인 뒤 삭제했다(리소스 그룹 삭제, Foundry 계정 purge, 로그인 앱 삭제). 결과 파일은 남기지 않았다.

## 2026-10-21: 새 구독에 전체 재배포, Agent 모델 교체

- 기존 리소스를 재사용하지 않고 East US 2에 새 환경을 만들었다. 구성은 Foundry 계정·프로젝트, 모델 배포,
  Grounding with Bing, ACR, Container Apps, 관리 ID, Entra 로그인이다.
- 로컬 환경 변수에 남아 있던 WebIQ 키는 HTTP 401로 거부됐다. 유효한 키로 프로젝트 연결을 다시 만들었다.
- `gpt-5.4-mini` Agent는 WebIQ MCP 요청에서 용량 800(분당 80만 토큰)에서도 HTTP 429를 반환했다.
  같은 배포에 대한 일반 모델 호출은 성공했다.
- Agent를 `gpt-5-mini`로 바꾸자 두 엔진 모두 답했다. 이어서 `gpt-6-luna`(용량 250)로 바꿨다.

| `gpt-6-luna` 확인 | WebIQ | Grounding with Bing |
| --- | --- | --- |
| Agent 직접 호출(답변 완료) | 4.65초, `mcp_call` 후 답변 | 5.61초, Bing 검색 후 답변 |
| 배포 앱 WebSocket(질문 → 음성 완료) | 16.52초, `mcp_call`, TTS 1,279,200바이트 | 15.50초, 인용 1개, TTS 1,081,800바이트 |

이 확인의 결과 파일은 남기지 않았다.

## 2026-10-04: 음성 송신 버퍼 보호 수정

- 버퍼 보호가 끊던 사례는 네트워크 역압보다 브라우저 메인 스레드 정지로 보였다. 이 판단은 가설이며
  재현 측정은 하지 않았다.
- 이제 96,000바이트 초과 상태가 1.5초 이상 이어지거나 480,000바이트를 넘을 때만 연결을 끊는다.
- 큰 도구 결과의 원본 표시 길이를 줄여 정지 원인을 완화했다. 회귀 테스트를 추가했다.

## 2026-09-29: End-to-end 개선과 지연 측정

- **Bing 웹 검색:** End-to-end의 Bing을 Bing Agent 대신 Foundry Toolbox의 Bing 기반 Web Search로 바꿨다.
  Voice Live가 Toolbox MCP를 직접 부르면 결과가 빈 글이 되어, 앱 서버가 대신 검색해 함수 결과로 넘긴다.
  Toolbox 검색은 9–14초(배포 앱 첫 호출 31초), WebIQ 검색은 0.5–0.7초였다.
  근거: [`e2e_websearch_azure_text_20260929.json`](../results/e2e_websearch_azure_text_20260929.json),
  [`e2e_websearch_azure_voice_20260929.json`](../results/e2e_websearch_azure_voice_20260929.json)
- **자막과 모델 이해:** End-to-end 자막은 별도 인식 모델이 만들어 모델이 들은 내용과 다를 수 있다.
  같은 음성을 두 엔진이 다르게 이해한 사례가 있어 End-to-end에서는 자막을 표시하지 않는다.
  엔진 비교에는 두 Agent가 같은 인식 문장을 받는 Agent 연결을 쓴다.
  근거: [`e2e_azure_voice_20260929.json`](../results/e2e_azure_voice_20260929.json),
  [`agent_azure_voice_hynix_20260929.json`](../results/agent_azure_voice_hynix_20260929.json)
- **답변 순서:** 검색 결과가 오기 전에 답변을 요청해 "잠시만요"로 끝나던 문제를 고쳤다.
  검색 전에 한 말은 "대기 멘트"로 따로 표시하고, 응답 시작 시간은 검색 뒤 실제 답변부터 잰다.
- **생각 단계 표시:** 단계 그림을 질문 → 생각 → 검색 → 찾은 결과 → 답변으로 바꾸고 단계별 시간을 적는다.
  근거: [`thinking_azure_text_20260929.json`](../results/thinking_azure_text_20260929.json),
  [`thinking_azure_voice_20260929.json`](../results/thinking_azure_voice_20260929.json)
- **발화 종료 감지:** 합성 음성 "서울역 근처 충전소 찾아줘."를 Agent 연결·WebIQ로 설정별 1회씩 측정했다.
  가장 긴 구간은 질문 확정 뒤 Agent가 검색을 시작하기까지의 약 2–3초였다.
  근거: [`turn_detection_timing_20260929.json`](../results/turn_detection_timing_20260929.json)

| 설정 | 말 끝 감지 | 질문 글자 확정 | 첫 검색 호출 | 첫 답변 음성 |
| --- | --- | --- | --- | --- |
| Semantic VAD 기본 | 0.74초 | 1.44초 | 4.42초 | 6.41초 |
| Semantic VAD · 무음 300 ms | 0.63초 | 1.32초 | 3.35초 | 5.62초 |
| Server VAD 기본 | 0.73초 | 1.40초 | 3.48초 | 5.96초 |
| Server VAD · 무음 300 ms | 0.64초 | 1.34초 | 3.44초 | 5.39초 |

## 2026-09-28: 동시 비교 화면

질문 한 번을 두 Agent에 동시에 보내 나란히 보여 주는 화면으로 바꿨다. 로컬 브라우저와 배포 앱에서
텍스트 "삼성전자 주식 찾아줘."와 음성 "서울역 근처 충전소 찾아줘."(가짜 마이크)에 두 엔진 모두 답했다.

근거: [`compare_browser_text_20260928.json`](../results/compare_browser_text_20260928.json),
[`compare_browser_voice_20260928.json`](../results/compare_browser_voice_20260928.json),
[`compare_azure_20260928.json`](../results/compare_azure_20260928.json)

## 2026-09-23: 연결 방식별 검색 도구, 첫 Azure 배포

- Voice Live 세션 도구는 `function`, `mcp`, `foundry_agent`만 지원한다. Grounding with Bing은 Foundry Agent 도구로만 쓴다.
- MCP로 끝난 응답 뒤에는 서비스가 답하지 않아 앱이 후속 `response.create`를 보낸다.
- 당시의 STT → LLM → TTS 방식은 2026-10-22에 삭제했다.
- Azure Container Apps에 배포하고 Entra 로그인 토큰으로 여러 조합의 실제 답변을 확인했다.

근거: [`voice_tool_capability_20260923.json`](../results/voice_tool_capability_20260923.json),
[`voice_tool_capability_mcp_20260923.json`](../results/voice_tool_capability_mcp_20260923.json),
[`voice_tool_capability_mcp_20260923_02.json`](../results/voice_tool_capability_mcp_20260923_02.json),
[`voice_tool_capability_mcp_20260923_03.json`](../results/voice_tool_capability_mcp_20260923_03.json),
[`voice_webiq_direct_mcp_20260923.json`](../results/voice_webiq_direct_mcp_20260923.json),
[`voice_text_model_availability_20260923.json`](../results/voice_text_model_availability_20260923.json),
[`voice_pipeline_app_20260923.json`](../results/voice_pipeline_app_20260923.json),
[`voice_pipeline_app_20260923_02.json`](../results/voice_pipeline_app_20260923_02.json),
[`voice_pipeline_app_20260923_03.json`](../results/voice_pipeline_app_20260923_03.json),
[`voice_pipeline_app_20260923_04.json`](../results/voice_pipeline_app_20260923_04.json),
[`voice_pipeline_azure_20260923.json`](../results/voice_pipeline_azure_20260923.json),
[`voice_pipeline_azure_20260923_02.json`](../results/voice_pipeline_azure_20260923_02.json)

## 2026-09-21: 실행 흐름 관측

SDK 요청, 도구 인수·결과, 답변·음성 이벤트 중 공개 가능한 값만 `flow` 이벤트로 화면에 보낸다.
내부 추론, 숨은 프롬프트, 인증값, 원본 오디오는 보내지 않는다. Bing은 원시 검색 결과를 공개하지 않아 인용만 보인다.

근거: [`agent_flow_services_20260921.json`](../results/agent_flow_services_20260921.json),
[`agent_flow_audio_20260921.json`](../results/agent_flow_audio_20260921.json)

## 2026-09-20: 고객 미팅용 검색 채팅

- 실제 TTS로 만든 질문을 브라우저 AudioWorklet → 앱 → Voice Live → 검색 Agent → TTS 경로로 확인했다.
  입력 장치는 테스트용 가상 스트림이며 물리 마이크·스피커는 확인하지 않았다.
- 첫 WebIQ 음성 시도는 송신 버퍼 보호로 중단됐다. 이 문제는 2026-10-04에 수정했다.

근거: [`meeting_voice_text_20260920.json`](../results/meeting_voice_text_20260920.json),
[`meeting_browser_chat_20260920.json`](../results/meeting_browser_chat_20260920.json),
[`meeting_browser_audio_20260920.json`](../results/meeting_browser_audio_20260920.json),
[`meeting_browser_completion_20260920.json`](../results/meeting_browser_completion_20260920.json)

## 2026-09-10: 앱 조작 데모

텍스트 모델이 앱 함수를 호출해 화면 상태를 바꾸는 `model_tools` 경로를 확인했다. 2026-10-22에 삭제했다.
근거: [`voice_model_app_control_20260910_01.json`](../results/voice_model_app_control_20260910_01.json)

## 2026-09-08: 첫 음성 연결

Voice Live에서 Bing Agent와 WebIQ Agent의 실제 답변·음성과, WebIQ `mcp_call`의 Foundry trace를 확인했다.
당시 결과 파일은 저장소에 없다.
