# 🟢 Analysis · Text — 뉴스/재무제표/SNS

담당: 서환

## 역할

뉴스 감성, 재무제표(가치투자 펀더멘털), SNS 심리를 분석하여
시장 외부 정보를 정량화한다.

## 입력 데이터

- 뉴스 본문 — 뉴스 API 크롤링 (한국어)
- 재무제표 — DART OpenAPI
- SNS 심리 — Reddit API
- profiling 블록의 사용자 컨텍스트 JSON

## 핵심 원칙: 할루시네이션 = 즉사

- 정량 데이터(PER 등 수치)는 DB/API에서 직접 조회
- LLM은 해석·요약만 담당, 수치를 생성하지 않음

## 코드

- `value_pipeline/` — 가치투자 피처 전처리 파이프라인 (DART 재무제표 + 감성 → 구조화 JSON).
  실행: `analysis/text/`에서 `python -m value_pipeline.run` (API 키 없으면 동봉 샘플·규칙 기반으로 동작).
- `gdelt_samsung.py` — GDELT DOC API로 뉴스 수집 (무료, 키 불필요).

## 참고

- HuggingFace FinBERT (사전학습 금융 감성 모델)
