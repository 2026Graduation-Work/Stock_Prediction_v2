# 심리 피처 A/B 비교실험

연구 질문 **“심리 지수를 반영하면 예측이 나아지는가?”**에 답하기 위한 고정 실험 러너다.
`stable/aggressive × baseline/treatment` 총 4런을 같은 행 집합·기간·시드·평가 함수로 실행한다.

## 입력 계약

CSV 또는 Parquet 한 행은 학습·평가에 쓰는 `날짜 × 종목` 관측치를 나타내며 다음 컬럼이 필요하다.

- 키: `Date`(`YYYY-MM-DD`, 시간 정보 없음), `Code`(앞자리 0을 보존한 6자리 문자열)
- Baseline: `config.yaml`의 `features.baseline` 또는 기준 모델의 `feature_names`
- Treatment 전용: `synthetic_psychology_index`, `news_sentiment`
- 정답: `Target_H20`(stable), `Target_H5`(aggressive), 모두 0/1
- 트레이딩: 신호 다음 거래일의 `Next_Day_Return`
- 급변구간: 날짜별 시장 변동성 `Market_Volatility`

누락값을 러너 안에서 임의 보간하지 않는다. 뉴스가 없는 날짜를 중립값 `0.0`으로 볼지 등은 데이터
생성 단계에서 명시적으로 결정해야 한다. 필요한 모든 컬럼이 완전한 공통 행만 입력해야 A/B 표본이
달라지는 문제를 막을 수 있다.

## 실행

`backend/analysis/chart/`에서 실행한다.

```bash
cp experiments/comparison/config.example.yaml experiments/comparison/config.yaml
python -m experiments.comparison.runner --config experiments/comparison/config.yaml
```

현재 저장소에는 원천 `data/processed/`와 결합된 심리 피처 테이블이 없으므로, 실제 결과 실행 전에
`data/comparison/comparison_input.parquet`를 준비해야 한다. 기존 baseline 예측 캐시는 확률만 담고
있어 정답·수익률·Treatment 재학습을 대체할 수 없다.

## 산출물

- `four_run_metrics.csv`: 전체 구간 4런 지표
- `volatile_subsample_metrics.csv`: 변동성 상위 20% 날짜의 4런 지표
- `comparison_deltas.csv`: 성향·표본별 `B - A` 차이
- `comparison_results.json`: 위 표의 JSON 묶음
- `experiment_manifest.json`: 시드, 기간, 실제 피처, 행 해시, 급변일 목록
- `predictions/*.parquet`: 각 런의 감사 가능한 OOS 예측

ML 지표는 AUC, 0.5 기준 적중률, Brier score, 10-bin ECE다. Trading 지표는 매일 확률 임계값을
넘는 상위 N종목의 다음 날 동일가중 수익률로 계산한 Sharpe, MDD, 누적수익률, 거래 수다. 급변일은
테스트 구간의 날짜별 평균 시장 변동성을 내림차순 정렬하여 정확히 상위 20%를 선택한다.

테스트용 합성 fixture에서 나온 숫자를 연구 결과로 보고하지 않는다. 실제 결론은 반드시 결합된
원천 데이터로 생성한 manifest와 함께 제시한다.
