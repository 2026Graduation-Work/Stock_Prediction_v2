# Chart model artifacts

이 디렉터리의 배포 모델은 3분류 LightGBM Booster다. 클래스는 `0=하락`,
`1=중립`, `2=상승`이며 서비스가 사용하는 스코어는 class 2의 확률이다.
화면에서는 이를 미래 상승 확률로 단정하지 않고 과거 유사 신호 기준의 상대
스코어로 설명한다.

## 2025 holdout 모델 반입

다음 두 모델은 2022~2024 학습·2025 final holdout 실행 결과의 SHA-256과 161개
피처·3분류 계약을 확인한 뒤 반입했다. 실제 profile 매핑과 해시는
[`registry.yaml`](registry.yaml)이 정본이다.

```text
baseline_h5_u175_d150_train2022_2024_holdout2025.txt
baseline_h20_u375_d300_train2022_2024_holdout2025.txt
```

새 모델로 교체할 때는 Colab `artifact_manifest.json`의 commit·SHA-256과 공용 ML 및
백테스트 결과를 검증한 뒤 모델과 registry를 함께 갱신한다.

## Python 추론

입력은 날짜 오름차순의 일봉 `Date, Open, High, Low, Close, Volume`이며 안정적인
60일 피처 계산을 위해 최소 65개 관측치가 필요하다.

```python
from pathlib import Path
import pandas as pd

from core.inference import load_prediction_model, predict_success_probability

model = load_prediction_model(
    Path("core/models/baseline_h5_u175_d150_train2022_2024_holdout2025.txt")
)
prices = pd.read_parquet("data/raw/005930.parquet").sort_values("Date").tail(85)
prob_up = predict_success_probability(prices, model)
latest_score = float(prob_up.iloc[-1])
```

- `aggressive` 프로파일은 H5, `stable` 프로파일은 H20을 선택한다.
- `predict_success_probability`는 저장 모델의 161개 피처 순서를 그대로 검사해
  class 2 확률만 반환한다.
- 모델의 학습 종료일, holdout 기간, SHA-256과 적용 라벨을 결과 근거에 함께 남긴다.
- 자동 매매 지시를 만들지 않는다. 스코어는 사용자가 판단할 수 있는 재점검 정보다.
