# 심리·뉴스 피처 A/B 비교

기존 chart 정본을 유지한 채 `stable(H20) / aggressive(H5) × A / B` 네 런의 ML 성능을
비교한다. 모델은 모두 3분류 LightGBM이며, 평가는 기존 공용 함수와 동일하게 class 2
(`Up`) 확률을 `Up vs rest`로 해석한다.

## 데이터 구성

새로운 H5/H20 통합 parquet를 만들지 않는다. 각 profile은 두 개의 종목별 parquet 디렉터리를
읽는다. 외부 피처 구성이 같다면 stable/aggressive의 B 경로는 같은 feature store를 가리켜도 된다.

- A `baseline_price_dir`: 기존 `data/processed/` (161개 Alpha158)
- B `treatment_price_dir`: `experiments.features.build_feature_panel`이 만든 feature store

B feature store 생성법과 외부 parquet의 `Date`, `Code`, `AvailableDate` 계약은 chart 상위
README의 **외부 피처 Parquet 입력 형식**을 따른다. 원본 processed를 수정하지 않는다.

라벨도 파일에서 가져오지 않는다. 두 경로를 기존 `load_parquet_data(...,
label_params=...)`로 읽으면서 profile 설정에 따라 다시 만든다.

Train 라벨의 가격 관측은 `train_end`에서 강제로 자른다. 따라서 train 종료 뒤 embargo나 2025
holdout 가격이 2024년 말 라벨 생성에 들어가지 않으며, 관측 기간이 모자란 train tail은 제거된다.
반면 test 라벨은 평가 정답이므로 `test_end` 이후의 가격 버퍼를 관측할 수 있다. 이 때문에 H20의
2025년 말 평가에는 2026년 가격 데이터가 필요하다.

- stable: dynamic sigma, H20, `up_mult=3.75`, `down_mult=3.00`
- aggressive: dynamic sigma, H5, `up_mult=1.75`, `down_mult=1.50`
- class: `0=Down`, `1=Neutral`, `2=Up`

A/B 공정성 검사는 profile 내부에서 `Date × Code × Y_Label`이 정확히 같은지 확인한다. H5와
H20은 라벨 tail과 관측 범위가 다를 수 있으므로 profile 사이의 행 동일성은 요구하지 않는다.

## 컬럼 추가 방법

외부 컬럼의 생성은 chart 담당 범위가 아니다. 전달받은 외부 parquet를 feature-store 설정의
`features.sources[].columns`에 추가하여 새 profile 이름으로 materialize한다. 그 다음 comparison
설정의 `features.treatment`에 같은 컬럼명을 추가한다.

```yaml
features:
  treatment:
    - synthetic_psychology_index
    - news_sentiment
    - news_volume
```

comparison 코드를 수정할 필요는 없다. baseline 161개 자체를 변경하는 경우에는 기존 모델의
feature contract와 서비스 추론까지 함께 바뀌므로 이 절차의 단순 treatment 추가에 해당하지 않는다.

## 실행

`backend/analysis/chart/`에서:

```bash
# 1. profile별 B feature store를 먼저 만든다(상위 README 참고).
python -m experiments.features.build_feature_panel --config experiments/configs/local.yaml

# 2. 예제를 복사해 실제 경로와 고정 universe를 설정한다.
cp experiments/comparison/config.example.yaml experiments/comparison/config.yaml

# 3. 4런 ML 비교를 실행한다.
python -m experiments.comparison.runner --config experiments/comparison/config.yaml
```

## 산출물과 지표 경계

- `four_run_metrics.csv`: profile별 A/B 전체 구간 ML 지표
- `volatile_subsample_metrics.csv`: 날짜별 종목 `Sigma` 평균 상위 20% 구간 ML 지표
- `comparison_deltas.csv`: profile·표본별 `B - A`
- `predictions/*.parquet`: `Date`, `Code`, 3분류 정답, `Prob`(class 2 확률), `Sigma`
- `experiment_manifest.json`: label 규칙, 실제 피처, profile 내부 행/라벨 hash

ML 지표는 공용 chart 평가 함수의 accuracy, balanced accuracy, macro F1, Brier, ROC AUC,
PR AUC와 ECE다. 이진 지표를 계산할 때만 `Y_Label == 2`를 양성으로 본다. 학습 자체를 binary로
바꾸는 의미가 아니다.

이 러너는 Sharpe/MDD/수익률을 계산하지 않는다. `Next_Day_Return` 평균은 chart 정본의 체결,
보유기간, 수수료, barrier 청산 규칙과 다르기 때문이다. 트레이딩 평가는 생성된 각 prediction
parquet를 해당 profile의 기존 `run_backtest.py --predictions-path ...`에 전달해 별도로 실행한다.
따라서 ML 비교 결과와 공용 백테스트 결과는 별도 artifact로 보존한다.

합성 fixture의 결과는 연구 결과로 사용하지 않는다. 공식 실행에서는 6자리 종목 universe와
2022~2024 train / 2025 test 기간을 config에 고정하고 manifest를 함께 보관한다. H20의 2025년
말 라벨에는 이후 관측 가격이 필요하므로 processed 데이터 coverage를 실행 전에 확인한다.
