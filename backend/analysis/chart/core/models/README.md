# Chart model artifacts

이 디렉터리의 배포 모델은 3분류 LightGBM Booster다. 클래스는 `0=하락`,
`1=중립`, `2=상승`이며 서비스가 사용하는 스코어는 class 2의 확률이다.
화면에서는 이를 미래 상승 확률로 단정하지 않고 과거 유사 신호 기준의 상대
스코어로 설명한다.

## 2025 holdout 모델 반입

현재 저장소에는 2022~2024 학습·2025 holdout 모델이 없다. Colab 실행이 성공한
뒤 Drive export의 다음 두 파일만 실제 해시와 평가 결과를 확인하고 반입한다.

```text
baseline_h5_u175_d150_train2022_2024_holdout2025.txt
baseline_h20_u375_d300_train2022_2024_holdout2025.txt
```

[`registry.example.yaml`](registry.example.yaml)을 `registry.yaml`로 복사하고
`sha256`을 `artifact_manifest.json`의 값으로 교체한다. 존재하지 않는 모델을
가리키는 registry는 만들지 않는다.

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
