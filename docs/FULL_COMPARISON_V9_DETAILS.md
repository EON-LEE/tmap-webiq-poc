# V9 전체 증거와 실제 답변

30문항 × Bing / Web IQ MCP 기본 / Web IQ MCP 최적화. 답변·실패 모두 유지.

[30행 전체질문·3조건 실제답변 CSV](../results/full_comparison_v9_20260908/question_results.csv) — Excel용 UTF-8 BOM. 셀 안 줄바꿈·실제답변을 그대로 보존한다.
CSV의 answer_source_urls는 실제 답변 인용/명시 URL, retrieved_source_urls는 도구 반환 URL이다. Bing 내부 검색 URL은 NOT_EXPOSED이며 검색실패를 뜻하지 않는다. 독립 검증 출처와 혼합하지 않았다.

정확성 기준은 실행 도중·분류 전에 동결했다. 비눈가림 AI 검토이며 별도 사람 평가가 아니다. 미확인은 오답이 아니다.
공개 원문 재조회와 날짜·조건 검토. 테스트 검색 payload 자체를 정답으로 쓰지 않았다. 영상은 메타데이터만 확인했다.

## 30개 대응 비교

| ID | Bing 입력/판정 | MCP 기본 입력/판정 | MCP 최적화 입력/판정 | 최적화 입력 감소율(기본 대비) |
| --- | --- | --- | --- | --- |
| W1 | 3,494 / correct | 16,833 / correct | 9,507 / correct | 43.5% |
| W2 | 8,129 / correct | 21,737 / correct | 9,603 / correct | 55.8% |
| W3 | 5,882 / correct | 17,893 / correct | 17,266 / correct | 3.5% |
| W4 | 2,294 / correct | 17,656 / correct | 10,015 / correct | 43.3% |
| W5 | 10,242 / correct | 17,297 / correct | 9,594 / correct | 44.5% |
| P1 | 12,365 / unverifiable | 37,585 / unverifiable | 13,675 / correct | 63.6% |
| P2 | 6,269 / correct | 16,674 / correct | 13,810 / correct | 17.2% |
| P3 | 7,829 / unverifiable | 20,857 / correct | 14,252 / correct | 31.7% |
| P4 | 8,668 / unverifiable | 15,031 / unverifiable | 12,591 / no_factual_answer | 16.2% |
| P5 | 13,336 / no_factual_answer | 16,884 / no_factual_answer | 9,996 / no_factual_answer | 40.8% |
| F1 | 7,491 / correct | 14,046 / correct | 14,200 / correct | -1.1% |
| F2 | 5,589 / correct | 10,367 / incorrect | 5,185 / incorrect | 50.0% |
| F3 | 2,441 / incorrect | 11,960 / correct | 4,918 / incorrect | 58.9% |
| F4 | 2,021 / unverifiable | 21,385 / incorrect | 7,766 / unverifiable | 63.7% |
| F5 | 6,801 / correct | 7,929 / correct | 5,746 / correct | 27.5% |
| N1 | 8,656 / correct | 0 / no_factual_answer | 0 / no_factual_answer | 미보고% |
| N2 | 9,059 / correct | 21,458 / correct | 0 / no_factual_answer | 미보고% |
| N3 | 7,477 / correct | 9,049 / correct | 7,245 / correct | 19.9% |
| N4 | 23,571 / no_factual_answer | 8,881 / unverifiable | 11,643 / incorrect | -31.1% |
| N5 | 5,775 / correct | 9,942 / correct | 7,487 / correct | 24.7% |
| V1 | 1,642 / no_factual_answer | 11,529 / correct | 8,846 / correct | 23.3% |
| V2 | 1,642 / no_factual_answer | 8,489 / incorrect | 7,333 / no_factual_answer | 13.6% |
| V3 | 4,403 / correct | 9,363 / correct | 8,000 / correct | 14.6% |
| V4 | 6,376 / unverifiable | 23,175 / no_factual_answer | 8,945 / no_factual_answer | 61.4% |
| V5 | 4,422 / no_factual_answer | 7,625 / correct | 7,044 / incorrect | 7.6% |
| B1 | 6,066 / correct | 26,114 / incorrect | 15,919 / correct | 39.0% |
| B2 | 3,137 / unverifiable | 14,883 / unverifiable | 0 / no_factual_answer | 미보고% |
| B3 | 6,592 / correct | 0 / no_factual_answer | 9,148 / correct | 미보고% |
| B4 | 9,493 / correct | 17,163 / incorrect | 9,783 / incorrect | 43.0% |
| B5 | 3,042 / correct | 16,676 / correct | 9,487 / correct | 43.1% |

## 실제 답변 90개·질문별 독립 검증

### W1 · web

9월 12일 인천공항 제1터미널 장기주차장에 일반 승용차를 24시간 세우면 얼마야?

**공통 판정 조건:** 2026-09-12 적용 / 일반 승용차 / 장기주차 24시간 요금

**독립 확인:** 인천공항 공식 일반요금: 장기주차장 소형 일 최대 9,000원. 일반 승용차 24시간, 할인·주차대행 제외.

#### Bing — correct

2026년 9월 12일 기준, 인천공항 **제1터미널 장기주차장**에 일반 승용차를 24시간 주차하면 **최대 9,000원**입니다. 경차·장애인·다자녀 등 할인 대상이 아니고, 주차대행료는 포함되지 않은 금액입니다. 【6:1†source】

- 판정: 공식 장기주차 소형 일최대9,000원과 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 3,494; 첫 TEXT: 5.85초; 완료: 9.15초.
- 원문: [W1-airport](https://www.airport.kr/ap_ko/969/subview.do) · [조회기록](../results/full_comparison_v9_20260908/sources/W1-airport.json)

#### Web IQ MCP 기본 — correct

인천공항 **제1터미널 장기주차장**에 일반 승용차를 **24시간** 주차하면 **9,000원**입니다. 경차·장애인 차량 등 감면 대상이 아니고, 24시간을 초과하면 추가 일수 요금이 붙습니다.

- 판정: 공식 장기주차 소형 일최대9,000원과 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 16,833; 첫 TEXT: 4.18초; 완료: 6.89초.
- 원문: [W1-airport](https://www.airport.kr/ap_ko/969/subview.do) · [조회기록](../results/full_comparison_v9_20260908/sources/W1-airport.json)

#### Web IQ MCP 최적화 — correct

2026년 9월 12일 기준, 인천공항 **제1터미널 장기주차장에 일반 승용차를 24시간 주차하면 9,000원**입니다. 일반 승용차는 소형차 요금이 적용되며, 24시간을 초과하면 하루 단위 요금이 추가됩니다.

- 판정: 공식 장기주차 소형 일최대9,000원과 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 9,507; 첫 TEXT: 4.80초; 완료: 8.08초.
- 원문: [W1-airport](https://www.airport.kr/ap_ko/969/subview.do) · [조회기록](../results/full_comparison_v9_20260908/sources/W1-airport.json)

### W2 · web

9월 12일 토요일 김포공항 국내선 주차장에 승용차 하루 세우면 얼마야?

**공통 판정 조건:** 토요일 요금 / 국내선·소형 승용차 / 24시간 기준

**독립 확인:** 김포공항 공식 국내선 소형: 금·토·일 및 법정공휴일 24시간 30,000원. 2026-09-12는 토요일.

#### Bing — correct

9월 12일 토요일에는 김포공항 **국내선 주차장 승용차 1일 최대 요금이 3만 원**입니다. 기본 30분 1,000원, 이후 15분마다 500원이 부과되며, 경차·장애인 차량·다자녀 가정 등은 조건에 따라 할인될 수 있습니다. 【6:0†source】

- 판정: 토요일 국내선 승용차24시간30,000원 공식표와 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 8,129; 첫 TEXT: 4.85초; 완료: 7.81초.
- 원문: [W2-official-parking](https://www.airport.co.kr/gimpo/cms/frCon/index.do?MENU_ID=1360) · [조회기록](../results/full_comparison_v9_20260908/sources/W2-official-parking.json)

#### Web IQ MCP 기본 — correct

9월 12일 토요일, 김포공항 **국내선 제1·제2주차장에 승용차를 하루 주차하면 최대 3만 원**입니다. 기본요금은 30분 1,000원, 이후 15분당 500원이며 경차·저공해차량 등 감면 대상이면 할인될 수 있습니다.

- 판정: 토요일 국내선 승용차24시간30,000원 공식표와 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 21,737; 첫 TEXT: 7.00초; 완료: 10.15초.
- 원문: [W2-official-parking](https://www.airport.co.kr/gimpo/cms/frCon/index.do?MENU_ID=1360) · [조회기록](../results/full_comparison_v9_20260908/sources/W2-official-parking.json)

#### Web IQ MCP 최적화 — correct

9월 12일 토요일 김포공항 국내선 주차장에 승용차를 24시간 세우면 **3만 원**입니다. 경차·저공해차·장애인 차량 등은 조건에 따라 **50% 할인**될 수 있습니다.

- 판정: 토요일 국내선 승용차24시간30,000원 공식표와 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 9,603; 첫 TEXT: 4.70초; 완료: 7.59초.
- 원문: [W2-official-parking](https://www.airport.co.kr/gimpo/cms/frCon/index.do?MENU_ID=1360) · [조회기록](../results/full_comparison_v9_20260908/sources/W2-official-parking.json)

### W3 · web

서울대공원 동물원에 소형견을 이동가방에 넣으면 들어갈 수 있어?

**공통 판정 조건:** 동물원과 공원 외곽 구분 / 이동가방 예외 여부 / 안내견과 일반 반려견 구분

**독립 확인:** 동물원 반입 제한은 일반 반려견에 적용. 소형·이동가방 예외를 입증하지 못함. 공원 외부와 동물원 구분; 장애인 보조견은 별도.

#### Bing — correct

아니요. **소형견을 이동가방에 넣어도 서울대공원 동물원 내부에는 입장할 수 없습니다.** 반려동물은 동물원·식물원·테마가든 내부 출입이 금지되며, 안내견만 예외입니다. 대신 공원 내 개방공간은 목줄·이름표와 배변봉투를 갖추면 이용할 수 있습니다. 【6:2†source】

- 판정: 동물원 일반 반려견 반입불가이며 이동가방도 예외가 아니라는 핵심과 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 5,882; 첫 TEXT: 4.29초; 완료: 9.26초.
- 원문: [W3-grandpark](https://grandpark.seoul.go.kr/conts/contsView/ko/S001001001006.do) · [조회기록](../results/full_comparison_v9_20260908/sources/W3-grandpark.json)

#### Web IQ MCP 기본 — correct

아니요. **소형견이라도 이동가방이나 케이지에 넣어 서울대공원 동물원 내부에 들어갈 수 없습니다.** 반려견과 함께라면 동물원 밖 서울대공원 산책로·호수 주변만 이용하시고, 안내견은 예외입니다.

- 판정: 동물원 일반 반려견 반입불가이며 이동가방도 예외가 아니라는 핵심과 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 17,893; 첫 TEXT: 4.09초; 완료: 7.15초.
- 원문: [W3-grandpark](https://grandpark.seoul.go.kr/conts/contsView/ko/S001001001006.do) · [조회기록](../results/full_comparison_v9_20260908/sources/W3-grandpark.json)

#### Web IQ MCP 최적화 — correct

아니요. **소형견이라도 이동가방에 넣은 일반 반려견은 서울대공원 동물원 내부에 들어갈 수 없고, 안내견만 예외**로 안내됩니다. 반려견과는 동물원 외부 광장이나 호수 주변 산책로를 이용하시고, 정확한 현장 기준은 방문 전 서울대공원 고객센터(02-500-7335~7)에 확인해 주세요.

- 판정: 동물원 일반 반려견 반입불가이며 이동가방도 예외가 아니라는 핵심과 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 17,266; 첫 TEXT: 6.00초; 완료: 9.81초.
- 원문: [W3-grandpark](https://grandpark.seoul.go.kr/conts/contsView/ko/S001001001006.do) · [조회기록](../results/full_comparison_v9_20260908/sources/W3-grandpark.json)

### W4 · web

2026년 9월 기준으로 일반 승용차가 남산 서울타워 정상까지 올라갈 수 있어?

**공통 판정 조건:** 일반 승용차 제한 / 현재 적용 / 허가 차량 예외를 일반화하지 않음

**독립 확인:** 공식 교통 안내상 일반 승용차 정상 진입 불가. 허가차·셔틀 예외를 일반화하지 않음.

#### Bing — correct

아니요. **2026년 9월 기준 일반 승용차는 남산서울타워 정상까지 올라갈 수 없습니다.** 일반 차량의 남산 순환도로 통행이 제한되어 있어, 인근 주차장에 세운 뒤 케이블카·순환버스·도보 등을 이용해야 합니다. 【6:0†source】

- 판정: 일반승용차 정상진입 제한을 공식 교통안내로 확인.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 2,294; 첫 TEXT: 4.25초; 완료: 8.12초.
- 원문: [W4-namsan](https://www.nseoultower.co.kr/visit/traffic.asp) · [조회기록](../results/full_comparison_v9_20260908/sources/W4-namsan.json)

#### Web IQ MCP 기본 — correct

아니요. **2026년 9월 기준 일반 승용차는 남산 순환도로 통행 제한으로 서울타워 정상까지 올라갈 수 없습니다.** 차량은 인근에 주차한 뒤 01A·01B 녹색순환버스, 케이블카 또는 도보를 이용해야 하며, 장애인 차량 등 일부 예외만 있습니다.

- 판정: 일반승용차 정상진입 제한을 공식 교통안내로 확인.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 17,656; 첫 TEXT: 4.87초; 완료: 8.19초.
- 원문: [W4-namsan](https://www.nseoultower.co.kr/visit/traffic.asp) · [조회기록](../results/full_comparison_v9_20260908/sources/W4-namsan.json)

#### Web IQ MCP 최적화 — correct

아니요. **2026년 9월 기준 일반 승용차는 남산 순환도로를 통해 남산서울타워 정상까지 올라갈 수 없습니다.** 차량은 남산 자락 주차장에 세운 뒤 녹색순환버스나 케이블카를 이용해야 하며, 장애인 차량 등 일부 예외만 별도 통행이 허용됩니다.

- 판정: 일반승용차 정상진입 제한을 공식 교통안내로 확인.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 10,015; 첫 TEXT: 4.49초; 완료: 7.98초.
- 원문: [W4-namsan](https://www.nseoultower.co.kr/visit/traffic.asp) · [조회기록](../results/full_comparison_v9_20260908/sources/W4-namsan.json)

### W5 · web

9월 12일 서울역에서 인천공항 제1터미널 가는 공항철도 직통열차 성인 요금 얼마야?

**공통 판정 조건:** 직통과 일반열차 구분 / 성인 기본 요금 / 할인가와 일반가 구분

**독립 확인:** 새 공항철도 공식 도메인 airportrailroad.com의 직통열차 소개: 어른13,000원. 별도 정상운임은 서울~T1 18,500원으로 병기한다. 답변13,000원은 현재 어른 판매운임과 일치하나 정상운임 명칭과는 구분.

#### Bing — correct

9월 12일 서울역에서 인천공항 **제1터미널까지 공항철도 직통열차 성인 요금은 13,000원**입니다. 현재 공식 안내 기준이며, 지정좌석제로 운행됩니다. cite6:1

- 판정: 현행 공식 직통열차 어른 판매운임13,000원 일치. 공식표는 별도로 정상운임18,500원을 병기한다.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 10,242; 첫 TEXT: 4.53초; 완료: 8.28초.
- 원문: [W5-official-fare](https://www.airportrailroad.com/train/express/introduce) · [조회기록](../results/full_comparison_v9_20260908/sources/W5-official-fare.json)

#### Web IQ MCP 기본 — correct

9월 12일 서울역에서 인천공항 제1터미널로 가는 공항철도 직통열차 **성인 편도 요금은 13,000원**입니다. 9월 6일 기준 안내 운임을 확인했으며, 할인 적용 시 요금은 달라질 수 있습니다.

- 판정: 현행 공식 직통열차 어른 판매운임13,000원 일치. 정상운임18,500원과 판매운임 구분.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 17,297; 첫 TEXT: 4.39초; 완료: 7.28초.
- 원문: [W5-official-fare](https://www.airportrailroad.com/train/express/introduce) · [조회기록](../results/full_comparison_v9_20260908/sources/W5-official-fare.json)

#### Web IQ MCP 최적화 — correct

9월 12일 서울역에서 인천공항 제1터미널로 가는 공항철도 직통열차 성인 편도 요금은 **13,000원**입니다. 할인 적용 여부나 실제 판매가는 예매 화면에서 최종 확인해 주세요.

- 판정: 현행 공식 직통열차 어른 판매운임13,000원 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 9,594; 첫 TEXT: 4.10초; 완료: 7.29초.
- 원문: [W5-official-fare](https://www.airportrailroad.com/train/express/introduce) · [조회기록](../results/full_comparison_v9_20260908/sources/W5-official-fare.json)

### P1 · places

광교호수공원 원천호수 근처에 자체 주차장 있는 카페 한 곳 찾아줘.

**공통 판정 조건:** 원천호수 인근 실제 장소 / 자체 주차장 근거 / 현재 지점·주소

**독립 확인:** 테이크웨이브 관광정보는 원천호수·법조로25 SK VIEW Lake 2층과 건물 지하2층 주차장을 명시. 슬로·르디투어는 별도 방문기 대조; 공영주차를 자체주차로 인정하지 않음.

#### Bing — unverifiable

광교호수공원 **원천호수에서 차로 가까운 ‘르디투어 광교’**를 추천해요. 경기 수원시 영통구 웰빙타운로36번길 46-234에 있으며, 카페 바로 옆에 **지상 전용 주차장**이 있고 매장 이용 시 주말 기준 **2시간 30분 무료**로 안내됩니다. 다만 원천호수 산책로 바로 앞은 아니어서 주차 후 이동이 필요해요. 【12:0†source】

- 판정: 르디투어의 실제 주소·전용주차는2025 방문기에서 확인되지만 원천호수 근처의 거리 적합성 및 현재 주말2시간30분 무료조건은 독립 최신근거 부족.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 12,365; 첫 TEXT: 10.28초; 완료: 14.92초.
- 원문: [P1-webiq_optimized-0](https://korean.visitkorea.or.kr/detail/ms_detail.do?cotid=e405409a-a528-46f6-bb20-33b3fed3b5ea) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-webiq_optimized-0.json)
- 원문: [P1-webiq_optimized-1](https://www.ktourmap.com/spotDetails.jsp?contentId=2892845) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-webiq_optimized-1.json)
- 원문: [P1-slo](https://m.blog.naver.com/1000answn/223900388212) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-slo.json)
- 원문: [P1-bing-0](https://m.blog.naver.com/superego_1/223856251580) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-bing-0.json)

#### Web IQ MCP 기본 — unverifiable

**슬로 광교**를 추천해요. 경기 수원시 영통구 광교호수공원로 277, 중흥S클래스 3번 게이트 상가에 있고 원천호수 바로 앞입니다. 카페 전용 주차장은 아니지만 **건물 상가 자체 주차장**을 이용할 수 있으며, 카페 이용 후 주차 등록이 필요합니다.

- 판정: 슬로 광교의 장소·건물상가주차는2025 방문기에서 확인되나 현재 주차등록 조건을 보장할 최신 운영자 근거 부족.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 37,585; 첫 TEXT: 8.99초; 완료: 14.87초.
- 원문: [P1-webiq_optimized-0](https://korean.visitkorea.or.kr/detail/ms_detail.do?cotid=e405409a-a528-46f6-bb20-33b3fed3b5ea) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-webiq_optimized-0.json)
- 원문: [P1-webiq_optimized-1](https://www.ktourmap.com/spotDetails.jsp?contentId=2892845) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-webiq_optimized-1.json)
- 원문: [P1-slo](https://m.blog.naver.com/1000answn/223900388212) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-slo.json)
- 원문: [P1-bing-0](https://m.blog.naver.com/superego_1/223856251580) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-bing-0.json)
- 원문: [P1-webiq_base-4](https://m.blog.naver.com/yom-yum/224121495809) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-webiq_base-4.json)
- 원문: [P1-webiq_base-5](https://m.blog.naver.com/mrlee8551/223714549487) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-webiq_base-5.json)

#### Web IQ MCP 최적화 — correct

**테이크웨이브**를 추천해요. 광교 원천호수공원 근처 **광교 SK VIEW Lake 근린생활타워 2층(수원시 영통구 법조로 25)**에 있고, 건물 **지하 2층 주차장**을 이용할 수 있는 것으로 확인됩니다. 주차 할인·무료 이용 조건은 최신 확인이 안 돼 방문 전 문의해 보세요.

- 판정: 관광정보에서 테이크웨이브의 법조로25·호수근처·건물지하2층 주차를 확인. 무료조건은 미확인으로 한정하여 과장하지 않았다.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 13,675; 첫 TEXT: 6.25초; 완료: 10.42초.
- 원문: [P1-webiq_optimized-0](https://korean.visitkorea.or.kr/detail/ms_detail.do?cotid=e405409a-a528-46f6-bb20-33b3fed3b5ea) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-webiq_optimized-0.json)
- 원문: [P1-webiq_optimized-1](https://www.ktourmap.com/spotDetails.jsp?contentId=2892845) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-webiq_optimized-1.json)
- 원문: [P1-slo](https://m.blog.naver.com/1000answn/223900388212) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-slo.json)
- 원문: [P1-bing-0](https://m.blog.naver.com/superego_1/223856251580) · [조회기록](../results/full_comparison_v9_20260908/sources/P1-bing-0.json)

### P2 · places

서울숲역 근처에 강아지가 실내에 들어갈 수 있는 카페 한 곳 찾아줘.

**공통 판정 조건:** 실내 동반 조건 / 실제 지점·주소 / 테라스 전용과 구분

**독립 확인:** 어라운드데이 서울숲2길24-1의 반려생활 장소정보와 2026 방문기에서 실내·모든 좌석 동반을 대조. 테라스 전용 체다앤올리는 대체 정답 아님.

#### Bing — correct

서울숲역 근처라면 **어라운드데이**를 추천해요. 서울 성동구 **서울숲2길 24-1**에 있고, 강아지의 **실내 동반이 가능**하며 대형견도 이용할 수 있고 펫 메뉴도 판매한다고 안내돼 있습니다. 영업시간은 **11:00~20:00**로 확인되지만, 방문 전 동반 가능 여부를 전화로 다시 확인해 주세요. 【6:2†source】

- 판정: 반려생활의 현행 장소정보와2026 방문기에 어라운드데이 주소·실내모든좌석 동반·대형견 및 펫메뉴가 일치. 방문전 확인 조건도 명시.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 6,269; 첫 TEXT: 4.63초; 완료: 8.75초.
- 원문: [P2-webiq_base-1](https://www.ban-life.com/store/view?type=s&id=2423) · [조회기록](../results/full_comparison_v9_20260908/sources/P2-webiq_base-1.json)
- 원문: [P2-bing-0](https://m.blog.naver.com/mirioli/224390044787) · [조회기록](../results/full_comparison_v9_20260908/sources/P2-bing-0.json)
- 원문: [P2-chedda](https://www.ban-life.com/store/view?type=s&id=14890) · [조회기록](../results/full_comparison_v9_20260908/sources/P2-chedda.json)

#### Web IQ MCP 기본 — correct

서울숲역 근처라면 **어라운드데이 서울숲**을 추천해요. 서울 성동구 서울숲2길 24-1에 있고, **모든 좌석에 강아지 동반이 가능한 실내 카페**로 안내되어 있으며 강아지 메뉴도 있습니다. 다만 운영시간이나 동반 정책이 바뀔 수 있으니 방문 전 전화 확인을 권해요.

- 판정: 반려생활의 현행 장소정보와2026 방문기에 어라운드데이 주소·실내모든좌석 동반·펫메뉴 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 16,674; 첫 TEXT: 4.60초; 완료: 8.69초.
- 원문: [P2-webiq_base-1](https://www.ban-life.com/store/view?type=s&id=2423) · [조회기록](../results/full_comparison_v9_20260908/sources/P2-webiq_base-1.json)
- 원문: [P2-bing-0](https://m.blog.naver.com/mirioli/224390044787) · [조회기록](../results/full_comparison_v9_20260908/sources/P2-bing-0.json)
- 원문: [P2-chedda](https://www.ban-life.com/store/view?type=s&id=14890) · [조회기록](../results/full_comparison_v9_20260908/sources/P2-chedda.json)

#### Web IQ MCP 최적화 — correct

서울숲역 근처라면 **어라운드데이**를 추천해요. 서울 성동구 서울숲2길 24-1에 있으며, **실내 모든 좌석에 강아지 동반이 가능**하고 반려견 메뉴도 있습니다. 다만 애견카페가 아닌 동반 가능 카페라 목줄·배변 등 펫티켓을 지켜주세요.

- 판정: 실내모든좌석 동반·주소·펫메뉴·동반카페 펫티켓이 장소 원문과 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 13,810; 첫 TEXT: 6.26초; 완료: 10.29초.
- 원문: [P2-webiq_base-1](https://www.ban-life.com/store/view?type=s&id=2423) · [조회기록](../results/full_comparison_v9_20260908/sources/P2-webiq_base-1.json)
- 원문: [P2-bing-0](https://m.blog.naver.com/mirioli/224390044787) · [조회기록](../results/full_comparison_v9_20260908/sources/P2-bing-0.json)
- 원문: [P2-chedda](https://www.ban-life.com/store/view?type=s&id=14890) · [조회기록](../results/full_comparison_v9_20260908/sources/P2-chedda.json)

### P3 · places

일산 호수공원 정발산역 쪽에서 아이랑 점심 먹을 주차 가능한 식당 하나 추천해줘.

**공통 판정 조건:** 정발산역·호수공원 인근 / 현재 영업 식당 / 주차 근거 / 없는 편의시설 추측 금지

**독립 확인:** 부페파크·포폴로피자는 정발산로43-20 건물주차 최대2시간 지원을 2026년5월 방문기에서 확인. 조선초가한끼는 2023년 방문기만 확보하여 현행 영업·편의시설을 단정할 수 없음.

#### Bing — unverifiable

**조선초가한끼 일산점**을 추천해요. 정발산역 2번 출구와 호수공원 사이에 있고, 건물 지하주차장을 이용할 수 있으며 **놀이방과 아기의자**가 있어 아이와 가기 좋습니다. 평일 점심은 12시부터지만 **15:00~17:30 브레이크타임**이 있고, 평일 점심 주문 마감은 14시로 안내돼요. 【6:2†source】

- 판정: 조선초가한끼 주소·주차·놀이방·아기의자는2023 방문기만 확인. 현재 영업과 시설을2026년으로 확정할 근거 부족.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 7,829; 첫 TEXT: 4.93초; 완료: 9.03초.
- 원문: [P3-webiq_base-0](https://m.blog.naver.com/borakim___/224278273007) · [조회기록](../results/full_comparison_v9_20260908/sources/P3-webiq_base-0.json)
- 원문: [P3-webiq_optimized-0](https://m.blog.naver.com/qxngsta/224289912769) · [조회기록](../results/full_comparison_v9_20260908/sources/P3-webiq_optimized-0.json)
- 원문: [P3-bing-0](https://m.blog.naver.com/whitesunga/223124262881) · [조회기록](../results/full_comparison_v9_20260908/sources/P3-bing-0.json)

#### Web IQ MCP 기본 — correct

**부페파크 일산점**을 추천해요. 정발산역 1번 출구에서 약 1분, 센트럴프라자 10층에 있고 아이들이 먹기 좋은 메뉴가 다양하며 아기의자도 확인됩니다.  

건물 지하주차장을 이용하면 **최대 2시간 무료**이고, 영업은 매일 12시부터예요. 평일에는 15시부터 18시까지 브레이크타임이 있으니 점심 방문을 권합니다.

- 판정: 현행운영자사이트의정발산로43-20주소와2026년5월 직접방문원문의주차2시간·점심12시·평일15~18시휴식이일치.현재현장상황보장은아님.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 20,857; 첫 TEXT: 6.22초; 완료: 11.88초.
- 원문: [P3-webiq_base-0](https://m.blog.naver.com/borakim___/224278273007) · [조회기록](../results/full_comparison_v9_20260908/sources/P3-webiq_base-0.json)
- 원문: [P3-webiq_optimized-0](https://m.blog.naver.com/qxngsta/224289912769) · [조회기록](../results/full_comparison_v9_20260908/sources/P3-webiq_optimized-0.json)
- 원문: [P3-bing-0](https://m.blog.naver.com/whitesunga/223124262881) · [조회기록](../results/full_comparison_v9_20260908/sources/P3-bing-0.json)
- 원문: [P3-buffet-operator](http://buffetpark.com/main/main.php) · [조회기록](../results/full_comparison_v9_20260908/sources/P3-buffet-operator.json)
- 원문: [P3-webiq_base-1](https://m.menupan.com/restaurant/onepage.asp?acode=e400541) · [조회기록](../results/full_comparison_v9_20260908/sources/P3-webiq_base-1.json)

#### Web IQ MCP 최적화 — correct

**포폴로피자**를 추천해요. 정발산역 1번 출구에서 가깝고 아이와 나눠 먹기 좋은 피자집이며, 센트럴플라자 지하주차장을 이용하면 **최대 2시간 지원**된다는 최근 확인 자료가 있습니다. 다만 대기가 길 수 있어 캐치테이블 확인이나 예약을 권하고, 화~일 11시 30분부터 영업하며 월요일은 쉽니다.

- 판정: 운영자2026년9월공지로현재영업정체성을확인하고2026년5월방문원문의건물주차2시간·11:30개점·월요일휴무를대조.대기상황은보장하지않음.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 14,252; 첫 TEXT: 9.24초; 완료: 13.40초.
- 원문: [P3-webiq_base-0](https://m.blog.naver.com/borakim___/224278273007) · [조회기록](../results/full_comparison_v9_20260908/sources/P3-webiq_base-0.json)
- 원문: [P3-webiq_optimized-0](https://m.blog.naver.com/qxngsta/224289912769) · [조회기록](../results/full_comparison_v9_20260908/sources/P3-webiq_optimized-0.json)
- 원문: [P3-bing-0](https://m.blog.naver.com/whitesunga/223124262881) · [조회기록](../results/full_comparison_v9_20260908/sources/P3-bing-0.json)
- 원문: [P3-popolo-operator](https://www.instagram.com/pizzeria_popolo/) · [조회기록](../results/full_comparison_v9_20260908/sources/P3-popolo-operator.json)
- 원문: [P3-webiq_optimized-1](https://m.blog.naver.com/anhoit/224378913057) · [조회기록](../results/full_comparison_v9_20260908/sources/P3-webiq_optimized-1.json)

### P4 · places

성수역 근처에 토요일 오전 9시에 여는 베이커리 카페 있어?

**공통 판정 조건:** 성수역 인근 / 토요일 09시 운영 / 베이커리 카페 업종·지점

**독립 확인:** 토요일 09:00은 평일 개점과 다름. 오로라베이커리 2023 방문기 및 일반 목록만으로 2026 토요일 09:00 보장 불가. 어니언·글로우 등 주말 늦은 개점 구분.

#### Bing — unverifiable

네. **오로라베이커리카페 성수점**은 성수역 3번 출구 바로 근처이며, **토요일 오전 9시 30분부터** 영업하는 것으로 확인됩니다. 【6:1†source】

다만 **오전 9시 정각**에 여는 곳으로는 확인되지 않았고, 가까운 **코끼리베이글**은 매일 오전 8시 30분부터지만 카페 좌석 이용 여부는 방문 전 확인이 필요합니다. 【6:0†source】

- 판정: 주추천은09:30으로09:00요청 미해결. 대안 코끼리베이글08:30은 제시하지만 카페 좌석 미확인이고 최신 토요일 조건 증거 부족.
- 기술실패: False; 전달결함: 09:00 이용조건을 충족하는 확정 추천 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 8,668; 첫 TEXT: 4.47초; 완료: 8.21초.
- 원문: [P4-bing-0](https://m.blog.naver.com/dlwndud1207/223180320951) · [조회기록](../results/full_comparison_v9_20260908/sources/P4-bing-0.json)
- 원문: [P4-bing-1](https://mindbridge.prestlab.com/blog-friend/2025-seongsu-beikeori-kape-best-10-bbangjisunrye-seongsukape-bbangjib-cuceon) · [조회기록](../results/full_comparison_v9_20260908/sources/P4-bing-1.json)
- 원문: [P4-onion](https://www.onionkr.com/) · [조회기록](../results/full_comparison_v9_20260908/sources/P4-onion.json)

#### Web IQ MCP 기본 — unverifiable

네. **스탠다드브레드 성수**가 토요일 오전 9시에 엽니다. 성수이로18길 37에 있으며 매일 **09:00~21:00**, 마지막 주문은 20:30입니다.  

다만 성수역 바로 근처의 **피넛버터바나나**는 주말 **12시부터**, **하페 브레드샵**은 토·일 **09:00~18:00**로 확인됩니다. 하페는 카페 좌석 없이 테이크아웃 전문으로 안내돼요.

- 판정: 스탠다드브레드09:00 주장에 대응하는 독립 원문들이403/404로 접근되지 않았고 운영자 최신시간 확인 불가. 거짓으로 단정하지 않음.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 15,031; 첫 TEXT: 4.23초; 완료: 11.89초.
- 원문: [P4-bing-0](https://m.blog.naver.com/dlwndud1207/223180320951) · [조회기록](../results/full_comparison_v9_20260908/sources/P4-bing-0.json)
- 원문: [P4-bing-1](https://mindbridge.prestlab.com/blog-friend/2025-seongsu-beikeori-kape-best-10-bbangjisunrye-seongsukape-bbangjib-cuceon) · [조회기록](../results/full_comparison_v9_20260908/sources/P4-bing-1.json)
- 원문: [P4-onion](https://www.onionkr.com/) · [조회기록](../results/full_comparison_v9_20260908/sources/P4-onion.json)
- 원문: [P4-webiq_base-0](https://www.seongsucafe.kr/ko) · [조회기록](../results/full_comparison_v9_20260908/sources/P4-webiq_base-0.json)
- 원문: [P4-webiq_base-1](https://www.bluer.co.kr/restaurants/51856) · [조회기록](../results/full_comparison_v9_20260908/sources/P4-webiq_base-1.json)
- 원문: [P4-webiq_base-2](https://www.siksinhot.com/theme/magazine/11637) · [조회기록](../results/full_comparison_v9_20260908/sources/P4-webiq_base-2.json)

#### Web IQ MCP 최적화 — no_factual_answer

있긴 하지만, 확인된 곳 중 **토요일 오전 9시 영업이 확인된 베이커리 카페는 없습니다.** 피넛버터바나나는 성수역 1번 출구에서 도보 약 4분이지만 주말에는 **낮 12시부터**, 사이드템포도 **오전 11시부터** 엽니다.

오전 9시에 빵과 카페를 이용하려면 **파리바게뜨 성수역점**이 후보지만, 토요일 영업시간은 현재 검색에서 확인되지 않았습니다.

- 판정: 토요일09:00 영업을 확인한 베이커리카페를 제시하지 못했다고 명시. 후보만 제시했으며 지역 전체 부재 주장으로 읽지 않음.
- 기술실패: False; 전달결함: 요청시간에 이용 가능한 추천 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 12,591; 첫 TEXT: 6.85초; 완료: 11.78초.
- 원문: [P4-bing-0](https://m.blog.naver.com/dlwndud1207/223180320951) · [조회기록](../results/full_comparison_v9_20260908/sources/P4-bing-0.json)
- 원문: [P4-bing-1](https://mindbridge.prestlab.com/blog-friend/2025-seongsu-beikeori-kape-best-10-bbangjisunrye-seongsukape-bbangjib-cuceon) · [조회기록](../results/full_comparison_v9_20260908/sources/P4-bing-1.json)
- 원문: [P4-onion](https://www.onionkr.com/) · [조회기록](../results/full_comparison_v9_20260908/sources/P4-onion.json)
- 원문: [P4-webiq_optimized-1](https://cafe.ambitstock.com/seongsu/cafe/%EC%82%AC%EC%9D%B4%EB%93%9C%ED%85%9C%ED%8F%AC/) · [조회기록](../results/full_comparison_v9_20260908/sources/P4-webiq_optimized-1.json)

### P5 · places

판교역 근처에 밤 10시에도 여는 서점 한 곳 알려줘.

**공통 판정 조건:** 판교역 인근 서점 / 22시 영업 가능 여부 / 폐점 시각·요일 예외

**독립 확인:** 교보문고 판교점 공식: 월~목20:00, 금~일/공휴일20:30 폐점. 22:00 영업 후보 아님. 다른 지점의 미발견을 지역 서점 전체 부재로 단정하지 않음.

#### Bing — no_factual_answer

판교역 바로 근처에는 밤 10시까지 여는 서점을 확인하지 못했습니다. 교보문고 판교점은 현대백화점 판교점 지하 2층에 있으며, 확인된 영업시간은 월~목요일 오후 8시, 금~일요일 오후 9시까지입니다. 【6:0†source】

- 판정: 22:00 이용가능한 서점을 확인하지 못했다고 명시. 대안 영업시간은 핵심요청에 대한 답이 아니며 금~일21시 주장은 공식20:30과 다름.
- 기술실패: False; 전달결함: 22:00 서점 미제시
- 부가오류/정밀도: 대안 교보판교 금~일21시 폐점은 공식20:30과 불일치
- 입력 텍스트: 13,336; 첫 TEXT: 8.33초; 완료: 11.26초.
- 원문: [P5-bing-0](https://store.kyobobook.co.kr/store-info/069) · [조회기록](../results/full_comparison_v9_20260908/sources/P5-bing-0.json)

#### Web IQ MCP 기본 — no_factual_answer

판교역 근처 **교보문고 판교점**을 알려드릴게요. 현대백화점 판교점 지하 2층에 있으며, **금요일~일요일과 공휴일에는 밤 8시 30분까지**라 밤 10시에는 문을 닫습니다.

- 판정: 교보판교가22시에 닫는다는 사실은 맞지만 요청한22:00 영업서점은 제시하지 않았다.
- 기술실패: False; 전달결함: 22:00 서점 미제시
- 부가오류/정밀도: 없음
- 입력 텍스트: 16,884; 첫 TEXT: 4.41초; 완료: 7.07초.
- 원문: [P5-bing-0](https://store.kyobobook.co.kr/store-info/069) · [조회기록](../results/full_comparison_v9_20260908/sources/P5-bing-0.json)

#### Web IQ MCP 최적화 — no_factual_answer

판교역 근처 **교보문고 판교점**을 추천드려요. 현대백화점 판교점 지하 2층에 있으며, **금~일요일에는 밤 8시 30분까지**라서 밤 10시에는 문을 닫습니다. 확인된 정보상 밤 10시까지 여는 서점은 찾지 못했습니다.

- 판정: 공식 폐점20:30은 맞고22:00 대상을 찾지 못했다고 명시. 지역 전체 부재를 단정한 것은 아님.
- 기술실패: False; 전달결함: 22:00 서점 미제시
- 부가오류/정밀도: 없음
- 입력 텍스트: 9,996; 첫 TEXT: 6.07초; 완료: 10.14초.
- 원문: [P5-bing-0](https://store.kyobobook.co.kr/store-info/069) · [조회기록](../results/full_comparison_v9_20260908/sources/P5-bing-0.json)

### F1 · finance

2026년 9월 7일 삼성전자 보통주 코스피 정규장 종가 얼마였어?

**공통 판정 조건:** 005930 / 2026-09-07 KRX 정규장 종가 / 시간외·최근가 배제

**독립 확인:** Naver 삼성전자005930 일별시세 2026-09-07 종가270,000원, 전일255,500원 대비14,500원(+5.68%). 정규장 역사자료로 대조.

#### Bing — correct

2026년 9월 7일 삼성전자 보통주(005930)의 **코스피 정규장 종가는 270,000원**입니다. 전 거래일보다 **14,500원(5.68%) 상승**했습니다. 【9:2†source】

- 판정: 005930 2026-09-07 역사종가270,000원 및전일대비14,500원/+5.68% 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 7,491; 첫 TEXT: 8.21초; 완료: 12.16초.
- 원문: [F1-naver](https://finance.naver.com/item/sise_day.naver?code=005930&page=1) · [조회기록](../results/full_comparison_v9_20260908/sources/F1-naver.json)

#### Web IQ MCP 기본 — correct

2026년 9월 7일 삼성전자 보통주(005930)의 코스피 정규장 종가는 **27만 원**입니다. 전일 대비 **1만 4,500원(5.68%) 상승**했습니다.

- 판정: 005930 2026-09-07 역사종가270,000원 및전일대비14,500원/+5.68% 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 14,046; 첫 TEXT: 6.03초; 완료: 9.94초.
- 원문: [F1-naver](https://finance.naver.com/item/sise_day.naver?code=005930&page=1) · [조회기록](../results/full_comparison_v9_20260908/sources/F1-naver.json)

#### Web IQ MCP 최적화 — correct

2026년 9월 7일 코스피 정규장에서 삼성전자 보통주(005930)의 종가는 **270,000원**이었습니다. 전일 대비 **14,500원(5.68%) 상승**한 가격입니다.

- 판정: 005930 2026-09-07 역사종가270,000원 및전일대비14,500원/+5.68% 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 14,200; 첫 TEXT: 8.53초; 완료: 12.50초.
- 원문: [F1-naver](https://finance.naver.com/item/sise_day.naver?code=005930&page=1) · [조회기록](../results/full_comparison_v9_20260908/sources/F1-naver.json)

### F2 · finance

2026년 9월 4일 미국 나스닥 종합지수 종가랑 등락률 알려줘.

**공통 판정 조건:** COMP 종합지수 / 2026-09-04 / 종가·전일 대비 등락

**독립 확인:** Nasdaq 공식 COMP 역사자료 2026-09-04 26,506.99; 09-03 26,584.06. 차이 -77.07, 반올림 -0.29%. 26,506 단정은 0.99포인트 정밀도 불일치.

#### Bing — correct

2026년 9월 4일 미국 **나스닥 종합지수(Nasdaq Composite)**는 **26,506.99**로 마감했고, 전일 대비 **0.29% 하락**했습니다.【6:1†source】

- 판정: Nasdaq 공식26506.99 및-0.29%와 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 5,589; 첫 TEXT: 6.05초; 완료: 8.76초.
- 원문: [F2-nasdaq](https://api.nasdaq.com/api/quote/COMP/historical?assetclass=index&fromdate=2026-09-01&todate=2026-09-08&limit=10) · [조회기록](../results/full_comparison_v9_20260908/sources/F2-nasdaq.json)

#### Web IQ MCP 기본 — incorrect

2026년 9월 4일 정규장 기준 **나스닥 종합지수는 18,203.47포인트로 마감**했고, 전일 대비 **0.58% 하락**했습니다.

- 판정: 18203.47/-0.58%는 지정일 공식26506.99/-0.29%와 크게 다름.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 10,367; 첫 TEXT: 10.19초; 완료: 11.88초.
- 원문: [F2-nasdaq](https://api.nasdaq.com/api/quote/COMP/historical?assetclass=index&fromdate=2026-09-01&todate=2026-09-08&limit=10) · [조회기록](../results/full_comparison_v9_20260908/sources/F2-nasdaq.json)

#### Web IQ MCP 최적화 — incorrect

2026년 9월 4일 미국 정규장 기준 나스닥 종합지수는 **26,506**으로 마감했고, 전일 대비 **77.07포인트 하락, 등락률은 -0.29%**였습니다.

- 판정: 26506으로 단정한 종가는 공식26506.99보다0.99포인트 낮다. -77.07/-0.29%는 맞으며 이는 큰 금융오류와 구분하는 minor_numeric 정밀도불일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: minor_numeric: 종가0.99포인트 차이(약0.0037%); 전체결론의 큰 품질차로 해석하지 않음
- 입력 텍스트: 5,185; 첫 TEXT: 6.13초; 완료: 8.08초.
- 원문: [F2-nasdaq](https://api.nasdaq.com/api/quote/COMP/historical?assetclass=index&fromdate=2026-09-01&todate=2026-09-08&limit=10) · [조회기록](../results/full_comparison_v9_20260908/sources/F2-nasdaq.json)

### F3 · finance

2026년 9월 4일 미국 S&P500 지수는 얼마로 마감했어?

**공통 판정 조건:** S&P500 지수 / 2026-09-04 정규장 마감 / ETF 가격과 구분

**독립 확인:** Yahoo 공개 역사 일봉 ^GSPC 2026-09-04 7,718.60009765625→7,718.60; 09-03 7,747.7099609375→7,747.71. 정규일봉 종가 -29.11(-0.38%). Nasdaq SPX 경로는 데이터 없음.

#### Bing — incorrect

2026년 9월 4일 미국 **S&P 500 지수는 정규장에서 5,847.32로 마감**했습니다. 전일보다 **18.14포인트(0.31%) 상승**했습니다. 【6:2†source】

- 판정: 5847.32/+0.31%는 지정일 역사일봉7718.60/-0.38%와 다름.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 2,441; 첫 TEXT: 5.72초; 완료: 9.59초.
- 원문: [F3-yahoo](https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?period1=1788393600&period2=1788825600&interval=1d) · [조회기록](../results/full_comparison_v9_20260908/sources/F3-yahoo.json)
- 원문: [F3-sp500](https://api.nasdaq.com/api/quote/SPX/historical?assetclass=index&fromdate=2026-09-01&todate=2026-09-08&limit=10) · [조회기록](../results/full_comparison_v9_20260908/sources/F3-sp500.json)

#### Web IQ MCP 기본 — correct

2026년 9월 4일 미국 정규장 기준 S&P 500 지수는 **7,718.60**으로 마감했습니다. 전일보다 **29.11포인트(0.38%) 하락**했습니다.

- 판정: 지정일 ^GSPC 역사일봉7718.60, 전일7747.71 대비-29.11/-0.38%와 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 11,960; 첫 TEXT: 8.32초; 완료: 12.22초.
- 원문: [F3-yahoo](https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?period1=1788393600&period2=1788825600&interval=1d) · [조회기록](../results/full_comparison_v9_20260908/sources/F3-yahoo.json)
- 원문: [F3-sp500](https://api.nasdaq.com/api/quote/SPX/historical?assetclass=index&fromdate=2026-09-01&todate=2026-09-08&limit=10) · [조회기록](../results/full_comparison_v9_20260908/sources/F3-sp500.json)

#### Web IQ MCP 최적화 — incorrect

2026년 9월 4일 미국 정규장에서 S&P 500 지수는 **5,847.32**로 마감했습니다. 전일 대비 **0.31% 상승**한 수치입니다.

- 판정: 5847.32/+0.31%는 지정일 역사일봉7718.60/-0.38%와 다름.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 4,918; 첫 TEXT: 6.36초; 완료: 9.48초.
- 원문: [F3-yahoo](https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?period1=1788393600&period2=1788825600&interval=1d) · [조회기록](../results/full_comparison_v9_20260908/sources/F3-yahoo.json)
- 원문: [F3-sp500](https://api.nasdaq.com/api/quote/SPX/historical?assetclass=index&fromdate=2026-09-01&todate=2026-09-08&limit=10) · [조회기록](../results/full_comparison_v9_20260908/sources/F3-sp500.json)

### F4 · finance

2026년 9월 8일 서울외국환중개 기준 원달러 매매기준율 알려줘.

**공통 판정 조건:** 지정기관·고시일 / USD/KRW 매매기준율 / 현찰·실시간 현물과 구분

**독립 확인:** 서울외국환중개 날짜2026-09-08 페이지 확인. 환율 숫자는 동적 표에서 공개 텍스트로 획득되지 않음. 다른 은행 매매기준율·15:30현물은 지정기관 일일 매매기준율의 증거가 아님.

#### Bing — unverifiable

2026년 9월 8일 서울외국환중개 기준 **원·달러 매매기준율은 1달러당 1,345.50원**입니다. 【6:3†source】

- 판정: 1345.50을 지정기관 일일 매매기준율로 확정할 독립 숫자자료 미확보. 해당 인용 기사도1344.80으로 달라 출처일치도에 결함.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 인용 원문 숫자1344.80과 답변1345.50 불일치; 참값 확정은 별개
- 입력 텍스트: 2,021; 첫 TEXT: 6.38초; 완료: 8.10초.
- 원문: [F4-http](http://www.smbs.biz/ExRate/TodayExRate.jsp) · [조회기록](../results/full_comparison_v9_20260908/sources/F4-http.json)
- 원문: [F4-smbs](https://www.smbs.biz/ExRate/TodayExRate.jsp) · [조회기록](../results/full_comparison_v9_20260908/sources/F4-smbs.json)
- 원문: [F4-bing-0](https://zipnews.kr/exchange-rate-today/) · [조회기록](../results/full_comparison_v9_20260908/sources/F4-bing-0.json)

#### Web IQ MCP 기본 — incorrect

2026년 9월 8일 서울외국환중개 기준 원·달러 매매기준율은 **1달러당 1,345.60원**입니다. 이는 **서울 15시 30분 기준 환율**이며, 은행의 실제 환전·송금 환율과는 다를 수 있습니다.

- 판정: 1345.60은 연합뉴스가 명시적으로 서울15:30 원달러 환율이라고 구분한 값이다. 일일 매매기준율을 요구한 질문에 다른 시각현물값을 대체한 핵심종류 불일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 21,385; 첫 TEXT: 7.20초; 완료: 10.37초.
- 원문: [F4-http](http://www.smbs.biz/ExRate/TodayExRate.jsp) · [조회기록](../results/full_comparison_v9_20260908/sources/F4-http.json)
- 원문: [F4-smbs](https://www.smbs.biz/ExRate/TodayExRate.jsp) · [조회기록](../results/full_comparison_v9_20260908/sources/F4-smbs.json)
- 원문: [F4-webiq_base-2](https://www.yna.co.kr/view/AKR20260908126300002) · [조회기록](../results/full_comparison_v9_20260908/sources/F4-webiq_base-2.json)

#### Web IQ MCP 최적화 — unverifiable

2026년 9월 8일 서울외국환중개 기준 원·달러 매매기준율은 **1달러당 1,344.80원**입니다. 어제보다 **2.20원 하락**한 수치입니다.

- 판정: 1344.80은 일반 은행성 환율기사에서 확인되지만 서울외국환중개 지정기관의 해당일 일일 매매기준율로 귀속할 근거가 없다.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 7,766; 첫 TEXT: 3.98초; 완료: 11.12초.
- 원문: [F4-http](http://www.smbs.biz/ExRate/TodayExRate.jsp) · [조회기록](../results/full_comparison_v9_20260908/sources/F4-http.json)
- 원문: [F4-smbs](https://www.smbs.biz/ExRate/TodayExRate.jsp) · [조회기록](../results/full_comparison_v9_20260908/sources/F4-smbs.json)
- 원문: [F4-webiq_optimized-0](https://zipnews.kr/exchange-rate-today/) · [조회기록](../results/full_comparison_v9_20260908/sources/F4-webiq_optimized-0.json)

### F5 · finance

2026년 9월 4일 테슬라 나스닥 정규장 종가는 몇 달러였어?

**공통 판정 조건:** TSLA USD / 2026-09-04 정규장 종가 / 시간외 가격 배제

**독립 확인:** Nasdaq 공식 TSLA 역사자료 2026-09-04 Close/Last $354.08. 시간외 가격으로 대체하지 않음.

#### Bing — correct

테슬라(TSLA)의 **2026년 9월 4일 나스닥 정규장 종가**는 **354.08달러**였습니다. 정규장 기준이며, 시간 외 거래 가격인 352.87달러와는 다릅니다. 【6:1†source】

- 판정: Nasdaq 공식09/04 TSLA종가354.08 일치. 추가 시간외352.87은 핵심종가 검증과 별개.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 추가 시간외352.87 독립 확인 안 함
- 입력 텍스트: 6,801; 첫 TEXT: 4.52초; 완료: 7.74초.
- 원문: [F5-tsla](https://api.nasdaq.com/api/quote/TSLA/historical?assetclass=stocks&fromdate=2026-09-01&todate=2026-09-08&limit=10) · [조회기록](../results/full_comparison_v9_20260908/sources/F5-tsla.json)

#### Web IQ MCP 기본 — correct

테슬라(TSLA)의 **2026년 9월 4일 나스닥 정규장 종가는 354.08달러**였습니다. 미국 동부시간 정규장 기준이며, 시간 외 거래 가격은 제외한 종가입니다.

- 판정: Nasdaq 공식09/04 TSLA종가354.08 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 7,929; 첫 TEXT: 6.22초; 완료: 9.49초.
- 원문: [F5-tsla](https://api.nasdaq.com/api/quote/TSLA/historical?assetclass=stocks&fromdate=2026-09-01&todate=2026-09-08&limit=10) · [조회기록](../results/full_comparison_v9_20260908/sources/F5-tsla.json)

#### Web IQ MCP 최적화 — correct

2026년 9월 4일 나스닥 정규장에서 테슬라(TSLA)는 **354.08달러**로 마감했습니다.

- 판정: Nasdaq 공식09/04 TSLA종가354.08 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 5,746; 첫 TEXT: 7.22초; 완료: 8.67초.
- 원문: [F5-tsla](https://api.nasdaq.com/api/quote/TSLA/historical?assetclass=stocks&fromdate=2026-09-01&todate=2026-09-08&limit=10) · [조회기록](../results/full_comparison_v9_20260908/sources/F5-tsla.json)

### N1 · news

9월 2일부터 8일 사이에 나온 서울 도로 통제 기사 하나 알려줘. 통제 날짜와 구간도 알려줘.

**공통 판정 조건:** 보도일 2026-09-02~08 / 통제 적용일·구간 / 종료·예정 구분

**독립 확인:** 게시일2026-09-02~08과 실제 통제일·도로구간을 각각 검토. 9월1일 기사는 범위 밖. 동일 행사라도 연도·도로구간 다르면 불일치.

#### Bing — correct

9월 4일 연합뉴스가 보도한 서울 도로 통제 기사로는 **서울세계불꽃축제와 도심 마라톤 통제**가 있습니다. 불꽃축제는 **9월 5일 오후 3시~자정 여의동로(마포대교 남단~63빌딩)**, **9월 5일 오전 9시~6일 오전 3시 원효대교 양방향**이 전면 통제됩니다. 【9:2†source】

추가로 마라톤 때문에 **9월 6일 세종대로·을지로·청계천로**도 통제됩니다. 세종대로는 구간별로 오전 6시 30분부터 8시 50분 또는 9시 15분까지, 을지로는 오전 7시 40분~9시 10분, 청계천로는 오전 7시 45분~10시 30분입니다. 【9:2†source】

- 판정: 9/4 연합뉴스 원문에9/5여의동로15~24시·원효대교09시~익일03시 및9/6마라톤구간이 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 8,656; 첫 TEXT: 7.51초; 완료: 14.70초.
- 원문: [N1-korea](https://www.koreaeaglenews.com/news/articleView.html?idxno=104752) · [조회기록](../results/full_comparison_v9_20260908/sources/N1-korea.json)
- 원문: [N1-bing-0](https://news.nate.com/view/20260904n08077) · [조회기록](../results/full_comparison_v9_20260908/sources/N1-bing-0.json)

#### Web IQ MCP 기본 — no_factual_answer

(답변 없음)

- 판정: 기술실패로 최종 사실답변 없음. 시도는 분모 유지.
- 기술실패: True; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 0; 첫 TEXT: 미보고초; 완료: 5.40초.
- 원문: [N1-korea](https://www.koreaeaglenews.com/news/articleView.html?idxno=104752) · [조회기록](../results/full_comparison_v9_20260908/sources/N1-korea.json)
- 원문: [N1-bing-0](https://news.nate.com/view/20260904n08077) · [조회기록](../results/full_comparison_v9_20260908/sources/N1-bing-0.json)
- 원문: [N1-webiq_base-0](https://www.yna.co.kr/view/AKR20260908132700004) · [조회기록](../results/full_comparison_v9_20260908/sources/N1-webiq_base-0.json)

#### Web IQ MCP 최적화 — no_factual_answer

(답변 없음)

- 판정: 기술실패로 최종 사실답변 없음. 시도는 분모 유지.
- 기술실패: True; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 0; 첫 TEXT: 미보고초; 완료: 5.47초.
- 원문: [N1-korea](https://www.koreaeaglenews.com/news/articleView.html?idxno=104752) · [조회기록](../results/full_comparison_v9_20260908/sources/N1-korea.json)
- 원문: [N1-bing-0](https://news.nate.com/view/20260904n08077) · [조회기록](../results/full_comparison_v9_20260908/sources/N1-bing-0.json)
- 원문: [N1-webiq_optimized-0](https://www.yna.co.kr/view/AKR20260908132700004) · [조회기록](../results/full_comparison_v9_20260908/sources/N1-webiq_optimized-0.json)

### N2 · news

9월 2일부터 8일 사이에 나온 전기차 충전요금 할인 기사 알려줘. 언제 어디에 적용되는지도 알려줘.

**공통 판정 조건:** 보도 기간 / 할인 적용 시간·사업자 / 전력량·최종 충전료 구분

**독립 확인:** 9/2 초기보도와9/3 확장발표를 구분.9/3 뉴데일리·머니투데이:9/5~10/31주말공휴일11~14시, 기후부공공총충전료최대32%, 한전11~17%, 자가소비전력량50%. 전력량50%를전체충전료50%로 대체하지 않음.

#### Bing — correct

9월 2~8일 사이에는 **9월 3일 발표된 가을철 전기차 충전요금 할인** 기사가 나왔습니다. 할인은 **2026년 9월 5일~10월 31일 중 주말·공휴일 오전 11시~오후 2시**에 적용됩니다. 【6:0†source】

적용 대상은 **기후에너지환경부 공공 급속충전기 약 9,600기**로 최대 **32%**, 한전 운영 충전기는 약 **11~17%**, 주택·회사 등의 자가소비용 충전기는 전력량요금 **50%** 할인입니다. 민간 충전사업자는 업체별로 직접 할인이나 포인트 적립 등 방식과 금액이 다르므로, 이용 전 앱에서 최종 요금을 확인해야 합니다. 【6:4†source】

- 판정: 9/3 기사 원문이9/5~10/31주말공휴일11~14시, 기후부최대32%, 한전11~17%, 자가소비전력량50%를 각각 구분한다.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 9,059; 첫 TEXT: 4.41초; 완료: 11.35초.
- 원문: [N2-bing-0](https://biz.newdaily.co.kr/site/data/html/2026/09/03/2026090300171.html) · [조회기록](../results/full_comparison_v9_20260908/sources/N2-bing-0.json)
- 원문: [N2-bing-1](https://www.mt.co.kr/economy/2026/09/03/2026090310473726689) · [조회기록](../results/full_comparison_v9_20260908/sources/N2-bing-1.json)
- 원문: [N2-aju](https://www.ajunews.com/view/20260902175413561) · [조회기록](../results/full_comparison_v9_20260908/sources/N2-aju.json)

#### Web IQ MCP 기본 — correct

9월 2~8일 사이에는 **9월 3일 보도된 정부의 가을철 전기차 충전요금 할인 기사**가 확인됩니다.

- **적용 기간:** 2026년 9월 5일~10월 31일  
- **적용 시간:** 주말·공휴일 오전 11시~오후 2시  
- **할인 폭:** 전기차 충전요금 최대 32%  
- **적용 장소:** 기후에너지환경부·한국전력공사가 운영하는 공공 급속충전기와, 정부 협약 민간 충전기에서 기후부 회원카드로 결제하는 경우입니다. 자택·회사 등 자가소비용 충전시설도 전기차 충전용 전력량요금 할인 대상이지만, 실제 최종 요금은 충전사업자별로 다를 수 있습니다.

- 판정: 9/3 보도와9/5~10/31·11~14시·기후부최대32%를 확인. 사업자별 최종요금 차이를 한정했다.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 21,458; 첫 TEXT: 6.23초; 완료: 16.36초.
- 원문: [N2-bing-0](https://biz.newdaily.co.kr/site/data/html/2026/09/03/2026090300171.html) · [조회기록](../results/full_comparison_v9_20260908/sources/N2-bing-0.json)
- 원문: [N2-bing-1](https://www.mt.co.kr/economy/2026/09/03/2026090310473726689) · [조회기록](../results/full_comparison_v9_20260908/sources/N2-bing-1.json)
- 원문: [N2-aju](https://www.ajunews.com/view/20260902175413561) · [조회기록](../results/full_comparison_v9_20260908/sources/N2-aju.json)
- 원문: [N2-webiq_base-0](https://www.nanamcom.co.kr/news/articleView.html?idxno=52873) · [조회기록](../results/full_comparison_v9_20260908/sources/N2-webiq_base-0.json)

#### Web IQ MCP 최적화 — no_factual_answer

(답변 없음)

- 판정: 기술실패로 최종 사실답변 없음. 시도는 분모 유지.
- 기술실패: True; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 0; 첫 TEXT: 미보고초; 완료: 7.65초.
- 원문: [N2-bing-0](https://biz.newdaily.co.kr/site/data/html/2026/09/03/2026090300171.html) · [조회기록](../results/full_comparison_v9_20260908/sources/N2-bing-0.json)
- 원문: [N2-bing-1](https://www.mt.co.kr/economy/2026/09/03/2026090310473726689) · [조회기록](../results/full_comparison_v9_20260908/sources/N2-bing-1.json)
- 원문: [N2-aju](https://www.ajunews.com/view/20260902175413561) · [조회기록](../results/full_comparison_v9_20260908/sources/N2-aju.json)
- 원문: [N2-webiq_optimized-0](https://www.nanamcom.co.kr/news/articleView.html?idxno=52873) · [조회기록](../results/full_comparison_v9_20260908/sources/N2-webiq_optimized-0.json)

### N3 · news

9월 12일이나 13일에 서울에서 열리는 축제를 최근 기사에서 하나 찾아줘.

**공통 판정 조건:** 서울 행사 / 2026-09-12 또는 13 개최 / 최근 보도와 운영 일정

**독립 확인:** 서울시 2026-09-02 문화달력: 서울무형문화축제 9/12~13, 남산골한옥마을/남산국악당. 방문일과 기사게시일은 별도 대조.

#### Bing — correct

최근 기사에서 확인된 축제는 **2026 서울무형문화축제**입니다. **9월 12~13일 남산골한옥마을**에서 열리며, 무형유산 31종 공연과 장인 시연, 전통주 소개·체험 등이 진행됩니다. 【6:0†source】

- 판정: 서울무형문화축제9/12~13 남산골한옥마을·31개종목이 공식문화달력과9/6기사 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 7,477; 첫 TEXT: 4.44초; 완료: 7.11초.
- 원문: [N3-seoul](https://news.seoul.go.kr/culture/archives/534130) · [조회기록](../results/full_comparison_v9_20260908/sources/N3-seoul.json)
- 원문: [N3-festival](https://festival.seoul.go.kr/festival/main/festivalView.do?festacode=390) · [조회기록](../results/full_comparison_v9_20260908/sources/N3-festival.json)
- 원문: [N3-bing-0](https://www.yna.co.kr/view/AKR20260905022100004) · [조회기록](../results/full_comparison_v9_20260908/sources/N3-bing-0.json)

#### Web IQ MCP 기본 — correct

최근 기사에서 확인된 축제는 **2026 서울무형문화축제**입니다. **9월 12~13일 서울 남산골한옥마을**에서 열리며, 무형유산 31개 종목을 보유자·전승자·시민이 함께 체험하는 참여형 축제입니다. (파이낸셜뉴스·연합뉴스, 9월 6일 보도)

- 판정: 서울무형문화축제9/12~13 남산골한옥마을·31개종목이 공식문화달력과9/6기사 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 9,049; 첫 TEXT: 4.27초; 완료: 8.74초.
- 원문: [N3-seoul](https://news.seoul.go.kr/culture/archives/534130) · [조회기록](../results/full_comparison_v9_20260908/sources/N3-seoul.json)
- 원문: [N3-festival](https://festival.seoul.go.kr/festival/main/festivalView.do?festacode=390) · [조회기록](../results/full_comparison_v9_20260908/sources/N3-festival.json)
- 원문: [N3-webiq_base-0](https://www.ekw.co.kr/news/articleView.html?idxno=20777) · [조회기록](../results/full_comparison_v9_20260908/sources/N3-webiq_base-0.json)

#### Web IQ MCP 최적화 — correct

최근 기사에서 확인된 축제는 **2026 서울무형문화축제**입니다. **9월 12~13일 서울 남산골한옥마을**에서 열리며, 무형유산 31개 종목을 선보인다고 합니다. (파이낸셜뉴스·연합뉴스, 9월 6일)

- 판정: 서울무형문화축제9/12~13 남산골한옥마을·31개종목이 공식문화달력과9/6기사 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 7,245; 첫 TEXT: 4.02초; 완료: 9.19초.
- 원문: [N3-seoul](https://news.seoul.go.kr/culture/archives/534130) · [조회기록](../results/full_comparison_v9_20260908/sources/N3-seoul.json)
- 원문: [N3-festival](https://festival.seoul.go.kr/festival/main/festivalView.do?festacode=390) · [조회기록](../results/full_comparison_v9_20260908/sources/N3-festival.json)
- 원문: [N3-webiq_optimized-0](https://www.ekw.co.kr/news/articleView.html?idxno=20777) · [조회기록](../results/full_comparison_v9_20260908/sources/N3-webiq_optimized-0.json)

### N4 · news

9월 2일부터 8일 사이에 나온 고속도로 전기차 충전소 소식 하나 알려줘.

**공통 판정 조건:** 지정 보도 기간 / 고속도로 충전 관련성 / 운영 중·선정·예정 구분

**독립 확인:** 9/4교통뉴스는9/5~10/31공공충전할인을보도. 본문은전력량50%/최종충전료최대32%를구분하며 고속도로라는단어는없다.2023고속도로충전소기사로2026이할인대상관계를보충할경우현행관계불확실.5/28발표는지정게시기간밖.

#### Bing — no_factual_answer

9월 2~8일에 **발표된 고속도로 전기차 충전소 소식은 확인하지 못했습니다.** 가장 가까운 관련 소식으로는 정부가 **9월 말부터 고속도로 휴게소 공공 급속충전기에 ‘플러그 앤 차지’ 자동 인증·결제 시스템을 시범 적용할 예정**이라는 5월 28일 발표가 있습니다. 【12:0†source】

- 판정: 요청게시기간9/2~8 기사는 찾지 못했다고 명시하고5/28발표로 대체. 범위외임을 숨기지는 않음.
- 기술실패: False; 전달결함: 지정기간 기사 미제시
- 부가오류/정밀도: 없음
- 입력 텍스트: 23,571; 첫 TEXT: 11.40초; 완료: 14.51초.
- 원문: [N4-webiq_base-0](https://www.cartvnews.com/news/articleView.html?idxno=702292) · [조회기록](../results/full_comparison_v9_20260908/sources/N4-webiq_base-0.json)
- 원문: [N4-webiq_base-4](https://www.edaily.co.kr/news/read?newsId=01246406635670584) · [조회기록](../results/full_comparison_v9_20260908/sources/N4-webiq_base-4.json)
- 원문: [N4-bing-0](https://news.nate.com/view/20260528n29155) · [조회기록](../results/full_comparison_v9_20260908/sources/N4-bing-0.json)

#### Web IQ MCP 기본 — unverifiable

9월 4일 보도에 따르면, **9월 5일부터 10월 31일까지 주말·공휴일 오전 11시~오후 2시** 고속도로를 포함한 공공 급속충전기 충전요금 할인이 재개됩니다. 기후에너지환경부와 한국전력공사가 운영하는 공공 급속충전기 약 1만4천 기 등이 대상이며, 보도 출처는 교통뉴스입니다.

- 판정: 9/4교통뉴스 할인기간·공공1만4천기는 확인되나 그 기사 자체의 고속도로 적용 관계를 명확히 입증하지 못함. 후속고속도로기사는2023자료.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 8,881; 첫 TEXT: 4.69초; 완료: 8.54초.
- 원문: [N4-webiq_base-0](https://www.cartvnews.com/news/articleView.html?idxno=702292) · [조회기록](../results/full_comparison_v9_20260908/sources/N4-webiq_base-0.json)
- 원문: [N4-webiq_base-4](https://www.edaily.co.kr/news/read?newsId=01246406635670584) · [조회기록](../results/full_comparison_v9_20260908/sources/N4-webiq_base-4.json)
- 원문: [N4-bing-0](https://news.nate.com/view/20260528n29155) · [조회기록](../results/full_comparison_v9_20260908/sources/N4-bing-0.json)

#### Web IQ MCP 최적화 — incorrect

9월 4일 소식입니다. 기후에너지환경부가 9월 5일부터 10월 31일까지 주말·공휴일 오전 11시부터 오후 2시까지 공공 전기차 충전요금을 50% 할인하며, 고속도로 휴게소의 공공 급속충전기도 대상에 포함됩니다. 다만 충전사업자별 최종 요금과 적용 여부는 확인이 필요합니다.

- 판정: 교통뉴스 본문은 전력량50%와 소비자총충전요금최대32%를 구분. 답변은 공공충전요금50%로 혼동했다. 사업자별확인 단서로 이 수치오류가 해소되지는 않음.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 11,643; 첫 TEXT: 7.73초; 완료: 11.96초.
- 원문: [N4-webiq_base-0](https://www.cartvnews.com/news/articleView.html?idxno=702292) · [조회기록](../results/full_comparison_v9_20260908/sources/N4-webiq_base-0.json)
- 원문: [N4-webiq_base-4](https://www.edaily.co.kr/news/read?newsId=01246406635670584) · [조회기록](../results/full_comparison_v9_20260908/sources/N4-webiq_base-4.json)
- 원문: [N4-bing-0](https://news.nate.com/view/20260528n29155) · [조회기록](../results/full_comparison_v9_20260908/sources/N4-bing-0.json)
- 원문: [N4-webiq_optimized-0](https://www.cartvnews.com/news/articleView.html?idxno=702292) · [조회기록](../results/full_comparison_v9_20260908/sources/N4-webiq_optimized-0.json)
- 원문: [N2-bing-0](https://biz.newdaily.co.kr/site/data/html/2026/09/03/2026090300171.html) · [조회기록](../results/full_comparison_v9_20260908/sources/N2-bing-0.json)

### N5 · news

2026년 추석에 고속도로 통행료 면제하는지 기사에서 확인해줘. 적용 날짜도 알려줘.

**공통 판정 조건:** 2026 추석 / 공식 발표 보도 / 면제일·차종 또는 미정 상태

**독립 확인:** 국제신문2026-09-01:대통령주재국무회의추석민생안정대책을보도하며9/24~27고속도로통행료면제를명시.공감신문9/7도확인.23일/28일경계진출입세부규정은별도확인필요.

#### Bing — correct

기사 기준으로 **2026년 추석 고속도로 통행료는 면제**되며, 적용 기간은 **9월 24일(목)부터 9월 27일(일)까지 4일간**입니다. 추석 당일인 9월 25일뿐 아니라 전날·다음 날과 일요일 귀경일도 포함되고, **9월 23일과 9월 28일은 현재 면제 대상이 아닙니다**. 【6:2†source】【6:4†source】

- 판정: 9/1국무회의 민생대책 보도를 담은 국제신문에서9/24~27면제 확인.23일·28일 경계진출입 세부규정은 아직 별도이므로 부가단정 주의.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 23일/28일 경계진출입 면제 예외까지 배제한 것으로 일반화하면 안 됨
- 입력 텍스트: 5,775; 첫 TEXT: 6.11초; 완료: 9.80초.
- 원문: [N5-webiq_base-2](https://www.kookje.co.kr/news2011/asp/newsbody.asp?key=20260901.99099000013) · [조회기록](../results/full_comparison_v9_20260908/sources/N5-webiq_base-2.json)
- 원문: [N5-webiq_base-0](https://www.gokorea.kr/news/articleView.html?idxno=877328) · [조회기록](../results/full_comparison_v9_20260908/sources/N5-webiq_base-0.json)
- 원문: [N5-bing-0](https://itsdwayne.co.kr/2026-chuseok-highway-toll-free-period/) · [조회기록](../results/full_comparison_v9_20260908/sources/N5-bing-0.json)

#### Web IQ MCP 기본 — correct

네. 기사에 따르면 **2026년 추석 연휴 전국 고속도로 통행료가 면제**됩니다. 적용 기간은 **2026년 9월 24일(목)부터 9월 27일(일)까지 4일간**입니다.

- 판정: 국제신문9/1 정부발표 보도와공감신문9/7원문에9/24~27전국고속도로면제 일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 9,942; 첫 TEXT: 4.02초; 완료: 7.39초.
- 원문: [N5-webiq_base-2](https://www.kookje.co.kr/news2011/asp/newsbody.asp?key=20260901.99099000013) · [조회기록](../results/full_comparison_v9_20260908/sources/N5-webiq_base-2.json)
- 원문: [N5-webiq_base-0](https://www.gokorea.kr/news/articleView.html?idxno=877328) · [조회기록](../results/full_comparison_v9_20260908/sources/N5-webiq_base-0.json)

#### Web IQ MCP 최적화 — correct

네. 기사 확인 결과, **2026년 추석 연휴인 9월 24일(목)부터 9월 27일(일)까지** 전국 고속도로 통행료가 면제됩니다. 연휴 기간 고속도로를 이용하는 **모든 차량**에 적용된다고 보도됐습니다.  
(출처: 국제신문 2026년 9월 1일, 공감신문 2026년 9월 7일)

- 판정: 국제신문9/1·공감신문9/7원문에9/24~27면제일정 확인.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 7,487; 첫 TEXT: 3.96초; 완료: 9.43초.
- 원문: [N5-webiq_base-2](https://www.kookje.co.kr/news2011/asp/newsbody.asp?key=20260901.99099000013) · [조회기록](../results/full_comparison_v9_20260908/sources/N5-webiq_base-2.json)
- 원문: [N5-webiq_base-0](https://www.gokorea.kr/news/articleView.html?idxno=877328) · [조회기록](../results/full_comparison_v9_20260908/sources/N5-webiq_base-0.json)
- 원문: [N5-webiq_optimized-0](https://www.gokorea.kr/news/articleView.html?idxno=877328) · [조회기록](../results/full_comparison_v9_20260908/sources/N5-webiq_optimized-0.json)
- 원문: [N5-webiq_optimized-2](https://www.kookje.co.kr/news2011/asp/newsbody.asp?key=20260901.99099000013) · [조회기록](../results/full_comparison_v9_20260908/sources/N5-webiq_optimized-2.json)

### V1 · videos

아이오닉5 급속충전 방법을 설명하는 현대자동차 공식 영상 찾아줘.

**공통 판정 조건:** 현대자동차 제작 / 아이오닉5 급속충전 / 실제 보기 URL / 휴대용 충전 대체 금지

**독립 확인:** https://www.youtube.com/watch?v=p9rftWFaopM 실제 현대자동차(hyundai korea) '취급설명서 | 아이오닉 5 - 완속, 급속 충전',154초. 메타데이터로 확인; 특정 급속챕터 시각은 재생 확인 안 함.

#### Bing — no_factual_answer

현대자동차 공식 채널에서 아이오닉 5 급속충전 방법 영상은 확인하지 못했습니다. 현대자동차 공식 유튜브에서 **‘아이오닉 5 급속 충전’** 또는 **‘전기차 충전 방법’**으로 검색해 주세요.

- 판정: 공식영상을 못 찾았다고 답하고직접링크를 제공하지 않음. 실제공식영상 존재를 부정한 것으로 확대하지 않음.
- 기술실패: False; 전달결함: 직접 영상 URL 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 1,642; 첫 TEXT: 4.76초; 완료: 7.52초.
- 원문: [V1-reference-watch](https://www.youtube.com/watch?v=p9rftWFaopM) · [조회기록](../results/full_comparison_v9_20260908/sources/V1-reference-watch.json)
- 원문: [V1-official-oembed](https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Dp9rftWFaopM&format=json) · [조회기록](../results/full_comparison_v9_20260908/sources/V1-official-oembed.json)

#### Web IQ MCP 기본 — correct

현대자동차 공식 영상 **「취급설명서 | 아이오닉 5 - 완속, 급속 충전」**을 찾았습니다. 급속 충전 방법은 영상 **2분 11초부터** 설명하며, 길이는 **2분 34초**, 제작자는 **현대자동차**입니다.

[영상 바로 보기](https://www.youtube.com/watch?v=p9rftWFaopM)

- 판정: 원본메타데이터의 현대자동차·아이오닉5완속급속충전·154초·직접URL 모두일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 급속시작2:11 챕터는 재생으로 독립확인하지 않음
- 입력 텍스트: 11,529; 첫 TEXT: 3.98초; 완료: 8.70초.
- 원문: [V1-reference-watch](https://www.youtube.com/watch?v=p9rftWFaopM) · [조회기록](../results/full_comparison_v9_20260908/sources/V1-reference-watch.json)
- 원문: [V1-official-oembed](https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Dp9rftWFaopM&format=json) · [조회기록](../results/full_comparison_v9_20260908/sources/V1-official-oembed.json)

#### Web IQ MCP 최적화 — correct

현대자동차 공식 영상입니다.

- **취급설명서 | 아이오닉 5 - 완속, 급속 충전** — 현대자동차, **2분 34초**  
  [영상 바로 보기](https://www.youtube.com/watch?v=p9rftWFaopM)  
  급속 충전은 완속 충전과 같은 절차로 진행하며, 급속 충전소의 케이블을 사용하는 방법을 설명합니다.

- 판정: 원본메타데이터의 현대자동차·아이오닉5완속급속충전·154초·직접URL 모두일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 완속과 동일절차라는 부가설명은 영상재생으로 확인하지 않음
- 입력 텍스트: 8,846; 첫 TEXT: 5.87초; 완료: 11.57초.
- 원문: [V1-reference-watch](https://www.youtube.com/watch?v=p9rftWFaopM) · [조회기록](../results/full_comparison_v9_20260908/sources/V1-reference-watch.json)
- 원문: [V1-official-oembed](https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Dp9rftWFaopM&format=json) · [조회기록](../results/full_comparison_v9_20260908/sources/V1-official-oembed.json)

### V2 · videos

기아 EV6 급속충전 방법을 설명하는 기아 공식 영상 찾아줘.

**공통 판정 조건:** 기아 공식 제작 / EV6 급속충전 / 실제 보기 URL

**독립 확인:** 공식 EV6 사용가이드8iP-ooQPDUI는존재하지만 급속절차위치재생미확인.기본답변i3bqInj3jw0는159초기아공식충전방법이나설명#니로EV.최적화대안_DRQk_DpDss는395초기아멤버스충전서비스소개로EV6절차아님.

#### Bing — no_factual_answer

기아 공식 채널에서 **EV6 급속충전 방법을 설명하는 영상을 확인하지 못했습니다.** 정확한 공식 영상 링크를 임의로 안내하지 않기 위해, 기아 공식 유튜브에서 `EV6 급속충전`으로 검색해 주세요.

- 판정: 기아공식 EV6급속충전영상 직접링크 미제시. 검색을 권할 뿐 requested 영상 없음.
- 기술실패: False; 전달결함: 직접 영상 URL 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 1,642; 첫 TEXT: 5.99초; 완료: 8.84초.
- 원문: [V2-official-watch](https://www.youtube.com/watch?v=8iP-ooQPDUI) · [조회기록](../results/full_comparison_v9_20260908/sources/V2-official-watch.json)
- 원문: [V2-charging-watch](https://www.youtube.com/watch?v=i3bqInj3jw0) · [조회기록](../results/full_comparison_v9_20260908/sources/V2-charging-watch.json)
- 원문: [V2-service-watch](https://www.youtube.com/watch?v=_DRQk_DpDss) · [조회기록](../results/full_comparison_v9_20260908/sources/V2-service-watch.json)

#### Web IQ MCP 기본 — incorrect

기아 공식 영상으로는 **「전기차 충전방법 | 내차사용설명서」**가 있습니다. EV 급속충전 연결 방법과 충전 과정을 설명하며, 길이는 **2분 39초**입니다.  
[영상 바로 보기](https://www.youtube.com/watch?v=i3bqInj3jw0) — 제작자: **기아(Kia Korea)**

- 판정: 제시영상은실제기아공식159초이나원본설명은 #니로EV. 명시차종EV6요청을 다른차종으로 대체했다.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 8,489; 첫 TEXT: 3.80초; 완료: 8.51초.
- 원문: [V2-official-watch](https://www.youtube.com/watch?v=8iP-ooQPDUI) · [조회기록](../results/full_comparison_v9_20260908/sources/V2-official-watch.json)
- 원문: [V2-charging-watch](https://www.youtube.com/watch?v=i3bqInj3jw0) · [조회기록](../results/full_comparison_v9_20260908/sources/V2-charging-watch.json)
- 원문: [V2-service-watch](https://www.youtube.com/watch?v=_DRQk_DpDss) · [조회기록](../results/full_comparison_v9_20260908/sources/V2-service-watch.json)
- 원문: [V2-webiq_base-1-oembed](https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Di3bqInj3jw0&format=json) · [조회기록](../results/full_comparison_v9_20260908/sources/V2-webiq_base-1-oembed.json)

#### Web IQ MCP 최적화 — no_factual_answer

기아 공식 채널 영상으로는 **‘Kia Members EV Charging Service Usage Guide’**가 있습니다. EV6 전용 급속충전 절차보다는 기아 멤버스 충전 서비스 이용법을 설명하며, 제작자 **기아(Kia Korea)**, 길이 **6분 36초**입니다: [영상 보기](https://www.youtube.com/watch?v=_DRQk_DpDss)

검색 결과에서 EV6 충전 방법을 다룬 9분 36초 영상도 확인됐지만, 제작자가 기아 공식 채널은 아니었습니다.

- 판정: 공식충전서비스 안내라는 대안만제시하고 EV6급속절차영상이아님을 인정.요청한방법영상은미제공.
- 기술실패: False; 전달결함: EV6 급속충전 절차 영상 미제공
- 부가오류/정밀도: 기재396초 vs원본395초:1초 메타데이터차이
- 입력 텍스트: 7,333; 첫 TEXT: 4.50초; 완료: 11.10초.
- 원문: [V2-official-watch](https://www.youtube.com/watch?v=8iP-ooQPDUI) · [조회기록](../results/full_comparison_v9_20260908/sources/V2-official-watch.json)
- 원문: [V2-charging-watch](https://www.youtube.com/watch?v=i3bqInj3jw0) · [조회기록](../results/full_comparison_v9_20260908/sources/V2-charging-watch.json)
- 원문: [V2-service-watch](https://www.youtube.com/watch?v=_DRQk_DpDss) · [조회기록](../results/full_comparison_v9_20260908/sources/V2-service-watch.json)

### V3 · videos

타이어뱅크에서 만든 타이어 공기압 셀프 주입 방법 영상 찾아줘.

**공통 판정 조건:** 타이어뱅크 제작 / 공기 주입 주제 / 직접 보기 링크

**독립 확인:** https://www.youtube.com/watch?v=tmpb0k1XUXU '타이어 공기압 셀프 주입기 사용법! 완전 easy하다구' 제작자 타이어뱅크 확인. 다른 타이어 유튜버 영상은 타이어뱅크 공식 아님.

#### Bing — correct

타이어뱅크 공식 유튜브 영상입니다.

- **「타이어 공기압 셀프 주입기 사용법! 완전 easy하다구✨」**  
  제작자: **타이어뱅크** · 길이: **검색 결과에서 확인되지 않음**  
  [유튜브에서 영상 보기]【6:0†source】

영상에서는 차량의 적정 공기압 확인부터 주입기 설정, 밸브 캡 제거, 호스 연결 순서까지 설명합니다.

- 판정: 인용에 실제 타이어뱅크 공식셀프주입영상 URL이 포함되어 제작자·주제 확인. 길이 미확인을 정직하게 명시.
- 기술실패: False; 전달결함: 영상길이 미제공, 직접 URL은 인용에만 포함; 영상보기 문구는 완전한 Markdown 링크가 아님
- 부가오류/정밀도: 주입 상세단계는 영상재생으로 별도확인하지 않음
- 입력 텍스트: 4,403; 첫 TEXT: 6.01초; 완료: 12.30초.
- 원문: [V3-official-watch](https://www.youtube.com/watch?v=tmpb0k1XUXU) · [조회기록](../results/full_comparison_v9_20260908/sources/V3-official-watch.json)
- 원문: [V3-official-oembed](https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Dtmpb0k1XUXU&format=json) · [조회기록](../results/full_comparison_v9_20260908/sources/V3-official-oembed.json)
- 원문: [V3-bing-0](https://www.youtube.com/watch?v=tmpb0k1XUXU) · [조회기록](../results/full_comparison_v9_20260908/sources/V3-bing-0.json)
- 원문: [V3-bing-0-oembed](https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Dtmpb0k1XUXU&format=json) · [조회기록](../results/full_comparison_v9_20260908/sources/V3-bing-0-oembed.json)

#### Web IQ MCP 기본 — correct

타이어뱅크 공식 영상입니다.

- **타이어 공기압 셀프 주입기 사용법! 완전 easy하다구** — 타이어뱅크, **1분 18초**  
  [영상 보기](https://www.youtube.com/watch?v=tmpb0k1XUXU)

차량의 적정 공기압 확인부터 주입기 설정, 호스 연결과 마무리까지 설명합니다.

- 판정: 타이어뱅크공식·셀프주입주제·실제직접URL 확인.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 길이78초 vs원본77초:1초 메타데이터차이; 핵심제작자·주제는일치, 부가단계설명은 영상재생으로 별도확인하지 않음
- 입력 텍스트: 9,363; 첫 TEXT: 3.77초; 완료: 9.96초.
- 원문: [V3-official-watch](https://www.youtube.com/watch?v=tmpb0k1XUXU) · [조회기록](../results/full_comparison_v9_20260908/sources/V3-official-watch.json)
- 원문: [V3-official-oembed](https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Dtmpb0k1XUXU&format=json) · [조회기록](../results/full_comparison_v9_20260908/sources/V3-official-oembed.json)

#### Web IQ MCP 최적화 — correct

타이어뱅크가 제작한 영상입니다.

- **타이어 공기압 셀프 주입기 사용법! 완전 easy하다구** — 타이어뱅크 · **1분 18초**  
  [영상 보기](https://www.youtube.com/watch?v=tmpb0k1XUXU)

차량의 적정 공기압 확인부터 주입기 설정, 호스 연결까지 단계별로 안내합니다.

- 판정: 타이어뱅크공식·셀프주입주제·실제직접URL 확인.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 길이78초 vs원본77초:1초 메타데이터차이; 핵심제작자·주제는일치, 부가단계설명은 영상재생으로 별도확인하지 않음
- 입력 텍스트: 8,000; 첫 TEXT: 3.60초; 완료: 9.78초.
- 원문: [V3-official-watch](https://www.youtube.com/watch?v=tmpb0k1XUXU) · [조회기록](../results/full_comparison_v9_20260908/sources/V3-official-watch.json)
- 원문: [V3-official-oembed](https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Dtmpb0k1XUXU&format=json) · [조회기록](../results/full_comparison_v9_20260908/sources/V3-official-oembed.json)

### V4 · videos

현대차 블루링크 앱에 차 등록하는 공식 안내 영상 찾아줘.

**공통 판정 조건:** 공식 제작자 / 앱 차량 등록 주제 / 다른 기능 영상과 구분

**독립 확인:** 39lpQhZjQus는74초현대공식마이현대소개영상이며설명에차량등록언급.절차시연까지메타데이터로입증안됨.공식등록문서는별도존재.카베이·오토브라더스·에이원오토는현대공식제작영상아님.

#### Bing — unverifiable

현대자동차 공식 채널의 **「마이현대 | 하나로 통합된 현대자동차 공식 앱」** 영상에서 앱 설치부터 차량 등록·관리·제어까지 안내합니다. 영상 제작자는 **현대자동차 공식 채널**이며, 검색 결과에서는 영상 길이를 확인하지 못했습니다. 【6:2†source】

[공식 영상 바로 보기](https://www.youtube.com/results?search_query=%EB%A7%88%EC%9D%B4%ED%98%84%EB%8C%80+%ED%95%98%EB%82%98%EB%A1%9C+%ED%86%B5%ED%95%A9%EB%90%9C+%ED%98%84%EB%8C%80%EC%9E%90%EB%8F%99%EC%B0%A8+%EA%B3%B5%EC%8B%9D+%EC%95%B1)  
참고로 현대차 공식 안내에 따르면 **마이현대 앱의 ‘마이’ 탭에서 차량 등록**을 시작하면 됩니다. 【6:0†source】

- 판정: 74초 공식 마이현대 소개영상 존재·차량등록 언급은 확인. 앱설치부터 등록절차를 설명하는방법영상인지 메타데이터만으로 확인되지 않음.
- 기술실패: False; 전달결함: 명시공식영상링크는 watch가 아닌 검색결과 URL, 영상길이 미제공
- 부가오류/정밀도: 없음
- 입력 텍스트: 6,376; 첫 TEXT: 10.35초; 완료: 25.10초.
- 원문: [V4-official-watch](https://www.youtube.com/watch?v=39lpQhZjQus) · [조회기록](../results/full_comparison_v9_20260908/sources/V4-official-watch.json)
- 원문: [V4-hyundai-registration](https://www.hyundai.com/kr/ko/digital-customer-support/app/myhyundai/bluelink-information) · [조회기록](../results/full_comparison_v9_20260908/sources/V4-hyundai-registration.json)

#### Web IQ MCP 기본 — no_factual_answer

현대자동차 **공식 안내 페이지**에서 마이현대 앱 차량 등록과 블루링크 가입 절차를 확인할 수 있습니다. 공식 영상은 검색 결과에서 확인되지 않아, 안내 페이지와 함께 등록 과정을 다루는 참고 영상 1개를 드립니다.

- [현대자동차 공식 차량 등록·블루링크 가입 안내](https://www.hyundai.com/kr/ko/digital-customer-support/app/myhyundai/bluelink-information) — 현대자동차
- [현대 블루링크 가입·차량 등록 방법](https://www.youtube.com/watch?v=KP4iYlEEMg8) — 오토브라더스 김실장, 11분 51초(참고 영상)

- 판정: 공식영상 미확인임을 명시하고 공식문서 및 비공식참고영상만 제공. 공식앱차량등록 영상요청은 미해결.
- 기술실패: False; 전달결함: 공식 차량등록 영상 미제공
- 부가오류/정밀도: 없음
- 입력 텍스트: 23,175; 첫 TEXT: 6.22초; 완료: 15.16초.
- 원문: [V4-official-watch](https://www.youtube.com/watch?v=39lpQhZjQus) · [조회기록](../results/full_comparison_v9_20260908/sources/V4-official-watch.json)
- 원문: [V4-hyundai-registration](https://www.hyundai.com/kr/ko/digital-customer-support/app/myhyundai/bluelink-information) · [조회기록](../results/full_comparison_v9_20260908/sources/V4-hyundai-registration.json)
- 원문: [V4-webiq_base-1](https://www.youtube.com/watch?v=KP4iYlEEMg8) · [조회기록](../results/full_comparison_v9_20260908/sources/V4-webiq_base-1.json)
- 원문: [V4-webiq_base-1-oembed](https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DKP4iYlEEMg8&format=json) · [조회기록](../results/full_comparison_v9_20260908/sources/V4-webiq_base-1-oembed.json)

#### Web IQ MCP 최적화 — no_factual_answer

현대자동차 **공식 채널 영상은 검색 결과에서 확인하지 못했습니다.** 대신 차량 등록·가입 과정을 다룬 영상 두 개를 안내드립니다.

- [현대 블루링크 처음 쓰시면 이 영상 꼭 보세요](https://www.youtube.com/watch?v=x0Gp32X2c6Y) — 제작자: 카베이 CARBAY, 4분 21초  
- [현대 블루링크 가입방법·사용법](https://www.youtube.com/watch?v=xeyEyVL-nYQ) — 제작자: 에이원오토 서백로, 3분 35초

- 판정: 현대공식영상 미확인임을 명시하고 CARBAY·에이원오토 비공식대안을 제공. 요청제작자의영상은 미제공.
- 기술실패: False; 전달결함: 공식 차량등록 영상 미제공
- 부가오류/정밀도: 없음
- 입력 텍스트: 8,945; 첫 TEXT: 7.10초; 완료: 13.51초.
- 원문: [V4-official-watch](https://www.youtube.com/watch?v=39lpQhZjQus) · [조회기록](../results/full_comparison_v9_20260908/sources/V4-official-watch.json)
- 원문: [V4-hyundai-registration](https://www.hyundai.com/kr/ko/digital-customer-support/app/myhyundai/bluelink-information) · [조회기록](../results/full_comparison_v9_20260908/sources/V4-hyundai-registration.json)
- 원문: [V4-webiq_optimized-0](https://www.youtube.com/watch?v=x0Gp32X2c6Y) · [조회기록](../results/full_comparison_v9_20260908/sources/V4-webiq_optimized-0.json)
- 원문: [V4-webiq_optimized-1](https://www.youtube.com/watch?v=xeyEyVL-nYQ) · [조회기록](../results/full_comparison_v9_20260908/sources/V4-webiq_optimized-1.json)

### V5 · videos

현대차에서 안드로이드 오토를 유선으로 연결하는 공식 영상 찾아줘.

**공통 판정 조건:** 현대 공식 제작 / 유선 Android Auto / 차량·인포테인먼트 차이 / 영상 실재

**독립 확인:** takvJ8H636M는현대공식HyundaiUSA232초이며설명에유선·무선연결및적용차종명시.최적화첫PzG_CJnn1G8도HyundaiUSA159초유무선ccNC공식영상.두번째PeHUcOUCpb8은ProgrammingKnowledge2비공식.

#### Bing — no_factual_answer

현대자동차 공식 채널의 **유선 안드로이드 오토 연결 영상은 확인하지 못했습니다.** 검색된 영상은 오토캐스트 제작 영상이라 현대차 공식 자료가 아닙니다【9:0†source】. 대신 현대차 공식 매뉴얼에는 USB 케이블을 차량 USB 단자에 연결한 뒤 **홈 화면 → Android Auto**를 선택하는 절차가 안내되어 있습니다【9:4†source】.

- 판정: 공식영상 미확인임을 명시하고 USB매뉴얼만제공. 실제공식영상의 부재를 단정하지는 않음.
- 기술실패: False; 전달결함: 공식 영상 직접 URL 미제공
- 부가오류/정밀도: 없음
- 입력 텍스트: 4,422; 첫 TEXT: 11.13초; 완료: 15.63초.
- 원문: [V5-hyundaiusa-watch](https://www.youtube.com/watch?v=takvJ8H636M) · [조회기록](../results/full_comparison_v9_20260908/sources/V5-hyundaiusa-watch.json)
- 원문: [V5-webiq_optimized-3](https://www.youtube.com/watch?v=PzG_CJnn1G8) · [조회기록](../results/full_comparison_v9_20260908/sources/V5-webiq_optimized-3.json)
- 원문: [V5-webiq_optimized-2](https://www.youtube.com/watch?v=PeHUcOUCpb8) · [조회기록](../results/full_comparison_v9_20260908/sources/V5-webiq_optimized-2.json)
- 원문: [V5-bing-1](https://ownersmanual.hyundai.com/ivi/ccNC/AVNT/KOR/Korean/Phoneprojection_wiredandroidauto.html) · [조회기록](../results/full_comparison_v9_20260908/sources/V5-bing-1.json)

#### Web IQ MCP 기본 — correct

현대 공식 채널 **HyundaiUSA**의 영상입니다. 유선 연결 방법은 **13초~1분 4초** 구간에서 확인할 수 있어요.

- [Android Auto™ | Hyundai](https://www.youtube.com/watch?v=takvJ8H636M) — 제작자: HyundaiUSA · **3분 52초**

- 판정: 현대공식HyundaiUSA·232초·유무선Android Auto안내가 원본설명에 명시. 유선영상을 찾는핵심조건과 직접URL 충족.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 13초~1:04 챕터시각은 영상재생으로 독립확인하지 않음
- 입력 텍스트: 7,625; 첫 TEXT: 4.22초; 완료: 8.28초.
- 원문: [V5-hyundaiusa-watch](https://www.youtube.com/watch?v=takvJ8H636M) · [조회기록](../results/full_comparison_v9_20260908/sources/V5-hyundaiusa-watch.json)
- 원문: [V5-webiq_optimized-3](https://www.youtube.com/watch?v=PzG_CJnn1G8) · [조회기록](../results/full_comparison_v9_20260908/sources/V5-webiq_optimized-3.json)
- 원문: [V5-webiq_optimized-2](https://www.youtube.com/watch?v=PeHUcOUCpb8) · [조회기록](../results/full_comparison_v9_20260908/sources/V5-webiq_optimized-2.json)
- 원문: [V5-hyundaiusa-oembed](https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DtakvJ8H636M&format=json) · [조회기록](../results/full_comparison_v9_20260908/sources/V5-hyundaiusa-oembed.json)

#### Web IQ MCP 최적화 — incorrect

현대 공식 채널 **HyundaiUSA**의 유선 안드로이드 오토 연결 영상입니다.

- [Android Auto Setup for ccNC Touchscreens | Hyundai](https://www.youtube.com/watch?v=PzG_CJnn1G8) — HyundaiUSA, 약 3분
- [How to Connect Your Hyundai to Android Auto](https://www.youtube.com/watch?v=PeHUcOUCpb8) — 현대차 터치스크린 모델용, 길이는 검색 결과에서 확인되지 않았습니다.

차량·연식에 따라 지원 방식이 다를 수 있으니, 영상의 적용 차종도 함께 확인해 주세요.

- 판정: 첫 ccNC영상은 실제HyundaiUSA공식이며유선포함으로 적합. 그러나 공식영상목록으로함께제시한두번째PeHUcOUCpb8의제작자는ProgrammingKnowledge2로현대공식아님. 유효영상1개와 제작자조건회귀를 함께기록.
- 기술실패: False; 전달결함: 두번째영상 제작자미표기
- 부가오류/정밀도: 첫영상159초를약3분으로반올림; 핵심오류로계산하지않음
- 입력 텍스트: 7,044; 첫 TEXT: 6.81초; 완료: 13.79초.
- 원문: [V5-hyundaiusa-watch](https://www.youtube.com/watch?v=takvJ8H636M) · [조회기록](../results/full_comparison_v9_20260908/sources/V5-hyundaiusa-watch.json)
- 원문: [V5-webiq_optimized-3](https://www.youtube.com/watch?v=PzG_CJnn1G8) · [조회기록](../results/full_comparison_v9_20260908/sources/V5-webiq_optimized-3.json)
- 원문: [V5-webiq_optimized-2](https://www.youtube.com/watch?v=PeHUcOUCpb8) · [조회기록](../results/full_comparison_v9_20260908/sources/V5-webiq_optimized-2.json)
- 원문: [V5-webiq_optimized-3-oembed](https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DPzG_CJnn1G8&format=json) · [조회기록](../results/full_comparison_v9_20260908/sources/V5-webiq_optimized-3-oembed.json)
- 원문: [V5-webiq_optimized-2-oembed](https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DPeHUcOUCpb8&format=json) · [조회기록](../results/full_comparison_v9_20260908/sources/V5-webiq_optimized-2-oembed.json)

### B1 · browse

서울식물원 공식 안내 보고 9월 12일 토요일 온실 입장 마감 시간을 알려줘.

**공통 판정 조건:** 계절·방문일 / 입장과 폐장 시간 / 공식 최신 안내

**독립 확인:** 서울식물원 공식 주제원 3~10월09:30~18:00, 입장마감17:00. 9월12일 토요일은 해당; 폐장과 입장마감 구분.

#### Bing — correct

서울식물원 공식 안내 기준, **9월 12일 토요일 온실 입장 마감은 오후 5시(17:00)**입니다. 온실 운영은 오후 6시까지이며, 9월은 3~10월 운영 기준에 해당합니다. 【6:0†source】

- 판정: 공식주제원3~10월입장마감17:00·폐장18:00에일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 6,066; 첫 TEXT: 7.80초; 완료: 10.94초.
- 원문: [B1-botanic](https://botanicpark.seoul.go.kr/front/introduce/useInfo.do) · [조회기록](../results/full_comparison_v9_20260908/sources/B1-botanic.json)

#### Web IQ MCP 기본 — incorrect

서울식물원 공식 안내에 따르면, **2026년 9월 12일 토요일 온실 입장 마감은 오후 6시**입니다. 다만 **매표는 오후 5시에 마감**되고, 온실 운영은 오후 6시까지입니다.

- 판정: 입장마감을18시라고단정하고17시는매표만이라고구분했지만공식은17시입장마감이다.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 26,114; 첫 TEXT: 8.34초; 완료: 11.79초.
- 원문: [B1-botanic](https://botanicpark.seoul.go.kr/front/introduce/useInfo.do) · [조회기록](../results/full_comparison_v9_20260908/sources/B1-botanic.json)

#### Web IQ MCP 최적화 — correct

서울식물원 공식 안내에 따르면 **2026년 9월 12일 토요일 온실 입장(매표) 마감은 오후 5시**입니다. 온실은 오후 6시까지 운영합니다.

- 판정: 공식주제원3~10월입장마감17:00·폐장18:00에일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 15,919; 첫 TEXT: 7.73초; 완료: 10.63초.
- 원문: [B1-botanic](https://botanicpark.seoul.go.kr/front/introduce/useInfo.do) · [조회기록](../results/full_comparison_v9_20260908/sources/B1-botanic.json)

### B2 · browse

국립과천과학관 공식 안내 보고 9월 12일 경차로 두 시간 주차하면 얼마인지 알려줘.

**공통 판정 조건:** 경차·2시간 / 현재 적용 요금 / 신구 공지 충돌·시행 여부

**독립 확인:** 과학관협회2026-04-01 공지의 기존·변경안 모두 할인차량 기본2시간1,500원. 4월6일 예정 시행·할인차량 일최대5,000원 변경안과 모바일 구형일일정액5,000원/경차50%=2,500원이 충돌. 정부현행 확인 실패 시 불확실성 명시.

#### Bing — unverifiable

국립과천과학관 공식 안내상 주차요금은 **일일 기준**이며, 일반차량 5,000원의 **50%인 2,500원**입니다. 따라서 **9월 12일 경차로 두 시간 주차해도 2,500원**이며, 시간 단위 요금은 별도로 안내되어 있지 않습니다. 【6:0†source】

- 판정: 모바일공식구형표는경차하루2500원이나2026년4월정부공지의기존·변경안모두2시간1500원으로충돌.9/12실제시행현행표를확정하지못해오답으로단정하지않음.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 시간단위요금이별도안내되지않았다는표현은4월공지의시간표존재와충돌
- 입력 텍스트: 3,137; 첫 TEXT: 4.70초; 완료: 8.01초.
- 원문: [B2-notice](https://www.scicenter.or.kr/bbs/board.php?bo_table=member_news&wr_id=14575) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-notice.json)
- 원문: [B2-old](https://smart.sciencecenter.go.kr/gcsci/info/info_parking.php) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-old.json)
- 원문: [B2-government](https://www.sciencecenter.go.kr/scipia/) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-government.json)
- 원문: [B2-webiq_base-2](https://smart.science.go.kr/board/view.action?boardId=BBS_0000002&menuCd=DOM_000000101004001000&dataSid=7720) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-webiq_base-2.json)
- 원문: [B2-webiq_base-1](https://www.zento.kr/blog/parking/national-science-museum-gwacheon-parking) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-webiq_base-1.json)

#### Web IQ MCP 기본 — unverifiable

국립과천과학관 공식 안내 기준으로 **2026년 9월 12일 경차를 2시간 주차하면 1,500원**입니다. 이는 2026년 4월 6일부터 적용된 할인차량의 **2시간 이내 기본요금**이며, 2시간을 초과하면 30분당 250원이 추가됩니다.

- 판정: 2026년4월정부공지의할인차량2시간1500원과일치하나그원문은4/6시행예정·변경안이라고명시.구형공식모바일/7월재인용과충돌하여이미시행확정이라는단정은독립검증불충분.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 4/6실제시행확정 및초과250원 현행적용은미확인
- 입력 텍스트: 14,883; 첫 TEXT: 6.08초; 완료: 9.28초.
- 원문: [B2-notice](https://www.scicenter.or.kr/bbs/board.php?bo_table=member_news&wr_id=14575) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-notice.json)
- 원문: [B2-old](https://smart.sciencecenter.go.kr/gcsci/info/info_parking.php) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-old.json)
- 원문: [B2-government](https://www.sciencecenter.go.kr/scipia/) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-government.json)
- 원문: [B2-webiq_base-2](https://smart.science.go.kr/board/view.action?boardId=BBS_0000002&menuCd=DOM_000000101004001000&dataSid=7720) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-webiq_base-2.json)
- 원문: [B2-webiq_base-1](https://www.zento.kr/blog/parking/national-science-museum-gwacheon-parking) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-webiq_base-1.json)

#### Web IQ MCP 최적화 — no_factual_answer

(답변 없음)

- 판정: 기술실패로최종사실답변없음.시도는분모유지.
- 기술실패: True; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 0; 첫 TEXT: 미보고초; 완료: 8.94초.
- 원문: [B2-notice](https://www.scicenter.or.kr/bbs/board.php?bo_table=member_news&wr_id=14575) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-notice.json)
- 원문: [B2-old](https://smart.sciencecenter.go.kr/gcsci/info/info_parking.php) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-old.json)
- 원문: [B2-government](https://www.sciencecenter.go.kr/scipia/) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-government.json)
- 원문: [B2-webiq_optimized-0](https://smart.science.go.kr/board/view.action?boardId=BBS_0000002&menuCd=DOM_000000101004001000&dataSid=7720) · [조회기록](../results/full_comparison_v9_20260908/sources/B2-webiq_optimized-0.json)

### B3 · browse

국립중앙박물관 공식 안내 보고 9월 12일 승용차로 세 시간 주차하면 얼마인지 알려줘.

**공통 판정 조건:** 승용차·3시간 계산 / 초과요금 단위 / 공식 현행 표

**독립 확인:** 국립중앙박물관 공식 현행표 승용차 기본60분1,000원+초과10분당500원. 3시간=1,000+12×500=7,000원. 공연4,000원·경차감면과 구분.

#### Bing — correct

국립중앙박물관 공식 안내 기준, **2026년 9월 12일 승용차로 3시간 주차하면 7,000원**입니다. 기본 60분 1,000원에 초과 120분(10분당 500원)을 더한 금액이며, 경차·친환경차 등 할인·면제 대상은 제외한 일반 요금입니다. 【6:0†source】

- 판정: 공식현행승용차60분1000원+초과120분/10×500원=7000원계산일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 6,592; 첫 TEXT: 7.03초; 완료: 10.50초.
- 원문: [B3-museum](https://www.museum.go.kr/MUSEUM/contents/M0106040000.do?menuId=parking-map) · [조회기록](../results/full_comparison_v9_20260908/sources/B3-museum.json)

#### Web IQ MCP 기본 — no_factual_answer

(답변 없음)

- 판정: 기술실패로최종사실답변없음.시도는분모유지.
- 기술실패: True; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 0; 첫 TEXT: 미보고초; 완료: 6.02초.
- 원문: [B3-museum](https://www.museum.go.kr/MUSEUM/contents/M0106040000.do?menuId=parking-map) · [조회기록](../results/full_comparison_v9_20260908/sources/B3-museum.json)
- 원문: [B3-webiq_base-0](https://www.museum.go.kr/MUSEUM/contents/M0106040000.do?menuId=parking-map) · [조회기록](../results/full_comparison_v9_20260908/sources/B3-webiq_base-0.json)

#### Web IQ MCP 최적화 — correct

국립중앙박물관 공식 안내 기준, **2026년 9월 12일 승용차(15인승 이하)로 3시간 주차하면 7,000원**입니다. 기본 60분 1,000원에 초과 120분(10분당 500원)을 더한 금액이며, 경차·친환경차 등 할인 대상이면 달라질 수 있습니다.

- 판정: 공식현행승용차60분1000원+초과120분/10×500원=7000원계산일치.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 9,148; 첫 TEXT: 6.38초; 완료: 9.79초.
- 원문: [B3-museum](https://www.museum.go.kr/MUSEUM/contents/M0106040000.do?menuId=parking-map) · [조회기록](../results/full_comparison_v9_20260908/sources/B3-museum.json)

### B4 · browse

서울랜드 공식 안내 보고 당일 이용권이 있으면 정문 주차장이 무료인지 알려줘.

**공통 판정 조건:** 정문 주차장 특정 / 이용권·정산 조건 / 다른 주차장 정책과 구분

**독립 확인:** 서울랜드 공식 동문주차장은 당일이용 후 사전정산 확인시무료. 질문은 정문주차장으로, 동문무료를 정문무료로 일반화하지 않음. 정문·서울대공원 주차장 관계 추가 대조.

#### Bing — correct

아니요. **서울랜드 정문 주차장은 당일 이용권이 있어도 무료가 아니라 유료**로 안내되어 있습니다. 당일 서울랜드 이용권 또는 영수증으로 1일 1회 무료주차가 적용되는 곳은 후문·동문·쌈이맛 주차장으로 확인됩니다. 【9:1†source】

- 판정: 핵심정문방향대공원주차장유료/동문이용객무료구분은공식FAQ와대공원요금표에부합.추가후문·쌈이맛명칭의현재운영은독립확인안됨.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 후문·쌈이맛 무료주차장 명칭/현행운영은 추가확인안됨
- 입력 텍스트: 9,493; 첫 TEXT: 8.02초; 완료: 11.34초.
- 원문: [B4-official-parking](https://seoulland.co.kr/?p=37) · [조회기록](../results/full_comparison_v9_20260908/sources/B4-official-parking.json)
- 원문: [B4-webiq_base-0](https://seoulland.co.kr/?p=21&gubunCode=service_faq_1616483992_25) · [조회기록](../results/full_comparison_v9_20260908/sources/B4-webiq_base-0.json)
- 원문: [B4-grandpark-current](https://grandpark.seoul.go.kr/conts/contsView/ko/S001001001007.do) · [조회기록](../results/full_comparison_v9_20260908/sources/B4-grandpark-current.json)

#### Web IQ MCP 기본 — incorrect

네. 서울랜드 공식 안내에 따르면 **당일 사용한 서울랜드 이용권이나 영수증을 출차 시 제시하면 동문주차장 주차가 무료**입니다. 단, 동물원·미술관·스카이리프트·캠핑장 이용권은 해당되지 않으며, 서울대공원 주차장은 별도 운영되어 무료 적용이 안 됩니다.

- 판정: 정문주차장이무료인지라는질문에'네'라고긍정한뒤동문무료로대상을바꿨다.동문조건자체는맞지만정문/대공원은별도유료이며핵심장소조건을혼동시킨다.
- 기술실패: False; 전달결함: 정문 질문에 동문으로 대상변경
- 부가오류/정밀도: 없음
- 입력 텍스트: 17,163; 첫 TEXT: 4.14초; 완료: 7.36초.
- 원문: [B4-official-parking](https://seoulland.co.kr/?p=37) · [조회기록](../results/full_comparison_v9_20260908/sources/B4-official-parking.json)
- 원문: [B4-webiq_base-0](https://seoulland.co.kr/?p=21&gubunCode=service_faq_1616483992_25) · [조회기록](../results/full_comparison_v9_20260908/sources/B4-webiq_base-0.json)
- 원문: [B4-grandpark-current](https://grandpark.seoul.go.kr/conts/contsView/ko/S001001001007.do) · [조회기록](../results/full_comparison_v9_20260908/sources/B4-grandpark-current.json)

#### Web IQ MCP 최적화 — incorrect

네. 서울랜드 공식 안내에 따르면 **당일 사용한 서울랜드 이용권이나 영수증을 출차 시 제시하면 동문주차장 주차가 무료**입니다. 단, 서울대공원 주차장은 별도 운영되어 유료이며, 동물원·미술관·스카이리프트·캠핑장 이용권은 무료 적용 대상이 아닙니다.

- 판정: 정문주차장이무료인지라는질문에'네'라고긍정한뒤동문무료로대상을바꿨다.동문조건자체는맞지만정문/대공원은별도유료이며핵심장소조건을혼동시킨다.
- 기술실패: False; 전달결함: 정문 질문에 동문으로 대상변경
- 부가오류/정밀도: 없음
- 입력 텍스트: 9,783; 첫 TEXT: 4.54초; 완료: 7.98초.
- 원문: [B4-official-parking](https://seoulland.co.kr/?p=37) · [조회기록](../results/full_comparison_v9_20260908/sources/B4-official-parking.json)
- 원문: [B4-webiq_base-0](https://seoulland.co.kr/?p=21&gubunCode=service_faq_1616483992_25) · [조회기록](../results/full_comparison_v9_20260908/sources/B4-webiq_base-0.json)
- 원문: [B4-grandpark-current](https://grandpark.seoul.go.kr/conts/contsView/ko/S001001001007.do) · [조회기록](../results/full_comparison_v9_20260908/sources/B4-grandpark-current.json)

### B5 · browse

광릉 국립수목원 공식 안내 보고 9월 12일 승용차로 가려면 주차도 예약해야 하는지 알려줘.

**공통 판정 조건:** 광릉 국립수목원 / 2026-09-12 / 입장·차량 예약 구분 / 예약 가능 잔여량 꾸미지 않음

**독립 확인:** 국립수목원 공식 예약안내: 사전예약한 차량에 한하여 주차 가능. 일반승용차 이용자는 차량예약 필요. 9월12일 잔여자리/예약성공은 확인하지 않음.

#### Bing — correct

네. **9월 12일에 승용차로 광릉 국립수목원에 가려면 주차를 사전 예약해야 합니다.** 공식 안내상 주차장은 **100% 사전 예약제**이며, 예약 차량만 주차장에 들어갈 수 있습니다. 차량 없이 방문할 때만 예약 없이 현장 발권이 가능합니다. 【6:0†source】【6:2†source】

- 판정: 국립수목원공식예약안내의사전예약차량만주차가능조건과일치.잔여예약가능성은주장하지않음.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 3,042; 첫 TEXT: 5.70초; 완료: 10.42초.
- 원문: [B5-official-reservation](https://kna.forest.go.kr/kfsweb/kfi/kfs/cms/cmsView.do?mn=UKNA_01_03_02&cmsId=FC_003507) · [조회기록](../results/full_comparison_v9_20260908/sources/B5-official-reservation.json)
- 원문: [B5-webiq_optimized-0](https://kna.forest.go.kr/kfsweb/kfi/kfs/cms/cmsView.do?mn=UKNA_01_03_01&cmsId=FC_003267%20) · [조회기록](../results/full_comparison_v9_20260908/sources/B5-webiq_optimized-0.json)
- 원문: [B5-webiq_optimized-1](https://kna.forest.go.kr/kfsweb/kfi/kfs/cms/cmsView.do?cmsId=FC_003167&mn=UKNA_01_02_01) · [조회기록](../results/full_comparison_v9_20260908/sources/B5-webiq_optimized-1.json)

#### Web IQ MCP 기본 — correct

네. **9월 12일에 승용차로 방문하려면 주차 예약이 필수**입니다. 국립수목원은 주차장을 100% 사전예약제로 운영하며, 미예약 차량은 주차장에 들어갈 수 없습니다. 예약은 공식 인터넷 예약시스템에서 주차 시간대와 차량번호를 입력해 진행하세요.

- 판정: 국립수목원공식예약안내의사전예약차량만주차가능조건과일치.잔여예약가능성은주장하지않음.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 16,676; 첫 TEXT: 4.46초; 완료: 8.72초.
- 원문: [B5-official-reservation](https://kna.forest.go.kr/kfsweb/kfi/kfs/cms/cmsView.do?mn=UKNA_01_03_02&cmsId=FC_003507) · [조회기록](../results/full_comparison_v9_20260908/sources/B5-official-reservation.json)
- 원문: [B5-webiq_optimized-0](https://kna.forest.go.kr/kfsweb/kfi/kfs/cms/cmsView.do?mn=UKNA_01_03_01&cmsId=FC_003267%20) · [조회기록](../results/full_comparison_v9_20260908/sources/B5-webiq_optimized-0.json)
- 원문: [B5-webiq_optimized-1](https://kna.forest.go.kr/kfsweb/kfi/kfs/cms/cmsView.do?cmsId=FC_003167&mn=UKNA_01_02_01) · [조회기록](../results/full_comparison_v9_20260908/sources/B5-webiq_optimized-1.json)

#### Web IQ MCP 최적화 — correct

네. **2026년 9월 12일에 승용차로 광릉 국립수목원에 가려면 차량·주차를 반드시 사전 예약해야 합니다.** 공식 안내상 미예약 차량은 주차장에 들어갈 수 없으며, 예약은 오전(9~13시) 또는 오후(13~18시) 시간대로 진행하고 주차요금은 입장 당일 별도 결제합니다.

- 판정: 공식사전차량예약필수·오전오후예약·입장당일주차료결제안내와일치.잔여자리확보는주장하지않음.
- 기술실패: False; 전달결함: 없음
- 부가오류/정밀도: 없음
- 입력 텍스트: 9,487; 첫 TEXT: 3.77초; 완료: 7.18초.
- 원문: [B5-official-reservation](https://kna.forest.go.kr/kfsweb/kfi/kfs/cms/cmsView.do?mn=UKNA_01_03_02&cmsId=FC_003507) · [조회기록](../results/full_comparison_v9_20260908/sources/B5-official-reservation.json)
- 원문: [B5-webiq_optimized-0](https://kna.forest.go.kr/kfsweb/kfi/kfs/cms/cmsView.do?mn=UKNA_01_03_01&cmsId=FC_003267%20) · [조회기록](../results/full_comparison_v9_20260908/sources/B5-webiq_optimized-0.json)
- 원문: [B5-webiq_optimized-1](https://kna.forest.go.kr/kfsweb/kfi/kfs/cms/cmsView.do?cmsId=FC_003167&mn=UKNA_01_02_01) · [조회기록](../results/full_comparison_v9_20260908/sources/B5-webiq_optimized-1.json)

## 초기 인수·실제 반환량 감사

기본 web/news=3개·passage1200자, browse4000자; 최적화=2개·800자, browse2000자. videos=3/2개. Places/Finance는 해당 인수 없음.
초기 정책이며 후속조회는 허용된다. 인수지원 여부·첫 호출과 후속을 구분한다. 아래 값은 실제 payload의 문자/개수이며 토큰 추정이 아니다.
Bing 내부 payload는 미노출. 도구가 호출되지 않았다는 이유만으로 실패 또는 재실행하지 않았다.

| ID/조건 | 호출/첫해당도구 | 요청 인수 | 반환 개수 | 본문 문자수 | 요청 개수/길이 준수 |
| --- | --- | --- | --- | --- | --- |
| W1/webiq_base | web/True | {"query": "인천공항 제1터미널 장기주차장 일반 승용차 24시간 요금 2026 9월 12일", "maxResults": 3, "contentFormat": "passage", "maxLength": 1200, "language": "ko", "region": "KR"} | {'webResults': 3} | [1194, 1195, 1198] | True/True |
| W1/webiq_optimized | web/True | {"query": "인천공항 제1여객터미널 장기주차장 일반 승용차 24시간 요금 2026 9월 12일", "maxResults": 2, "contentFormat": "passage", "maxLength": 800, "language": "ko", "region": "KR"} | {'webResults': 2} | [790, 784] | True/True |
| W2/webiq_base | web/True | {"query": "김포공항 국내선 주차장 승용차 1일 주차요금 2026년 9월", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1188, 1187, 1021] | True/True |
| W2/webiq_base | web/False | {"query": "site:airport.co.kr 김포공항 주차요금 국내선 금 토 일 30,000원", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1191, 0, 0] | True/True |
| W2/webiq_optimized | web/True | {"query": "김포공항 국내선 주차장 승용차 1일 주차요금 2026 토요일", "maxResults": 2, "contentFormat": "passage", "maxLength": 800, "language": "ko", "region": "KR"} | {'webResults': 2} | [797, 795] | True/True |
| W3/webiq_optimized | web/True | {"query": "서울대공원 동물원 반려견 이동가방 입장 가능 소형견 출입 안내", "maxResults": 2, "contentFormat": "passage", "maxLength": 800, "language": "ko", "region": "KR"} | {'webResults': 2} | [790, 792] | True/True |
| W3/webiq_optimized | web/False | {"query": "site:grandpark.seoul.go.kr 서울동물원 반려동물 출입 안내견 애완동물", "maxResults": 2, "contentFormat": "passage", "maxLength": 800, "language": "ko", "region": "KR"} | {'webResults': 2} | [794, 793] | True/True |
| W3/webiq_base | web/True | {"query": "서울대공원 동물원 반려견 이동가방 입장 가능 소형견 반려동물 출입 2026", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1194, 1190, 1197] | True/True |
| W4/webiq_base | web/True | {"query": "남산서울타워 정상 일반 승용차 진입 가능 차량 통제 2026 9월", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1197, 1193, 1190] | True/True |
| W4/webiq_optimized | web/True | {"query": "2026년 9월 남산서울타워 정상 일반 승용차 차량 통행 가능 최신 공지", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [794, 793] | True/True |
| W5/webiq_base | web/True | {"query": "서울역 인천공항 제1터미널 공항철도 직통열차 성인 요금 2026", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1191, 1188, 1186] | True/True |
| W5/webiq_optimized | web/True | {"query": "공항철도 직통열차 서울역 인천공항 1터미널 성인 운임 2026", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [794, 797] | True/True |
| P1/webiq_optimized | places/True | {"query": "광교호수공원 원천호수 근처 자체 주차장 있는 카페", "language": "ko", "region": "KR"} | {'placeResults': 10} | [] | None/None |
| P1/webiq_optimized | web/True | {"query": "광교호수공원 카페 자체 주차장 테이크웨이브 주차", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [795, 796] | True/True |
| P1/webiq_base | places/True | {"query": "광교호수공원 원천호수 근처 자체 주차장 카페", "language": "ko", "region": "KR"} | {'placeResults': 10} | [] | None/None |
| P1/webiq_base | web/True | {"query": "광교호수공원 원천호수 카페 자체 주차장 \"주차\"", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1198, 1191, 1183] | True/True |
| P1/webiq_base | web/False | {"query": "광교호수공원 카페 슬로 주차 자체 주차장", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1192, 1194, 1196] | True/True |
| P2/webiq_base | web/True | {"query": "서울숲역 강아지 동반 실내 카페", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1188, 1187, 1189] | True/True |
| P2/webiq_optimized | places/True | {"query": "서울숲역 근처 강아지 실내 동반 가능한 카페", "language": "ko", "region": "KR"} | {'placeResults': 10} | [] | None/None |
| P2/webiq_optimized | web/True | {"query": "서울숲역 강아지 동반 실내 카페 어라운드데이 반려견", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [795, 790] | True/True |
| P3/webiq_base | places/True | {"query": "일산 호수공원 정발산역 아이와 점심 주차 가능한 식당", "language": "ko", "region": "KR"} | {'placeResults': 10} | [] | None/None |
| P3/webiq_base | web/True | {"query": "부페파크 일산점 주차 아이 점심 영업시간", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1188, 1188, 1194] | True/True |
| P3/webiq_optimized | places/True | {"query": "일산 호수공원 정발산역 아이와 점심 주차 가능한 식당", "language": "ko", "region": "KR"} | {'placeResults': 10} | [] | None/None |
| P3/webiq_optimized | web/True | {"query": "포폴로피자 일산 주차 가능 주차장 영업시간", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [794, 795] | True/True |
| P4/webiq_optimized | web/True | {"query": "성수역 근처 베이커리 카페 토요일 오전 9시 영업", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [784, 788] | True/True |
| P4/webiq_optimized | places/True | {"query": "성수역 베이커리 카페", "language": "ko", "region": "KR"} | {'placeResults': 10} | [] | None/None |
| P4/webiq_base | web/True | {"query": "성수역 베이커리 카페 토요일 오전 9시 영업", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1195, 998, 1189] | True/True |
| P5/webiq_base | web/True | {"query": "판교역 근처 서점 밤 10시 영업시간", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1188, 1194, 1188] | True/True |
| P5/webiq_optimized | places/True | {"query": "판교역 근처 밤 10시까지 영업하는 서점", "language": "ko", "region": "KR"} | {'placeResults': 2} | [] | None/None |
| P5/webiq_optimized | web/True | {"query": "판교역 서점 영업시간 22:00 교보문고 영풍문고", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [796, 796] | True/True |
| F1/webiq_base | finance/True | {"query": "삼성전자 보통주 005930 2026년 9월 7일 코스피 정규장 종가 KRW", "language": "ko", "region": "KR"} | {'financeResults': 0} | [] | None/None |
| F1/webiq_base | web/True | {"query": "2026년 9월 7일 삼성전자 주가 종가 005930", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1196, 1169, 1195] | True/True |
| F1/webiq_optimized | finance/True | {"query": "삼성전자 보통주 2026년 9월 7일 코스피 정규장 종가 KRW 005930"} | {'financeResults': 0} | [] | None/None |
| F1/webiq_optimized | web/True | {"query": "삼성전자 2026년 9월 7일 종가 005930", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [791, 794] | True/True |
| F1/webiq_optimized | web/False | {"query": "005930 2026-09-07 270000 종가 삼성전자 KRX", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [795, 798] | True/True |
| F2/webiq_optimized | web/True | {"query": "Nasdaq Composite September 4 2026 close change percent", "maxResults": 2, "contentFormat": "passage", "maxLength": 800, "region": "US", "language": "en"} | {'webResults': 2} | [797, 792] | True/True |
| F2/webiq_optimized | finance/True | {"query": "Nasdaq Composite IXIC historical close September 4 2026 regular session", "language": "en", "region": "US"} | {'financeResults': 0} | [] | None/None |
| F2/webiq_base | finance/True | {"query": "NASDAQ Composite 2026-09-04 historical close change percent regular session USD"} | {'financeResults': 0} | [] | None/None |
| F2/webiq_base | web/True | {"query": "Nasdaq Composite September 4 2026 close percent change", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1197, 1194, 1197] | True/True |
| F2/webiq_base | web/False | {"query": "site:nasdaq.com/market-activity/index/comp historical 2026-09-04 Nasdaq Composite 18203.47", "maxResults": 3, "language": "en", "region": "US", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1199, 590, 1192] | True/True |
| F3/webiq_base | finance/True | {"query": "S&P 500 index closing value on September 4, 2026, US regular market, USD", "language": "ko", "region": "KR"} | {'financeResults': 1} | [] | None/None |
| F3/webiq_base | web/True | {"query": "S&P 500 September 4 2026 close 2026-09-04 historical data", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1193, 1193, 1196] | True/True |
| F3/webiq_base | web/False | {"query": "\"September 4, 2026\" \"S&P 500\" \"7,718.60\"", "maxResults": 3, "language": "en", "region": "US", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1193, 1189, 1186] | True/True |
| F3/webiq_optimized | finance/True | {"query": "S&P 500 index closing value September 4, 2026 regular session US dollars"} | {'financeResults': 0} | [] | None/None |
| F3/webiq_optimized | web/True | {"query": "S&P 500 September 4 2026 close 2026-09-04", "maxResults": 2, "contentFormat": "passage", "maxLength": 800, "language": "ko", "region": "KR"} | {'webResults': 2} | [795, 795] | True/True |
| F4/webiq_base | web/True | {"query": "2026년 9월 8일 서울외국환중개 원달러 매매기준율", "maxResults": 3, "contentFormat": "passage", "maxLength": 1200, "language": "ko", "region": "KR"} | {'webResults': 3} | [1194, 597, 1189] | True/True |
| F4/webiq_base | web/False | {"query": "site:smbs.co.kr/ExRate 2026.09.08 USD 매매기준율", "maxResults": 3, "contentFormat": "passage", "maxLength": 1200, "language": "ko", "region": "KR"} | {'webResults': 3} | [597, 422, 1010] | True/True |
| F4/webiq_optimized | web/True | {"query": "2026년 9월 8일 서울외국환중개 원달러 매매기준율", "maxResults": 2, "contentFormat": "passage", "maxLength": 800, "language": "ko", "region": "KR"} | {'webResults': 2} | [795, 597] | True/True |
| F5/webiq_optimized | finance/True | {"query": "Tesla TSLA Nasdaq regular session closing price on September 4, 2026 in USD"} | {'financeResults': 1} | [] | None/None |
| F5/webiq_optimized | web/True | {"query": "TSLA historical data September 4 2026 close Nasdaq", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [795, 794] | True/True |
| F5/webiq_base | finance/True | {"query": "Tesla (TSLA) Nasdaq regular session closing price on September 4, 2026 in USD", "language": "ko", "region": "KR"} | {'financeResults': 1} | [] | None/None |
| F5/webiq_base | web/True | {"query": "TSLA historical data September 4 2026 close Nasdaq regular session USD", "maxResults": 3, "language": "en", "region": "US", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1193, 1196, 1189] | True/True |
| N1/webiq_base | news/True | {"query": "서울 도로 통제 기사 2026년 9월 2일 9월 8일 통제 구간", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'newsResults': 3} | [460, 473, 428] | True/True |
| N1/webiq_base | browse/True | {} | {} | None | None/None |
| N1/webiq_optimized | news/True | {"query": "서울 도로 통제 2026년 9월 2일 9월 8일", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'newsResults': 2} | [466, 400] | True/True |
| N1/webiq_optimized | browse/True | {} | {} | None | None/None |
| N2/webiq_base | news/True | {"query": "전기차 충전요금 할인 2026년 9월 2일 9월 8일", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'newsResults': 3} | [474, 452, 463] | True/True |
| N2/webiq_base | web/True | {"query": "site:me.go.kr 전기차 충전요금 9월 5일 10월 31일 오전 11시 오후 2시 2026", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1188, 1191, 1198] | True/True |
| N2/webiq_optimized | news/True | {"query": "전기차 충전요금 할인 2026년 9월 2일 9월 8일", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'newsResults': 2} | [468, 447] | True/True |
| N2/webiq_optimized | browse/True | {} | {} | None | None/None |
| N3/webiq_optimized | news/True | {"query": "서울 축제 2026년 9월 12일 13일 최근 기사", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'newsResults': 2} | [439, 460] | True/True |
| N3/webiq_base | news/True | {"query": "서울 축제 2026년 9월 12일 13일", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'newsResults': 3} | [449, 351, 470] | True/True |
| N4/webiq_base | news/True | {"query": "고속도로 전기차 충전소 2026년 9월 2일 9월 8일", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'newsResults': 3} | [447, 1032, 485] | True/True |
| N4/webiq_optimized | news/True | {"query": "고속도로 전기차 충전소 2026년 9월 2일 9월 8일", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'newsResults': 2} | [443, 796] | True/True |
| N4/webiq_optimized | news/False | {"query": "고속도로 휴게소 전기차 충전 2026년 9월 2일 OR 9월 3일 OR 9월 4일 OR 9월 5일 OR 9월 6일 OR 9월 7일 OR 9월 8일", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'newsResults': 2} | [402, 383] | True/True |
| N5/webiq_base | news/True | {"query": "2026년 추석 고속도로 통행료 면제 적용 날짜", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'newsResults': 3} | [413, 469, 427] | True/True |
| N5/webiq_optimized | news/True | {"query": "2026년 추석 고속도로 통행료 면제 적용 날짜", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'newsResults': 2} | [410, 466] | True/True |
| V1/webiq_optimized | videos/True | {"query": "아이오닉 5 급속 충전 방법 현대자동차 공식", "maxResults": 2, "language": "ko", "region": "KR"} | {'videoResults': 2} | [] | True/None |
| V1/webiq_base | videos/True | {"query": "현대자동차 공식 아이오닉 5 급속 충전 방법", "maxResults": 3, "language": "ko", "region": "KR"} | {'videoResults': 3} | [] | True/None |
| V2/webiq_base | videos/True | {"query": "기아 공식 EV6 급속충전 방법", "maxResults": 3, "language": "ko", "region": "KR"} | {'videoResults': 3} | [] | True/None |
| V2/webiq_optimized | videos/True | {"query": "기아 EV6 급속충전 방법 기아 공식", "maxResults": 2, "language": "ko", "region": "KR"} | {'videoResults': 2} | [] | True/None |
| V3/webiq_base | videos/True | {"query": "타이어뱅크 타이어 공기압 셀프 주입 방법", "maxResults": 3, "language": "ko", "region": "KR"} | {'videoResults': 3} | [] | True/None |
| V3/webiq_optimized | videos/True | {"query": "타이어뱅크 타이어 공기압 셀프 주입 방법", "maxResults": 2, "language": "ko", "region": "KR"} | {'videoResults': 2} | [] | True/None |
| V4/webiq_optimized | videos/True | {"query": "현대자동차 공식 블루링크 앱 차량 등록 방법", "maxResults": 2, "language": "ko", "region": "KR"} | {'videoResults': 2} | [] | True/None |
| V4/webiq_optimized | videos/False | {"query": "site:youtube.com 현대자동차 블루링크 차량 등록 앱 공식", "maxResults": 2, "language": "ko", "region": "KR"} | {'videoResults': 2} | [] | True/None |
| V4/webiq_base | videos/True | {"query": "현대차 블루링크 앱 차량 등록 공식 안내", "maxResults": 3, "language": "ko", "region": "KR"} | {'videoResults': 3} | [] | True/None |
| V4/webiq_base | web/True | {"query": "현대자동차 공식 유튜브 블루링크 차량 등록 앱", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1190, 1198, 1196] | True/True |
| V5/webiq_base | videos/True | {"query": "현대자동차 공식 안드로이드 오토 유선 연결 방법", "maxResults": 3, "language": "ko", "region": "KR"} | {'videoResults': 3} | [] | True/None |
| V5/webiq_optimized | videos/True | {"query": "현대자동차 안드로이드 오토 유선 연결 공식", "maxResults": 2, "language": "ko", "region": "KR"} | {'videoResults': 2} | [] | True/None |
| V5/webiq_optimized | web/True | {"query": "site:youtube.com 현대자동차 공식 안드로이드 오토 연결 유선", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [414, 443] | True/True |
| B1/webiq_base | web/True | {"query": "서울식물원 공식 안내 온실 9월 12일 토요일 입장 마감 시간", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1197, 1193, 1195] | True/True |
| B1/webiq_base | web/False | {"query": "site:botanicpark.seoul.go.kr 서울식물원 관람안내 온실 입장마감 3월 10월", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [375, 431, 382] | True/True |
| B1/webiq_optimized | web/True | {"query": "서울식물원 공식 안내 2026년 9월 12일 토요일 온실 입장 마감 시간", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [793, 794] | True/True |
| B1/webiq_optimized | web/False | {"query": "site:botanicpark.seoul.go.kr 온실 관람시간 입장마감 3월 10월 서울식물원", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [375, 431] | True/True |
| B2/webiq_optimized | web/True | {"query": "국립과천과학관 공식 주차요금 경차 2시간 2026 9월 12일", "maxResults": 2, "contentFormat": "passage", "maxLength": 800, "language": "ko", "region": "KR"} | {'webResults': 2} | [738, 796] | True/True |
| B2/webiq_optimized | browse/True | {} | {} | None | None/None |
| B2/webiq_base | web/True | {"query": "국립과천과학관 공식 주차요금 경차 2026 9월", "maxResults": 3, "contentFormat": "passage", "maxLength": 1200, "language": "ko", "region": "KR"} | {'webResults': 3} | [1198, 1195, 745] | True/True |
| B3/webiq_base | web/True | {"query": "국립중앙박물관 공식 주차 요금 승용차 3시간 2026 9월 12일", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1191, 1197, 934] | True/True |
| B3/webiq_base | browse/True | {} | {} | None | None/None |
| B3/webiq_optimized | web/True | {"query": "국립중앙박물관 공식 주차요금 승용차 3시간 9월 12일", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [795, 794] | True/True |
| B4/webiq_base | web/True | {"query": "서울랜드 공식 안내 당일 이용권 정문 주차장 무료 주차", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1191, 1195, 1194] | True/True |
| B4/webiq_optimized | web/True | {"query": "서울랜드 공식 안내 당일 이용권 정문 주차장 무료", "maxResults": 2, "contentFormat": "passage", "maxLength": 800, "language": "ko", "region": "KR"} | {'webResults': 2} | [791, 790] | True/True |
| B5/webiq_optimized | web/True | {"query": "국립수목원 광릉 주차 예약 승용차 2026년 9월 12일 공식 안내", "maxResults": 2, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 800} | {'webResults': 2} | [795, 795] | True/True |
| B5/webiq_base | web/True | {"query": "광릉 국립수목원 공식 안내 9월 12일 승용차 주차 예약", "maxResults": 3, "language": "ko", "region": "KR", "contentFormat": "passage", "maxLength": 1200} | {'webResults': 3} | [1194, 1193, 1190] | True/True |

## 기능군별 동일질문 비교 (최적화 vs MCP 기본)

| 기능군 | 사용가능 대응쌍 | 기본→최적화 입력 합 | 입력 감소율 | 정확확인 수 차이(전체군) |
| --- | --- | --- | --- | --- |
| web | 5/5 | 91,416→55,985 | 38.8% | +0 |
| places | 5/5 | 107,031→64,324 | 39.9% | +1 |
| finance | 5/5 | 65,687→37,815 | 42.4% | -1 |
| news | 3/5 | 27,872→26,375 | 5.4% | -1 |
| videos | 5/5 | 60,181→40,168 | 33.3% | -1 |
| browse | 3/5 | 59,953→35,189 | 41.3% | +2 |
| all | 26/30 | 412,140→259,856 | 36.9% | +0 |

## 계측·비용 한계

주요3조건토큰·시간표는세조건모두완료하고usage가있는공통26문항만사용한다. 제외문항: N1, N2, B2, B3. 정확성·실패는전체30문항분모다.
5개기술실패는browse호출이기록되어있으며agent_tool_user_error와0 usage가관측되었다. 기록인수는빈값/확인불가다. public_call의잘못된JSON정규화가능성때문에이기록만으로상류의실제요청인수나근본원인을단정하지않는다.
입력 토큰은 Agent LLM API보고 텍스트 입력이며 오디오 제외. 캐시는 입력의 부분집합이고 reasoning은 output의 부분집합이라 재합산하지 않는다. 원본 usage는 JSONL에 보존했다.
첫 TEXT는 response.audio_transcript.delta 수신, 완료는 response.done. 모델 서버 TTFT·순수검색시간·마이크/스피커 지연이 아니다. 결측은 0 아님; 실패의 0 usage도 무료 아님.
Web IQ web/news/videos/browse 단위요율 $12.50/1000(사용자표), Bing $14/1000 transactions(공식). Places/Finance·내부과금건수·모델/음성 합산은 미확정. 요청당 총비용 비교 불가.

## 원본 추적

- runs.jsonl SHA256: `503c0e9433e7f53f16abff5b05091c4b484fbbc9bd3a2b1177f9a2fec4aed3af`
- [90행 집계 및 모든 usage](../results/full_comparison_v9_20260908/summary.json)
- [검증·출처 SHA256·예산](../results/full_comparison_v9_20260908/verification.json)
- [사전 고정 정확성 기준](../results/full_comparison_v9_20260908/accuracy_protocol.json)

## 실제 관측 도구 호출과 단위요율

실패를 포함한 원본에 노출된 호출 수다. 과금 영수증이 아니며 숨겨진 내부 재시도·transactions와 동일하다고 가정하지 않는다.

| 도구 | MCP 기본 호출 | MCP 최적화 호출 | 알려진 단위요율 |
| --- | ---: | ---: | --- |
| web | 28 | 24 | $12.50/1,000 calls (사용자표) |
| places | 2 | 5 | 미확정 |
| finance | 4 | 4 | 미확정 |
| news | 5 | 6 | $12.50/1,000 calls (사용자표) |
| videos | 5 | 6 | $12.50/1,000 calls (사용자표) |
| browse | 2 | 3 | $12.50/1,000 calls (사용자표) |
| Bing 내부 검색 | 관측불가 | 해당없음 | $14/1,000 transactions (Microsoft) |

캐시·오디오·출력·reasoning 각각의 실제 usage 합계/평균은 summary.json의 all_reported에 보존했다. 캐시와 reasoning을 총량에 다시 더하지 않는다.
