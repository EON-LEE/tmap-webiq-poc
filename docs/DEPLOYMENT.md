# 배포

FastAPI 서버와 화면을 Docker 이미지 하나로 만들어 Azure Container Apps에 올린다.
환경 전체를 `scripts/provision.py` 한 명령으로 올리고 내린다(Terraform의 plan / apply / destroy와 같은 방식).
접속 주소, 리소스 이름, ID는 저장소에 적지 않는다.

## 명령 요약

| 하려는 일 | 명령 | 걸리는 시간 |
| --- | --- | --- |
| 계획 보기(읽기만) | `python scripts/provision.py --subscription <구독> --resource-group <RG>` | 1분 |
| 올리기 | 위 명령 + `--apply` | 새 환경 약 20분, 다시 실행 약 2분 |
| 내리기 계획(읽기만) | 위 명령 + `--destroy` | 1분 |
| 내리기 | 위 명령 + `--destroy --apply` | 약 30분 |
| 코드만 갱신 | `python scripts/deploy_app.py ... --apply` | 약 3분 |
| WebIQ 키 교체 | `python scripts/setup_webiq_connection.py ... --apply` | 1분 |

`--apply`가 없으면 아무것도 바꾸지 않는다.

## 준비

- Azure CLI 로그인(`az login`)과 Bicep(`az bicep install`)
- 구독의 Owner 권한(역할 부여용)과 Entra 앱 등록 권한
- WebIQ API 키: `WEBIQ_API_KEY` 환경 변수. 없으면 실행 중에 숨김 입력으로 받는다.
- 모델 할당량: 기본값은 `gpt-6-luna` GlobalStandard 용량 250(분당 25만 토큰)이다. 계획에서 남은 양을 보여 준다.

## 올리기

```bash
python scripts/provision.py --subscription <구독> --resource-group <RG>          # 계획
python scripts/provision.py --subscription <구독> --resource-group <RG> --apply  # 생성·갱신
```

| 단계 | 내용 |
| --- | --- |
| 1 | 리소스 공급자 등록. 리소스 그룹이 없으면 만든다(있으면 지역과 태그를 바꾸지 않는다) |
| 2 | `infra/main.bicep`: Foundry 계정·프로젝트·모델, Grounding with Bing과 연결, ACR, Log Analytics, Container Apps 환경, 관리 ID와 역할 |
| 3 | WebIQ 키를 확인한 뒤 프로젝트 연결 `webiq-mcp`에 저장 |
| 4 | 검색 Agent 2개와 End-to-end Bing용 웹 검색 Toolbox. 정의가 같으면 재사용 |
| 5 | ACR에서 이미지 빌드 |
| 6 | Entra 로그인 앱 생성·갱신 |
| 7 | Container App 배포. Microsoft Entra 로그인 필수, `/healthz`만 예외 |
| 8 | `/healthz` 200과 로그인 없는 요청 차단 확인 |

끝나면 앱 주소와 로컬 `.env` 값을 출력한다. 다시 실행하면 같은 상태로 맞춘다.
WebIQ 키와 로그인 비밀값은 HTTPS 요청 본문으로만 보내며 명령줄, 출력, 파일에 남기지 않는다.

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--name` | `tmap-webiq-poc` | Container App 이름. 다른 리소스 이름은 이 값과 구독·리소스 그룹으로 정한다 |
| `--location` | `eastus2` | Voice Live와 모델을 함께 쓸 수 있는 지역 |
| `--model`, `--model-version`, `--model-sku`, `--model-capacity` | `gpt-6-luna`, `2026-09-22`, `GlobalStandard`, `250` | 두 Agent의 모델 |
| `--image` | 없음 | 이미 있는 이미지를 쓰고 빌드를 건너뛴다 |
| `--new-sign-in-secret` | 꺼짐 | 로그인 비밀값을 새로 만든다. 끄면 재사용하되, 만료 30일 전이면 새로 만든다 |

`gpt-5.4-mini` Agent는 WebIQ 요청에서 HTTP 429를 반환해 쓰지 않는다(2026-10-21 확인).

## 내리기

```bash
python scripts/provision.py --subscription <구독> --resource-group <RG> --destroy          # 지울 목록만 보기
python scripts/provision.py --subscription <구독> --resource-group <RG> --destroy --apply  # 삭제
```

리소스 그룹 전체, 그 안의 Foundry 계정(즉시 purge해 이름과 모델 할당량을 바로 돌려받음),
Entra 로그인 앱을 지운다. 실행 전 리소스 그룹 이름을 직접 입력해야 한다(자동화에서는 `--yes`).
수동으로 만든 환경도 지울 수 있다.

내린 뒤에는 비용이 0이다. 다시 올리면 **주소가 바뀌고**, WebIQ 키를 다시 넣어야 한다.

## 코드만 갱신

```bash
python scripts/deploy_app.py --subscription <구독> --resource-group <RG> --registry <ACR> --name <앱> --apply
```

이미지를 빌드해 기존 앱의 이미지만 바꾼다. 로그인이 꺼진 앱은 거부한다. 리비전이 바뀌면 진행 중인 음성 연결이 끊긴다.

## WebIQ 키 교체

```bash
python scripts/setup_webiq_connection.py --connection-id <WEBIQ_CONNECTION_ID> --apply
```

키를 WebIQ에 확인한 뒤 저장한다. 실행 중인 앱은 10분 안에 새 키를 쓴다.

## 운영 참고

- 올려 둔 동안은 복제본 1개가 항상 켜져 있어 사용하지 않아도 컨테이너 비용이 든다. 쓰지 않을 때는 내린다.
- 세션당 15분, 프로세스당 동시 음성 세션 4개로 제한한다. 비교 화면은 질문마다 두 세션을 쓴다.
- 서버는 대화와 음성 원본을 저장하지 않는다.
- 배포 확인은 브라우저로 로그인해 질문 하나를 보내 본다. 스크립트로 확인할 때는
  `az account get-access-token --scope api://<로그인 앱 client ID>/.default` 토큰을 `Authorization: Bearer`로 붙인다.
