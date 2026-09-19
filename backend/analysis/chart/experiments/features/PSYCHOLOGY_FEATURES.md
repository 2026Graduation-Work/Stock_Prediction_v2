# 시장 심리 피처 정의 (psychology_market_v1)

A/B 비교실험의 **Treatment 조건**에 넣을 시장 심리 피처의 정의서다. 계산 코드는
`experiments/features/psychology/`, 생성 CLI는
`experiments/features/build_psychology_features.py`, 검증 테스트는
`experiments/tests/test_psychology_features.py`에 있다.

이 문서와 코드는 **피처 생성까지만** 다룬다. 학습·백테스트·실험 실행은 포함하지 않는다.

## 1. 심리 데이터의 세 층

이 프로젝트에서 "심리"는 세 가지 다른 것을 가리키며, 쓰이는 위치가 서로 다르다.
혼동하면 개인정보·편향 문제로 이어지므로 아래 구분을 지킨다.

| 층 | 예 | 쓰이는 곳 | 이번 작업 범위 |
| --- | --- | --- | --- |
| **시장 심리 피처** | 이 문서의 4개 피처 | **모델 인풋** (`features.treatment`) | ✅ 이번 범위 |
| 뉴스 감성 지수 | `news_sentiment` (text 블록) | 모델 인풋, 추후 결합 | ❌ 별도 트랙 |
| 개인 설문 기반 IPS | profiling 블록의 성향 점수 | **결과 번역·정렬 레이어에만** | ❌ 모델 피처로 쓰지 않음 |

개인 설문 기반 IPS를 모델 피처로 쓰지 않는 이유는 두 가지다. 첫째, 개인 응답이
가격 예측 모델의 학습 데이터로 들어가면 개인정보가 모델 가중치에 섞인다. 둘째,
"성향이 공격적인 사용자에게 상승 예측이 더 많이 나오는" 순환 구조가 생겨 예측
자체가 편향된다. IPS는 AGENTS.md의 **소프트 틸트** — 정렬·가중치·설명에만 쓴다.

### 이름 규약

기존 실험 설정에 나오는 `synthetic_psychology_index`는 **테스트 픽스처**다
(`comparison/tests/test_runner.py`의 `np.sin(phase / 7)`). 실제 피처가 아니다.
이 문서의 피처는 모두 `psych_` 접두사를 쓰며 `synthetic_`을 쓰지 않는다.

## 2. 입력과 산출물

- 입력: 저장소의 가격·거래량 계열 (`data/processed/<Code>.parquet`의 `Date`,
  `Code`, `Close`, `Volume`). 외부 API 호출·신규 수집·뉴스 데이터를 쓰지 않는다.
- 산출물: `data/external/psychology_market_v1.parquet`
  (`ONBOARDING.md` §9 추가 피처 계약: `Date | Code | AvailableDate | 숫자 컬럼`)
- 메타데이터: 같은 경로의 `.meta.json` (설정·버전·입력 지문·행 수)
- 산출물과 feature store는 **Git에 올리지 않는다.** 저장소에는 생성 스크립트,
  이 문서, `samples/`의 소규모 검증 샘플만 둔다.

## 3. 피처 정의

기호: `C_t` 종가, `V_t` 거래량, `r_t = ln(C_t / C_{t-1})`.
모든 창은 **기준일 `t`를 포함해 과거 방향으로만** 닫혀 있고, 창이 다 차지 않은
구간은 값을 만들지 않고 행 자체를 남기지 않는다(0으로 채우지 않는다).

### 3.1 `psych_fear_greed` — 공포·탐욕 (윈도우 20거래일)

```
fear_greed_t = tanh( Σ_{i=t-19..t} r_i / ( sd_20(r)_t · √20 ) )
```

`sd_20`은 표본표준편차(ddof=1). 분모가 0이면 결측 처리한다.

- **대응 개념:** 공포·탐욕(fear & greed). 탐욕 국면은 "낮은 변동성에서 꾸준히
  오르는" 형태로, 공포 국면은 "높은 변동성에서 무너지는" 형태로 나타난다는 관찰을
  위험조정 모멘텀 하나로 표현한다.
- **근거:** 상승폭(`roc_20`)과 변동성(`std_20`)은 baseline Alpha158에 이미 각각
  들어 있지만, **두 값의 비율**은 없다. 같은 +5%라도 변동성이 절반이면 심리적
  의미가 다르다. GBDT는 두 피처의 비율을 축 정렬 분할로 근사하기 어려우므로 비율을
  직접 주는 것이 추가 정보가 된다.
- **한계:** 이것은 심리의 직접 측정이 아니라 가격 통계다. 실적 재평가로 인한 저변동
  상승도 "탐욕"과 같은 값을 낸다. 시장 전체가 아니라 종목 단위 값이다.

### 3.2 `psych_herding` — 군집행동 (윈도우 20거래일)

```
herding_t = Σ_{i=t-19..t} sign(r_i) · V_i / Σ_{i=t-19..t} V_i
```

거래량 가중 방향 일치도. 값의 **크기**가 군집 강도, **부호**가 쏠린 방향이다.
수익률이 정확히 0인 날은 0으로 기여한다.

- **대응 개념:** 군집행동(herding). 군집은 "많은 참여자가 같은 방향으로 동시에
  거래하는 것"이므로, 거래량이 실린 날의 방향이 한쪽으로 몰린 정도가 직접적인
  관측치다.
- **근거:** Alpha158의 `cntp/cntn`(상승일 수)은 거래량을 반영하지 않아 소액 거래와
  대량 거래를 같게 센다. `vsump/vsumn`은 거래량 변화량의 방향이지 **가격 방향과
  거래량의 결합**이 아니다. 이 피처는 그 결합을 명시한다.
- **한계:** 지수 편입·수급 이벤트로 생긴 일방향 대량 거래도 같은 값을 만든다.
  종목별 값이므로 시장 전체 군집(횡단면 분산 기반 CSAD류)은 잡지 못한다. 거래정지
  구간은 거래량 0이라 값이 희석된다.

### 3.3 `psych_overreaction` — 과잉반응 (단기 5거래일 / 기준 60거래일)

```
r5_t = ln(C_t / C_{t-5})
z_t  = ( r5_t − mean_60(r5)_t ) / sd_60(r5)_t
overreaction_t = tanh( z_t / 2 )
```

- **대응 개념:** 과잉반응(overreaction, De Bondt–Thaler)과 단기 반전 압력. 최근 5일
  수익률이 그 종목 자신의 최근 분포에서 얼마나 벗어났는지를 본다. `+`는 과열,
  `−`는 과매도 방향이다.
- **근거:** 과잉반응은 절대 수익률이 아니라 **그 종목의 평소 변동 대비** 얼마나
  튀었는지로 판단해야 한다. 종목별 z-score는 변동성이 큰 종목과 작은 종목을 같은
  척도로 비교하게 해 준다. Alpha158에는 `roc_5`·`std_20` 등 원재료는 있으나 이
  형태의 자기 정규화 이격은 없다.
- **한계:** 과잉반응 가설은 이 값과 **반대 방향**으로 미래 수익이 움직인다고 보지만,
  같은 값이 모멘텀 지속으로도 해석된다. 어느 쪽인지는 이 피처가 정하지 않고 학습
  결과가 정한다. 즉 이 피처는 "과잉 정도"를 주고 해석은 모델에 맡긴다.

### 3.4 `psych_disposition` — 처분효과·손실회피 (윈도우 60거래일)

```
P_t   = Σ_{i=t-59..t} C_i · V_i / Σ_{i=t-59..t} V_i     (거래량가중 평균단가)
cgo_t = ( C_t − P_t ) / P_t                              (미실현 손익 비율)
disposition_t = tanh( cgo_t / 0.10 )
```

- **대응 개념:** 처분효과(disposition effect, Shefrin–Statman)와 손실회피. 보유자
  평균 취득단가 대비 현재가가 이익이면 조기 실현(매도) 압력이, 손실이면 손실 확정을
  피하려는 보유 지속 성향이 생긴다는 관찰이다.
- **근거:** Grinblatt–Han의 capital gains overhang과 같은 구성이다. 실제 취득단가
  분포는 관측할 수 없으므로 최근 60거래일 거래량가중 평균체결가를 프록시로 쓴다.
  Alpha158의 `vwap_0`는 **당일** 값이라 이 괴리를 담지 못한다.
- **한계:** 60일 밖에서 매수한 장기 보유자의 취득단가는 반영되지 않는다. 회전율이
  매우 낮은 종목에서는 평균단가 추정이 불안정하다. `0.10`(10% 괴리)이라는 압축
  상수는 데이터로 적합한 값이 아니라 고정 상수이며, 바꾸려면 새 profile을 만든다.

### 3.5 요약 축 2개 (모델 인풋 아님)

```
psych_greed_fear_axis     = ( psych_fear_greed  + psych_disposition ) / 2
psych_crowd_pressure_axis = ( psych_herding     + psych_overreaction ) / 2
```

원지표의 **동일가중 평균**이다(가중치 탐색·튜닝을 하지 않는다). 화이트박스 원칙에
따라 화면·정렬·설명에서 "지금 이 종목의 심리 상태"를 한두 개 축으로 요약할 때 쓴다.
원지표와 함께 학습에 넣으면 완전한 선형종속이 생기므로 **`features.treatment`에는
넣지 않는다.**

### 3.6 요약표

| 컬럼 | 개념 | 윈도우 | 범위 | 모델 인풋 |
| --- | --- | --- | --- | --- |
| `psych_fear_greed` | 공포·탐욕 | 20 | [-1, 1] | ✅ |
| `psych_herding` | 군집행동 | 20 | [-1, 1] | ✅ |
| `psych_overreaction` | 과잉반응·단기반전 | 5 / 60 | [-1, 1] | ✅ |
| `psych_disposition` | 처분효과·손실회피 | 60 | [-1, 1] | ✅ |
| `psych_greed_fear_axis` | 위 요약 | — | [-1, 1] | ❌ 설명·정렬용 |
| `psych_crowd_pressure_axis` | 위 요약 | — | [-1, 1] | ❌ 설명·정렬용 |

피처 개수를 4개로 제한한 이유는 baseline이 161피처이기 때문이다. 추가분이 많으면
A/B 차이가 어느 개념에서 왔는지 해석할 수 없다.

## 4. 미래 정보(lookahead) 차단

두 겹으로 막는다.

1. **계산 시점.** 모든 롤링 창은 기준일 `t`를 포함해 과거로만 닫혀 있다. `t` 이후
   가격·거래량은 어떤 피처에도 들어가지 않는다.
2. **사용 시점.** 산출물의 `AvailableDate`는 항상 `t`의 **다음 거래일**이다. `t`
   종가로 계산한 값이므로 `t` 당일 행에는 붙일 수 없다. 결합 시
   `apply_period: one_day`가 이 규약을 강제한다.

검증 테스트:

- `test_future_rows_do_not_change_past_features` — 뒤쪽 날짜를 잘라내도 앞 구간 값이
  바이트 단위로 같다.
- `test_changing_a_future_price_does_not_change_earlier_features` — 특정 날짜 이후
  가격·거래량을 흔들어도 그 이전 피처가 불변이고, 그 이후 값은 실제로 바뀐다
  (대조군까지 확인해 테스트가 헛돌지 않게 한다).
- `test_available_date_is_strictly_after_observation_date`

**워밍업은 65거래일이다** (`max(20+1, 20+1, 5+60, 60)`). 종목별로 이 구간이 채워지기
전에는 행을 만들지 않는다. 0으로 채우면 "중립 심리"라는 없는 정보를 만드는 것이므로
그렇게 하지 않는다.

## 5. 결정론

- 난수·피팅·전역 통계(전체 기간 표준화)를 쓰지 않는다. 압축 상수(`tanh` 나눗수)는
  사람이 고른 고정값이며 학습 데이터를 보고 조정하지 않는다.
- 입력 행 순서가 달라도 출력이 같다.
- 메타데이터에 `feature_profile`, `generator_version`, 전체 `config`, 입력·출력
  지문(SHA-256), 행 수, 실행 환경(python/pandas/numpy 버전)을 기록한다.
- 윈도우나 상수를 바꾸면 기존 산출물을 덮어쓰지 말고 **새 profile 이름**
  (`psychology_market_v2`)과 새 경로를 쓴다.

검증 테스트: `test_repeated_runs_are_identical`,
`test_row_order_does_not_change_output`, `test_cli_output_is_reproducible_across_runs`.

## 6. 생성과 결합 절차

```bash
# 0) backend/analysis/chart/ 에서 실행한다.

# 1) 심리 피처 원본을 만든다.
#    실험 시작일보다 최소 65거래일 앞선 기간을 포함해야 실험 구간에 결측이 없다.
python -m experiments.features.build_psychology_features \
    --price-dir data/processed \
    --out data/external/psychology_market_v1.parquet

# 2) 기존 도구로 treatment feature store를 만든다(이 스크립트가 하지 않는다).
python -m experiments.features.build_feature_panel \
    --config experiments/configs/local_psychology.yaml

# 3) A/B 비교실험은 별도 작업이다. 이 문서의 범위가 아니다.
```

`experiments/configs/local_psychology.yaml`의 관련 부분:

```yaml
features:
  profile_name: psychology_market_v1
  base_processed_dir: data/processed
  base_columns: "*"
  materialized_dir: data/feature_store/psychology_market_v1
  sources:
    - name: psychology_market
      path: data/external/psychology_market_v1.parquet
      apply_period: one_day
      columns:
        - psych_fear_greed
        - psych_herding
        - psych_overreaction
        - psych_disposition
        - psych_greed_fear_axis
        - psych_crowd_pressure_axis
      # 워밍업 구간은 값이 없다. zero로 채우면 없는 "중립 심리"를 만들게 되므로
      # 행을 제거하고, 그 구간이 실험 기간과 겹치지 않는지 아래 주의사항으로 확인한다.
      missing: { policy: drop, add_indicator: false }
```

`experiments/comparison/config.yaml`의 관련 부분:

```yaml
features:
  baseline_model_file: ../../core/models/baseline_h5_u175_d150_train2022_2024_holdout2025.txt
  treatment:
    - psych_fear_greed
    - psych_herding
    - psych_overreaction
    - psych_disposition

profiles:
  stable:
    data:
      baseline_price_dir: ../../data/processed
      treatment_price_dir: ../../data/feature_store/psychology_market_v1
```

`config.example.yaml`은 이번 작업에서 바꾸지 않았다. 그 파일의
`synthetic_psychology_index`/`news_sentiment` 목록은 `comparison/tests/test_runner.py`가
값으로 검증하고 있어, 바꾸려면 러너 테스트를 함께 고쳐야 한다. 실제 실험은 위처럼
`config.yaml`(Git 제외)에서 설정한다.

### 실험 구간을 잡을 때 주의

러너는 baseline store와 treatment store의 `Date`·`Code`·라벨·161피처가 **완전히
같을 때만** 실행된다(`_assert_ab_alignment`). 심리 피처 때문에 행이 어긋나는 경우는
둘뿐이며 모두 실행 중단으로 드러난다.

1. **워밍업 + 1거래일.** treatment store는 각 종목의 첫 거래일부터 65거래일이 지난
   **그 다음 거래일**부터 시작한다. `train_start`를 그보다 이르게 잡으면 안 된다.
2. **기간 중 신규 상장.** 실험 기간 안에서 상장한 종목은 그 종목만 시작이 늦어져
   행이 어긋난다. `tickers` 목록에서 빼거나 기간을 조정한다.

`missing.policy: zero`로 바꾸면 이 오류는 사라지지만, 워밍업 구간이 "심리 중립"이라는
없는 관측으로 채워진다. 권장하지 않는다.

## 7. 생성 검증

저장소에는 종목 하나의 Alpha158 패널이 커밋되어 있다
(`backend/analysis/chart/data/processed/005930.parquet`, `.gitignore`의 명시적 예외).
전체 `data/processed`(약 7GB)는 로컬 생성물이다. 참고로 `data/005930/`의 xlsx는 가격이
아니라 BigKinds 뉴스 기사 원문이므로 이 피처의 입력이 아니다.

### 7.1 실제 종목 검증 (005930, 2023년)

```bash
python -m experiments.features.build_psychology_features \
    --price-dir data/processed --codes 005930 \
    --start 2023-01-01 --end 2023-12-31 --out /tmp/psych_005930_2023.parquet
```

196행 / 1종목 / 2023-03-31~2023-12-29가 생성된다(입력 2023-01-02부터, 워밍업
65거래일 소진). 결측 0, 모든 값이 [-1, 1] 안, `AvailableDate > Date`.

테스트 `test_real_ticker_generation`, `test_real_ticker_has_no_lookahead`,
`test_real_ticker_generation_is_deterministic`가 이 패널로 CI에서 같은 검증을 한다.
파일이 없는 환경에서는 skip된다.

### 7.2 다종목·형식 검증 (합성 패널)

커밋된 실제 데이터가 한 종목뿐이라, 다종목 결합과 feature store 왕복 검증은 시드를
고정한 합성 OHLCV 패널(`psychology/demo_panel.py`)로 한다.

```bash
python -m experiments.features.build_psychology_features \
    --demo --out /tmp/psychology_demo.parquet --sample-csv /tmp/sample.csv
```

`samples/psychology_market_v1_sample.csv`가 이 합성 패널로 만든 소규모 샘플이다.
**여기 있는 숫자는 연구 결과가 아니다.** 실제 값은 `data/processed`를 채운 뒤 같은
스크립트를 `--price-dir`로 돌려 얻는다.

## 8. 이번 작업에서 하지 않은 것

- 학습·백테스트·A/B 실험 실행. `comparison_results.json` 등 결과 파일을 만들지 않았다.
- 러너·모델 파일 수정.
- 뉴스 감성 결합(별도 트랙), 개인 IPS의 모델 투입(구조적으로 하지 않음).
- 실제 시장 데이터로 만든 피처 값. 데이터 준비 후 위 절차로 생성한다.
