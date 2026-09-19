# 차트 분석 블록

기술적 피처와 3분류 LightGBM으로 profile별 상대 스코어를 생성하고 공용 평가·백테스트를
수행한다.

설치, 데이터, 모델, config, 학습, 평가, 추론, 추가 피처, 파일 구조는
[`ONBOARDING.md`](ONBOARDING.md) 하나를 기준으로 한다.

빠른 검증:

```bash
pip install -r requirements.txt
ruff check .
pytest
```
