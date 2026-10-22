# 배포

FastAPI 서버와 정적 화면을 Docker 이미지 하나로 만들어 Azure Container Apps에 올린다.
새 환경은 `scripts/provision.py` 한 명령으로 만든다. 접속 주소, 리소스 이름, ID는 저장소에 적지 않는다.

## 준비

- Azure CLI 로그인(`az login`)과 Bicep(`az bicep install`)
- 구독의 Owner 권한(역할 부여용)과 Entra 앱 등록 권한
- WebIQ API 키: `WEBIQ_API_KEY` 환경 변수. 없으면 실행 중에 숨김 입력으로 받는다.
- 모델 할당량: 기본값은 `gpt-6-luna` GlobalStandard 용량 250(분당 25만 토큰)이다. 계획 단계에서 남은 양을 보여 준다.

## 새 환경 만들기

```bash
# 계획: 읽기만 한다(이름, 할당량, what-if)
python scripts/provision.py --subscription <구독> --resource-group <리소스 그룹>

# 생성
python scripts/provision.py --subscription <구독> --resource-group <리소스 그룹> --apply
```

`--apply`는 아래 순서로 실행한다. 다시 실행하면 같은 상태로 맞춘다.

| 단계 | 내용 |
| --- | --- |
| 1 | 리소스 공급자 등록. 리소스 그룹이 없으면 만든다(있으면 지역과 태그를 바꾸지 않는다) |
| 2 | `infra/main.bicep` 배포: Foundry 계정·프로젝트·모델, Grounding with Bing과 프로젝트 연결, ACR, Log Analytics, Container Apps 환경, 관리 ID와 역할 |
| 3 | WebIQ 키를 한 번 호출해 확인한 뒤 프로젝트 연결 `webiq-mcp`에 저장 |
| 4 | 검색 Agent `tmap-voice-bing`, `tmap-voice-webiq`와 End-to-end Bing용 웹 검색 Toolbox `tmap-web-search` 생성. 정의가 같으면 재사용 |
| 5 | ACR에서 이미지 빌드 |
| 6 | Entra 로그인 앱 생성·갱신(단일 테넌트, Azure CLI 사전 승인) |
| 7 | Container App 배포. Microsoft Entra 로그인 필수, `/healthz`만 예외 |
| 8 | `/healthz` 200과 로그인 없는 `/api/config` 차단 확인 |

끝나면 앱 주소와 로컬 `.env`에 넣을 값을 출력한다. WebIQ 키와 로그인 비밀값은 HTTPS 요청 본문으로만 보내며
명령줄, 출력, 파일에 남기지 않는다. 계획 단계의 what-if는 할당량 부족 같은 사전 검증 오류를 미리 보여 준다.
2026-10-22 실측으로 새 환경은 약 20분(대부분 Container Apps 환경 생성), 다시 실행은 2.4분 걸렸다.

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--name` | `tmap-webiq-poc` | Container App 이름. 다른 리소스 이름은 이 값과 구독·리소스 그룹으로 정한다 |
| `--location` | `eastus2` | Voice Live와 모델을 함께 쓸 수 있는 지역 |
| `--model`, `--model-version`, `--model-sku`, `--model-capacity` | `gpt-6-luna`, `2026-09-22`, `GlobalStandard`, `250` | 두 Agent가 쓰는 모델 배포 |
| `--image` | 없음 | 이미 있는 이미지를 쓰고 빌드를 건너뛴다 |
| `--new-sign-in-secret` | 꺼짐 | 로그인 비밀값을 새로 만든다(유효기간 1년). 끄면 기존 값을 재사용하되, 만료 30일 전이거나 Entra에 없으면 새로 만든다 |

**모델 주의(2026-10-21 확인):** `gpt-5.4-mini` Agent는 WebIQ MCP 요청에서 용량 800에서도 HTTP 429를 반환했다.
같은 Agent를 `gpt-5-mini`와 `gpt-6-luna`로 바꾸자 두 엔진 모두 답했다.

## 코드만 바꿨을 때

```bash
python scripts/deploy_voice_app.py --subscription <구독> --resource-group <리소스 그룹> --registry <ACR> --name <앱> --apply
```

ACR에서 이미지를 빌드하고 기존 앱의 이미지만 바꾼다. 로그인이 꺼진 앱, 관리 ID나 Agent 설정이 없는 앱은 거부한다.
`--apply`가 없으면 계획만 보여 준다. 활성 음성 연결은 리비전 교체 때 끊기므로 배포 전에 종료한다.

## WebIQ 키 교체

```bash
python scripts/setup_webiq_connection.py --connection-id <WEBIQ_CONNECTION_ID> --apply
```

키는 `WEBIQ_API_KEY` 또는 숨김 입력으로 받고, WebIQ에 확인한 뒤 저장한다. 실행 중인 앱은 10분 안에 새 키를 쓴다.

## 배포 후 확인

1. 브라우저로 앱 주소를 열고 Microsoft Entra로 로그인한다.
2. 질문 하나를 보내 두 엔진의 답변과 음성이 나오는지 본다.
3. 스크립트로 확인할 때는 `az account get-access-token --scope api://<로그인 앱 client ID>/.default` 토큰을
   `Authorization: Bearer`로 붙여 `/api/config`와 `/ws/voice`(Origin은 앱 주소)에 보낸다.

## 정리

```bash
az group delete --name <리소스 그룹>
az cognitiveservices account purge --location <지역> --resource-group <리소스 그룹> --name <Foundry 계정>
az ad app delete --id <로그인 앱 client ID>
```

삭제한 Foundry 계정은 48시간 동안 이름과 모델 할당량을 붙잡으므로 `purge`로 바로 해제한다.

## 운영 범위

- 복제본 1개를 항상 켜 두므로 사용하지 않아도 컨테이너 비용이 든다.
- 세션당 15분, 프로세스당 동시 음성 세션 4개로 제한한다. 비교 화면은 질문마다 두 세션을 쓴다.
- 서버는 대화와 음성 원본을 저장하지 않는다.
- 이 스크립트 도입 전에 수동으로 만든 환경은 이름 규칙이 달라 `provision.py` 대상이 아니다.
  그런 환경의 코드 갱신에는 `deploy_voice_app.py`, 키 교체에는 `setup_webiq_connection.py`를 쓴다.
