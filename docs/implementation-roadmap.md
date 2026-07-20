# 구현 및 통합 로드맵

> 기준일: 2026-07-21. PR 상태는 수시로 변하므로 병합할 때 이 문서의 상태 표도 갱신한다.

## 목표와 완료 판정

최종 산출물은 설문 결과를 성향별 모델 선택과 설명에 사용하고, 동일 조건 A/B 실험으로
"심리 지수를 반영하면 예측이 나아지는가?"에 정량 답변하는 재현 가능한 데모다.

완료는 아래 세 조건을 모두 만족한 상태다.

1. **연구**: 실제 결합 데이터로 4런을 실행하고 전체·급변 구간 지표와 manifest를 보관한다.
2. **제품**: 로그인 → 최초 설문 → 대시보드 → 종목 상세 → 성능 비교가 실제 데이터 경로로 이어진다.
3. **증빙**: 같은 config로 결과를 재현할 수 있고, 화면의 모든 수치에 원천·모델·기준일이 표시된다.

샘플·합성 fixture·mock fallback은 UI와 장애 경로 검증에만 사용하며 연구 결과로 보고하지 않는다.

## 통합 현황

2026-07-21 기준 열린 PR의 안전한 처리 순서는 다음과 같다.

| 순서 | PR | 역할 | 현재 게이트 |
| --- | --- | --- | --- |
| 1 | #24 | 회의 피드백·시장 정보 UI | CI 확인 후 리뷰·병합 |
| 2 | #29 → #30 → (#31, #33) → #34 | 온보딩 → 인증 조회 → 실제 artifact·상세 조회 → E2E | 앞 PR 병합 후 차례로 `main` retarget |
| 3 | #35 | 사용자 노출 HITL 문구 | #33 뒤에 병합해 `display.ts` 충돌 방지 |
| 4 | #27 → #28 | 평가 경계 보완 → 비교 러너 실행 준비 | CI 확인 후 순차 병합 |
| 5 | #36 → #22 | BigKinds 경로 계약 → 가치투자 오케스트레이션 | #36 병합 후 #22의 main 충돌 해소·전체 test |
| 6 | #37 → #26 | 누수 차단 보완 → 외부 피처 결합 | #37 병합 후 기존 4개 리뷰 재확인 |
| 독립 | #32 | 이 구현·통합 로드맵 | 다른 코드 PR과 무관하게 리뷰·병합 |

병합 원칙:

- 같은 파일을 만지는 체인은 반드시 앞 PR부터 병합하고 다음 PR의 base를 `main`으로 바꾼다.
- #22와 #26은 각각 보조 PR #36·#37을 먼저 병합하고 부모 브랜치에서 CI와 리뷰를
  다시 확인하기 전 승인하지 않는다.
- 각 단계에서 CI가 초록인지 확인하고, 스키마 파일은 이 과정에서 변경하지 않는다.

## P0 연구 경로

### 1. 비교 입력 데이터 고정

`backend/analysis/chart/data/comparison/comparison_input.parquet` 한 행은
`날짜 × 종목` 관측치다. 생성 단계에서 아래를 확정하고 manifest에 기록한다.

| 항목 | 고정 계약 |
| --- | --- |
| 조인 키 | `Date`: datetime, `Code`: 앞자리 0을 보존한 6자리 문자열 |
| Baseline | 기준 LightGBM 모델의 차트 피처 161개 |
| Treatment 전용 | `synthetic_psychology_index`, `news_sentiment` |
| 성향 라벨 | stable=`Target_H20`, aggressive=`Target_H5`, 각각 0/1 |
| Trading | `Next_Day_Return` |
| 급변 구간 | `Market_Volatility` 일평균 상위 20% 날짜 |
| 재현성 | 명시적 종목 목록·학습/평가 기간·고정 시드·공용 평가함수 |

결측 뉴스 감성을 중립값으로 볼지, 해당 행을 제외할지는 데이터 생성 단계의 결정으로 남기고
러너 안에서 임의 보간하지 않는다. A/B는 피처 세트 외의 행·라벨·기간이 완전히 같아야 한다.

### 2. 4런 실행과 결과 반영

`backend/analysis/chart/`에서 실행한다.

```bash
cp experiments/comparison/config.example.yaml experiments/comparison/config.yaml
python -m experiments.comparison.runner --config experiments/comparison/config.yaml
```

보관할 산출물:

- `comparison_results.json`: 프론트 성능 화면 입력
- `experiment_manifest.json`: 시드·기간·피처·행 해시·급변일
- `four_run_metrics.csv`, `volatile_subsample_metrics.csv`, `comparison_deltas.csv`
- `predictions/*.parquet`: OOS 예측 감사 자료

`comparison_results.json`은 `frontend/artifacts/performance/`에 전달한다. PR #31의
`frontend/lib/performance-data.ts`가 빌드 시 이 파일을 읽어 화면 데이터로 변환한다.
실제 artifact가 없을 때만 샘플 배지를 유지하고, 파일이 있는데 구조 또는 B-A 델타가
틀리면 빌드를 실패시킨다.

### 3. 결론 작성 규칙

- Sharpe를 1차, MDD를 2차 Trading 지표로 보되 모든 ML·Trading 지표를 함께 공개한다.
- 전체 구간과 급변 구간을 모두 보고하고 불리한 결과를 숨기지 않는다.
- 관측 차이와 통계적 유의성을 구분한다. 검정이 없으면 "유의한 개선"이라고 쓰지 않는다.
- negative result도 그대로 결론으로 채택한다.

## P0 제품 경로

### 1. 인증·프로필

- env 없음: 데모 로그인과 mock fallback으로 CI·리허설이 가능해야 한다.
- env 있음: Supabase Auth 사용자와 `users`·`ips_profiles`가 연결되어야 한다.
- 최초 로그인은 `/survey`, 프로필 보유 사용자는 `/`, 로그아웃은 `/login`으로 이동한다.
- 설문 저장 후 새로고침해도 프로필과 회피 제약이 유지되어야 한다.

### 2. 대시보드·상세

- 대시보드 조회는 사용자 프로필·보유종목을 한 번만 읽고 추천·알림에 공유한다.
- `avoided_assets`는 DB 쿼리 단계에서 하드 필터로 적용한다.
- `/stocks/[code]`는 예측·Top3 근거·모델/기준일·리스크 고지의 출처를 표시한다.
- 현재 DB에는 과거 가격과 유사 신호 히스토그램 저장 계약이 없다. 임의 컬럼을 추가하지 말고
  chart output 저장 방식 또는 별도 테이블을 팀 합의한 뒤 실제 조회로 전환한다.
- 행동 제안 문구는 만들지 않는다. UI의 HITL 3버튼만 사용자의 선택을 받는다.

### 3. 성능 화면

- PR #31의 artifact 로더를 통해 `comparison_results.json`을 읽으며, 화면 컴포넌트는
  mock 또는 실제 데이터 출처와 무관하게 같은 뷰모델을 받는다.
- 샘플일 때 `샘플 데이터`와 중립적 placeholder를 표시한다.
- 실제 결과일 때만 러너 결과 배지를 표시하고 B-A를 결정적으로 요약한다.
- y축은 ML 지표 0~1처럼 고정하고, 개선·저하·동일을 같은 규칙으로 표현한다.

## 팀에서 필요한 입력

### 차트 담당

- 실제 비교 입력 parquet/csv와 컬럼 설명
- 명시적 종목 목록, 학습/평가 기간, 라벨 임계값·H 정의, 고정 시드
- 실행 가능한 config·학습 코드·기준 모델 artifact
- stable/aggressive 모델이 갈리는 정확한 규칙

### 텍스트 담당

- 종목별 BigKinds 원본과 실제 수록 기간. 현재 삼성전자 2025 파일 1개는 이름과 달리
  실제로 `2025-10-29~2025-12-31` 20,000건만 있어 앞 기간을 추가 다운로드해야 한다.
- `Date`·`Code` 키를 지킨 일별 `news_sentiment` 산출물
- 뉴스가 없는 거래일의 처리 규칙과 FinBERT 모델 버전
- #36을 #22에 병합해 `backend/analysis/text/data/raw/{code}/NewsResult_*.xlsx`
  정본 경로·실제 min/max 커버리지·겹침 dedup을 적용하고 silent fallback을 재검증

### DB·배포 담당

- 빈 Supabase 프로젝트에 migration·seed 적용 확인
- Vercel과 로컬의 URL·anon key 주입, Auth redirect URL 등록
- 실제 키는 저장소·회의록·스크린샷에 남기지 않는다.

### 팀 합의

- 최종 유니버스와 실험 기간
- `max_risk_tier` 1~5 휴리스틱
- 가격 이력·유사 수익률 분포의 DB 저장 계약
- LLM key-event/설명 출력 계약. 점수·필터·매매 행동에는 LLM을 사용하지 않는다.

## 독립적으로 선행 가능한 작업

팀 데이터가 오기 전에도 아래는 진행할 수 있다. 2~5는 PR #30~#34에서 스캐폴드와
회귀 테스트까지 준비했으며, 부모 PR 병합 후 실제 데이터로 전환한다.

1. 열린 PR 리뷰 해결 여부와 CI·base·충돌 상태 자동 점검
2. runner JSON ↔ 프론트 타입·델타 계약 검증
3. mock Supabase 기반 로그인→설문→대시보드 E2E 회귀 테스트
4. 기존 `predictions`·`prediction_features` 기반 종목 상세 조회 adapter와 mock fallback
5. 실제 artifact 부재·잘못된 artifact·DB 장애의 명시적 상태 UI
6. 발표용 재현 runbook과 데이터 provenance 체크리스트

## 통합 게이트

PR 또는 릴리스 후보는 관련 항목을 모두 통과해야 한다.

- Python: `ruff check .`, `pytest`
- Frontend: `pnpm lint`, `pnpm build`
- JSON: schema v1.0 검증과 고정 정렬
- 브라우저: 1440px·1024px, 콘솔 오류 0, 가로 overflow 없음
- E2E: 로그인 → 설문 → 대시보드 → 상세 → 성능 화면
- 연구: 실제 입력 hash·config·seed·manifest 보관
- 보안: secret 미커밋, 유료 기능 임의 활성화 없음
