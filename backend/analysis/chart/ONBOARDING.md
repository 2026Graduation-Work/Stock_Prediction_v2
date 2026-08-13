# Chart 온보딩

이 문서가 chart 파트의 실행·재현·수정 기준이다. 모든 명령은
`backend/analysis/chart/`에서 실행한다.

## 1. 현재 정본

| profile | 모델 | 라벨 | 학습 | 평가 | 모델 파일 |
| --- | --- | --- | --- | --- | --- |
| `aggressive` | H5 | dynamic sigma `u1.75/d1.50` | 2022~2024 | 2025 | `core/models/baseline_h5_u175_d150_train2022_2024_holdout2025.txt` |
| `stable` | H20 | dynamic sigma `u3.75/d3.00` | 2022~2024 | 2025 | `core/models/baseline_h20_u375_d300_train2022_2024_holdout2025.txt` |

- LightGBM 3분류: `0=down`, `1=neutral`, `2=up`
- 서비스 스코어: class 2 확률
- 피처: Alpha158 계열 161개
- 모델 매핑·SHA-256 정본: `core/models/registry.yaml`
- 고정 universe: `experiments/configs/universes/kospi_all_2024-12-30.csv`
- 공식 config: `experiments/configs/holdout_2025_h5.yaml`, `holdout_2025_h20.yaml`

2025 결과 요약:

| 모델 | ROC AUC | Rank IC | 수익률 | Sharpe | MDD | 거래 수 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| H5 | 0.6022 | 0.1137 | -3.04% | -1.77 | -3.36% | 15 |
| H20 | 0.5821 | 0.0685 | 2.77% | 1.08 | -1.00% | 8 |

거래 수가 적고 동일가중 benchmark 약 25.1%를 하회하므로 성과를 과대해석하지 않는다.

## 2. 파일 구조와 역할

```text
backend/analysis/chart/
├── core/
│   ├── features.py              # 서비스 추론용 161개 피처 계산
│   ├── inference.py             # 모델 로드, class 2 스코어 추론
│   └── models/
│       ├── registry.yaml        # profile → 모델·라벨·SHA 매핑 정본
│       └── baseline_*.txt       # 배포용 H5/H20 LightGBM 모델
├── data_collectors/
│   ├── price_collector.py       # raw OHLCV 수집·갱신
│   └── preprocess_data.py       # raw → 종목별 processed 161피처
├── data/                        # Git 제외
│   ├── raw/<Code>.parquet
│   ├── processed/<Code>.parquet
│   ├── external/*.parquet       # 선택: 추가 피처 원본
│   └── feature_store/<name>/    # 선택: 추가 피처 결합 결과
├── experiments/
│   ├── configs/                 # 공식·로컬 실험 config
│   ├── train_src/loaders.py     # config 기준 H5/H20 3분류 라벨 재생성
│   ├── train_src/lgbm_wrapper.py# LightGBM 학습·저장
│   ├── train.py                 # 학습 + OOS prediction 생성
│   ├── run_ml_evaluation.py     # 공용 ML 평가
│   ├── run_backtest.py          # 공용 백테스트
│   ├── run_experiment_analysis.py # ML 평가 + 백테스트 실행
│   ├── run_inference.py         # 전 종목 배치 추론
│   ├── evaluation/              # 공용 평가 함수
│   ├── backtest/engine.py       # VectorBT 실행 엔진
│   ├── features/                # 외부 피처 검증·결합
│   ├── comparison/              # baseline/treatment 4런 비교
│   ├── handoff/                 # universe·Drive 패키지 생성
│   └── results/legacy_screening/# 과거 H5/H20 선정 근거·결과(로컬 보관)
├── notebooks/
│   └── chart_holdout_2025_colab.ipynb
└── requirements.txt
```

## 3. 환경 준비

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

검증:

```bash
ruff check .
pytest
```

## 4. 데이터 준비

### 새로 구축

```bash
python data_collectors/price_collector.py --mode full --start-date 2016-01-01
python data_collectors/preprocess_data.py --mode full
```

### 최신 거래일 갱신

```bash
python data_collectors/price_collector.py --mode update
python data_collectors/preprocess_data.py --mode update
```

학습 입력은 `data/processed/<Code>.parquet`이다. 파일 안의 기존 `Y_Label`은 최종
target이 아니다. `experiments/train_src/loaders.py`가 실행 config에 따라 H5/H20
라벨을 다시 계산한다. H5/H20 전용 parquet를 별도로 만들지 않는다.

## 5. 기존 모델 추론

### 단일 종목

```python
from pathlib import Path
import pandas as pd

from core.inference import load_prediction_model, predict_success_probability

model = load_prediction_model(
    Path("core/models/baseline_h5_u175_d150_train2022_2024_holdout2025.txt")
)
prices = pd.read_parquet("data/raw/005930.parquet").sort_values("Date").tail(100)
scores = predict_success_probability(prices, model)
latest_score = float(scores.iloc[-1])
```

H20은 모델 경로만 아래 파일로 바꾼다.

```text
core/models/baseline_h20_u375_d300_train2022_2024_holdout2025.txt
```

### 전 종목

```bash
python experiments/run_inference.py \
  --profile aggressive \
  --target-date 2025-12-31 \
  --output-dir experiments/results/inference_h5
```

H20은 `--profile stable`로 실행한다. `--model-path`는 registry 밖의 모델을 시험할 때만
사용한다. 출력의 `REVIEW`는 사전 합의한 스코어 임계 도달 표시이며 매수·매도 지시가 아니다.

모델 스코어는 미래 상승을 보장하는 확률이 아니다. 화면에서는 과거 유사 신호 기준의
상대 스코어로 표현하고 자동 매매 지시로 사용하지 않는다.

## 6. H5/H20 재학습

### 로컬

공식 config를 복사해 `experiment_name`, `data.price_dir`, `data.version`만 실행 환경에
맞게 수정한다. 공식 파일은 직접 덮어쓰지 않는다.

```bash
cp experiments/configs/holdout_2025_h5.yaml experiments/configs/local_h5.yaml
cp experiments/configs/holdout_2025_h20.yaml experiments/configs/local_h20.yaml

python experiments/train.py --config experiments/configs/local_h5.yaml
python experiments/run_experiment_analysis.py --config experiments/configs/local_h5.yaml

python experiments/train.py --config experiments/configs/local_h20.yaml
python experiments/run_experiment_analysis.py --config experiments/configs/local_h20.yaml
```

개별 실행:

```bash
python experiments/run_ml_evaluation.py --config experiments/configs/local_h5.yaml
python experiments/run_backtest.py --config experiments/configs/local_h5.yaml
```

### Colab

`notebooks/chart_holdout_2025_colab.ipynb`를 연다.

수정할 값:

```python
REPO_URL = "https://github.com/<ORG>/<REPO>.git"
COMMIT_SHA = "실행할 정확한 commit SHA"
DATA_SOURCE = DRIVE_ROOT / "input/chart_processed_holdout2025_v1.tar.gz"
```

모든 셀을 순서대로 실행한다. 결과는 Drive의 `outputs/<commit>/`에 모델, prediction,
config, coverage, ML 평가, 백테스트, manifest, checksum으로 저장한다.

## 7. Config 핵심 필드

```yaml
data:
  price_dir: data/processed
  version: 데이터_스냅샷_ID
  tickers: [005930, ...]
  splits:
    - train_start: "2022-01-01"
      train_end: "2024-12-31"
      test_start: "2025-01-08"
      test_end: "2025-12-31"

labels:
  type: dynamic_sigma
  horizon: 5
  up_mult: 1.75
  down_mult: 1.50

model:
  type: LGBM
  objective: multiclass
  params: {...}

training:
  skip_validation: true
```

- `labels`: target 생성 규칙
- `model.params`: LightGBM 파라미터
- `strategy`: 스코어 임계·Top-N
- `backtest`: 체결 지연·비용·보유기간·청산 규칙
- `evaluation`: 평가 bin·benchmark 설정

2025 final holdout 재현 시 라벨·모델·백테스트 파라미터를 바꾸지 않는다.

## 8. 실행 결과 위치

```text
experiments/train_src/cache/models/<hash>_fold0_model.txt
experiments/cache/<hash>_predictions.parquet
experiments/results/<experiment_name>/
├── model_metrics_by_fold.csv
├── calibration_by_fold.csv
├── backtest_metrics_summary.json
├── backtest_metrics_by_fold.csv
├── benchmark_comparison.csv
├── benchmark_metadata.csv
├── fold_alignment.csv
├── trades.csv
└── daily_returns.csv
```

반드시 확인할 값:

- prediction과 평가 라벨의 `Date × Code` 정합성
- ROC AUC, PR AUC, Rank IC, calibration
- 수익률, Sharpe, MDD, 거래 수
- benchmark source와 비용·보유기간
- 모델 SHA-256과 실행 commit

## 9. 추가 피처 붙이기

기존 161피처 parquet를 수정하지 않는다. 추가 피처는 별도 parquet로 받는다.

필수 컬럼:

```text
Date | Code | AvailableDate | <numeric_feature_columns...>
```

- `AvailableDate`: 모델이 처음 사용할 수 있는 거래일
- 장 마감 뒤 생성된 값은 다음 거래일을 기록
- `(Code, Date, AvailableDate)` 중복 금지
- target·label·future·next 계열 컬럼 금지

로컬 config 예시:

```yaml
data:
  price_dir: data/feature_store/extra_v1

features:
  profile_name: extra_v1
  base_processed_dir: data/processed
  base_columns: "*"
  materialized_dir: data/feature_store/extra_v1
  sources:
    - name: external
      path: data/external/external.parquet
      apply_period: one_day
      columns: [feature_a, feature_b]
      missing: {policy: zero, add_indicator: true}
```

생성·학습:

```bash
python -m experiments.features.build_feature_panel \
  --config experiments/configs/local_extra.yaml
python experiments/train.py --config experiments/configs/local_extra.yaml
python experiments/run_experiment_analysis.py --config experiments/configs/local_extra.yaml
```

추가 피처 컬럼을 바꿀 때 수정할 곳:

1. 외부 parquet의 숫자 컬럼
2. `features.sources[].columns`
3. 새 `profile_name`, `materialized_dir`
4. 비교실험이면 `experiments/comparison/config.yaml`의 `features.treatment`

결합 코드 수정은 필요 없다. 피처 구성이 바뀌면 기존 feature store를 덮어쓰지 말고 새
경로를 사용한다.

## 10. 기존 161피처 자체를 수정할 때

추가 외부 피처와 달리 다음 파일을 함께 수정한다.

1. `data_collectors/preprocess_data.py`: 학습 parquet 피처 생성
2. `core/features.py`: 서비스 추론 피처 생성
3. `core/inference.py`의 `FEATURE_COLS`: 입력 순서
4. 관련 테스트
5. processed 전체 재생성
6. H5/H20 모두 재학습·재평가
7. 모델 파일과 `core/models/registry.yaml` SHA 갱신

학습 모델의 `feature_name()`과 `core.inference.FEATURE_COLS`의 이름·순서·개수가 정확히
같아야 한다.

## 11. 라벨·모델·전략을 수정할 때

| 변경 | 수정 위치 |
| --- | --- |
| horizon·barrier | config의 `labels` |
| LightGBM 파라미터 | config의 `model.params` |
| 학습·평가 기간 | config의 `data.splits` |
| 종목 목록 | config의 `data.tickers`, universe CSV |
| Top-N·임계 | config의 `strategy` |
| 체결·비용·청산 | config의 `backtest` |
| 완전히 새로운 라벨식 | `experiments/train_src/loaders.py`와 테스트 |

라벨 변경 시 저장된 `Y_Label`을 직접 수정하지 않는다. loader가 실행 시 재생성한다.

## 12. Baseline/Treatment 비교

실제 외부 데이터가 있을 때만 사용한다.

```bash
cp experiments/comparison/config.example.yaml experiments/comparison/config.yaml
python -m experiments.comparison.runner \
  --config experiments/comparison/config.yaml
```

- A: 기존 161피처
- B: A + 추가 피처
- stable H20과 aggressive H5를 각각 A/B 비교
- 같은 profile 내부의 키·라벨·baseline 피처 동일성을 자동 검사
- ML 평가는 공용 평가 함수 사용
- trading 평가는 생성된 prediction을 `run_backtest.py --predictions-path`에 전달

## 13. Universe와 Drive 패키지

Universe 재생성:

```bash
python -m experiments.handoff.build_kospi_universe \
  --cutoff 2024-12-30 \
  --processed-dir data/processed \
  --output experiments/configs/universes/kospi_all_2024-12-30.csv
```

Drive archive 생성:

```bash
python -m experiments.handoff.package_processed \
  --processed-dir data/processed \
  --universe-file experiments/configs/universes/kospi_all_2024-12-30.csv \
  --output-dir /path/to/metadata \
  --dataset-id chart_kospi_holdout2025_v1 \
  --archive /path/to/chart_processed_holdout2025_v1.tar.gz
```

- archive `.sha256`: 업로드 파일 검증
- `DATA_MANIFEST.json`: universe·기간·행·피처·정책 기록
- `SHA256SUMS`: 압축 해제 파일 일괄 검증

세 파일은 학습 필수 입력이 아니라 Drive 재현성 자료다.

## 14. 과거 파일 통합 위치

- 정본 코드·데이터: `backend/analysis/chart/`
- 과거 스크리닝 근거: `experiments/results/legacy_screening/SELECTION_REPORT.md`
- 이전 대용량 cache 백업: `chart_handoff_output/legacy_analysis_chart_backup/chart/`

루트의 구형 `analysis/chart/`는 더 이상 사용하지 않는다. 백업은 현재 코드·데이터 검증 후
용량이 필요할 때 수동 삭제한다.

## 15. 변경 완료 체크

```text
[ ] config와 universe가 고정됐다.
[ ] 학습 라벨이 train_end 이후 가격을 보지 않는다.
[ ] prediction과 평가 라벨 키가 정합하다.
[ ] 공용 ML 평가와 공용 backtest를 사용했다.
[ ] 모델은 161피처·3분류 계약을 만족한다.
[ ] 모델 SHA와 실행 commit을 registry에 기록했다.
[ ] ruff check . / pytest가 통과했다.
[ ] 사용자 노출 문구는 자동 매매 지시나 확정적 상승 확률로 표현하지 않는다.
```
