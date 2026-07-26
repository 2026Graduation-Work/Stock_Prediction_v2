# 차트 분석 블록

이 블록은 기술적 지표와 DT 계열 모델(LightGBM)을 사용해 상승·하락 확률을
산출하고, 해당 신호의 백테스트와 평가를 수행합니다. 결과는 투자 권유가 아닌
과거 데이터 기반의 실험 결과이며, 불확실성과 검증 조건을 함께 확인해야 합니다.

## 개발 환경

Python 3.10~3.12 환경에서 아래 명령을 `backend/analysis/chart/` 디렉터리에서 실행합니다.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 데이터와 설정

원시·처리 데이터, 예측 캐시, 학습 캐시, 개별 실험 결과는 용량과 재현성 문제로
Git에 올리지 않습니다. 필요한 데이터는 로컬에서 수집·전처리합니다.

```bash
python data_collectors/price_collector.py
python data_collectors/preprocess_data.py
```

공유되는 일반 실험 설정은 `experiments/configs/base.yaml` 하나의 템플릿뿐입니다.
구체적인 실험 설정은 아래처럼 로컬 파일로 복사해 만들며 Git에서 무시됩니다.

```bash
cp experiments/configs/base.yaml experiments/configs/local.yaml
# local.yaml에서 기간, horizon, barrier, 모델·전략 파라미터를 수정
```

데이터를 갱신하면 `data.version`도 증가시킨다. 학습 캐시 키는 parquet 파일명·크기·수정시각
manifest와 이 버전을 포함하므로, 일반적인 데이터 갱신은 기존 모델/예측 캐시를 재사용하지 않는다.
내용을 바꾸면서 파일 메타데이터를 의도적으로 보존한 경우에도 `data.version`을 반드시 바꾼다.

비교실험의 종목 유니버스는 `data.tickers`에 6자리 코드 목록으로 고정한다. 실행 시점마다
구성 종목이 달라지는 `KOSPI_TOP200` 실시간 별칭은 재현성 때문에 허용하지 않으며, 목록을
만든 기준일과 코드를 실험 설정과 함께 보관한다. `data.start_date`/`data.end_date`는 모든
자동 생성 fold의 최종 경계로 적용된다.

`core/config.example.yaml`은 서비스 추론용 로컬 설정 템플릿입니다. 필요할 때만
`core/config.yaml`으로 복사해 사용하며, 이 파일도 Git에 올리지 않습니다.

## 실험 실행

```bash
# 학습 및 예측 캐시 생성
python experiments/train.py --config experiments/configs/local.yaml

# 생성된 예측 캐시를 이용한 백테스트
python experiments/run_backtest.py --config experiments/configs/local.yaml

# 분류 성능·확률 보정·Rank IC 평가와 백테스트를 순서대로 실행
python experiments/run_experiment_analysis.py --config experiments/configs/local.yaml

# 결과 대시보드
streamlit run experiments/result_dashboard/app.py
```

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
│   ├── result_dashboard/    # Streamlit 결과 대시보드
│   ├── scripts/             # factor/horizon 분석 및 순차 실행 보조 스크립트
│   ├── train.py             # 학습·예측 캐시 생성
│   └── run_backtest.py      # 캐시 기반 백테스트
└── requirements.txt
```
