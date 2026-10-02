# Web IQ 도구가 Trace에 안 보일 때

## 결론

**Web IQ의 limited access 때문에 instrumentation이 차단된다는 공식 근거는 확인하지 못했다.**
현재 알려진 정보만으로 사용자 환경의 원인을 확정할 수는 없다.
MAF의 실행 위치, 원응답의 tool item, OTel span/event, Foundry 화면을 분리해서 확인해야 한다.

특히 현재 프로젝트에 고정한 `azure-ai-projects` 2.5.0의 instrumentation은
`mcp_call`·`web_search_call`을 읽지만, 그 경로에서 호출마다 별도 tool execution span을
생성하는 것이 아니라 **부모 span의 output messages 또는 event**에 넣는다.
민감한 내용 기록이 꺼져 있으면 이름·인수 일부도 빠질 수 있다.
“호출이 없었다”, “독립 tool span이 없다”, “인수가 보이지 않는다”는 서로 다른 현상이다.[T2]

## 1. 먼저 실제 연결 방식을 구분

| 연결 방식 | 누가 검색을 실행하는가 | 클라이언트에서 볼 수 있는 범위 |
| --- | --- | --- |
| MAF 로컬 함수 / 클라이언트 MCP | MAF 프로세스 | 실제 함수/네트워크 호출을 감싸는 실행 span 가능 |
| Foundry/OpenAI hosted MCP | 서비스 | 응답에 노출된 tool item과 서비스가 제공하는 trace |
| 새 SDK의 `WebIQPreviewTool` | 서비스 | 해당 서버측 tool과 응답·trace 계약에 따라 다름 |

MAF 문서는 클라이언트가 직접 연 MCP 연결과 hosted MCP를 명시적으로 구분한다.
전자의 trace context 전달이 후자의 서비스 내부까지 자동 적용되는 것은 아니다.[T1]

Projects 2.6.0에는 `type="web_iq_preview"`인 서버측 Web IQ 도구가 추가됐다.
클래스 이름에 Preview가 있다는 것만으로 제품 접근 상태나 trace 지원 여부를 판단하지 않는다.
이 저장소는 기존 동작을 유지하기 위해 2.5.0과 서비스 MCP를 사용하며 tracing만을 이유로 올리지 않았다.[T3]

## 2. MAF에서 확인할 설정

Python에서는 공식 관측 설정인 `agent_framework.observability.configure_otel_providers()`를,
이미 provider를 설정했다면 `enable_instrumentation(enable_sensitive_data=False)` 경로를 확인한다.
.NET에서는 Agent의 `UseOpenTelemetry(sourceName: ...)`와 exporter의 `AddSource(...)`가 맞아야 한다.
정확한 예제와 각 overload는 [MAF 공식 가이드](https://learn.microsoft.com/en-us/agent-framework/agents/observability)를 따른다.[T1]

민감한 내용 기록을 켜는 것은 누락된 독립 실행 span을 만드는 해결책이 아니다.
검색어·결과·전사 내용의 외부 전송이 허용될 때만 해당 옵션을 따로 검토한다.

## 3. 이 저장소에 적용한 방식

`src/tmap_poc/telemetry.py`에서 OTel provider를 구성하고 **클라이언트 생성 전에**
Projects와 Voice Live의 공식 instrumentor를 활성화한다.

```python
os.environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"] = "true"
settings.tracing_implementation = "opentelemetry"
AIProjectInstrumentor().instrument(
    enable_content_recording=False,
    enable_trace_context_propagation=True,
    enable_baggage_propagation=False,
)
VoiceLiveInstrumentor().instrument(enable_content_recording=False)
```

이 환경변수는 **SDK의 GenAI tracing 옵트인**이다. Web IQ의 limited access와 다른 조건이다.
Projects의 propagation 설정은 이후 `get_openai_client()`로 얻는 클라이언트에 적용된다.[T5][T6]

| 기록 | 의미 |
| --- | --- |
| `navigation.text.request` | 애플리케이션의 실제 텍스트 요청 범위 |
| `navigation.voice.session` | 애플리케이션의 실제 음성 세션 범위 |
| `tool.call.observed` event | 응답에서 실제로 발견한 도구 호출 item |
| `observe_tool finance/web` | Voice Live가 보낸 실제 in-progress → completed/failed 이벤트의 클라이언트 관측 구간 |
| `execute_tool webiq.<tool>` | 클라이언트 MCP 어댑터가 실제 HTTP 호출을 수행한 범위 |
| `foundry.response.correlated` event | 서비스가 명시적으로 제공한 Foundry 응답 ID |

기본 음성 앱의 Web IQ는 **hosted MCP**다. 실제 도구 시작·종료 이벤트가 모두 수신되면
`observe_tool` 자식 span을 만들고, 종료 결과만 있으면 관측 이벤트만 남긴다.
`observe_tool`의 시간은 서비스 이벤트를 수신한 구간이지 서버 내부 검색 지연이 아니다.
따라서 이 경로에는 클라이언트의
`execute_tool webiq.*` span이 생길 것이라고 약속하지 않는다.
그 span은 실제로 로컬 MCP 어댑터를 실행하는 경우에만 생긴다.
완성된 tool item을 받은 시점으로 검색 시작 시간을 역산하지 않는다.

앱은 취소 시 연결 자원을 정리하기 위해 직접 관리하는 aiohttp 세션에 SDK 연결을 얹는다.
따라서 공식 SDK `connect()` manager의 lifecycle span 대신 애플리케이션의 음성 세션 span이
상위 범위를 제공하고, 공식 SDK의 send/receive 계측을 사용한다.
이는 Voice Live 내부·Web IQ 서버 내부를 직접 계측했다는 뜻이 아니다.

## 4. 로컬과 Azure에 보내기

기본은 **콘솔의 메타데이터 trace**다. prompt·검색 인수·원문·음성 내용의 SDK trace 기록은 비활성화한다.
추가로 exporter 앞에서 메타데이터 허용 목록을 적용한다. 고정한 Voice Live 1.3.0의
완료 전사 이벤트가 content opt-out에도 내용을 포함하는 경로를 확인했기 때문이다.
따라서 SDK 옵션만 신뢰하지 않고 콘솔·Azure 양쪽에서 전사·메시지·원문과 오류 설명을 제거한다.
도구 이름·종류·ID·상태·사용량과 실제 span 관계는 유지한다.
화면과 명시적으로 저장하는 실험 원본은 사용자 답변을 보여주기 위한 별도 기록이다.
일반 서버 로그는 trace exporter와 별개이므로 외부 공유 전에는 함께 검토한다.

```text
TMAP_TRACE_EXPORTER=console
```

Foundry 프로젝트에 연결된 기존 App Insights로 내보내려면:

```bash
uv sync --frozen --extra azure-tracing
```

```text
TMAP_TRACE_EXPORTER=foundry
```

`foundry` 모드는 공식 SDK로 현재 프로젝트의 기존 연결 문자열을 메모리에서 조회한다.
프로젝트에 연결이 없으면 **Agents → Traces → Connect** 안내와 함께 실패한다.
새 App Insights를 자동 생성하거나 다른 프로젝트의 대상으로 조용히 대체하지 않는다.
직접 연결 문자열을 지정할 때만 `TMAP_TRACE_EXPORTER=azure`와
`APPLICATIONINSIGHTS_CONNECTION_STRING`을 사용한다.
Azure exporter의 로컬 오프라인 저장은 끈다.
배포용 Docker 이미지는 선택 exporter도 포함한다.
`TMAP_TRACE_EXPORTER=none`이면 애플리케이션의 자동 tracing 초기화를 끈다.

음성 화면의 Trace ID로 콘솔/App Insights의 trace를 찾는다.
앱 세션 ID, Voice Live 응답 ID, Foundry 응답 ID, MCP item ID는 같은 ID가 아니다.
화면의 대화 다운로드는 Azure trace 전체 다운로드가 아니다.

### 데모 안에서 시각화

- **Foundry 실행 트레이스**에서 대화를 선택하고 **불러오기 / 새로고침**을 누른다.
- 프로젝트에 연결된 Application Insights의 실제 span을 조회해 호출 트리·시간 막대로 표시한다.
- Agent·모델·도구를 중심으로 보고, 세부 음성 송수신 span은 별도로 펼친다.
- 수집 지연이나 실행 중인 대화는 일부 span만 먼저 보일 수 있다. 빈 결과를 실패로 간주하지 않는다.
- 서버가 발급한 해당 대화의 4시간 조회 권한으로만 접근한다. 임의 Trace ID·KQL·저장소 ID는 입력받지 않는다.
- 조회 권한 값은 브라우저 메모리에만 유지하며 기록 다운로드·URL·화면에는 넣지 않는다.
- 대화 초기화 또는 페이지 새로고침은 이 브라우저의 선택·권한을 비운다. 서버 로그 삭제는 아니다.

이 화면의 API는 span 이름·부모 ID·상태·시간·모델·도구·토큰 등 필요한 메타데이터만 조회한다.
서버 trace에 들어 있는 원래 프롬프트·답변·도구 원문은 별도로 가져오지 않는다.
조회 권한 오류는 화면에 알리며, 조회는 15초 캐시를 사용하고 자동 무한 조회하지 않는다.
배포 ID에는 기존 App Insights 조회 권한이 필요하다. 앱이 역할을 자동 부여하지 않는다.

## 5. 서버 trace와 Voice Live relay의 한계

Foundry 프로젝트의 서버 tracing에는 해당 프로젝트의 Application Insights 연결과
조회 권한이 필요하다. 클라이언트 span을 exporter로 보내는 설정과 구분한다.[T4]

`response.invocation.delta`는 공식 문서에서 hosted-agent invocation의 non-speech SSE relay로
정의한다. 모든 Prompt Agent 세션에서 Responses 이벤트가 온다고 가정하지 않는다.
SDK·API가 실제로 제공하는 필드만 기록하며, `response.foundry_agent_call.completed`의
`agent_response_id`처럼 명시적인 값이 있을 때만 Foundry 응답과 연결한다.[T7]

이번 코드의 음성 API는 `2026-07-15`다. 이벤트의 존재와 payload 노출은 실제 서비스 구성에 따라
달라질 수 있다. Voice Live의 `response.id`를 Foundry 응답 ID로 대신 쓰지 않는다.

## 6. 문제를 좁히는 순서

1. Python/.NET, SDK 버전, 실제 tool type과 실행 위치를 확인한다.
2. 같은 호출의 원응답에 `mcp_call` 등 실제 실행 item이 있는지 본다.
3. 로컬 exporter에서 span 생성과 sampling, SDK instrumentation 활성 여부를 확인한다.
4. 독립 tool span만 찾지 말고 부모 span의 output messages/events도 확인한다.
5. 같은 Trace ID가 올바른 App Insights·Foundry 프로젝트에 들어갔는지 본다.
6. 원응답에는 호출이 있지만 서버 tool span이 없으면 서비스의 trace 제공 범위 문제로 좁힌다.

## 7. 이 앱의 실제 연결 결과

사용자 승인 후 기존 Application Insights를 현재 Foundry 프로젝트에 연결했다.
신규 Azure 리소스·역할은 만들지 않았다. 현재 로컬 앱은 `foundry` 모드를 사용한다.
연결 상태 근거: `results/foundry_tracing_setup_20260908.json`.
서버 측 trace에는 입력·답변·도구 내용이 저장될 수 있으며, 앱의 메타데이터 필터와는 별도의
서비스 수집 정책이다.

**Foundry 서버의 실제 tool span도 수집됐다.** 연결 후 한 번 실행한 금융 질의에서,
같은 Trace ID 아래 다음 행을 Application Insights 쿼리로 확인했다.

| Span | 출처·의미 |
| --- | --- |
| `navigation.voice.session` | 앱의 음성 세션 |
| `invoke_agent tmap-voice-webiq:1` | Foundry의 Agent 실행 |
| `execute_tool mcp_webiq.finance` | Foundry의 금융 도구 실행 |
| `observe_tool finance` | 별도의 클라이언트 이벤트 관측 구간 |

Trace ID: **`89479b3500353602f02a7cdd2ef0fe68`**.
서버의 `execute_tool`은 `invoke_agent`를 부모로 참조한다.
앱이 만든 관측 span을 서버 실행 span으로 이름만 바꿔 표시한 것이 아니다.
근거: `results/foundry_trace_ingestion_20260908_01.json`.
포털 수집에는 지연이 있어 실행 직후 바로 나타나지 않을 수 있다.
이 앱의 연결 문제는 해결했지만, 질문에 언급된 다른 MAF 구성의 원인까지 동일하다고 단정하지 않는다.

2026-09-08 로컬 앱 → Voice Live → Foundry Web IQ Agent의 실제 요청에서
`tool.call.observed` 이벤트가 콘솔의 `navigation.voice.session` span에 포함됐다.
Trace ID는 `291946695c88cd735c70170c320e5f78`, 도구는 `mcp_call / web`이다.
근거: `results/voice_app_trace_20260908_01.json`.
이는 이 앱에서 호출 관측을 기록한 결과이며, 다른 MAF 구성이나 Foundry 포털의
서버 내부 span까지 동일하게 노출된다는 뜻은 아니다. [연결 현황](VOICE_STATUS.md)

Foundry 포털에서는 **프로젝트 선택 → Agents → Traces**에서 앱의 OpenTelemetry Trace ID를 검색한다.
개별 도구 카드는 금융의 최근 거래가·이전 종가·거래 시각을 구분하고,
중복 `structuredResponse`를 제거해 보여준다. Web IQ의 서비스 `traceId`는 포털 검색용
OpenTelemetry Trace ID와 다른 값이다.

## 근거

- **[T1]** [MAF observability](https://learn.microsoft.com/en-us/agent-framework/agents/observability): Python/.NET 설정과 client/hosted MCP의 propagation 경계.
- **[T2]** [Projects 2.5.0 response instrumentor](https://github.com/Azure/azure-sdk-for-python/blob/azure-ai-projects_2.5.0/sdk/ai/azure-ai-projects/azure/ai/projects/telemetry/_responses_instrumentor.py#L1064-L1104): tool item의 output message/event 처리. 같은 파일 1247–1257, 1339–1357행의 content gate.
- **[T3]** [Projects WebIQPreviewTool](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/azure/ai/projects/models/_models.py#L17651-L17689), [2.6.0 변경 이력](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/CHANGELOG.md).
- **[T4]** [Foundry trace 설정](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup).
- **[T5]** [AIProjectInstrumentor 2.5.0](https://github.com/Azure/azure-sdk-for-python/blob/azure-ai-projects_2.5.0/sdk/ai/azure-ai-projects/azure/ai/projects/telemetry/_ai_project_instrumentor.py#L202-L264).
- **[T6]** [VoiceLiveInstrumentor 1.3.0](https://github.com/Azure/azure-sdk-for-python/blob/azure-ai-voicelive_1.3.0/sdk/voicelive/azure-ai-voicelive/azure/ai/voicelive/telemetry/_voicelive_instrumentor.py#L137-L178).
- **[T7]** [Voice Live 2026-07-15 protocol](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live-api-reference-2026-07-15#responseinvocationdelta): invocation delta와 Foundry 응답 ID.
- **[T8]** [Azure Monitor exporter 예제](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/monitor/azure-monitor-opentelemetry-exporter/samples/traces/sample_trace.py#L8-L28).
