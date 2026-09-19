# 심리 피처 검증 샘플

`PSYCHOLOGY_FEATURES.md`의 형식을 눈으로 확인하기 위한 소규모 샘플이다.

- `psychology_market_v1_sample.csv` — 종목당 8행만 잘라낸 산출물 발췌
- `psychology_market_v1_sample.meta.json` — 그 샘플을 만든 **전체 실행**의 메타데이터
  (168행 / 3종목 / 2024-04-01~2024-06-17)

재현 명령:

```bash
python -m experiments.features.build_psychology_features \
    --demo --demo-periods 120 --out <임시경로>.parquet \
    --sample-csv experiments/features/samples/psychology_market_v1_sample.csv \
    --sample-rows 8
```

**여기 있는 숫자는 연구 결과가 아니다.** 시드를 고정한 합성 가격 패널
(`psychology/demo_panel.py`)로 만든 값이며, 형식·결정론 확인 용도다. 실제 값은
`data/processed`를 만든 뒤 `--price-dir data/processed`로 생성한다. 실제 피처
데이터와 feature store는 용량 때문에 Git에 올리지 않는다.
