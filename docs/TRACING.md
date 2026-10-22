# Trace

앱은 OpenTelemetry로 메타데이터 trace를 남긴다. 프롬프트, 질문·답변, 도구 인수·원문, 음성은 내보내지 않는다.
SDK의 내용 기록 끄기 옵션이 적용되지 않는 경로가 있어, exporter 앞에서 허용 목록에 있는 속성만 남긴다.

## 설정

| `TMAP_TRACE_EXPORTER` | 동작 |
| --- | --- |
| `console`(로컬 기본값) | 표준 출력에 메타데이터 span을 쓴다 |
| `none` | tracing을 켜지 않는다. `provision.py`로 만든 배포의 값이다 |
| `foundry` | 현재 Foundry 프로젝트에 연결된 Application Insights로 보낸다. 연결 문자열은 실행 시 메모리에서 조회한다 |
| `azure` | `APPLICATIONINSIGHTS_CONNECTION_STRING`으로 지정한 Application Insights로 보낸다 |

`foundry`와 `azure`는 `uv sync --extra azure-tracing`이 필요하다(배포 이미지에는 포함). `foundry` 모드는 프로젝트에
Application Insights 연결이 없으면 시작하지 않는다. 이때 Foundry에서 **Agents → Traces → Connect**로 기존 리소스를
연결한다. `provision.py`는 Application Insights를 만들지 않는다.

## 기록

| 이름 | 의미 |
| --- | --- |
| `navigation.voice.session` | 앱의 음성 세션 1개 |
| `voice.response.created` 이벤트 | Voice Live 응답 시작 |
| `tool.call.observed` 이벤트 | 응답에서 실제로 받은 도구 호출 |
| `observe_tool <도구>` | Voice Live가 보낸 도구 시작·끝 이벤트를 앱이 받은 구간. 서버 내부 검색 시간이 아니다 |
| `execute_tool web_search` | End-to-end Bing에서 앱 서버가 Toolbox Web Search를 부른 구간 |
| `foundry.response.correlated` 이벤트 | 서비스가 알려 준 Foundry 응답 ID |

프로젝트에 Application Insights가 연결돼 있으면 서버 쪽 `invoke_agent <Agent>`와 `execute_tool mcp_webiq.<도구>`도
같은 Trace ID에 쌓인다(2026-09-08 확인). 서버 trace에는 입력·답변·도구 내용이 저장될 수 있으며,
이는 앱의 메타데이터 필터와 별개인 서비스 수집 정책을 따른다.

## 찾기

Foundry 포털에서 **프로젝트 → Agents → Traces**를 연다. 콘솔 exporter를 쓰면 출력된 Trace ID로 찾는다.
수집에는 몇 분 지연이 있다. 앱 세션 ID, Voice Live 응답 ID, Foundry 응답 ID, WebIQ의 `traceId`는 서로 다른 값이다.

## 도구 span이 보이지 않을 때

1. 원응답에 `mcp_call` 같은 실제 도구 item이 있는지 확인한다.
2. hosted MCP 도구는 독립 span 대신 부모 span의 이벤트나 출력 메시지로 기록될 수 있다(azure-ai-projects 2.5.0).
3. 같은 Trace ID가 올바른 프로젝트의 Application Insights에 들어갔는지 확인한다.
4. 원응답에는 호출이 있는데 서버 span이 없으면, 서비스의 trace 제공 범위 문제로 본다.
