# 음성 앱 실행과 배포

정적 화면과 FastAPI를 함께 제공한다. 차량 화면, 별도 프런트엔드 서버, Node 빌드는 필요 없다.
2026-09-23 이 문서의 절차대로 Azure Container Apps에 배포했다. 접속 주소·리소스 이름·ID 같은
환경별 식별자는 저장소에 기록하지 않고 별도로 공유한다.

**현재 상태:** 배포된 앱에서 Microsoft Entra 로그인 후 Agent 연결 / STT → LLM → TTS / End-to-end ×
WebIQ·Bing 여섯 조합이 앱의 Managed Identity로 실제 답변과 음성을 반환함을 확인했다. [연결 결과](VOICE_STATUS.md)
2026-09-29부터 화면에서는 Agent 연결과 End-to-end만 고를 수 있다(STT → LLM → TTS는 API로만 사용).

> **2026-09-29 임시 공개:** 고객 미팅 시연을 위해 사용자 요청으로 Container Apps 인증(`platform.enabled`)을 껐다.
> 주소를 아는 사람은 누구나 로그인 없이 쓸 수 있고, 사용량은 앱의 Managed Identity로 과금된다.
> Entra 앱 등록과 인증 설정은 지워지지 않아 다시 켤 수 있다. 시연이 끝나면 인증을 다시 켜거나 앱을 내린다.
>
> ```bash
> az containerapp auth update --name YOUR_APP --resource-group YOUR_RG --subscription YOUR_SUBSCRIPTION --enabled true
> ```
>
> 인증이 꺼진 동안 배포 스크립트는 `--allow-anonymous`를 명시해야 이미지를 갱신한다.

## 1. 로컬에서 먼저 사용

```bash
uv sync --frozen
uv run tmap serve
```

Windows 브라우저에서 `http://localhost:8000`을 연다. 로컬은 `TMAP_AUTH_MODE=cli`이며,
기존 Azure CLI 로그인과 명시적인 `TMAP_POC_AZ_SUBSCRIPTION`을 사용한다.
브라우저 마이크를 사용하므로 WSL에 PyAudio나 마이크 장치를 설정할 필요가 없다.

`.env`의 실제 값은 저장소에 추가하지 않는다. 기존 파일을 새 예제로 덮어쓰지 않는다.
준비되지 않은 설정은 화면에 표시하고 시작을 막는다.

## 2. Foundry와 Voice Live

양쪽 Agent는 동일한 모델·업무 지시를 사용한다. Bing은 내장 `bing_grounding`,
Web IQ는 기존 Foundry 연결을 사용하는 서비스 MCP다.

`uv run tmap prepare-agents`는 등록 계획만 표시하고,
`uv run tmap prepare-agents --apply`는 실제 Agent 버전을 등록한다.
Agent 준비는 모델 추론 실행은 아니지만 서비스 설정을 변경하는 작업이다.
기존 일반 벤치마크 Agent의 JSON 지시를 음성용이라고 가정하지 않는다.

SDK는 `azure-ai-voicelive[aiohttp]` 1.3.0, 음성 API 버전은 `2026-07-15`이다.
모노 PCM16 24kHz를 송수신하며 실제 서비스 오디오만 재생한다.
앱 맥락은 대화 메시지로 추가하고 서버의 수신 확인 후 녹음을 시작한다.
Agent 모드에서 지원하지 않는 `session.update.instructions`를 사용하지 않는다.

Voice Live Agent 지원 리전의 Foundry 호스트가 필요하다.
기존 환경에 East US 2 후보가 있지만 실제 Agent 연결·교차 리소스 권한은 별도다.
새 리소스를 자동 생성하지 않는다.

참고: [Agent 연결](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live-agents-quickstart),
[지원 리전](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions?tabs=voice-live#regions).

## 3. 컨테이너

```bash
docker build -t navigation-voice .
```

이미지는 Python과 정적 파일만 포함하며 잠금 파일로 의존성을 설치한다.
`.env`, 실험 결과·문서, Git 정보와 로컬 가상환경은 빌드에 포함하지 않는다.
루트 사용자가 아닌 계정으로 실행한다.

컨테이너의 기본 포트는 8000, 상태 확인 경로는 `/healthz`다.
로컬 컨테이너에는 호스트의 Azure CLI 로그인이 자동 전달되지 않는다.
로컬 음성 개발은 위의 `uv run tmap serve`를 사용하고, Azure 배포에서는 Managed Identity를 쓴다.

## 4. 최초 Azure 호스팅 준비

사용 승인을 받은 기존 리소스를 우선 사용한다. 아래 항목이 없으면 생성과 비용 승인을
먼저 진행한다. 이 저장소의 배포 도구가 임의로 만들어주지는 않는다.

| 항목 | 필요한 설정 |
| --- | --- |
| Azure Container Registry | 이미지 빌드와 보관(Basic). 앱 ID에 `AcrPull` |
| Container Apps 환경·앱 | 앱 컨테이너 1개, HTTPS ingress, target port 8000, 복제본 1개(최소·최대) |
| 앱 인증 | Microsoft Entra 로그인 필수. 인증 없이 열리는 경로는 `/healthz`뿐 |
| Managed Identity | 사용자 할당 ID. Voice Live 리소스에 `Cognitive Services User`, Agent와 WebIQ 프로젝트 연결이 있는 Foundry 리소스에 `Foundry User` |
| 환경변수 | 프로젝트·Voice Live 호스트, 두 Agent의 이름·버전, 교차 리소스 이름, `AZURE_CLIENT_ID` |

`Foundry User`는 이전 이름이 `Azure AI User`인 역할이다. 이 역할로 Agent 연결·Agent 도구 호출과
WebIQ 연결 키 조회(세션 시작 시 메모리에서만 사용)가 모두 동작함을 배포 앱에서 확인했다.
복제본 1개를 항상 켜 두므로 사용하지 않아도 컨테이너 비용이 발생한다.

**인증 설정에서 확인한 사항**

- Container Apps 인증에는 App Service의 `requireAuthentication` 필드가 없다.
  `unauthenticatedClientAction=RedirectToLoginPage`로 로그인을 강제하며, 브라우저는 로그인 페이지로 이동하고
  브라우저가 아닌 요청은 401을 받는다.
- CLI의 `az containerapp auth update --set ...enabled=true`는 값을 문자열로 보내 거부된다.
  Entra 공급자 활성화는 `authConfigs/current`를 JSON 불리언으로 PUT해 설정한다.
- 기본 권한 정책의 `allowedApplications`가 빈 목록이면 로그인한 요청도 403이 된다.
  로그인 앱의 client ID를 넣는다. 배포 확인에 Azure CLI 토큰을 쓰려면 Azure CLI client ID도 함께 허용하고,
  앱 등록에서 `user_impersonation` 범위를 Azure CLI에 사전 승인한다.
- CLI 기본 계정의 테넌트가 구독 테넌트와 다르면 `containerapp create`의 자동 `AcrPull` 부여가 실패한다.
  역할은 미리 부여하고, Microsoft Graph 작업(앱 등록·비밀값)은
  `az account get-access-token --subscription <구독> --resource-type ms-graph`로 받은 토큰으로 수행한다.
- 로그인 비밀값은 앱 등록에서 만든 뒤 출력하지 않고 Container App 비밀값에만 저장한다(만료 1년).
- 역할·인증 변경은 반영까지 1분 이상 걸릴 수 있다.

화면 공유는 처음에 내부 사용자로 제한한다. 고객 접근은 허용된 게스트 등 인증 방식을 정한 뒤 연다.
**익명 앱을 공개하거나 키가 들어간 정적 페이지를 배포하지 않는다.** 예외는 위의 임시 공개처럼
소유자가 명시적으로 요청한 짧은 시연뿐이며, 이때도 키는 서버에만 둔다.
활성 음성 연결은 리비전 교체 시 끊길 수 있으므로 배포 전에 종료한다.

앱 환경변수:

```text
TMAP_AUTH_MODE=managed_identity
GWB_PROJECT_ENDPOINT=<existing Foundry project endpoint>
TMAP_VOICE_ENDPOINT=<existing supported Voice Live endpoint>
TMAP_BING_AGENT_NAME=<prepared Bing agent>
TMAP_BING_AGENT_VERSION=<pinned version>
TMAP_WEBIQ_AGENT_NAME=<prepared Web IQ agent>
TMAP_WEBIQ_AGENT_VERSION=<pinned version>
TMAP_ALLOWED_ORIGINS=https://<your-container-app-host>
TMAP_WEB_SEARCH_TOOLBOX=<Foundry toolbox name with the web_search tool>
```

`TMAP_WEB_SEARCH_TOOLBOX`는 End-to-end의 Bing 검색용이다. 프로젝트에 `web_search` 도구 하나를 담은 Toolbox를 만들고
(`POST {project_endpoint}/toolboxes/{name}/versions?api-version=v1`, 예: `{"tools": [{"type": "web_search",
"user_location": {"type": "approximate", "country": "KR"}}]}`) 이름을 넣는다. 앱은 실행 ID의 Entra 토큰
(`https://ai.azure.com/.default`)으로 `{project_endpoint}/toolboxes/{name}/mcp?api-version=v1`을 부른다.
비워 두면 End-to-end의 Bing은 Bing Agent를 거친다.

사용자 할당 ID는 `AZURE_CLIENT_ID`를 추가한다. 서로 다른 Foundry 리소스를 연결하면
`TMAP_VOICE_FOUNDRY_RESOURCE_OVERRIDE`와 필요한 경우
`TMAP_VOICE_AGENT_IDENTITY_CLIENT_ID`를 설정한다.
Web IQ의 비밀값은 기존 Foundry 연결에서 관리하며 브라우저로 전달하지 않는다.

프로젝트에 Application Insights가 연결돼 있고 실행 ID가 그 연결을 읽을 권한이 있으면
`TMAP_TRACE_EXPORTER=foundry`를 추가해 Foundry Traces로 보낸다.
연결 문자열을 배포 환경에 복사하지 않고 실행 시 메모리에서 조회한다.
현재 로컬 환경은 이 방식으로 서버 Agent·tool span 수집까지 확인했다. [트레이스 안내](TRACING.md)

## 5. 이후 배포는 한 명령

```bash
uv run python scripts/deploy_voice_app.py --subscription YOUR_SUBSCRIPTION --resource-group YOUR_RG --registry YOUR_ACR --name YOUR_APP
```

기본은 완전한 오프라인 계획 표시다. `--apply`를 추가하면 다음 작업만 한다.

1. 지정 구독의 기존 앱·인증·ID·설정과 레지스트리를 읽는다.
2. 인증 필수·Entra·단일 컨테이너·포트·Agent 설정을 확인한다(`--allow-anonymous`면 인증 확인만 건너뛴다).
3. ACR에서 Dockerfile을 빌드한다.
4. 기존 앱 이미지를 갱신하고 Managed Identity 모드와 허용 origin을 설정한다.

리소스 생성·역할 부여·비밀값 출력은 하지 않는다. 모든 Azure CLI 호출은 구독을 명시한다.
배포가 제출됐다는 것과 새 리비전에서 음성 연결까지 완료됐다는 것은 구분한다.
2026-09-23 배포 앱에 이 명령을 실행해 검증·빌드·리비전 교체가 동작함을 확인했다.

배포 후에는 새 리비전이 `Running`/`Healthy`인지, `/healthz`가 200이고 `/api/config`가 로그인 없이 401인지 확인한다.
실제 동작은 `api://<로그인 앱 client ID>` 토큰을 `Authorization: Bearer`로 붙여 `/api/config`와
`/ws/voice`(Origin은 앱 주소)에 보내 확인한다. 토큰과 주소는 결과 파일에 남기지 않는다.

## 6. 운영 범위

최소 앱은 세션당 15분, 프로세스당 동시 음성 세션 4개로 제한한다. 비교 화면은 질문마다 WebIQ·Bing 두 세션을 쓰므로
비교 두 개(또는 한 엔진 재연결 중 겹침)까지 허용한다.
서버는 대화·음성 원본을 자동 저장하지 않는다. 실험은 로컬 CLI가 실행 폴더에 기록한다.
장기 운영·다중 복제·서버 기록 보관이 필요해지면 영구 저장소와 사용자별 권한을 별도로 추가한다.

텍스트 모델·검색·Voice Live·컨테이너 비용은 다른 항목이다.
음성 토큰을 Luna의 텍스트 토큰 단가에 그대로 대입하거나 미관측 호출을 무료로 처리하지 않는다.
자동 재연결로 유료 질문을 반복 실행하지 않는다.

참고: [Container Apps ingress](https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview),
[Container Apps 인증](https://learn.microsoft.com/en-us/azure/container-apps/authentication).
