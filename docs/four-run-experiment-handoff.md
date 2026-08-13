# Chart × 심리·뉴스 A/B 실험 인수인계

> 기준: 2025 final holdout, 기존 chart 3분류 LightGBM 정본 유지
> 연구 질문: 심리·뉴스 소프트 틸트를 추가하면 chart baseline보다 OOS 성능이 나아지는가?

## 1. 고정한 설계

Universe는 2025 holdout 결과를 보고 종목을 고르는 일을 막기 위해 학습 종료 직전
마지막 거래일인 **2024-12-30 기준 KOSPI 전 종목 스냅샷**으로 고정한다. 현재 시점의
KOSPI 목록을 다시 조회해 대체하지 않는다. 우선주 등 6자리 영문·숫자 KRX 단축코드도
스냅샷에 있으면 포함한다.

| profile | horizon | dynamic-sigma barrier | 학습 | 최종 평가 |
| --- | ---: | --- | --- | --- |
| `aggressive` | H5 | `up=1.75`, `down=1.50` | 2022-01-01~2024-12-31 | 2025 |
| `stable` | H20 | `up=3.75`, `down=3.00` | 2022-01-01~2024-12-31 | 2025 |

- 학습 objective는 기존 chart 정본과 같은 `multiclass`, `num_class=3`이다.
- 클래스는 `0=down`, `1=neutral`, `2=up`이다. 모델 학습을 binary로 바꾸지 않는다.
- 확률 지표에 필요한 양성 점수는 3분류 결과의 `prob_up`(`class 2`)을 쓴다.
- A는 chart baseline 피처, B는 같은 baseline에 심리·뉴스 피처만 더한다.
- H5 A/B끼리, H20 A/B끼리 같은 universe·기간·행·seed·모델 파라미터를 쓴다.
  H5와 H20은 라벨 horizon이 다르므로 서로 같은 행 집합을 강제하지 않는다.
- 2025는 마지막까지 보지 않는 final holdout이다. 하이퍼파라미터나 결측 정책을
  2025 결과를 보고 다시 고르면 final holdout 의미가 사라진다.

공식 설정은 다음 두 파일이다.

```text
backend/analysis/chart/experiments/configs/holdout_2025_h5.yaml
backend/analysis/chart/experiments/configs/holdout_2025_h20.yaml
```

고정 universe는 `experiments/configs/universes/kospi_all_2024-12-30.csv`다. 다시
생성해야 할 때는 `backend/analysis/chart/`에서 아래 명령을 사용한다. 현재 활성 목록만
쓰지 않고 cutoff 이후 상장폐지된 KOSPI 주권도 복원하며, processed 누락이 있으면 실패한다.

```bash
python -m experiments.handoff.build_kospi_universe \
  --cutoff 2024-12-30 \
  --processed-dir /path/to/analysis/chart/data/processed \
  --output experiments/configs/universes/kospi_all_2024-12-30.csv
```

## 2. 별도 H5/H20 라벨 parquet를 만들지 않는 이유

Drive의 chart 정본은 기존 `data/processed/<Code>.parquet` 한 세트다. H5/H20별
parquet 또는 `Target_H5`/`Target_H20`가 든 통합 parquet를 새로 만들지 않는다.

`experiments/train_src/loaders.py`는 파일에 저장된 `Y_Label`을 최종 실험 target으로
신뢰하지 않고, 실행할 때 config의 `labels`로 다시 계산한다.

```text
같은 processed 스냅샷
  ├─ H5 config  → dynamic sigma 1.75/1.50 → Y_Label 0/1/2
  └─ H20 config → dynamic sigma 3.75/3.00 → Y_Label 0/1/2
```

따라서 processed parquet 안의 기존 `Y_Label`은 전처리 당시 기본 설정의 편의 컬럼일
수 있으며, 최종 H5/H20 라벨로 직접 사용하면 안 된다. 학습 종료일의 라벨은 2025
가격을 보지 못하게 관측 범위를 닫고, 2025 평가 라벨은 horizon 이후 가격 버퍼를
읽어 계산해야 한다. 이 경계 처리는 공식 loader와 train 흐름을 재사용한다.

## 3. 우리 chart 팀이 Drive에 올릴 것

권장 폴더는 다음과 같다.

```text
team-drive/experiments/chart_psychology_ab/v1/
├── chart_processed_holdout2025_v1.tar.gz
├── chart_processed_holdout2025_v1.tar.gz.sha256
├── DATA_MANIFEST.json
├── SHA256SUMS
├── universe.csv
└── README.md
```

archive를 풀면 다음 구조다.

```text
processed/
├── 000020.parquet
├── 000040.parquet
└── ...                    # universe.csv에 고정된 종목만
universe.csv
DATA_MANIFEST.json
SHA256SUMS
```

필수 전달물:

- 고정 universe의 종목별 processed parquet
- `universe.csv`: 헤더 `Code`, 6자리 영문·숫자 KRX 단축코드, 중복 없음
- `DATA_MANIFEST.json`: 기간, 행 수, feature 수, commit, 파일별 hash와 라벨 정책
- `SHA256SUMS`: 추출 파일 검증값
- archive 자체의 `.sha256`: Drive 업로드·다운로드 손상 확인값
- 이 문서와 두 holdout config가 포함된 Git commit 또는 PR

raw 가격, LightGBM `.bin` cache, 과거 prediction cache, H5/H20 라벨 복제본은 필수
전달물이 아니다. raw는 전처리를 처음부터 감사해야 할 때만 별도 archive로 보관한다.

## 4. 패키지 생성과 검증

`backend/analysis/chart/`에서 실행한다. 이 명령은 입력 parquet를 수정하지 않는다.

먼저 metadata만 만들어 검증한다.

```bash
python -m experiments.handoff.package_processed \
  --processed-dir data/processed \
  --universe-file /path/to/final_universe.csv \
  --output-dir /path/to/chart_handoff_metadata \
  --dataset-id chart_processed_holdout2025_v1
```

검증이 끝난 뒤 Drive 업로드용 archive까지 한 번에 만들려면 비어 있는 새 output
디렉터리로 다시 실행한다.

```bash
python -m experiments.handoff.package_processed \
  --processed-dir data/processed \
  --universe-file /path/to/final_universe.csv \
  --output-dir /path/to/chart_handoff_v1 \
  --dataset-id chart_processed_holdout2025_v1 \
  --archive /path/to/chart_processed_holdout2025_v1.tar.gz
```

도구는 universe 누락 파일, 파일명과 `Code` 불일치, 중복 `Date × Code`, 시간값이
있는 `Date`, `Sigma` 결측, 파일 간 schema/feature 수 불일치를 거부한다. 대상 폴더나
archive가 이미 있으면 덮어쓰지 않는다.

받는 사람은 다음처럼 확인한다.

```bash
sha256sum -c chart_processed_holdout2025_v1.tar.gz.sha256
tar -xzf chart_processed_holdout2025_v1.tar.gz
cd <압축을 푼 폴더>
sha256sum -c SHA256SUMS
```

`SHA256SUMS`의 경로는 추출 루트 기준이다. `DATA_MANIFEST.json`의
`stored_y_label_is_not_experiment_target`가 `true`인지도 확인한다.

## 5. `DATA_MANIFEST.json`과 `SHA256SUMS`

이 파일들은 LightGBM 학습 입력이 아니다. 같은 로컬 `data/processed`를 계속 쓰던 기존
흐름에서는 없어도 바로 학습할 수 있다. 이번에는 약 2.3 GiB의 parquet 묶음을 Drive로
다른 실행 환경에 옮기므로, 업로드 전후 데이터가 동일한지와 어떤 스냅샷을 썼는지를
남기기 위해 함께 만든다. 패키징 도구가 자동 생성하므로 사용자가 수동으로 작성하지 않는다.

- archive `.sha256`: Drive에 올린 압축 파일 한 개가 손상되지 않았는지 확인한다.
- `DATA_MANIFEST.json`: universe·기간·행 수·161개 피처·Git commit·라벨 정책을 기록한다.
- `SHA256SUMS`: 압축을 푼 뒤 847개 parquet 각각을 한 명령으로 검사한다.

Colab 학습 자체에는 archive만 있으면 된다. 나머지는 결과 재현과 팀 인수인계용이며,
`DATA_MANIFEST.json`에도 파일별 hash가 있어 `SHA256SUMS`는 명령행 검증 편의를 위한
중복 표현이다.

`DATA_MANIFEST.json`은 데이터가 어떤 조건에서 만들어졌는지 설명하는 영수증이다.
주요 필드는 다음과 같다.

- dataset ID와 생성 UTC 시각
- 전처리 코드 Git commit
- 고정 universe와 `universe.csv` hash
- 전체·공통 데이터 기간, 총 행 수
- required column과 chart feature 수
- 파일별 행 수, 기간, byte 크기, schema hash, SHA-256
- 저장된 `Y_Label`을 최종 target으로 쓰지 않는다는 선언
- H5/H20 config로 실행 시 재라벨한다는 정책
- `Market_Volatility` 계산·용도

`SHA256SUMS`는 설명서가 아니라 파일 바이트가 같은지 확인하는 목록이다. 두 파일 모두
필요하다. manifest만 있으면 파일 손상을 일괄 검사하기 어렵고, checksum만 있으면 데이터
생성 조건을 알 수 없다.

## 6. 심리·뉴스 피처는 어떻게 결합하는가

실제 심리·뉴스 값의 생성은 각 담당자 범위다. chart 팀은 외부 입력 계약과 결합 경로만
제공한다. 기존 processed parquet를 직접 수정하거나 `comparison_input.parquet` 하나로
수작업 합치지 않는다.

외부 parquet의 필수 키:

| 컬럼 | 의미 |
| --- | --- |
| `Date` | 값을 관측·계산한 기준일 |
| `Code` | 6자리 종목 코드 |
| `AvailableDate` | 모델이 이 값을 처음 사용할 수 있는 거래일 |

피처 값은 숫자형이어야 하며 `(Code, Date, AvailableDate)`와
`(Code, AvailableDate)`가 중복되면 안 된다. 장 마감 뒤 만든 뉴스 값은 다음 거래일을
`AvailableDate`로 기록한다. `AvailableDate`가 없으면 미래 정보 유입을 검증할 수 없으므로
공식 A/B 입력으로 받지 않는다.

결합은 이미 구현된 feature-store builder를 사용한다.

```yaml
data:
  # builder가 만든 결합 패널을 학습·평가·백테스트가 읽는다.
  price_dir: "data/feature_store/psychology_news_v1"

features:
  profile_name: "psychology_news_v1"
  base_processed_dir: "data/processed"
  base_columns: "*"
  exclude_columns: []
  materialized_dir: "data/feature_store/psychology_news_v1"
  sources:
    - name: "psychology"
      path: "data/external/psychology.parquet"
      apply_period: "one_day"
      columns: ["synthetic_psychology_index"]
      missing: {policy: "error", add_indicator: true}
    - name: "news"
      path: "data/external/news_daily.parquet"
      apply_period: "one_day"
      columns: ["news_sentiment"]
      missing: {policy: "zero", add_indicator: true}
```

위 결측 정책은 형식 예시일 뿐이다. 각 담당자가 정의하고 실험 전에 고정해야 하며,
2025 결과를 본 뒤 바꾸면 안 된다.

```bash
python -m experiments.features.build_feature_panel \
  --config experiments/configs/local_treatment.yaml
```

builder는 원본 `data/processed`를 건드리지 않고
`data/feature_store/<profile>/<Code>.parquet`와 `feature_manifest.json`을 만든다.
`Date/Code/AvailableDate`, 공개 시점, 컬럼 충돌, target 유사 컬럼, 결측 정책을 검증한다.

## 7. 컬럼을 더 붙이는 위치

외부 피처를 추가하거나 빼는 경우에는 코드를 수정하지 않는다.

1. 계약에 맞는 별도 parquet를 `data/external/`에 둔다.
2. 로컬 config의 `features.sources[].columns`에 컬럼을 추가한다.
3. B의 treatment feature 목록에도 같은 컬럼을 추가한다.
4. 기존 폴더를 덮어쓰지 말고 새 `profile_name`과 `materialized_dir`로 builder를 실행한다.
5. 생성된 `feature_manifest.json`에서 적용 기간·결측률·fingerprint를 확인한다.

새로운 chart baseline 피처 자체를 추가하는 것은 다른 작업이다. 이 경우
`core/features.py`, 전처리, 학습 feature 목록과 서비스 추론을 함께 수정하고 baseline
모델을 다시 학습해야 한다. A/B 양쪽 baseline도 같게 바꾸고 데이터·모델 버전을 올린다.

평가용 보조 컬럼은 모델 feature 목록에 넣지 않는다. 새로운 급변 지표 등을 도입한다면
공용 평가 코드와 config에만 추가하고 사전에 규칙을 고정한다.

## 8. `Market_Volatility`와 trading 평가

별도 `Market_Volatility` parquet 컬럼을 만들 필요가 없다. 평가 시 해당 실험의 고정
universe에서 다음처럼 결정론적으로 계산한다.

```python
market_volatility = panel.groupby("Date", sort=True)["Sigma"].mean()
```

테스트 날짜의 이 값이 큰 순서로 사전에 정한 상위 20% 날짜를 급변 구간으로 삼는다.
이는 모델 입력 피처가 아니라 전체/급변 구간을 나누는 평가용 값이다. B에만 넣거나,
2025 결과를 본 뒤 상위 비율을 고르면 안 된다.

`Next_Day_Return`을 새로 만들어 자체 Sharpe/MDD를 계산하지 않는다. A/B가 만든 OOS
`prob_up` prediction을 기존 `experiments/backtest/engine.py`와 공용 평가 모듈에
전달한다. 진입 지연, open 체결, 보유기간, barrier, 수수료는 H5/H20 config의 기존
백테스트 규칙을 그대로 따른다. 이는 모델별 자체 평가 코드를 금지한 SSOT 원칙을
지키기 위함이다.

상장폐지 종목은 폐지 전까지 prediction을 만들 수 있지만, 미래 H5/H20 outcome을 끝까지
관측할 수 없는 마지막 tail에는 평가 라벨이 없다. 원본 prediction은 백테스트용으로
보존하고 ML 평가지표에서만 정답 라벨이 있는 `Date × Code`로 제한한다. 반대로 정답은
있는데 prediction이 없거나 키가 중복되면 오류로 중단한다.

## 9. Colab 학습 뒤 받아야 할 모델

Colab에서 공식 config로 다음 두 모델을 학습한다.

```text
aggressive: H5,  train 2022~2024, test 2025, u1.75/d1.50
stable:     H20, train 2022~2024, test 2025, u3.75/d3.00
```

돌려받을 때 모델 `.txt`만 받지 말고 다음을 함께 받는다.

- 실제 사용 config snapshot
- validation/ML/backtest 결과와 OOS predictions
- prediction hash와 모델 파일 SHA-256
- 실행 commit, Python·LightGBM 버전
- Colab 출력 로그

검토가 끝난 모델만 `backend/analysis/chart/core/models/`에 명확한 이름으로 두고 registry에
연결한다. 모델 폴더의 README와 registry 예시를 따라 추론 입력, 161개 feature 순서,
`class 2 → prob_up`, 학습 종료일을 함께 기록한다. 2025 평가를 본 모델을 다시 튜닝한 뒤
같은 결과를 final holdout이라고 부르면 안 된다.

## 10. 실행 순서와 완료 조건

1. 최종 universe CSV를 고정한다.
2. processed coverage에서 H5/H20별 실제 labelable train/test 행 수를 확인한다.
   미래 관측이 부족한 마지막 tail은 제외하되 상장폐지 종목의 이전 유효 행은 유지한다.
3. 위 CLI로 processed snapshot을 검증하고 Drive archive를 만든다.
4. archive와 metadata/hash를 Drive에 올리고 다른 팀원이 checksum을 검증한다.
5. 담당자에게 `Date/Code/AvailableDate` 계약의 심리·뉴스 parquet를 받는다.
6. feature-store builder로 treatment 패널을 만든다.
7. 동일 processed·universe로 baseline과 treatment를 각각 학습한다.
8. profile별 A/B가 동일한 OOS key를 썼는지 검사한다.
9. 공용 ML 평가와 기존 backtest SSOT로 전체·급변 구간을 평가한다.
10. 결과, prediction, config, experiment manifest를 함께 보관한다.

완료 조건:

- [ ] processed archive, 고정 universe, `DATA_MANIFEST.json`, `SHA256SUMS`가 있다.
- [ ] 다른 팀원이 archive와 추출 파일 hash를 모두 검증했다.
- [ ] H5/H20 모두 기존 loader의 3분류 동적 라벨을 사용했다.
- [ ] 외부 피처의 `AvailableDate`와 결측 정책이 기록됐다.
- [ ] H5 A/B와 H20 A/B의 OOS key가 각각 동일하다.
- [ ] 전체·급변 구간을 공용 평가 함수와 기존 backtest로 평가했다.
- [ ] 4개 OOS prediction, config snapshot, experiment manifest가 있다.
- [ ] negative result를 포함해 과장 없이 연구 결론을 기록했다.
