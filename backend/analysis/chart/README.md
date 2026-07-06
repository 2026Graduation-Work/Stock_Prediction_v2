# 🟢 Chart Pattern & Technical Analysis Block (차트 분석 블록)

이 블록은 행동재무학 기반 주가 예측 시스템 중 **기술적 분석(차트 패턴 및 기술적 지표)**과 **설명 가능한 AI(DT 계열 ML 모델)**를 활용한 주가 상승/하락 확률 예측 및 백테스트 실험 영역을 담당합니다.

외부에서 이 레포지토리를 클론하여 로컬에서 실험 및 수집을 독자적으로 수행하고 싶다면 아래 가이드를 따라 주시기 바랍니다.

---

## 🛠️ 1. 개발 환경 설정

이 블록은 파이썬 3.10 ~ 3.12 환경에서 가장 안정적으로 작동합니다.

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 필요한 패키지 의존성 설치
pip install -r requirements.txt
```

---

## ⚙️ 2. 설정 파일 (Config) 구성

실험 및 예측에 쓰이는 파라미터는 `core/config.yaml`을 통해 관리됩니다. 이 파일은 로컬용 설정이므로 Git 추적에서 제외되어 있습니다.

1. 제공되는 뼈대 파일인 `core/config.example.yaml`을 복사하여 **`core/config.yaml`**을 생성합니다.
   ```bash
   cp core/config.example.yaml core/config.yaml
   ```
2. 필요에 따라 `core/config.yaml` 내부 설정을 편집하여 사용합니다.
   * `data.start_date` 및 `data.end_date`: 백테스트 및 학습 데이터 기간 범위 지정.
   * `data.split_strategy`: 데이터 분할 전략 (`sliding`, `expanding`, `single` 중 선택).
   * `model.params`: LightGBM 하이퍼파라미터 및 규제 강도 조절.
   * `strategy`: 시그널 진입 임계점(`prob_threshold`) 및 포트폴리오 개수(`top_n`) 지정.

---

## 📊 3. 데이터 수집 및 구성 (Data Setup)

보안 및 저장 용량 상의 이유로 원시 데이터(`.parquet`, `.csv`)는 Git 저장소에 포함되어 있지 않습니다. 아래 스크립트를 통해 로컬에 데이터를 스스로 빌드해야 합니다.

1. **원시 OHLCV 데이터 수집**:
   `collectors/price_collector.py` 스크립트를 실행합니다.
   ```bash
   python collectors/price_collector.py
   ```
   * 이 명령을 실행하면 루트 폴더에 자동으로 `data/` 디렉토리가 생성되고, KOSPI/KOSDAQ의 모든 활성 종목 및 상장폐지 이력 종목의 일봉 수정주가 데이터(Parquet 포맷)가 다운로드됩니다.
   * 이미 수집된 종목은 Skip되어 이어받기가 가능합니다.

---

## 🔬 4. 로컬 실험 및 백테스트 실행 (R&D)

데이터 수집이 완료되면, 모델 학습과 퀀트 백테스트 시뮬레이션을 돌려 성능을 테스트할 수 있습니다.

### 4.1 모델 학습 + 백테스트 전체 실행
`experiments/run_experiment.py`를 실행하여 모델을 학습시키고 백테스트를 일괄 수행합니다.
```bash
python experiments/run_experiment.py --config core/config.yaml
```
* 이 과정에서 `core/features.py`를 호출하여 피처 엔지니어링을 수행합니다.
* 데이터 기간 분할(embargo 처리 포함)을 거쳐 LightGBM 모델을 학습하고 검증합니다.
* 최종 예측 확률값을 바탕으로 가상의 포트폴리오를 구성해 거래 비용(수수료+세금)을 반영한 백테스트 시뮬레이션 결과가 생성됩니다.
* 예측 결과는 `experiments/cache/` 폴더에 캐싱됩니다.

### 4.2 초고속 백테스트 단독 실행 (★추천)
모델 학습과 예측 확률 계산은 시간이 수 분 이상 걸리는 무거운 작업입니다. 만약 **이미 한 번 돌려서 예측 캐시가 있다면**, 모델 재학습 없이 **백테스트 설정(수수료, 진입 확률, 익절선 등)만 바꾸어 1초 만에 결과를 시뮬레이션**할 수 있습니다.
```bash
python experiments/run_backtest.py --config core/config.yaml
```
* 이 스크립트는 캐시된 예측 확률 데이터를 로드하고, `core/config.yaml`에 명시된 전략 파라미터(`prob_threshold`, `top_n`, `fee` 등)만 동적으로 변경해 백테스트만 즉각 실행합니다.

### 4.3 로컬 결과 시각화 대시보드
백테스트의 결과와 피처 기여도(SHAP 등)를 대시보드로 분석하려면 Streamlit 앱을 실행합니다.
```bash
streamlit run experiments/dashboard/app.py
```

---

## 📁 5. 디렉토리 역할 요약
* `core/`: 프로덕션 예측 파이프라인 연동 모듈 (웹 API나 자동화 예측 스케줄러가 임포트하여 사용하는 순수 핵심 코드)
* `collectors/`: 데이터 수집 전용 모듈
* `experiments/`: R&D 목적의 로컬 연구, 모델 성능 테스트 및 백테스트 시뮬레이션 코드

---

## 📂 6. 상세 파일 구조 및 설명

```
backend/analysis/chart/
├── README.md                 # 블록 개요, 실행법 및 가이드라인
├── requirements.txt          # 차트 분석 블록 의존 패키지 리스트
│
├── core/                     # [1] 실서비스 예측 파이프라인 연동 모듈 (API용)
│   ├── __init__.py           # 주요 추론 및 전처리 함수 외부 노출 (from core import ...)
│   ├── config.py             # config.yaml 설정 로더 헬퍼
│   ├── config.example.yaml   # 설정 파일 복사용 뼈대 템플릿
│   ├── features.py           # Alpha158 기술적 지표 생성 및 동적 트리플 배리어 라벨러
│   ├── inference.py          # LightGBM Booster 모델 복원 및 실시간 상승 성공 확률 예측
│   └── models/               # 실제 서비스 배포용 모델 가중치 파일(.txt) 적재 공간
│
├── collectors/               # [2] 데이터 수집 전용 모듈
│   ├── __init__.py
│   └── price_collector.py    # FDR/pykrx를 활용해 생존편향 없이 전 종목 일봉 OHLCV 데이터를 수집
│
└── experiments/              # [3] 로컬 연구, 모델 학습 및 백테스트 시뮬레이션 (R&D)
    ├── __init__.py
    ├── run_experiment.py     # 전체 학습-검증-테스트 및 백테스트 일괄 실행 메인 파일
    ├── run_backtest.py       # 모델 재학습 없이 초고속 백테스트 단독 실행 파일
    │
    ├── src/                  # 실험을 보조하는 백그라운드 모듈 (난잡함 방지를 위해 격리)
    │   ├── __init__.py
    │   ├── loaders.py        # 대용량 Parquet 데이터를 고속 병렬 로드하고 라벨링하는 모듈
    │   ├── lgbm_wrapper.py   # 학습/캐싱을 포함한 LightGBM 훈련 래퍼 클래스
    │   ├── base_model.py     # 퀀트 모델링 추상 베이스 클래스
    │   └── swing_strategy.py # 모델 예측 확률 기반 진입 및 동일 비중 할당 전략
    │
    ├── backtest/             # VectorBT 기반 백테스트 시뮬레이터 엔진
    │   ├── __init__.py
    │   ├── engine.py         # 수수료/세금을 고려한 동적 소프트/하드 스톱 시뮬레이션 및 성과 집계
    │   └── metrics.py        # 백테스트 관련 평가 지표
    └── dashboard/            # 실험 성과 시각화 분석
        └── app.py            # 월별 히트맵 및 피처 기여도 분석용 Streamlit 웹 어플리케이션
```
