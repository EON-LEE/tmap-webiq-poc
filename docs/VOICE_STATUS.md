# 음성 연결 현황

실제 연결 기록 기준: 2026-09-08, 2026-09-10, 2026-09-20, 2026-09-21, 2026-09-23, 2026-09-28, 2026-09-29 UTC. 성능 벤치마크와 별도의 소량 기능 확인.

## 2026-09-29: End-to-end의 Bing을 Agent 없이 Foundry Toolbox Web Search로 연결

사용자 요청으로 End-to-end의 Bing 쪽을 Bing Agent 대신 **Foundry Toolbox의 Bing 기반 Web Search**로 바꿨다.
이제 두 모드로 시연한다. **Agent 연결**은 같은 모델·지시의 두 Agent가 검색 도구만 달리해 답하고,
**End-to-end**는 Agent 없이 음성 모델이 WebIQ 검색과 Bing 웹 검색을 직접 부른다.

- 공식 문서 기준 Grounding with Bing 도구는 Agent 안에서만 쓸 수 있고 Toolbox에 넣을 수 없다. 같은 Bing 기반인
  Web Search 도구는 Toolbox에 넣으면 MCP 주소(`/toolboxes/{name}/mcp`)로 노출된다. 프로젝트에 `tmap-web-search`
  Toolbox를 만들었다(버전 2: `web_search` + 한국 위치, 기본값).
- Voice Live가 Toolbox MCP를 직접 부르게 해 보니 Entra 토큰은 `headers.Authorization`에 너무 길어 거부됐고
  (`authorization` 필드는 통과), 호출은 끝나도 Toolbox가 결과를 MCP `resource` 형식으로 돌려줘 모델이 받은 결과가
  빈 글이었다(모델이 “확인 중입니다”만 반복). 그래서 모델에는 `web_search` 함수를 주고 앱 서버가 Toolbox MCP를 불러
  결과 글과 출처를 함수 결과로 넘긴다.
- Toolbox Web Search 한 번은 앱에서 직접 잰 값으로 9–14초, 배포 앱의 첫 호출은 31초였다. Toolbox 안에서 Bing 결과를
  긴 답변 글로 정리하기 때문으로 보인다. WebIQ 검색은 0.5–0.7초였다.
- 화면은 Bing 칸에 “모델이 Bing으로 검색한 내용 · 웹 검색”, 검색어, 검색 답변 요약과 출처 링크를 보여 준다.
  End-to-end 설정에서는 쓰이지 않는 “Bing Agent 답변 전달”을 숨긴다.

배포 앱(리비전 9)에서 1회씩 확인했다.

| End-to-end 질문 | WebIQ | Grounding with Bing(Toolbox Web Search) |
| --- | --- | --- |
| 텍스트 “삼성전자 주가 알려줘.” | 금융 조회 0.7초, 응답 시작 1.4초, 272,500원 | 웹 검색 31.3초(첫 호출), 출처 5개, 응답 시작 32.0초, 272,500원 +1.06% |
| 음성 “하이닉스 주식 종가 알려줘.” | 금융 조회 0.5초, 응답 시작 0.9초, 1,765,000원 | 웹 검색 8.9초, 출처 3개, 응답 시작 9.6초, 종가 1,765,000원 |

같은 배포에서 Agent 연결도 그대로 동작했다(“서울역 근처 충전소 찾아줘.”: WebIQ 장소 검색 10건, Bing 답변, 응답 시작 약 4.7초).
근거: [`e2e_websearch_azure_text_20260929.json`](../results/e2e_websearch_azure_text_20260929.json),
[`e2e_websearch_azure_voice_20260929.json`](../results/e2e_websearch_azure_voice_20260929.json)

## 2026-09-29: End-to-end 점검 — 설정 잠김, 자막과 모델 이해 차이, 검색 결과 전 답변 요청

사용자가 End-to-end로 “하이닉스”를 말했는데 화면 자막은 “하이브”였고, WebIQ는 하이닉스를, Bing은 하이브를 찾았다.
End-to-end도 Voice Live다(`model=gpt-realtime-mini`로 연결). 점검 결과와 조치는 다음과 같다.

- **자막은 모델이 들은 내용이 아니다.** Realtime 모델은 음성을 직접 받고, 화면 자막은 별도 인식 모델
  (`gpt-4o-mini-transcribe`)이 따로 만든다. Voice Live API 문서도 자막이 모델의 해석과 다를 수 있다고 적는다.
  엔진마다 세션이 따로라 같은 음성을 두 모델이 다르게 이해할 수 있다. 처음에는 “자막”으로 표시했으나
  사용자 요청으로 End-to-end에서는 자막을 아예 없앴다(질문 줄은 “음성 질문 · 모델이 음성을 직접 들어요”).
  받아쓰기가 실패해도 End-to-end 연결은 끊지 않는다. Agent 연결의 인식 문장은 “Agent가 받은 질문”으로 표시한다.
  모델이 이해한 내용은 WebIQ 검색어와 Bing Agent에 보낸 요청으로 확인한다.
- **설정이 잠겨 있었다.** 질문 뒤 연결이 열려 있는 동안 방식·모델 외 11개 설정이 비활성이었다.
  이제 모든 설정을 언제든 바꿀 수 있고, 바꾸면 연결을 끝내고 다음 질문부터 새 설정으로 비교한다.
  OpenAI native 음성은 Bing 답변 전달을 먼저 바꿔야만 보였는데, 이제 바로 고르면 필요한 설정이 함께 바뀐다.
  End-to-end에서는 STT 항목을 숨긴다.
- **WebIQ가 검색 결과 없이 답하던 문제.** 검색 호출은 응답이 끝난 뒤 실행되는데(응답 종료 11.82초 → 검색 시작 11.83초
  → 완료 12.32초), 앱이 응답 종료 즉시 답변을 요청해 모델이 “확인하고 있어요, 잠시만요”만 말하고 끝났다.
  이제 검색이 돌아온 뒤 답변을 요청한다.
- **대기 멘트를 답변으로 계산하던 문제.** 사용자 사례의 “응답 0.6초”는 “잠시만요” 대기 멘트였다.
  검색 전에 한 말은 “대기 멘트”로 따로 표시하고, 응답 시작 시간은 검색 뒤 실제 답변부터 잰다.
- 고객 미팅을 위해 로그인을 임시로 껐다. [배포 안내](DEPLOYMENT.md)

배포 앱에서 같은 합성 음성 “하이닉스 주식 종가 알려줘.”를 가짜 마이크로 넣어 두 방식을 1회씩 비교했다.

| 방식 | WebIQ | Grounding with Bing |
| --- | --- | --- |
| End-to-end | 자막 “하이닉스…”, 모델 검색어 “SK하이닉스 주가”, 결과 1건, 응답 시작 1.0초 | 자막 “**테이닉스**…”, 모델이 Agent에 보낸 요청 “**파이닉스** 주식 종가” → Agent가 “혹시 SK하이닉스라면…”으로 추측, 응답 시작 4.2초 |
| Agent 연결 | 인식 “하이닉스 주식 종가 알려줘.”, 금융 조회 1회, SK하이닉스 종가 답변, 응답 시작 5.3초 | 인식 “하이닉스 주식 종가 알려줘.”, 출처 1개, SK하이닉스 종가 답변, 응답 시작 7.1초 |

같은 음성인데 End-to-end에서는 두 엔진이 서로 다른 질문을 받았다. 자막을 없앤 뒤 배포 확인에서 같은 음성을 End-to-end로 한 번 더 넣었을 때는
WebIQ 쪽 모델이 질문을 알아듣지 못해 “어떤 걸 알려드릴까요?”라고 되물었고, Bing 쪽 모델은 “지금의 주식 종가”로 이해했다.
End-to-end는 같은 음성도 실행마다 알아듣는 내용이 달랐다. 검색 엔진 비교에는 Agent 연결을 쓴다.
End-to-end는 응답이 빠른 대신(WebIQ 1.0초) 엔진마다 이해가 달라질 수 있음을 설명할 때만 쓴다.
각 1회 관측이며 합성 음성이라 실제 마이크·주변 소음과는 다를 수 있다.
근거: [`e2e_azure_voice_20260929.json`](../results/e2e_azure_voice_20260929.json),
[`agent_azure_voice_hynix_20260929.json`](../results/agent_azure_voice_hynix_20260929.json)

## 2026-09-29: Agent가 생각하는 구간 표시, STT → LLM → TTS 화면 제외

질문 뒤 Agent가 검색을 시작하기까지 2–3초 동안 화면에 변화가 없어, 질문을 이해하지 못한 것처럼 보였다.
엔진별 단계 그림을 **질문 → 생각 → 검색 → 찾은 결과 → 답변** 5단계로 바꾸고, 단계가 끝나면 걸린 시간을 적는다.
답변이 나오기 전까지 답변 자리에 지금 하는 일을 말풍선으로 보여 준다
(말씀을 듣는 중 → 글자로 바꾸는 중 → 생각하는 중 → WebIQ로 ○○ 검색 중 → 답변 준비 중).
Grounding with Bing은 검색이 Agent 안에서 처리되어 생각과 검색을 나눌 수 없으므로 “생각·검색 중”, “검색 포함 x.x초”로 표시한다.
Bing 안내 문구는 “Bing은 검색 결과 원문을 공개하지 않아요. 답변에 사용한 출처 링크만 받을 수 있어요.”로 고쳤다
(이전 문구의 “검색어도 공개되지 않는다”는 Foundry API 기준으로 정확하지 않았다).
STT → LLM → TTS는 비교 시연에 필요 없어 설정 화면에서 뺐다(API는 유지). End-to-end는 그대로 둔다.
시간은 브라우저가 서비스 이벤트를 받은 시각 기준이다. Agent 연결에서는 검색 완료가 답변 시작과 거의 함께 전달되어
WebIQ의 검색 시간에 답변을 쓰기 시작하는 시간이 포함될 수 있다.

배포된 앱(Microsoft Entra 인증)에 격리된 헤드리스 Chrome으로 접속해 150 ms마다 화면을 기록했다.

| 질문 | WebIQ | Grounding with Bing |
| --- | --- | --- |
| 텍스트 “삼성전자 주식 찾아줘.” | 생각 2.7초 → 금융 조회 1.4초 → 결과 1건, 응답 시작 4.1초 | 생각(검색 포함) 4.6초 → 출처 1개, 응답 시작 4.6초 |
| 음성 “서울역 근처 충전소 찾아줘.”(가짜 마이크) | 인식 0.7초 → 생각 2.5초 → 장소 검색 1.6초 → 결과 10건 → 작성 0.2초, 응답 시작 5.0초 | 인식 0.9초 → 생각(검색 포함) 8.2초 → 출처 1개, 응답 시작 9.1초 |

두 엔진 모두 생각 단계 말풍선이 실제로 표시됐고, 페이지 오류·모바일 가로 넘침은 없었다. 각 1회 관측이다.
근거: [`thinking_azure_text_20260929.json`](../results/thinking_azure_text_20260929.json),
[`thinking_azure_voice_20260929.json`](../results/thinking_azure_voice_20260929.json)

## 2026-09-29: 발화 종료 감지와 답변 지연 측정

사용자가 실제 마이크로 “말이 끝났다는 인식이 느리다”고 보고했다. Voice Live TTS로 만든
“서울역 근처 충전소 찾아줘.” 음성을 앱 WebSocket에 100 ms 단위로 실시간 전송하고,
말이 실제로 끝난 시점부터 각 단계가 도착한 시간을 쟀다(Agent 연결 · WebIQ, 설정별 1회씩).

| 설정 | 말 끝 감지 | 질문 글자 확정 | 첫 검색 호출 | 첫 답변 음성 |
| --- | --- | --- | --- | --- |
| 기본(Azure 다국어 Semantic VAD, 무음 대기 서비스 기본값) | 0.74초 | 1.44초 | 4.42초 | 6.41초 |
| Semantic VAD · 무음 300 ms | 0.63초 | 1.32초 | 3.35초 | 5.62초 |
| Server VAD · 기본 | 0.73초 | 1.40초 | 3.48초 | 5.96초 |
| Server VAD · 무음 300 ms | 0.64초 | 1.34초 | 3.44초 | 5.39초 |

서비스가 알려 준 발화 종료 위치로 보면 기본 무음 대기는 약 500 ms다. 300 ms로 줄여도 말 끝 감지는 약 0.1초만 빨라졌다.
말하는 동안 중간 인식 글자는 오지 않았고(Azure Speech), 질문 글자는 말이 끝나고 약 1.3–1.4초 뒤에 확정됐다.
가장 긴 구간은 질문 확정 뒤 Agent가 검색을 시작하기까지의 약 2–3초였다.
깨끗한 합성 음성의 1회 측정이며, 실제 마이크 주변 소음은 말 끝 감지를 늦출 수 있다.

근거: [`turn_detection_timing_20260929.json`](../results/turn_detection_timing_20260929.json)

## 2026-09-28: WebIQ vs Grounding with Bing 동시 비교 화면

고객 시연 목표를 “TMAP 고객에게 WebIQ와 Grounding with Bing을 비교해 WebIQ 도입을 설득”으로 다시 정했다.
화면은 질문 한 번을 두 Agent에 동시에 보내 나란히 보여 준다. 엔진마다 질문 → 검색 → 찾은 결과 → 답변
4단계를 그림으로 표시하고, WebIQ는 검색 종류·검색어·결과를, Bing은 비공개 검색과 답변 출처를 보여 준다.
연결 방식·모델 선택과 앱 조작 데모, 자세한 이벤트 목록은 기본 화면에서 뺐다(설정 패널에 음성 처리 방식은 남김).
서버는 비교 한 번에 세션 두 개를 쓰므로 동시 세션 한도를 2개에서 4개로 올렸다. 그 밖의 백엔드 동작은 바꾸지 않았다.

로컬 서버와 격리된 헤드리스 Chrome에서 실제 서비스로 확인했다(데스크톱 1440×1000, 모바일 390×844, 페이지 오류·가로 넘침 없음).

| 질문 | WebIQ | Grounding with Bing |
| --- | --- | --- |
| 텍스트 “삼성전자 주식 찾아줘.” | 금융 조회 1회(검색 1.8초), 결과 1건(주가·등락률), 응답 시작 4.5초 | 검색 비공개, 출처 1개, 응답 시작 4.5초 |
| 음성 “서울역 근처 충전소 찾아줘.”(가짜 마이크) | 두 엔진 모두 음성 인식, 장소 검색 1회(1.5초), 결과 10건(분류·24시간 영업·좌표), 응답 시작 5.0초 | 검색 비공개, 출처 1개, 응답 시작 4.4초 |

음성 확인은 Voice Live TTS로 만든 질문 음성을 Chrome의 가짜 마이크 입력으로 넣은 것이다.
한 마이크 입력이 두 엔진에 똑같이 전달되고 같은 비교 행으로 정렬됐다. 물리 마이크·스피커 확인은 아니다.
응답 시간은 각 한 번의 관측값이며 벤치마크가 아니다. 두 엔진 답변의 사실 정확성은 평가하지 않았다.

같은 코드를 Azure Container Apps에 배포하고, Microsoft Entra 로그인 토큰으로 두 엔진을 동시에 호출해
둘 다 실제 답변을 받았다(WebIQ `finance` 호출, Bing 출처 1개). 로그인 없이는 여전히 401이다.

근거:
- [`compare_browser_text_20260928.json`](../results/compare_browser_text_20260928.json): 실제 브라우저 텍스트 비교
- [`compare_browser_voice_20260928.json`](../results/compare_browser_voice_20260928.json): 실제 브라우저 음성 비교(가짜 마이크)
- [`compare_azure_20260928.json`](../results/compare_azure_20260928.json): 배포 앱에서 두 엔진 동시 호출

## 2026-09-23: 연결 방식별 검색 도구 연결 확인

Voice Live 공식 문서는 한 모델 표에서 입력 방식으로 구분한다.
`gpt-realtime` 계열은 음성을 직접 입력받는 **end-to-end** 모델이고,
`gpt-4.1`·`gpt-5` 계열 텍스트 모델은 **Azure STT → LLM → Azure TTS**로 동작한다.
**Agent 연결**은 기존 Foundry Agent의 텍스트 모델을 사용하며 이 화면에서 답변 모델을 바꾸지 않는다.
세션 도구는 `function`, `mcp`, `foundry_agent`만 문서화되어 있으며 Bing 도구는 없다.
독립 Bing Search API는 2025-08-11 종료됐고 Grounding with Bing은 Foundry Agent 도구로만 사용한다.

기존 리소스와 Agent `:1`만 사용해 텍스트 질문으로 확인했다. 새 리소스·Agent·권한은 만들지 않았다.

| 구성 | 결과 |
| --- | --- |
| `gpt-4.1-mini` + WebIQ Agent(`foundry_agent`) | 텍스트 모델이 Agent를 호출하고 결과로 답변. 서비스가 후속 응답을 자동 생성 |
| `gpt-5-mini` + WebIQ·Bing Agent 동시 | 한 세션에서 두 Agent 모두 호출, 두 결과를 함께 답변 |
| `gpt-realtime-mini` + WebIQ·Bing Agent 동시 | end-to-end 모델에서도 두 Agent 모두 호출 |
| `gpt-4.1-mini` + 공개 MCP 직접 연결 | 도구 목록·검색 호출·원본 결과 확인. 서비스가 이어서 답하지 않아 앱의 후속 `response.create` 1회 필요 |
| `gpt-realtime-mini` + 공개 MCP 직접 연결 | 검색 → 문서 조회 호출 후 답변. 도구 호출마다 앱의 후속 요청 필요(2회) |

Agent 호출 방식에서는 Agent에 보낸 질문과 Agent 답변만 수신했다. Agent 내부의 검색어·원본 결과는
전달되지 않는다. 출처는 선택 모델이 Agent 답변을 다시 정리한 확인에서는 0건(9월 8일 결과 포함)이었고,
Agent 답변을 그대로 전달한 `gpt-5-mini` 앱 확인에서는 Bing 인용 2건이 전달됐다.
MCP 직접 연결은 먼저 공개 Microsoft Learn MCP로 확인한 뒤, 사용자 승인에 따라 WebIQ Agent의 기존
프로젝트 연결에서 키를 읽어 WebIQ MCP(`https://api.microsoft.ai/v3/mcp`)로 확인했다.
Voice Live의 세션 MCP 도구는 Foundry 프로젝트 연결을 참조하지 않고 요청 헤더로 인증한다.

추가 텍스트 모델 `gpt-5`, `gpt-5.6-luna`, `gpt-4.1`, `gpt-4o-mini`도 이 Voice Live 리소스에서 답변했다.

### 구현과 앱 확인

화면에 **Agent 연결 / STT → LLM → TTS / End-to-end** 연결 방식을 두었다.
WebIQ는 선택한 모델에 MCP로 직접, Bing은 Bing Agent 도구로 연결한다.
WebIQ 도구 목록이 준비된 뒤에만 대화를 시작하고, 도구 호출로 끝난 응답에는 앱이 답변 생성을 요청한다(최대 3회).
실행 흐름은 검색 연결 방식, 세션 검색 도구(키 제외), 위임한 질문, 후속 답변 요청을 보여 준다.

앱 WebSocket으로 “삼성전자 주식 찾아줘.”를 여섯 조합에 보내 모두 실제 답변과 TTS를 받았다.
응답 이벤트에 키나 헤더가 포함되지 않음을 확인했다.

| 조합 | 실제 동작 |
| --- | --- |
| Agent 연결 · WebIQ | Agent가 `finance` 호출 후 답변 |
| Agent 연결 · Bing | 답변과 인용 1건. 도구 정보는 수신되지 않음 |
| STT → LLM → TTS · WebIQ · `gpt-4.1-mini` | 모델이 `finance` 직접 호출, 앱 후속 요청 1회 후 답변 |
| STT → LLM → TTS · Bing · `gpt-5-mini` | 원문과 맥락을 Bing Agent에 위임, Agent 답변과 인용 2건 |
| End-to-end · WebIQ · `gpt-realtime-mini` | 영어·한국어 검색 두 번, 앱 후속 요청 2회 후 답변 |
| End-to-end · Bing · `gpt-realtime-mini` | “삼성전자 주식”만 위임해 Bing Agent가 원하는 정보를 되물음 |

확인 과정에서 두 결함을 고쳤다. `gpt-realtime-mini`가 대기 멘트를 말하면서 같은 응답에서
다시 검색하면 후속 요청을 보내지 않던 문제, 그리고 후속 응답을 대기 멘트로만 끝내던 문제다.
이제 응답의 마지막 항목이 검색 호출이면 후속 요청을 보내고, 후속 요청에 검색 결과로 답하라는 지시를 붙인다.
Bing 위임 지시에는 원문을 줄이지 말라는 문구를 추가했다. `gpt-5-mini`는 원문을 넘겼지만
`gpt-realtime-mini`는 여전히 짧게 넘겨 Agent가 되물었다. 이는 모델별 실제 차이로 기록한다.

근거:
- [`voice_tool_capability_20260923.json`](../results/voice_tool_capability_20260923.json): Agent 도구 3건. MCP 2건은 도구 목록 준비 전에 질문해 무효
- [`voice_tool_capability_mcp_20260923.json`](../results/voice_tool_capability_mcp_20260923.json): 확인 스크립트가 이벤트 수신을 중단시킨 무효 재시도
- [`voice_tool_capability_mcp_20260923_02.json`](../results/voice_tool_capability_mcp_20260923_02.json): 텍스트 모델 MCP 답변 확인
- [`voice_tool_capability_mcp_20260923_03.json`](../results/voice_tool_capability_mcp_20260923_03.json): end-to-end 모델 MCP 답변 확인
- [`voice_webiq_direct_mcp_20260923.json`](../results/voice_webiq_direct_mcp_20260923.json): WebIQ MCP 직접 연결(텍스트·end-to-end)과 Bing Agent 직접 전달
- [`voice_text_model_availability_20260923.json`](../results/voice_text_model_availability_20260923.json): 추가 텍스트 모델 응답 확인
- [`voice_pipeline_app_20260923.json`](../results/voice_pipeline_app_20260923.json): 첫 앱 확인. End-to-end · WebIQ가 대기 멘트로 끝난 결함 기록
- [`voice_pipeline_app_20260923_02.json`](../results/voice_pipeline_app_20260923_02.json): 후속 요청 수정 후에도 대기 멘트로 끝난 기록
- [`voice_pipeline_app_20260923_03.json`](../results/voice_pipeline_app_20260923_03.json): 여섯 조합 모두 실제 답변
- [`voice_pipeline_app_20260923_04.json`](../results/voice_pipeline_app_20260923_04.json): Bing 위임 지시 수정 후 두 Bing 조합 재확인
- [`voice_pipeline_azure_20260923.json`](../results/voice_pipeline_azure_20260923.json): Azure Container App에서 Entra 로그인 토큰으로 여섯 조합 모두 실제 답변(앱 Managed Identity 사용)
- [`voice_pipeline_azure_20260923_02.json`](../results/voice_pipeline_azure_20260923_02.json): 저장소 배포 명령으로 교체한 새 리비전에서 두 조합 재확인. 이번에는 `gpt-realtime-mini`도 질문 원문을 Bing Agent에 넘겨 시세를 받음

### Azure 배포

같은 날 Azure Container Apps에 배포했다. Microsoft Entra 로그인이 필수이며 인증 없이 열리는 경로는 `/healthz`뿐이다.
앱은 사용자 할당 Managed Identity로 Voice Live·Foundry Agent·WebIQ 연결을 사용한다.
로컬과 같은 여섯 조합을 공개 주소의 인증 경로로 확인했다. 브라우저 마이크·스피커로는 아직 확인하지 않았다.
접속 주소와 리소스 식별자는 저장소에 기록하지 않는다. 절차는 [배포 안내](DEPLOYMENT.md)에 정리했다.

## 2026-09-21: 모드 없는 에이전트 실행 흐름

디버그 버튼·모달·설정 탭을 없앴다. 대화 오른쪽에 실제 입력, SDK 요청,
도구와 인수·반환값, 답변·음성 이벤트를 항상 표시한다. 좁은 화면에서는 대화 아래로
이어지며 배경을 `inert`로 만들지 않는다.
시나리오와 적용 가능한 엔진·모델 선택은 상단 한 줄로 모았다.
검색 대화 / 음성 모델 + 검색 / 내비게이션 조작이 실제 연결 모드를 전환하며,
사용하지 않는 모델 입력은 숨긴다. 직접 검색 Agent의 LLM은 변경하지 않는다고 명시한다.
STT·TTS·고급 설정만 접기 영역에 남겼다. 시나리오·모델 전환은 이전 연결을 종료하되
대화·실행 흐름·작성 중인 질문을 보존하며, 선택만으로 API 연결·질문 전송을 시작하지 않는다.
입력창 위 예시도 해당 시나리오에 맞춰 바뀐다. 화면 리허설은 오프라인 미리보기로 구분한다.
예시는 “삼성전자 주식 찾아줘.”, “서울역 근처 충전소 찾아줘.”, “인천공항 주차비 얼마야?”로 바꿨다.

기존 앱은 실제 도구 출력과 답변은 받았지만, SDK 제출·세션 보고값·VAD·입력 확정·
도구 인수/목록·오디오 생성 경계의 일부 이벤트를 화면으로 전달하지 않았다.
SDK 1.3.0과 공식 문서를 확인하고 공개 가능한 `flow` 관측만 추가했다.
연결 대상은 **설정값**, `service_model`은 **Voice Live 세션 보고값**으로 구분한다.
내부 추론, 숨은 프롬프트, 인증값, 원본 오디오는 노출하지 않는다.

**실제 동일 질문 확인:** 업데이트된 앱 WebSocket에 “삼성전자 주식 찾아줘.”를
각각 텍스트로 보냈다. WebIQ는 관측 이벤트 21개와 실제 `finance` 호출·완료,
TTS 1,134,000바이트를 반환했다. Bing은 관측 이벤트 13개와 답변 인용 1개,
TTS 1,131,000바이트를 반환했고 도구 호출·검색 질의는 이 경로에서 수신되지 않았다.
둘 다 실제 최종 답변과 `response_done=completed`를 받았다. 시세 정확성이나 성능 비교 결과는 아니다.

**음성 관측 확인:** 실제 Voice Live TTS로 만든 같은 질문을 PCM으로 앱 WebSocket에
실시간 전송했다. WebIQ에서 발화 시작·종료, 입력 버퍼 확정, 실제 STT 확정 문장,
`finance` 호출·완료, 오디오 생성 시작·종료, TTS 787,800바이트를 확인했다.
이 확인은 프로토콜 클라이언트의 합성 입력이며 **물리 마이크·스피커나 브라우저
AudioWorklet을 새로 검증한 것은 아니다.** 이전 브라우저 음성 확인과 구분한다.

현재 Bing 문서는 Agents API를 통한 검색 질의 확인 가능성을 설명하지만,
원시 grounding 결과는 개발자·최종 사용자에게 제공하지 않는다고 명시한다.
따라서 화면은 **이번 Voice Live 연결에서 무엇을 받았는지**만 보여 준다.
WebIQ 공개 도구 문서도 모든 연결에서 Finance를 보장하지 않으며, 이번 실제 호출과 구분한다.
자세한 지원 범위와 공식 근거는 [관측 계약](VOICE_OPTIONS.md#always-visible-api-observations)을 참고한다.

근거:
- [`agent_flow_services_20260921.json`](../results/agent_flow_services_20260921.json): 양쪽 실제 텍스트 요청·관측 이벤트·도구/인용·응답
- [`agent_flow_audio_20260921.json`](../results/agent_flow_audio_20260921.json): 실제 합성 음성 → STT·금융 조회·TTS 관측

기존 8123 시연 화면에 진행 중인 대화가 있어 종료하거나 초기화하지 않았다.
새 백엔드는 별도 **http://localhost:8124**에서 실행했다.
8124의 허용 Origin은 해당 프로세스에만 설정했으며 기존 `.env`나 Azure 리소스는 바꾸지 않았다.
모델·시나리오 선택을 간소화한 최신 화면과 관측값 보호 수정을 반영한 미리보기는
**http://localhost:8125**에 별도로 시작했다. 기존 연결은 유지하고 8125의 Origin도
새 프로세스에만 지정했다.

## 2026-09-20/21: 고객 미팅용 검색 채팅

### 확인한 문제와 조치

| 문제 | 조치 / 남은 범위 |
| --- | --- |
| 기본 화면이 실제 검색이 아닌 `model_tools` 예시 지도 | 기본을 직접 검색 Agent 채팅으로 변경. 내비게이션은 상단 시나리오에서 명시적으로 선택 |
| 전체 전사가 디버그에 숨고 Bing 인용 이벤트가 버려짐 | 사용자 전사·답변·검색 근거를 기본 채팅에 표시. 사용자 중간 전사와 확정 문장은 같은 행으로 갱신 |
| 로컬 설정은 모델 연결용 구독·Voice Live 호스트만 존재 | 기존 프로젝트와 양쪽 Agent `:1`을 읽기 전용으로 확인해 `.env` 복원. 새 Agent·리소스·권한 생성 없음 |
| WSL에서 Windows 마운트 아래 가상환경을 읽다가 실행 지연 | 잠긴 의존성을 기존 캐시에서 WSL 네이티브 파일시스템의 별도 환경으로 복원. 원래 환경을 덮어쓰지 않음 |
| 검색 원문이 길고 서로 다른 엔진의 노출 형태가 다름 | WebIQ는 실제 MCP 결과, Bing은 실제 답변 인용으로 구분. 카드 3개와 나머지 펼치기, 원본은 오른쪽 실행 흐름에서 확인 |
| 엔진을 바꿔도 같은 대화처럼 보일 위험 | 이전 연결을 종료하고 새 세션 사용. 화면의 이전 답변은 기존 엔진 표시 유지 |
| 출처만 온 응답과 늦은 이벤트가 계속 대기 중으로 보일 위험 | 응답별 `response_done` 처리·종료 상태 캐시. 세션은 유지하고 실패·중단·텍스트 미제공을 구분 |
| 설정 파일 존재를 실제 연결 성공으로 오인할 위험 | 설정 확인 범위를 API에 명시. Agent 고정 버전과 경고는 고급 설정에 표시 |
| 정확성·비용을 화면 완성도로 오인할 위험 | 시연 성공과 사실 정확성·지연·가격 벤치마크를 분리. UI 요약은 모델 입력 토큰을 줄이는 최적화가 아님 |

### 실제 확인

기존 WebIQ / Bing 검색 Agent의 고정 버전과 동일한 `gpt-5-6-luna` 모델을 확인했다.
직접 서비스 확인에서 두 경로 모두 실제 답변과 TTS 바이트를 수신했다.
별도 브라우저 질문 **“인천공항 공식 홈페이지 기준으로 제1여객터미널 장기주차장 소형차 하루 요금을 알려줘.”**에서는
두 답변 모두 하루 최대 9,000원을 반환했고, WebIQ 결과 5개와 Bing 인용 1개를 각 답변 아래 표시했다.
이 질문에서는 공항 공식 출처 링크를 확인했지만 모든 답변의 독립적인 정확성 평가는 하지 않았다.

음성 경로는 **실제 Azure TTS로 만든 3.8375초짜리 질문**을 테스트용 가상 MediaStream에 넣고,
브라우저의 실제 PCM AudioWorklet → 앱 WebSocket → Voice Live STT → 검색 Agent → TTS를 거쳤다.
양쪽에서 **“인천공항 장기주차장 하루 요금을 알려줘.”**라는 실제 STT 확정 문장을 받았고,
일반 화면에 `나 · 음성`으로 표시했다. Bing은 TTS 712,800바이트·브라우저 재생 노드 31개,
WebIQ 재시도는 843,000바이트·37개와 최종 답변을 확인했다.
**응답 이벤트는 모의 데이터가 아니지만 입력 장치는 테스트용 가상 스트림이었다.
물리 마이크, 실제 스피커 소리와 현장 소음·권한은 검증하지 않았다.**

첫 WebIQ 음성 시도에서는 96,000바이트 송신 버퍼 보호가 작동해 답변 도중 중단됐다.
실패를 보존했으며 같은 코드를 새 세션으로 재시도해 완료했다. 측정된 SDK 오디오 append는
중앙값 0.15ms·최대 12.86ms였고, 재시도 브라우저에서는 최대 1,468.8ms의 송신 스케줄 간격을 관측했다.
**근본 원인은 확정하지 않았으며**, 버퍼 제한을 올려 실패를 숨기지 않았다.
별도로, 버퍼에 데이터가 있는 비동기 송수신 루프가 다른 작업에 실행 기회를
주지 않는 문제를 회귀 테스트로 재현해 각 이벤트 후 명시적으로 양보하도록 수정했다.
이 변경과 응답 종료 처리를 반영한 서버를 재시작한 뒤, 같은 TTS 질문으로
두 엔진의 실제 음성 경로를 다시 실행했다. WebIQ는 검색 결과 5개·TTS 817,800바이트,
Bing은 인용 1개·TTS 889,200바이트와 각각 `response_done.status=completed`를 받았다.
두 화면 모두 전사·최종 답변이 표시되고 대기 표시는 사라졌으며 연결은 유지됐다.
송신 버퍼 관측 최고치는 각각 72,000 / 24,000바이트로 기존 보호 한도 이하였다.
**각 한 번의 추가 성공은 최초 중단의 원인 확정이나 재발 방지 보장은 아니다.**
미팅 전 실제 사용할 브라우저·마이크·스피커로 한 번 재생하고, 전송 지연 경고가 나오면
기존 세션을 그대로 계속하지 말고 다시 시작하거나 텍스트로 시연한다.

일반적인 주차 질문에서는 비공식 블로그가 인용되거나 불필요한 대형차 요금까지 답하기도 했다.
범위와 공식 출처를 명시한 예시 질문을 제공하되, 그것을 모든 질문에 대한 품질 보장으로 해석하지 않는다.
한 차례 직접 텍스트 확인의 API 입력 토큰은 Bing 3,534 / WebIQ 71,201이었다.
도구 설명·문맥 등을 포함한 단일 실행 관측값이며 순수 검색 토큰, 성능 우열 또는 질문당 총비용이 아니다.

**근본 원인 재검토 (후속 수정).** 관측된 피크(48,000 / 62,400 / 72,000 / 24,000바이트)가 모두
한 프레임(4,800바이트) 단위였고, 62,400바이트 사례에서 `observed_largest_send_scheduling_gap_ms = 1468.8`가
함께 기록된 점에 근거해 **"가드가 네트워크 역압이 아니라 브라우저 메인 스레드 정지를 측정하고 있었다"**는
가설을 세웠다: 메인 스레드가 큰 도구 결과를 `JSON.stringify`로 직렬화하는 동안 AudioWorklet의
`port.onmessage` 프레임이 큐에 쌓이고, 스레드가 풀리면 한꺼번에 처리되며 `socket.send()`가
연속 호출돼 `bufferedAmount`가 순간적으로 치솟는다 — 실제 전송 지연이 아니라 그 직전의 렌더링 정지가 원인이다.
WebIQ 입력 토큰(71,201)이 Bing(3,534)보다 훨씬 커서 `compare-view.js`의 원본 데이터 렌더링이
WebIQ 쪽에서 더 큰 정지를 유발했을 가능성이 높다. **이 인과관계는 자동화된 장시간-작업(long task)
측정으로 재현/반증하지 않았으며, 과거 관측값에 들어맞는 가설이다.**

이 가설에 따라 두 가지를 수정했다: (1) `app.js`의 버퍼 가드는 더 이상 `bufferedAmount` 단발
관측만으로 연결을 끊지 않는다. 96,000바이트를 넘는 상태가 `BACKPRESSURE_SUSTAIN_MS`(1.5초) 동안
지속될 때만 실제 역압으로 보고 끊으며, 480,000바이트를 넘으면 지속 시간과 무관하게 즉시 끊는
무조건적 안전장치(`BACKPRESSURE_HARD_LIMIT_BYTES`)를 유지한다. (2) `compare-view.js`의 원본
데이터 렌더링(`compactStringify`, `search-results.js`)은 직렬화 중 긴 문자열과 긴 배열을 잘라
재귀 범위를 미리 줄여, 정지의 소스 자체를 완화한다. 두 수정 모두 `96,000바이트 한도를 올려 실패를
숨기지 않는다`는 원칙을 지킨다. 회귀 테스트는 `tests/frontend.test.cjs`에 추가했다
(일시적 스파이크는 통과, 지속된 역압과 하드 캡 초과는 여전히 실패 처리).

근거:
- [`meeting_voice_text_20260920.json`](../results/meeting_voice_text_20260920.json): 실제 서비스 확인 원본
- [`meeting_browser_chat_20260920.json`](../results/meeting_browser_chat_20260920.json): 실제 텍스트 UI 관측 요약
- [`meeting_browser_audio_20260920.json`](../results/meeting_browser_audio_20260920.json): 합성 음성 입력의 실패·완료 시도와 한계
- [`meeting_browser_completion_20260920.json`](../results/meeting_browser_completion_20260920.json): 송수신 양보·응답 종료 처리 반영 후 서버 재시작 및 양쪽 실제 음성 경로 재확인
- 기존 정확성 비교는 [V9 보고서](REPORT.md)를 따르며 이번 소량 연결 확인과 합산하지 않는다.

## 2026-09-10: 음성 앱 조작 경로

`model_tools`는 STT → 선택한 텍스트 LLM → 앱 함수 호출 → 화면 반영 확인 → Azure TTS 경로다.
앱 열기·검색·경로 미리 보기·안내 시작·경유지 추가·안내 종료·현재 상태 조회를 제공한다.
명령 처리기와 시연 데이터는 `navigation.py`, 음성 함수 호출/확인 처리는 `navigation_voice.py`,
화면 렌더링은 `static/navigation-view.js`로 분리했다. 음성 자막을 키워드로 파싱해 앱을 실행하지 않는다.

기존 POC 구독의 East US 2 리소스를 Azure 읽기 전용 메타데이터로 확인해,
Git에서 제외된 현재 worktree의 `.env`에 구독과 Voice Live 엔드포인트를 복원했다.
다른 작업공간의 `.env`를 읽거나 복사하지 않았고 새 리소스·역할을 만들지 않았다.

실제 Entra 인증으로 `gpt-4.1-mini`·Azure Speech·`ko-KR-SunHiNeural` 세션 생성과 설정 적용을 확인했다.
이후 실행 중인 앱의 WebSocket에 **텍스트로 “티맵 켜줘”**를 보내 실제 모델의 `open_app` 호출,
`app_open=true`·`revision=1` 상태 변경, 서비스 PCM 오디오 516,600바이트와 음성 자막을 수신했다.
이 확인에서는 프로토콜 클라이언트가 상태 수신 후 ACK를 직접 보냈다.
**브라우저 실제 렌더링 확인, 마이크 입력, 스피커 재생, 음성 지연 실측의 근거는 아니다.**
연결 초기화와 단일 명령의 실행 시간은 각각 3.579초·7.897초였으며 성능 벤치마크가 아니다.
서버 준비 전 로컬 연결 거절도 근거 파일에 별도 기록했다.

근거: [`voice_model_app_control_20260910_01.json`](../results/voice_model_app_control_20260910_01.json).
SDK 계약·화면 리허설·이번 모델 연결·아래 기존 검색 Agent 연결 결과는 서로 다른 근거다.
지도·장소·거리·시간은 시연용이며 실제 TMAP 앱, GPS, 교통, 충전기 가용성은 연결되지 않았다.

## 1. 기존 연결 결과 (9월 8일 기록)

| 경로 | 확인 결과 |
| --- | --- |
| 브라우저 화면 | `http://localhost:8010` — Bing/Web IQ 시작 가능 |
| Voice Live → Bing Agent | 실제 답변 텍스트·PCM 오디오 수신, 공식 출처 인용 수신 |
| Voice Live → Web IQ Agent | 실제 `mcp_call / web`, 답변 텍스트·PCM 오디오 수신 |
| 로컬 앱 WebSocket → Web IQ | 실제 응답·오디오·Trace ID 수신 |
| 사용자 마이크·스피커 | 사용자의 브라우저 권한 승인과 실제 대화 필요. 자동 녹음하지 않음 |
| 대화 초기화 | 현재 연결·오디오 종료, 대화·입력 맥락·화면 기록 삭제. 다음 시작은 새 세션 |
| 도구 결과 표시 | 검색어·상태·결과·출처 카드. 원본 JSON 접기, 중복 래퍼 제거 |
| 사이트 내 트레이스 | 실제 Foundry span의 호출 트리·시간 막대·상세 정보. 대화별 조회 권한 사용 |
| 실행 모드·모델 | 직접 Agent / Realtime → Agent 도구, `gpt-realtime`·`gpt-realtime-mini` 선택 |
| STT·TTS·지연 설정 | 모드별 지원 조합만 표시하고 실제 세션에 적용. 대화 중에는 변경 불가 |
| Azure 배포·권한 변경 | 새 리소스·역할 변경 없음. 승인받은 기존 App Insights의 프로젝트 연결만 추가 |

Voice Live 입력은 짧은 텍스트 질문, 출력은 서비스가 생성한 실제 음성이었다.
이를 마이크 인식 정확도나 실제 스피커 지연 측정으로 부르지 않는다.
음성 원본은 파일에 저장하지 않고 수신 바이트 수만 기록했다.

## 2. 수정한 연결 문제

| 문제 | 조치 |
| --- | --- |
| 처음 띄운 미리보기가 빈 설정 사용 | 기존 로컬 `.env`를 읽는 정상 실행으로 전환 |
| 음성 호스트·Agent 이름 미설정 | 로컬 설정 추가, 음성용 Agent 두 버전 등록 |
| 토큰 발급 34초가 준비 제한 30초 초과 | 인증·WebSocket 연결·세션 준비 제한을 분리 |

호스트 연결 전에 발급하는 토큰이나 구독 기본값을 파일·로그에 기록하지 않는다.
실제 설정은 Git에서 제외된 로컬 환경 파일에만 보관한다.

## 3. 트레이스

| 항목 | 실제 관측 |
| --- | --- |
| Foundry 수집 Trace ID | `89479b3500353602f02a7cdd2ef0fe68` |
| 부모 span | `navigation.voice.session` |
| Foundry 서버 span | `invoke_agent tmap-voice-webiq:1` → `execute_tool mcp_webiq.finance` |
| 별도 클라이언트 span | `observe_tool finance` — 실제 서비스 이벤트의 수신 구간 |
| 출력 대상 | 현재 Foundry 프로젝트의 기존 Application Insights. 실제 수집 행 확인 |
| 보기 | Foundry → 프로젝트 선택 → Agents → Traces에서 위 Trace ID 검색 |

서버가 보낸 실제 실행 span과 앱의 관측 span을 구분했다. 이 연결 확인은 성능 비교 실험이 아니다.
초기 콘솔 전용 Trace ID `291946695c88cd735c70170c320e5f78`는 이력으로 남아 있다.

이 실행에서 Bing은 인용을 반환했지만 도구 item은 음성 이벤트에 노출되지 않았다.
Web IQ는 도구 item을 반환했지만 음성 인용 annotation은 없었다.
미노출을 검색 실패 또는 출처 없음으로 단정하지 않는다.

## 4. 실행·근거

```bash
uv run tmap serve --port 8010
```

연결만 확인하는 명령:

```bash
uv run python scripts/check_voice_connection.py
```

`--prompt`를 지정하면 실제 검색·모델·오디오 비용이 발생한다.

- `results/voice_connection_20260908_01.json`: 양쪽 Agent 응답·오디오 수신
- `results/voice_app_websocket_20260908_01.json`: 실제 로컬 앱 경유 결과
- `results/voice_app_trace_20260908_01.json`: 콘솔에서 추출한 실제 부모 span
- `results/voice_foundry_tracing_20260908_01.json`: 금융 도구 실행과 실제 오디오 수신
- `results/foundry_trace_ingestion_20260908_01.json`: 같은 Trace ID의 서버·클라이언트 span 수집 행
- [Trace 설정](TRACING.md) · [배포 안내](DEPLOYMENT.md)
