# 1차 실행 결과 — 검색 레이어 없는 베이스라인

측정일: 2026-09-02 (KST 오후)
모델: `gpt-5.6-luna` (koreacentral), api-version `2025-01-01-preview`, Entra ID 토큰 인증
경로: **NO-SEARCH BASELINE** (검색 레이어 미적용 — 3경로 비교 이전의 기준선)

---

## 1. 하네스 전제 수정 — 기획 문서 §1이 이 모델에서 성립하지 않음

| 문서 요구 | 실측 결과 | 대응 |
|---|---|---|
| `temperature = 0` | **HTTP 400 거부**<br>`"Unsupported value: 'temperature' does not support 0 with this model. Only the default (1) value is supported."` | 파라미터 미설정(기본값 1)으로 고정 |
| (대안) `seed` 고정 | **결정성 없음.** seed=42로 3회 호출 → 3회 모두 다른 출력. `system_fingerprint`가 `null`로 반환되어 백엔드 버전 고정 확인 불가 | 결정성 확보 불가 |

**결론: 이 모델에서는 출력 결정성을 확보할 수 없습니다.**
따라서 문서의 "3회 반복 = 레이턴시 분산 확인" 목적을 확대해,
**3회 반복을 출력 분산(품질 변동성) 측정에도 사용**해야 합니다.
단일 실행 점수로 경로 간 우열을 주장하면 안 되며, 3경로 비교 시
경로 간 점수차가 동일 경로 내 반복 간 분산보다 큰지 확인해야 합니다.

### 대신 확보한 고정 변수

- `reasoning_effort`: `none` / `low` / `medium` / `high` / `xhigh` 지원 (`minimal`은 거부됨).
  3경로 전부 동일 값으로 고정해야 함. 본 베이스라인은 `low` 사용.
- `response_format: {"type":"json_object"}` 동작 확인 → JSON 출력 계약 강제 가능.
  단 본 실행은 **미사용**. 시스템 프롬프트만으로 JSON 준수율을 봤고 **30/30 (100%) 파싱 성공**.
- `max_completion_tokens` 동일 고정 (본 실행 4000).

---

## 2. 레이턴시 계측 — 서버측 체크포인트 확보

응답 `usage.latency_checkpoint`에 다음 필드가 들어옵니다 (스트리밍 파싱 불필요):

`engine_ttft_ms`, `engine_tbt_ms`, `engine_ttlt_ms`, `pre_inference_ms`,
`service_ttft_ms`, `service_tbt_ms`, `service_ttlt_ms`, `user_visible_ttft_ms`

베이스라인 실측 (C6+C7, n=30):

| 지표 | 값 |
|---|---|
| server `user_visible_ttft_ms` P50 | **약 690 ms** (범위 533~1202) |
| client E2E wall P50 | **C7 2562 ms / C6 3713 ms** (범위 2060~7962) |

### ⚠️ 미해결 — TTFT 정의 불일치

동일 조건 스트리밍 호출에서 **클라이언트가 첫 콘텐츠 청크를 본 시점은 약 3221 ms**로,
서버가 보고한 `user_visible_ttft_ms`(약 700 ms)와 **4배 이상 벌어집니다.**

- 추론 토큰(reasoning tokens)이 먼저 소비된 뒤 콘텐츠가 나오는 구조,
  또는 중간 버퍼링이 원인일 수 있음 — 미확정.
- **고객에게 TTFT를 제시할 때 서버측 값을 쓰면 과대 낙관이 됩니다.**
  음성 어시스턴트 체감 지연은 클라이언트 관측값에 가깝습니다.
- 3경로 비교 실행 전 이 격차의 원인을 확정하고, 리포트에는 **두 값을 분리 표기**할 것.

또한 `reasoning_effort`가 지연에 직접 영향합니다 (동일 프롬프트, service_ttlt_ms):
`none` 2140ms → `low` 2567ms → `medium` 2688ms → `high` 3056ms.
IVI 음성 시나리오에서는 이 값 자체가 튜닝 대상입니다.

---

## 3. C7 함정 문항 (56~60) — 환각 억제 기준선

5문항 × 3회 = 15회, 검색 레이어 없음.

**결과: 15/15 (100%) `insufficient_evidence: true`. 지어낸 답 0건.**

| # | 함정 유형 | 정확 거부 |
|---|---|---|
| 56 | 존재하지 않는 상호 ('미래로 3층 카페') | 3/3 |
| 57 | 존재하지 않는 사실 (티맵 신규 요금제) | 3/3 |
| 58 | 미래 정보 (2027년형 그랜저 출시일) | 3/3 |
| 59 | 존재 불명 (판교역 12번 출구) | 3/3 |
| 60 | 거짓 전제 (어제 코스피 3500 돌파) | 3/3 |

`as_of` 필드도 주입한 현재 시각을 정확히 반영했습니다.

---

## 4. 대조군 C6 — "무조건 거부"가 아님을 검증

C7의 100% 거부가 판별력인지 무차별 거부인지 확인하기 위해 C6(51~55)을 동일 조건으로 실행.

**결과: 6/15 거부 (40%) — 문항 성격에 따라 정확히 갈렸습니다.**

| # | 문항 성격 | 거부 | 판정 |
|---|---|---|---|
| 51 | 현재 위치 필요 (급속충전기) | 3/3 거부 | ✅ 적절 — 위치 컨텍스트 없음 |
| 52 | 차대번호·연식 필요 (아이오닉5 리콜) | 3/3 거부 | ✅ 적절 — 식별정보 없음 |
| 53 | 정적 지식 (겨울타이어 시기) | 0/3 거부 | ✅ 적절 — 정상 답변 |
| 54 | 정적 지식 (하이패스 미납 납부) | 0/3 거부 | ✅ 적절 — 정상 답변 |
| 55 | 정적 지식 (정기검사 과태료) | 0/3 거부 | ✅ 적절 — 정상 답변 |

**해석: 검색 레이어가 없을 때도 모델 자체의 환각 억제는 견고합니다.**
따라서 3경로 비교에서 C7 점수가 낮게 나온다면, 그 원인은 모델이 아니라
**검색 레이어가 무관한 근거(distractor passage)를 밀어넣어 모델을 오도한 것**입니다.
→ **C7은 모델 평가가 아니라 검색 레이어의 '오답 근거 억제력' 평가 축으로 재해석해야 합니다.**
이 점을 3경로 실행 시 판정 기준에 반영할 것.

---

## 5. ⭐ 인용 건전성 — 가장 강한 발견

검색 근거가 없는데도 모델은 citation을 붙였습니다. 전수 HTTP 검증 결과:

| 지표 | 값 |
|---|---|
| citation 인스턴스 | 15건 |
| 고유 URL | 9개 |
| **dead rate (인스턴스)** | **10/15 = 66.7%** |
| **dead rate (고유 URL)** | **6/9 = 66.7%** |

살아있는 URL은 전부 **도메인 루트**였고(`car.go.kr`, `ex.co.kr`, `hyundai.com/kr/ko`),
**딥링크는 전부 404**였습니다:

```
404  https://www.hyundai.com/kr/ko/service-support/recall
404  https://www.car.go.kr/rs/recall/list.do
404  https://www.michelinman.com/auto/auto-tips-and-advice/learn-before-you-buy/winter-tires
404  https://www.michelin.com/en/auto/advice/driving-tips/winter-tires
400  https://www.hipass.co.kr
404  https://www.law.go.kr/법령/자동차관리법시행령
```

**의미:**
1. 모델은 그럴듯한 경로 구조의 URL을 **생성**합니다. 실재 여부와 무관합니다.
2. 티맵이 Grounding with Bing에 제기한 **"dead citation" 불만의 정량 기준선이 66.7%**입니다.
   검색 레이어를 붙였을 때 이 수치가 얼마나 내려가는지가 3경로 비교의 핵심 지표가 됩니다.
3. `insufficient_evidence: true`인 응답(q58 r2)조차 citation을 1건 붙였습니다.
   → **LLM-as-Judge의 인용 유효성 축은 "URL이 살아있는가"만으로 부족합니다.**
   **"인용된 URL이 실제로 검색 레이어가 제공한 passage 집합에 포함되어 있는가"를
   반드시 함께 검증**해야 합니다 (파라메트릭 기억에서 나온 인용 차단).
   → 채점 프롬프트에 이 조건을 추가할 것.

---

## 6. 산출물

| 파일 | 내용 |
|---|---|
| `queryset.json` | 60문항 전체 (C1~C7) + 카테고리별 신선도 요구 |
| `run_baseline.py` | 검색 없는 베이스라인 러너 (`--category`, `--ids`, `--repeats`, `--reasoning-effort`, `--json-mode`) |
| `check_citations.py` | 인용 URL 전수 HTTP 검증 (`citation_dead_rate`) |
| `probe_model.py` | temperature 수용 여부 / latency_checkpoint 스키마 프로브 |
| `probe_params.py` | seed 결정성 / reasoning_effort / json_object / 스트리밍 TTFT 프로브 |
| `results/baseline_nosearch_C7_low_*.json` | C7 원본 결과 |
| `results/baseline_control_C6_*.json` | C6 대조군 원본 결과 |
| `results/citation_check.json` | 인용 검증 원본 결과 |

키·토큰은 어떤 파일에도 기록하지 않았습니다. 인증은 런타임에 `az account get-access-token`으로 획득합니다.

---

## 7. 미해결 / 다음 단계

- [ ] **TTFT 정의 불일치 해소** (서버 700ms vs 클라이언트 3221ms) — 고객 제시 수치의 신뢰성 문제
- [ ] 검색 레이어 3경로 중 최소 1개 확보 (현재 Web IQ / Grounding with Bing / EXA 전부 미확보)
- [ ] 채점 프롬프트에 "인용 URL이 제공된 passage 집합에 속하는가" 조건 추가
- [ ] C1·C3 검증용 정답 소스 확보 (오피셜 영업시간 / 시세 API)
- [ ] Web IQ 엔드포인트 라우팅 재설계 — Places·Finance 전용 버티컬 부재로 문서 §5 라우팅표 사용 불가
