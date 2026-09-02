# TMAP IVI — 검색 그라운딩 벤치마크 하네스

티맵모빌리티 IVI / 모바일 음성 어시스턴트의 최신 정보 feeding 품질을
**Web IQ vs Grounding with Bing vs EXA** 3경로로 비교하기 위한 실행 하네스입니다.

> ⚠️ **Private 저장소입니다. 공개 전환 금지.**
> 실명 고객(티맵) 평가 데이터와 경쟁 비교 결과가 들어 있습니다.
> 원본 기획 문서는 내부 제품 상태 정보를 포함하므로 **이 저장소에 커밋하지 않습니다.**
> (`.gitignore`로 차단. 원본은 OneDrive에 보관)

---

## 설계 원칙 — 검색 레이어만 변수

기획 문서의 전제는 "검색 레이어만 변수로 만든다"입니다. 이걸 코드 구조로 강제합니다.

```
질문 ─┬─ [null]    검색 없음            ─┐
      ├─ [webiq]   raw passage 반환      ├─→ 동일 합성 프롬프트 → 동일 모델 → 답변 → 채점
      ├─ [exa]     raw passage 반환      ─┘
      └─ [gwb]     합성된 답변 반환 ─────────────────────────────→ 답변 → 채점
```

`null` / `webiq` / `exa`는 같은 인터페이스(정규화된 passage 반환) 아래 갈리고,
그 위의 프롬프트·모델·파라미터·채점은 전부 공유합니다.

**GwB만 구조가 다릅니다.** 원본 passage가 아니라 모델이 합성한 최종 답변을 반환하므로
같은 인터페이스에 억지로 맞출 수 없고, `retrieval_latency`를 분리 계측할 수도 없습니다.
이 비대칭은 결과 리포트에 반드시 명시해야 하는 항목입니다.

---

## 실측으로 확인된 제약 (기획 문서와 다름)

| 문서 요구 | 실측 | 대응 |
|---|---|---|
| `temperature = 0` | **HTTP 400 거부.** 기본값만 허용 | 파라미터 미설정 |
| (대안) `seed` 고정 | **결정성 없음.** 동일 seed 3회 → 전부 다른 출력, `system_fingerprint`는 `null` | 결정성 확보 불가 |

**출력 결정성을 확보할 수 없습니다.** 따라서 3회 반복은 레이턴시 분산뿐 아니라
**출력 분산 측정**에도 씁니다. 경로 간 점수차가 동일 경로 내 반복 간 분산보다 큰지
확인하기 전에는 우열을 주장할 수 없습니다.

대신 고정 가능한 변수: `reasoning_effort`(`none`/`low`/`medium`/`high`/`xhigh`),
`response_format`(`json_object`), `max_completion_tokens`.

### 레이턴시 계측

응답 `usage.latency_checkpoint`에 서버측 값이 들어옵니다
(`engine_ttft_ms`, `user_visible_ttft_ms`, `service_ttlt_ms`, `pre_inference_ms` 등).
스트리밍 파싱 없이 수집 가능합니다.

> ⚠️ **미해결**: 동일 조건에서 클라이언트가 관측한 첫 청크 시점과 서버가 보고한
> `user_visible_ttft_ms`가 4배 이상 벌어집니다. 고객에게 서버측 값만 제시하면
> 과대 낙관이 됩니다. 원인 확정 전까지 리포트에는 **두 값을 분리 표기**합니다.

---

## 구조

```
config/
  queryset.json          60문항 (C1~C7) + 카테고리별 신선도 요구
  runtime.example.env    환경변수 템플릿
src/tmap_poc/
  config.py              환경변수 기반 설정 (엔드포인트·구독은 코드에 두지 않음)
  auth.py                Entra ID 토큰 (런타임 획득, 메모리 보관, 디스크 기록 없음)
scripts/
  probe_model.py         temperature 수용 여부 / latency_checkpoint 스키마
  probe_params.py        seed 결정성 / reasoning_effort / JSON 모드 / 스트리밍 TTFT
  check_citations.py     인용 URL 전수 HTTP 검증 (citation_dead_rate)
docs/
  FINDINGS_baseline.md   1차 실행 결과
results/                 실행 결과 원본 JSON
run_baseline.py          검색 없는 베이스라인 러너 (null 경로)
```

---

## 실행

```bash
cp config/runtime.example.env .env      # 값 채우기 (.env는 커밋되지 않음)
az login

python3 run_baseline.py --category C7 --repeats 3
python3 run_baseline.py --ids 56,57 --repeats 1 --reasoning-effort high
python3 scripts/check_citations.py
```

인증은 API 키가 아니라 Entra ID입니다 (대상 리소스는 로컬 인증 비활성화).
토큰은 실행 중 메모리에만 두고 어디에도 기록하지 않습니다.

---

## 1차 결과 요약

검색 레이어 없는 베이스라인 (상세: `docs/FINDINGS_baseline.md`)

- **C7 함정 문항 5개 × 3회 = 15/15 정확 거부.** 지어낸 답 0건.
- **대조군 C6에서 판별력 확인** — 위치·식별정보가 필요한 문항은 거부, 정적 지식은 정상 답변.
  즉 무차별 거부가 아님. 3경로 비교에서 C7 점수가 떨어지면 원인은 모델이 아니라
  **검색 레이어가 무관한 근거를 밀어넣어 모델을 오도한 것**으로 해석해야 합니다.
- **인용 dead rate 66.7%** (10/15). 살아있는 건 도메인 루트뿐, 딥링크는 전부 404.
  모델이 그럴듯한 URL을 생성합니다. 검색 레이어 도입 시 이 수치가 얼마나 내려가는지가
  핵심 비교 지표입니다.
- `insufficient_evidence: true`인 응답조차 citation을 붙였습니다. 따라서 채점의
  인용 유효성 축은 "URL이 살아있는가"로 부족하고,
  **"인용 URL이 검색 레이어가 제공한 passage 집합에 속하는가"를 함께 검증**해야 합니다.

---

## 커밋 금지

- 원본 기획 문서 (내부 제품 상태 정보 포함)
- 토큰·API 키·인증서
- 구독 ID / 테넌트 ID / 리소스 엔드포인트 → `.env`에만 두고, 결과 파일에는 마스킹해 기록

---

## 개발 환경 메모

WSL Ubuntu의 파일을 Windows UNC 경로(`\\wsl$\...`)로 편집하면:

- 줄바꿈이 **CRLF**로 저장됩니다. 셸 스크립트가 깨지므로 Python으로 정규화해야 합니다
  (`sed -i`는 이 마운트에서 반영되지 않음).
- Windows git이 소유권을 거부합니다. 다음 등록이 필요합니다:
  ```
  git config --global --add safe.directory '//wsl$/Ubuntu/home/<user>/<path>'
  ```
