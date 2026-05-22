# 🟢 Green Block — LLM (뉴스/재무제표/SNS)

담당: 서환

## 역할

뉴스 감성, 재무제표(가치투자 펀더멘털), SNS 심리를 분석하여
시장 외부 정보를 정량화한다.

## 입력 데이터

- 뉴스 본문 — 뉴스 API 크롤링 (한국어)
- 재무제표 — DART OpenAPI
- SNS 심리 — Reddit API
- yellow 블록의 사용자 컨텍스트 JSON

## 핵심 원칙: 할루시네이션 = 즉사

- 정량 데이터(PER 등 수치)는 DB/API에서 직접 조회
- LLM은 해석·요약만 담당, 수치를 생성하지 않음

## 참고

- HuggingFace FinBERT (사전학습 금융 감성 모델)
