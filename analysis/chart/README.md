# 🟢 Analysis · Chart — 차트/기술적 분석

담당: 진세

## 역할

주가 차트와 기술적 분석 지표를 기반으로 가격 흐름을 분석한다.
화이트박스 원칙에 따라 DT(Decision Tree) 계열 머신러닝 모델을 사용한다.

## 입력 데이터

- OHLCV (시가/고가/저가/종가/거래량) — yfinance, KRX API
- 기술 분석 지표 3대 카테고리
  - 추세 (Trend): 이동평균선, MACD 등
  - 모멘텀 (Momentum): RSI, 스토캐스틱 등
  - 변동성 (Volatility): 볼린저밴드, ATR 등
- profiling 블록의 사용자 컨텍스트 JSON

## 모델 후보

RandomForest / XGBoost / LightGBM (회의 ②에서 1차 선정)

## 참고

- Microsoft Qlib: https://github.com/microsoft/qlib
