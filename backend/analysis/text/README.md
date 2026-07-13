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
  실행: `backend/analysis/text/`에서 `python -m value_pipeline.run` (API 키 없으면 동봉 샘플·규칙 기반으로 동작).
- `gdelt_samsung.py` — GDELT DOC API로 뉴스 수집 (무료, 키 불필요).
- `preprocess.py` — 빅카인즈 수동 다운로드 엑셀을 병합·정제하여 FinBERT 입력 CSV 생성.

## 빅카인즈 뉴스 전처리

1. `NewsResult_*.xlsx` 파일을 `backend/analysis/text/data/raw/` 아래에 둔다. 하위 디렉터리도
   재귀 탐색하며, 파일명에 적힌 기간은 커버리지 계산에 사용하지 않는다.
2. `pip install -r analysis/text/requirements-preprocess.txt`로 의존성을 설치한다.
3. 저장소의 `backend/` 디렉터리에서 실행한다.

```bash
python -m analysis.text.preprocess --ticker 005930 --out news_corpus.csv
```

상대 `--out` 경로는 `backend/analysis/text/data/processed/`를 기준으로 해석한다. 결과 CSV는
`news_id,date,title,body,press,ticker` 컬럼으로 고정되며, 실제 수록 기간과 뉴스가 0건인 날짜는
표준 출력 리포트에서 확인할 수 있다.

## 참고

- HuggingFace FinBERT (사전학습 금융 감성 모델)
