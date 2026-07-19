# 차트 분석 블록

이 블록은 기술적 지표와 DT 계열 모델(LightGBM)을 사용해 상승·하락 확률을
산출하고, 해당 신호의 백테스트와 평가를 수행합니다. 결과는 투자 권유가 아닌
과거 데이터 기반의 실험 결과이며, 불확실성과 검증 조건을 함께 확인해야 합니다.

## 개발 환경

Python 3.10~3.12 환경에서 아래 명령을 `backend/analysis/chart/` 디렉터리에서 실행합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 데이터와 설정

원시·처리 데이터, 예측 캐시, 학습 캐시, 개별 실험 결과는 용량과 재현성 문제로
Git에 올리지 않습니다.

### 최초 데이터 구축과 갱신

Git clone 뒤에는 데이터가 없다. 각 실험자는 아래 순서로 공개 시장 가격을 수집하고
로컬에서 Alpha158 처리 패널을 만든다. `processed/`는 현재 약 7GB이므로 Git이나
Drive의 필수 배포물로 관리하지 않는다.

```bash
# 1. 최초 구축: 최근 10년 가격을 data/raw/에 수집한다.
python data_collectors/price_collector.py --mode full --start-date 2016-01-01

# 2. Alpha158·변동성·Triple Barrier 입력을 data/processed/에 생성한다.
python data_collectors/preprocess_data.py --mode full

# 이후 갱신: 새 거래일만 수집·전처리한다.
python data_collectors/price_collector.py --mode update
python data_collectors/preprocess_data.py --mode update
```

수집 결과는 `data/raw/<Code>.parquet`, 전처리 결과는
`data/processed/<Code>.parquet`에 저장된다. 수집 실패 종목은
`data/failed_downloads.csv`에서 확인한다. 실험 비교에 정확히 같은 데이터 시점이
필요한 경우에만 팀 Drive에 **raw 스냅샷**과 `DATA_MANIFEST.json`을 보관한다.
manifest에는 기준일, 종목 수, raw 파일 수, 전처리 코드 commit을 기록한다.
그 스냅샷은 재현 목적의 선택 항목이며, processed 전체를 공유하지 않는다.

공유되는 일반 실험 설정은 `experiments/configs/base.yaml` 하나의 템플릿뿐입니다.
구체적인 실험 설정은 아래처럼 로컬 파일로 복사해 만들며 Git에서 무시됩니다.

```bash
cp experiments/configs/base.yaml experiments/configs/local.yaml
# local.yaml에서 기간, horizon, barrier, 모델·전략 파라미터를 수정
```

학습 캐시 키는 parquet 파일명·크기·수정시각과 선택적인 `data.version`을 포함한다.
raw/processed를 갱신하면 보통 새 캐시가 생성된다. 같은 파일 메타데이터를 유지한 채
내용을 바꾼 특수한 경우에는 `local.yaml`의 `data.version`에 새 식별자를 넣어 캐시를
분리한다.

`core/config.example.yaml`은 서비스 추론용 로컬 설정 템플릿입니다. 필요할 때만
`core/config.yaml`으로 복사해 사용하며, 이 파일도 Git에 올리지 않습니다.

### 외부 피처 Parquet 입력 형식

뉴스 감성·재무 점수처럼 Alpha158에 없는 값을 학습에 추가할 때는 기존
`data/processed/`를 수정하지 않고, 별도 Parquet 파일을 만든다. 외부 피처 결합
도구는 아래 형식의 로컬 파일을 `data/external/`에서 읽어 별도
`data/feature_store/<profile>/`에 결합 패널을 만든다. 외부 데이터와 결합 결과는
Git에 올리지 않는다.

한 행은 한 종목의 한 피처 관측치이며, 다음 세 컬럼은 항상 필요하다.

| 컬럼 | 의미 | 예시 |
| --- | --- | --- |
| `Date` | 피처를 관측·계산한 기준일 | `2024-05-02` |
| `Code` | 앞자리 0을 보존한 6자리 종목 코드 | `005930` |
| `AvailableDate` | **모델이 이 값을 처음 사용해도 되는 거래일** | `2024-05-03` |

`AvailableDate`는 미래 정보 유입을 막기 위한 기준이다. 장 마감 뒤 집계한 5월
2일 뉴스 감성은 5월 3일을 `AvailableDate`로 기록한다. 재무제표는 실제 공시
시각을 반영해, 시장에서 알 수 있게 된 첫 거래일을 기록한다.

```text
# data/external/news_daily.parquet의 논리적 예시
Date        Code    AvailableDate    news_sentiment    article_count
2024-05-02  005930  2024-05-03       0.42              18
2024-05-03  005930  2024-05-07      -0.11               7

# data/external/financial.parquet의 논리적 예시
Date        Code    AvailableDate    financial_health_score    roe    debt_ratio
2024-03-31  005930  2024-05-16       8.2                       0.12   0.35
```

설정에서는 피처 값이 적용되는 기간을 아래처럼 사람이 읽기 쉬운 이름으로
선택한다.

```yaml
features:
  profile_name: "alpha158_text_financial_v1"
  # builder가 읽는 변하지 않는 Alpha158 원본. 이 경로는 학습에 직접 쓰지 않는다.
  base_processed_dir: "data/processed"
  base_columns: "*"  # "*"는 기존 Alpha158 전체, 목록을 쓰면 해당 컬럼만 사용
  exclude_columns: [] # base_columns에서 빼고 싶은 Alpha158 컬럼
  materialized_dir: "data/feature_store/alpha158_text_financial_v1"

  sources:
    # 하루짜리 정보: AvailableDate 당일에만 사용한다.
    # 일별 뉴스·SNS 감성처럼 다음 날 새 값이 들어오는 피처에 사용한다.
    - name: "news"
      path: "data/external/news_daily.parquet"
      apply_period: "one_day"
      columns: ["news_sentiment", "article_count"]
      missing: {policy: "zero", add_indicator: true}

    # 다음 업데이트 전까지 유지할 정보: 가장 최근 공개값을 계속 사용한다.
    # 분기 재무제표·재무 건전성 점수처럼 공시 후 다음 공시까지 유효한 피처에 사용한다.
    - name: "financial"
      path: "data/external/financial.parquet"
      apply_period: "until_next_update"
      columns: ["financial_health_score", "roe", "debt_ratio"]
      missing: {policy: "error", add_indicator: true}
```

- `one_day`: `AvailableDate`와 같은 거래일에만 값을 붙인다. 예: 5월 3일 뉴스
  감성은 5월 3일 행에만 사용한다.
- `until_next_update`: `AvailableDate`부터 다음 값이 공개되기 전까지 가장 최근
  값을 유지한다. 예: 5월 16일 재무 점수는 다음 공시값이 나오기 전까지 사용한다.
- 두 방식 모두 `AvailableDate`보다 이른 날짜에는 절대 값을 붙이지 않는다.
- `base_columns`에는 사용할 Alpha158 컬럼 목록을 넣을 수 있다. `Date`, OHLCV,
  `Sigma`, `Trading_Halt` 등 라벨 생성에 필요한 가격 메타데이터는 자동으로 남는다.
- `missing.policy`는 `zero`, `forward_fill`, `drop`, `error` 중 하나다. `add_indicator`
  를 켜면 해당 값이 원래 비어 있었는지를 나타내는 피처도 함께 만든다.
- 외부 파일 안에서 `(Code, Date, AvailableDate)`가 중복되면 안 되며, 숫자형
  피처만 넣는다. 같은 `(Code, AvailableDate)`에 두 값이 있어도 안 된다.
  `Y_Label`, 미래 수익률, 미래 가격은 넣을 수 없다.

외부 피처를 준비한 뒤 feature store를 한 번 생성한다. 이 과정은 원본
`data/processed/`를 수정하지 않는다.

```bash
# local.yaml 하나로 외부 피처 결합 패널을 생성한다.
python -m experiments.features.build_feature_panel --config experiments/configs/local.yaml

# 이어서 기존 학습·평가·백테스트 명령을 그대로 사용한다.
python experiments/train.py --config experiments/configs/local.yaml
python experiments/run_ml_evaluation.py --config experiments/configs/local.yaml
python experiments/run_backtest.py --config experiments/configs/local.yaml
```

`local.yaml`에서는 원본과 학습 데이터를 아래처럼 분리한다. builder는
`features.base_processed_dir`를 읽고, `train.py`·평가·백테스트는 기존처럼
`data.price_dir`만 읽는다. 따라서 feature store를 만든 뒤 같은 설정 파일을
수정할 필요가 없다.

```yaml
data:
  # 학습·검증·test·backtest가 읽는 결합 완료 패널
  price_dir: "data/feature_store/alpha158_text_financial_v1"

features:
  # build_feature_panel.py만 읽는 Alpha158 원본
  base_processed_dir: "data/processed"
  materialized_dir: "data/feature_store/alpha158_text_financial_v1"
  # sources, base_columns, labels, model 등은 위 예시처럼 설정
```

#### 외부 피처 실험 체크리스트

1. `data/external/`에 표준 Parquet을 준비한다. `AvailableDate`는 해당 값을
   모델이 처음 사용할 수 있는 거래일이어야 한다.
2. `local.yaml`에서 `base_columns`, `sources`, `one_day` 또는
   `until_next_update`, 결측 정책을 정한다.
3. `build_feature_panel.py`를 실행한다. 새 profile 경로를 사용하면 기존 실험
   feature store를 보존할 수 있다.
4. 같은 `local.yaml`으로 `train.py`를 실행한다. 모델은 결합 패널의 Alpha158와
   외부 피처를 함께 학습한다.
5. 같은 설정으로 평가와 백테스트를 실행한다. 라벨은 기존 `labels` 설정에 따라
   가격 데이터에서 다시 생성되며, 외부 피처를 넣어도 target 계산은 바뀌지 않는다.

새로운 뉴스·재무 컬럼을 추가하거나 뺄 때는 1~3단계와 `features` 설정만 바꾸면
된다. horizon·barrier·LightGBM 파라미터도 기존 `labels`·`model` 설정만 바꾸면
된다. 완전히 새로운 라벨 계산식 또는 모델 종류를 도입할 때만 별도 코드 확장이
필요하다.

feature store 안에는 종목별 `<Code>.parquet`과 `feature_manifest.json`이 생성된다.
manifest에는 입력 외부 파일의 fingerprint, 적용 기간, 결측 처리, 소스별 결측률이
기록된다. 같은 출력 경로에 이미 파일이 있으면 실수로 덮어쓰지 않고 실패하므로,
피처 구성을 바꿨을 때는 새 profile 이름과 경로를 사용한다.

## 실험 실행

처음 실행은 아래 순서가 기준이다. `local.yaml`의 `experiment_name`은 결과 폴더
이름이므로, 서로 다른 실험에는 반드시 다른 이름을 사용한다.

```bash
# 0. 기준 설정을 복사해 로컬 실험을 정의한다.
cp experiments/configs/base.yaml experiments/configs/local.yaml

# 1. raw 수집과 processed 생성은 위 "최초 데이터 구축" 절차를 먼저 수행한다.

# 2. 학습하고 각 test fold의 상승 확률 예측 캐시를 생성한다.
python experiments/train.py --config experiments/configs/local.yaml

# 3. 생성된 예측 캐시로 ML 평가와 백테스트를 순서대로 실행한다.
python experiments/run_experiment_analysis.py --config experiments/configs/local.yaml

# 4. 선택: 결과 대시보드를 실행한다.
streamlit run experiments/result_dashboard/app.py
```

학습만 다시 하거나 평가·백테스트만 다시 실행할 때는 아래 개별 명령을 쓴다.

```bash
python experiments/train.py --config experiments/configs/local.yaml
python experiments/run_ml_evaluation.py --config experiments/configs/local.yaml
python experiments/run_backtest.py --config experiments/configs/local.yaml
```

### 실행 뒤 확인할 결과

`<experiment_name>`은 `local.yaml`의 값이다. 모든 경로는
`backend/analysis/chart/` 기준이다.

| 단계 | 생성 위치 | 먼저 확인할 항목 |
| --- | --- | --- |
| 학습 | `experiments/train_src/cache/models/<prediction_hash>_fold*_model.txt` | fold마다 모델이 생성됐는지 |
| 학습 | `experiments/cache/<prediction_hash>_predictions.parquet` | OOS 예측 캐시가 생성됐는지 |
| 학습 검증 | `experiments/results/<experiment_name>/validation_metrics_by_fold.csv` | 모든 fold의 `validation_passed`가 `True`인지 |
| ML 평가 | `experiments/results/<experiment_name>/model_metrics_by_fold.csv`, `calibration_by_fold.csv` | Accuracy/F1뿐 아니라 `rank_ic`, 확률 보정 상태 |
| ML·백테스트 정합성 | `experiments/results/<experiment_name>/fold_alignment.csv` | 행 정합성 검사와 fold별 표본 수 |
| 백테스트 | `experiments/results/<experiment_name>/backtest_metrics_by_fold.csv`, `backtest_metrics_by_year.csv` | 수익률·Sharpe·MDD·거래 수가 모든 fold에서 합리적인지 |
| 벤치마크 | `benchmark_comparison.csv`, `benchmark_metadata.csv` | 모델과 기준 전략의 비교 및 KRX 지수 출처 |
| 실행 재현 | `backtest_metrics_summary.json`, `config_snapshot.yaml` | `prediction_hash`, 비용·보유기간·설정 스냅샷 |

`validation_passed=False`, `fold_alignment.csv`의 정합성 실패, 비어 있는 fold,
또는 거래 수가 0인 백테스트는 결과를 해석하거나 공유하기 전에 원인을 해결해야 한다.
`.bin` 학습 캐시와 예측 캐시는 로컬 재실행을 빠르게 하기 위한 파일이며 Git에 올리지
않는다.

fresh checkout에서 로컬 설정 하나로 순차 실행하려면 다음 보조 스크립트를 쓴다. 과거의
개별 실험 config 파일은 Git으로 공유하지 않으므로 스크립트가 직접 참조하지 않는다.

```bash
bash experiments/scripts/batch/run_sequential_eval.sh experiments/configs/local.yaml
# 또는 학습+분석만 실행
bash experiments/scripts/batch/run_h10_selection.sh experiments/configs/local.yaml
```

개별 실행 결과는 `experiments/results/`에 로컬 보관합니다. Git에는
[`experiments/results/README.md`](experiments/results/README.md)의 대표 결과 요약만
남깁니다. 대표 결과를 갱신할 때는 사용한 데이터 기간, 분할, 비용, 설정과
`prediction_hash`를 기록합니다.

## 심리 피처 A/B 비교실험

Baseline(차트 피처)과 Treatment(Baseline + 합성 심리지수 + 뉴스 감성)를
`stable`/`aggressive`별로 비교합니다. 입력 계약과 고정 조건, 결과 표는
[`experiments/comparison/README.md`](experiments/comparison/README.md)를 따릅니다.

```bash
python -m experiments.comparison.runner --config experiments/comparison/config.yaml
```

## 디렉터리 구조

```text
backend/analysis/chart/
├── core/                    # 서비스 추론용 피처·설정·모델 로더
├── data_collectors/         # 가격 수집과 전처리
├── experiments/
│   ├── backtest/            # VectorBT 기반 백테스트 엔진
│   ├── comparison/          # 심리 피처 A/B 비교실험
│   ├── configs/base.yaml    # 공유 기본 실험 템플릿
│   ├── evaluation/          # ML·백테스트 공통 평가 모듈
│   ├── features/            # 외부 Parquet 검증·feature store 생성 도구
│   ├── result_dashboard/    # Streamlit 결과 대시보드
│   ├── scripts/             # factor/horizon 분석 및 순차 실행 보조 스크립트
│   ├── train.py             # 학습·예측 캐시 생성
│   └── run_backtest.py      # 캐시 기반 백테스트
└── requirements.txt
```
