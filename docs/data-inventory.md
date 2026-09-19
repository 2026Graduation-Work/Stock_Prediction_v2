# 데이터 인벤토리 — 화면 수치의 출처

- 작성: 2026-09-19 (main `039809e` 기준)
- 용도: 중간보고서 "데이터 경계" 표의 원본. 화면에 나오는 수치를 한 행씩 적고, 실데이터인지와 실데이터로 바꾸려면 무엇이 필요한지 적는다.
- 범위: 시장 브리핑 바, 대시보드(성향 카드·추천/보유 종목 카드·포트폴리오 맵), 종목 상세(상단·인사이트 카드 6종), `/performance`
- 이 문서는 팀의 데이터 취급 기록이며 법률 자문이 아니다. 약관은 바뀔 수 있으니 실데이터 전환 전에 다시 확인한다.

## 분류 기호

| 기호 | 뜻 |
|---|---|
| ✅ 연결 | 실데이터가 화면까지 이어져 있다 |
| 🟡 있음·세팅미완 | 원천 데이터나 계산 코드는 레포에 있지만 화면까지 연결이 안 됐다 |
| 🔵 새로확보 | 레포에 없어 새로 받아야 한다 |
| ⚪ 데모유지 | 손으로 정한 값·합성값. 당분간 예시로 두고, 화면에 예시임을 표시해야 한다 |
| ⛔ 사용불가 | 약관 등으로 쓸 수 없다 |

## 데이터 경로 공통 사항

화면 데이터는 두 갈래 중 하나로 들어온다. **둘 다 실데이터가 아니다.**

1. **mock** — `frontend/lib/mock-data.ts`, `frontend/lib/providers/fixtures.ts`, `frontend/lib/mock-performance.ts`. Supabase 환경변수가 없거나 조회가 실패하면 쓰인다(`frontend/lib/queries.ts:585` `withFallback`).
2. **Supabase** — `frontend/lib/queries.ts`가 테이블을 직접 조회한다. 그런데 테이블을 채우는 것은 **손으로 쓴 데모 시드**(`supabase/seed.sql`, 김민지 페르소나)뿐이고, 백엔드에서 Supabase에 쓰는 코드는 없다(`backend/` 전체에서 `supabase`·`predictions`·`market_status` 쓰기 없음). 설문 결과 저장(`frontend/lib/save-profile.ts:58`)만 예외다.

- Supabase 경로로 들어온 값은 `source: "supabase"`가 붙어 **"샘플" 배지 없이** 표시된다(`frontend/lib/mappers.ts:136`, `frontend/app/components/market-status-bar.tsx:49`). 시드 값도 실데이터처럼 보인다는 뜻이다.
- 로컬 `frontend/`에는 `.env.example`만 있다. 배포(Vercel) 환경에 Supabase 변수가 설정됐는지는 이 문서에서 확인하지 않았다.

## 1. 시장 브리핑 바

컴포넌트 `frontend/app/components/market-status-bar.tsx` · 데이터 `frontend/lib/queries.ts:197` → Supabase `market_status`(`supabase/seed.sql:474`) 또는 mock(`frontend/lib/mock-data.ts:14`)

| 화면 위치 | 코드 출처 | 원천 | 기간 | 약관 메모 | 분류 | 실데이터 전환에 필요한 것 |
|---|---|---|---|---|---|---|
| 기준일("2025.10.02 기준") | `market-status-bar.tsx:56` ← `mock-data.ts:15` / `seed.sql:482` | mock / seed | mock 2025-10-02, seed 2026-07-07 | — | ⚪ | 지수 데이터를 연결하면 그 날짜를 쓴다 |
| KOSPI·KOSDAQ·KOSPI 200 지수와 등락률 | `market-status-bar.tsx:22-24` ← `mock-data.ts:20-41` / `seed.sql:486-489` | mock / seed | 위와 같음 | pykrx는 KRX 로그인 필요(§5). FDR의 내부 원천별 약관 확인 필요 | 🔵 | FinanceDataReader `KS11`은 로그인 없이 조회됨(§5 참고). `KQ11`·`KS200`도 같은 방식으로 받아 `market_status.index_quotes`에 적재 |
| 원/달러 | `market-status-bar.tsx:22-24` ← `mock-data.ts:42-48` | mock / seed | 위와 같음 | — | 🔵 | 환율 원천 선정(FDR `USD/KRW`는 이번에 시험하지 않음) |
| 변동성 점수 61 · 거래량 점수 48 | `market-status-bar.tsx:69-70` ← `mock-data.ts:18-19` | mock / seed | — | — | ⚪ | **산식이 정의돼 있지 않다.** 지수 일봉에서 계산할 산식부터 정해야 한다 |
| 시장 상태 라벨·코멘트("주의" 등) | `market-status-bar.tsx:75,78` ← `display.ts:112` + `condition` | mock / seed | — | — | ⚪ | 위 점수 산식과 상태 구간 정의 |

## 2. 대시보드

### 2-1. 성향 카드

컴포넌트 `frontend/app/components/investor-profile-card.tsx` · 데이터: 이 브라우저에서 설문을 마쳤으면 저장된 결과(`frontend/app/components/dashboard.tsx:118-126`, `frontend/lib/save-profile.ts:127`), 아니면 `queries.ts:225` → Supabase `ips_profiles`(시드) 또는 mock `mock-data.ts:52`

| 화면 위치 | 코드 출처 | 원천 | 기간 | 약관 메모 | 분류 | 실데이터 전환에 필요한 것 |
|---|---|---|---|---|---|---|
| 성향 유형·페르소나 | `investor-profile-card.tsx:40` ← `dashboard.tsx:56-57` | 사용자 설문 응답(규칙 기반 산출) | 설문 시점 | 개인정보: 로그인 시 Supabase 저장 | ✅ | 설문 전·비로그인 상태는 김민지 데모(⚪) |
| 위험 감수 점수 | `investor-profile-card.tsx:43` ← `dashboard.tsx:58` | 설문 `risk_tolerance`×100 | 설문 시점 | 위와 같음 | ✅ | — |
| 심리 민감도 점수 | `investor-profile-card.tsx:44` ← `dashboard.tsx:59` | 설문 `fomo_index`×100 | 설문 시점 | 위와 같음 | ✅ | — |
| 투자 기간 | `investor-profile-card.tsx:49` ← `dashboard.tsx:47-48` | 설문 `time_horizon_months` | 설문 시점 | 위와 같음 | ✅ | — |
| 설문 시점 | `investor-profile-card.tsx:82` ← `dashboard.tsx:50-53` | 설문 `timestamp` | — | — | ✅ | — |

### 2-2. 추천 종목·보유 종목 알림 카드

컴포넌트 `frontend/app/components/stock-card.tsx` · 데이터 `queries.ts:250,285` → Supabase `predictions`(시드 4행, `seed.sql:248`) 또는 mock `mock-data.ts:63-112`

모델 쪽 현황: 차트 블록에 LightGBM 기준 모델 2개(`backend/analysis/chart/core/models/baseline_h5_…txt`, `baseline_h20_…txt`)와 추론 함수(`backend/analysis/chart/core/inference.py:80` `predict_success_probability`)가 있다. 출력은 **상승 확률까지**다. 전 종목 순위(`rank_percentile`)·신호등 매핑·수익률 밴드·적중률을 계산해 `predictions`에 적재하는 코드는 없다. h10 모델도 없다.

| 화면 위치 | 코드 출처 | 원천 | 기간 | 약관 메모 | 분류 | 실데이터 전환에 필요한 것 |
|---|---|---|---|---|---|---|
| 위험등급 N · 라벨 | `stock-card.tsx:84` ← `stocks.risk_grade` / `mock-data.ts:67` | seed / mock | — | — | ⚪ | **등급 산식이 정의돼 있지 않다**(변동성 기준인지 등). 산식 합의 |
| 위험 플래그(고변동성 등) | `stock-card.tsx:86` ← `stocks.risk_flags` / `mock-data.ts:102` | seed / mock | — | — | ⚪ | SPAC·관리종목은 종목 목록(FDR `KRX-DESC` 등)에서, 고변동성은 가격에서 계산 |
| 신호등 · "신호 강도 상위 N%" | `stock-card.tsx:95-97` ← `signal_light`·`rank_percentile` | seed / mock | — | — | 🟡 | 전 종목 일괄 추론 → 순위 → 신호등 매핑(`schema/chart_output.schema.json`) → `predictions` 적재 |
| 예상 수익률 밴드 · N% 신뢰구간 | `stock-card.tsx:107,122` ← `return_low/high`·`return_ci_level` | seed / mock | — | — | 🟡 | 신호 구간별 과거 실현 수익률 분포 산출(백테스트) |
| 적중률 · 유사 사례 N건 | `stock-card.tsx:129,131` ← `bucket_hit_rate`·`similar_case_count` | seed / mock | — | — | 🟡 | 위 백테스트에서 구간별 적중률·표본 수 |
| H5·H10·H20 방향과 일치도 | `stock-card.tsx:137-151` ← `horizon_h5/h10/h20` | seed / mock | — | — | 🟡 | h5·h20 모델은 있음. h10 모델 학습 필요 |
| 주의 문구 | `stock-card.tsx:161` ← `predictions.caution` / `mock-data.ts:103` | seed / mock 문장 | — | — | ⚪ | 위험등급·성향 비교 규칙으로 생성 |
| 회피 설정으로 제외된 종목 N개·목록 | `dashboard.tsx:204-221` ← `avoided_assets` + `stocks.risk_flags` / `mock-data.ts:116-119` | 회피 항목은 설문(✅), 제외 종목은 seed / mock | — | — | ⚪ | 종목별 플래그를 실데이터로 채우면 목록이 자동으로 맞는다 |

### 2-3. 포트폴리오 맵

컴포넌트 `frontend/app/components/portfolio-heatmap.tsx` · 데이터 `queries.ts:217,322` → Supabase `portfolio_holdings`(시드) 또는 mock `mock-data.ts:143`

| 화면 위치 | 코드 출처 | 원천 | 기간 | 약관 메모 | 분류 | 실데이터 전환에 필요한 것 |
|---|---|---|---|---|---|---|
| 보유 수량 · 매입금액(만원) · 타일 크기 | `portfolio-heatmap.tsx:31,108` | seed / mock | — | 개인 자산 정보 | ⚪ | **보유 종목 입력 UI가 없다.** 입력 화면을 만들거나 데모로 유지 |
| 보유 종목 신호 라벨·색 | `portfolio-heatmap.tsx:86-106` ← `predictions.signal_light` | seed / mock | — | — | 🟡 | 2-2 신호 파이프라인과 같음 |

## 3. 종목 상세

페이지 `frontend/app/stocks/[code]/page.tsx`는 항상 mock(`getMockStockDetailData`)으로 먼저 그리고, 로그인 상태면 Supabase로 다시 조회한다(`frontend/app/components/stock-detail-boundary.tsx:38`). Supabase 경로는 현재가·가격 추이·수익률 분포·AI 조언을 채우지 않는다(`frontend/lib/mappers.ts:177`). 상세 mock은 삼성전자·현대차·셀트리온 3종목, 인사이트 카드 데이터는 삼성전자·현대차 2종목뿐이다(`frontend/lib/providers/index.ts:2`).

### 3-1. 상단·예측 영역

컴포넌트 `frontend/app/components/stock-detail.tsx`

| 화면 위치 | 코드 출처 | 원천 | 기간 | 약관 메모 | 분류 | 실데이터 전환에 필요한 것 |
|---|---|---|---|---|---|---|
| 현재가 · 등락률 | `stock-detail.tsx:230-233` ← `mock-data.ts:236-237` | mock | 2025-10-02 | FDR 원천 약관 확인 | 🟡 | 레포에 삼성전자 일봉이 있다(`backend/analysis/chart/data/raw/005930.parquet`, 2010-01-04 ~ 2026-06-19, FDR). 다른 종목은 FDR로 수집 |
| 데이터·예측 기준일 | `stock-detail.tsx:224` ← `asOf` | mock / seed | 2025-10-02 | — | ⚪ | 신호 파이프라인 기준일을 쓴다 |
| 신호등·순위·밴드·적중률·유사 사례·H5/H10/H20 | `stock-detail.tsx:254-315,420` | mock / seed | — | — | 🟡 | 2-2와 같음 |
| 과거 유사 신호 실현 수익률 분포(히스토그램) | `stock-detail.tsx:335` ← `mock-data.ts:200,244,290` | mock(손으로 정한 도수) | — | — | 🟡 | 백테스트 결과의 구간별 도수. Supabase 경로는 일부러 비워 둔다(`stock-detail.tsx:187`) |
| 가격 추이 차트(60거래일) | `stock-detail.tsx:382` ← `mock-data.ts:176` `priceSeries` | **합성 곡선**(보간 + 사인파) | 날짜 없음 | — | 🟡 | 현재가와 같은 원천. 삼성전자는 레포 parquet로 바로 가능 |
| 근거 Top 3(제목·설명·출처) | `stock-detail.tsx:437` ← `mock-data.ts:211,257,305` / `prediction_features` | mock / seed 문장 | — | — | 🟡 | 모델 기여도(LightGBM `pred_contrib`)를 한국어 라벨로 매핑. ⚠️ mock 문장에 "영업이익이 시장 예상치를 9% 상회" 같은 **사실처럼 읽히는 합성 주장**이 있다 |
| AI 조언 문단 | `stock-detail.tsx:522` ← `mock-data.ts:231,277,325` | mock 문장(숫자 포함) | — | — | ⚪ | 생성기가 없다. 템플릿이나 LLM 생성은 별도 결정 필요 |

### 3-2. 인사이트 카드 6종

컴포넌트 `frontend/app/components/insight-cards.tsx` · 데이터 `frontend/lib/providers/index.ts:103` `loadStockInsights`

| 화면 위치 | 코드 출처 | 원천 | 기간 | 약관 메모 | 분류 | 실데이터 전환에 필요한 것 |
|---|---|---|---|---|---|---|
| **확인해 볼 점**(성향 넛지 최대 2개) | `insight-cards.tsx:686` ← `providers/index.ts:164` `toNudgeMarket` + `lib/profiling/nudges.ts` | 판정 규칙은 기획 확정본. 입력값은 수급 픽스처·감성·합성 가격·변동성 백분위 픽스처·보유 종목 | 입력 카드별로 다름 | — | ⚪ | 입력(수급·가격·백분위)이 실데이터가 되면 따라서 실데이터가 된다 |
| **기여도 분해**(신호별 비중 %) | `insight-cards.tsx:294,691` ← `fixtures.ts:87` `CONTRIBUTION_FIXTURE` | 픽스처(손으로 정한 가중치) | — | — | 🟡 | 모델 `pred_contrib` → 피처 묶음(기술·재무·감성·수급)별 합. 현재 모델 피처는 Alpha158 기술지표뿐이라 재무·감성·수급 항목은 모델에 없다 |
| **수급**(개인·외국인·기관 20영업일 순매수, 억원) | `insight-cards.tsx:311-339,700` ← `fixtures.ts:62` `SUPPLY_FIXTURE` | 픽스처(시드 고정 난수) | 2025-09-04 ~ 2025-10-02 | KRX 데이터 이용 조건 확인 필요(`providers/index.ts:71` TODO) | 🔵 | pykrx 조회 실패(§5, KRX 로그인 필요). KRX 계정과 약관 확인 후 수집. 기타법인 포함해야 합계가 0이 된다 |
| **뉴스 감성** 삼성전자(일별 점수·기사 수) | `insight-cards.tsx:388,709` ← `providers/sentiment-fixture.ts` | **실데이터**: BigKinds 수동 다운로드 기사 8,920건을 KR-FinBERT로 채점 | 2025-12-02 ~ 2025-12-21 (20일 창) | BigKinds: 가공 데이터 Git 비보관 결정과 충돌(아래 §4) | ✅ | 정적 스냅샷이다. 상세 화면 기준일(2025-10-02)과 기간이 맞지 않는다(`sentiment-fixture.ts:10`) |
| 뉴스 감성 삼성전자 대표 기사 3건(제목·언론사) | `insight-cards.tsx:452` ← `sentiment-fixture.ts:119` | 실제 기사 제목 | 2025-12-21 | 기사 제목을 공개 레포에 보관하고 공개 화면에 노출 중 | ✅ | 제목 노출 가능 여부 확인. 안 되면 건수·점수만 표시 |
| 뉴스 감성 현대차 | `fixtures.ts:69` `HYUNDAI_SENTIMENT` | 합성(난수) + "[합성 픽스처]" 제목 | 삼성전자와 같은 날짜 | — | ⚪ | 현대차 BigKinds 기사 수동 다운로드 후 같은 스크립트(`frontend/scripts/build_sentiment_fixture.py`)로 생성 |
| **위험/변동성**: 연 변동성 % | `insight-cards.tsx:480` ← `providers/index.ts:143` `riskSnapshot` | 합성 가격 곡선에서 계산 | 60거래일 | — | 🟡 | 실제 일봉만 연결하면 계산식은 그대로 쓴다 |
| 위험/변동성: "시장 상위 N%" | `insight-cards.tsx:482` ← `fixtures.ts:192` | 픽스처(손으로 정한 백분위) | — | — | 🔵 | 전 종목 60일 변동성 분포(전 종목 일봉) |
| 위험/변동성: 3개월 고점 대비 · 최근 3거래일 | `insight-cards.tsx:497,500` ← `riskSnapshot` | 합성 가격에서 계산 | 60거래일 | — | 🟡 | 실제 일봉 연결 |
| **재무** 6지표(PER·PBR·ROE·영업이익률·부채비율·매출 증가율) | `insight-cards.tsx:510,723` ← `fixtures.ts:165` | 픽스처("실제 공시값이 아니다") | "최근 4개 분기 합산" 라벨만 있음 | DART Open API(무료 키) | 🟡 | `value_pipeline` DART 수집기(`backend/analysis/text/value_pipeline/collectors.py:248`)가 PER·PBR·ROE·매출 증가율·부채비율을 계산한다. 영업이익률은 추가해야 하고, 수집기는 연간 기준이라 "4개 분기 합산" 라벨과 다르다. 주식수 as-of 문제(PR #67 후속)도 남아 있다 |
| **성향 프로필 8축**(데모 슬라이더) | `insight-cards.tsx:534` ← Supabase `ips_profiles.profile_payload.style_axes` / `mock-data.ts:128` | 설문 v1.1 응답(로그인) / 데모 값 | 설문 시점 | — | ✅ | 비로그인은 김민지 데모(⚪) |

## 4. /performance

페이지 `frontend/app/performance/page.tsx` · 데이터 `frontend/lib/performance-data.ts:52` → `frontend/artifacts/performance/comparison_results.json`(없음) → mock `frontend/lib/mock-performance.ts`

결과 파일을 만드는 러너는 있다(`backend/analysis/chart/experiments/comparison/runner.py:562`). 시장 심리 피처(`backend/analysis/chart/experiments/features/psychology/`, PR #69)도 main에 있다. 다만 러너를 돌린 결과가 커밋되지 않아 화면은 샘플을 보여 준다.

| 화면 위치 | 코드 출처 | 원천 | 기간 | 약관 메모 | 분류 | 실데이터 전환에 필요한 것 |
|---|---|---|---|---|---|---|
| 4런 지표표(AUC·적중률·Brier·ECE·Sharpe·MDD·누적수익률·거래 수) | `performance-dashboard.tsx:135,312` ← `mock-performance.ts:5` | mock("화면 검증용 샘플") | — | — | 🟡 | 러너 실행 → `comparison_results.json`을 `frontend/artifacts/performance/`에 둔다. 전 종목 일봉·피처 준비 필요 |
| 급변 구간 서브샘플 | `performance-dashboard.tsx:154` | mock | — | — | 🟡 | 위와 같음 |
| A vs B 비교(전체·급변) | `performance-dashboard.tsx:160-168` | mock | — | — | 🟡 | 위와 같음 |
| 결론 문구 | `performance-dashboard.tsx:188` ← `performance-data.ts:48` | 샘플 고정 문구 | — | — | 🟡 | 결과 파일이 있으면 `buildExperimentConclusion`이 생성 |
| 헤더의 성향·시장 브리핑 | `performance/page.tsx:12` | **항상 mock**(로그인해도 Supabase를 조회하지 않음) | — | — | ⚪ | 대시보드와 같은 조회로 바꾸기 |

## 분류별 개수

위 표의 행 기준(43행).

| 분류 | 개수 |
|---|---|
| ✅ 연결 | 8 |
| 🟡 있음·세팅미완 | 18 |
| 🔵 새로확보 | 4 |
| ⚪ 데모유지 | 13 |
| ⛔ 사용불가 | 0 (화면 밖 네이버 경로는 §약관 이슈) |

✅ 8개 중 6개는 사용자가 직접 답한 설문 결과이고, 시장 데이터로 ✅인 것은 **삼성전자 뉴스 감성 1종(점수·대표 기사)뿐**이다.

## 실데이터 전환 우선순위 Top 5 (작업량 대비 효과)

1. **가격 계열**(현재가·등락률·가격 추이·연 변동성·고점 대비·3거래일 수익률, 6행): 삼성전자 일봉이 이미 레포에 있고 계산식도 있어서, 원천만 바꾸면 된다. 수급 외 넛지 입력도 함께 실데이터가 된다.
2. **시장 브리핑 지수**(KOSPI·KOSDAQ·KOSPI 200): FDR로 로그인 없이 조회되는 것을 확인했다. 모든 화면 맨 위에 있어서 첫인상이 바뀐다. Supabase 시드 값이 "샘플" 배지 없이 보이는 문제도 같이 고친다.
3. **/performance 비교실험 실행**: 러너와 심리 피처가 main에 있다. 연구 질문 ①(A/B)의 결과 그 자체라 중간보고서에 가장 직접 쓰인다.
4. **재무 6지표**: DART 수집기가 이미 머지돼 있다. 영업이익률 추가, 연간/분기 라벨 정리, 주식수 as-of 후속이 필요하다.
5. **뉴스 감성 기간 정렬 + 현대차 실데이터**: 스크립트가 있어 현대차는 기사 다운로드만 하면 된다. 상세 기준일을 감성 기간(2025-10-29 ~ 12-31 코퍼스) 안으로 맞추면 카드 간 기간 불일치도 사라진다.

그다음은 신호 파이프라인(전 종목 추론 → 순위·신호등 → 백테스트 밴드·적중률 → `predictions` 적재)이다. 효과는 가장 크지만(10행 이상) 작업량도 가장 크다.

## 5. pykrx 조회 결과 (2026-09-19)

환경: pykrx 1.2.9, Python 3.14, 로컬(WSL). 받은 데이터는 커밋하지 않았다.

| 조회 | 호출 | 결과 |
|---|---|---|
| 삼성전자 2025-12 투자자별 순매수(개인·외국인·기관합계·기타법인) | `stock.get_market_trading_value_by_date("20251201", "20251231", "005930", on="순매수")` | ❌ 실패. `KRX 로그인 실패: KRX_ID 또는 KRX_PW 환경 변수가 설정되지 않았습니다.` 다음 `Expecting value: line 1 column 1 (char 0)`. 빈 DataFrame(0×0) 반환 |
| KOSPI 일봉 2025-12 | `stock.get_index_ohlcv_by_date("20251201", "20251231", "1001")` | ❌ 실패. 같은 JSON 디코딩 오류 후 `KeyError: '지수명'` |

해석: 현재 pykrx는 KRX 정보데이터시스템 **회원 로그인**을 요구하고, 로그인 없이 요청하면 KRX가 JSON이 아닌 응답을 돌려준다. 수급 카드를 실데이터로 바꾸려면 KRX 계정과 그 이용 조건 확인이 먼저다.

참고(과제 범위 밖 추가 확인): FinanceDataReader `fdr.DataReader("KS11", "2025-12-01", "2025-12-31")`는 로그인 없이 정상 조회됐다(2025-12-30 종가 4,214.17). 투자자별 수급은 FDR에 없다.

## 6. 약관 이슈

### 네이버 검색 API (2026-09-07 약관 변경)

변경 내용: 검색 결과를 AI 입력·학습·평가·노출에 쓰는 것과 저장·캐싱(단기 임시 보관 제외)이 금지됐다. 코드는 이번 PR에서 고치지 않았고, 이어지는 경로만 적는다.

| 함수 | 위치 | 하는 일 | 이어지는 산출물 | 화면 |
|---|---|---|---|---|
| `collect_news` | `backend/analysis/text/value_pipeline/collectors.py:58` | BigKinds 워크북이 그 날짜를 덮지 않으면 네이버로 폴백(`:100-110`) | 일별 `ValueSignal` JSON의 뉴스 피처. `news_source`가 `naver_api`/`naver`로 기록됨 | 없음 |
| `_fetch_naver_news_api` | `collectors.py:168` | `openapi.naver.com/v1/search/news.json` 호출(`NAVER_CLIENT_ID`/`SECRET`가 있을 때) | 위 JSON의 감성 점수(KR-FinBERT = AI 입력), 핵심 사건(Gemini LLM = AI 입력), `key_events` 문장(= 저장) | 없음 |
| `_crawl_naver_news` | `collectors.py:216` | `search.naver.com` 검색 결과 페이지 크롤링(키가 없을 때) | 위와 같음 | 없음 |
| LLM 캐시 | `backend/analysis/text/value_pipeline/llm.py:37` `llm_cache/` | LLM 응답을 파일로 동결 | 네이버 기사로 만든 요약이 디스크에 남음 | 없음 |

- 경로가 열리는 조건: BigKinds 워크북이 없는 날짜. 배치(`value_pipeline/batch.py`)도 같은 `collect_news`를 쓴다.
- 화면에는 이어지지 않는다. 화면의 뉴스 감성(`sentiment-fixture.ts`)은 BigKinds 코퍼스만 쓴다.
- 이미 추적 중인 네이버 유래 산출물: `backend/analysis/text/value_pipeline/output_sample/005930_2026-05-29.json` (`news_source: naver_api`, `social_source: naver`, `llm_used: true`). 아래 목록 참고.
- 이번 PR에서 `llm_cache/`를 `.gitignore`에 추가했다(아직 추적 파일은 없음).

### BigKinds

- 결정 문서(`docs/decisions/bigkinds-acquisition.md`)는 "뉴스 원문 Excel과 가공 데이터는 Git에 올리지 않는다"고 정했다.
- 이번 PR에서 원본 `data/005930/삼성전자_20220101-20221231.xlsx`(약 24MB)를 추적 해제했다. **히스토리 재작성은 하지 않아 과거 커밋(#39, `f1a751f`)에는 남아 있다.** 공개 레포 히스토리에서도 지우려면 `git filter-repo`와 강제 푸시가 필요하고, 팀 합의가 필요하다.
- 아래 목록의 가공 파일(기사 제목 포함)도 결정과 충돌한다. 삭제 여부는 팀 결정 사항이다.

## 7. 추적 중인 데이터 파일 전수 (git ls-files, csv/json/parquet/xlsx)

| 파일 | 크기 | 내용 | 기사 텍스트 |
|---|---|---|---|
| `data/005930/삼성전자_20220101-20221231.xlsx` | 24MB | BigKinds 원본(본문·URL) | **있음 → 이번 PR에서 추적 해제** |
| `backend/analysis/text/value_pipeline/005930_2022-01_news_monthly.json` | 24K | 2022-01 월간 감성 요약 | **있음**: 기사 제목 원문 165건(일별·월간 key_events) |
| `backend/analysis/text/005930_2022-06-15.json` | 4K | 일별 ValueSignal 예시(BigKinds) | **있음**: LLM이 요약한 사건 문장 6건 + BigKinds `news_id` |
| `backend/analysis/text/value_pipeline/output_sample/005930_2026-05-29.json` | 4K | 일별 출력 예시(**네이버 API·네이버 소셜**, LLM 사용) | **있음**: 사건 문장 5건 — 네이버 약관 대상 |
| `backend/analysis/text/data/processed/news_sentiment_daily.csv` | 4K | 삼성전자 일별 감성 점수·기사 수 | 없음(날짜·건수·점수만) |
| `backend/analysis/chart/data/raw/005930.parquet` | 152K | 삼성전자 일봉(FDR) 2010-01-04 ~ 2026-06-19 | 없음 |
| `backend/analysis/chart/data/processed/005930.parquet` | 3.1M | 삼성전자 피처 174열 | 없음 |
| `backend/analysis/chart/data/ticker_metadata.csv` | 160K | 종목 코드·이름·상장폐지 여부 | 없음 |
| `backend/analysis/chart/experiments/configs/universes/kospi_all_2024-12-30.csv` | 40K | KOSPI 유니버스 | 없음 |
| `backend/analysis/chart/experiments/features/samples/psychology_market_v1_sample.csv` (+ `.meta.json`) | 4K | 심리 피처 샘플 24행 | 없음 |
| `frontend/test-results/.last-run.json` | 4K | Playwright 마지막 실행 결과 | 없음 |
| `schema/*.json` (4개) | — | 스키마·예시 | 없음 |

csv/json/parquet/xlsx는 아니지만 기사 텍스트가 든 추적 파일:

- `frontend/lib/providers/sentiment-fixture.ts` — BigKinds 기사 제목 3건 + 언론사명(화면 노출 중)
