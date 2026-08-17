# 차트 분석 블록

기술적 피처와 3분류 LightGBM으로 profile별 상대 스코어를 생성하고 공용 평가·백테스트를
수행한다.

## 문서 안내

사람이 읽고 관리하는 chart 문서는 `docs/`에 모은다.

| 문서 | 역할 |
| --- | --- |
| [`docs/ONBOARDING.md`](docs/ONBOARDING.md) | 설치, 데이터, 모델, 학습·평가·추론과 A/B 실행 |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) | 날짜순 작업 기록과 현재 검증 상태 |
| [`docs/EXPERIMENT_RESULTS.md`](docs/EXPERIMENT_RESULTS.md) | 대표 실험 결과와 해석 |

완료된 실험 계획이나 회의용 로드맵은 별도 문서로 남기지 않고 진행 기록과 결과
정본에 반영한다. 자동 생성 report와 config snapshot은 근거 산출물이므로 각 결과
폴더에 둔다.

빠른 검증:

```bash
pip install -r requirements.txt
ruff check .
pytest
```
