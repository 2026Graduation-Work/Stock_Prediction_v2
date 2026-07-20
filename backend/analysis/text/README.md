# 🟢 Analysis · Text — 뉴스/재무제표

담당: 서환

## 역할

뉴스 감성과 재무제표(가치투자 펀더멘털)를 분석하여
시장 외부 정보를 정량화한다.
(SNS/소셜 심리는 데이터 확보 난이도로 파이프라인에서 제외됨 → News + Financial 2-에이전트.)

## 입력 데이터

- 뉴스 — 빅카인즈 수동 다운로드 엑셀(`data/raw/{종목코드}/NewsResult_*.xlsx`) 우선,
  없으면 네이버 검색 OpenAPI / HTML 크롤로 폴백 (한국어)
- 재무제표 — DART OpenAPI (`DART_API_KEY` 필수)
- profiling 블록의 사용자 컨텍스트 JSON

## 핵심 원칙: 할루시네이션 = 즉사

- 정량 데이터(PER 등 수치)는 DB/API에서 직접 조회
- **점수 산출은 100% 결정론.** 뉴스 관련성 판정까지 규칙으로 한다 — 어떤 기사를 채점할지
  LLM이 정하면 그건 곧 점수를 LLM이 정하는 것이다
- LLM은 핵심 이벤트 추출·근거 문장만 담당. `GEMINI_API_KEY` 유무로 숫자가 바뀌면 버그
- LLM 출력은 content-hash로 캐시되어 설명 텍스트까지 재현 가능

## 코드

- `value_pipeline/` — 가치투자 피처 전처리 파이프라인 (빅카인즈 뉴스 감성 + DART 재무제표 → 구조화 JSON).
  LangGraph 오케스트레이션:
  `START → ingest → {news_agent ‖ financial_agent} → validation_agent → synthesis_agent → END`.
  뉴스 수집은 `preprocess.load_daily_news()`(빅카인즈 point-in-time 로더)를 우선 사용한다.
  실행: `backend/analysis/text/`에서 `python -m value_pipeline.run`.
  **검증 기준: [VALUE_PIPELINE_VALIDATION.md](VALUE_PIPELINE_VALIDATION.md)** — 출력을 데이터셋에
  넣기 전에 반드시 이 문서의 PASS/FAIL 기준을 따를 것.
- `preprocess.py` — 빅카인즈 수동 다운로드 엑셀을 병합·정제하여 FinBERT 입력 CSV 생성.
  `load_daily_news()`는 value_pipeline이 쓰는 하루치 point-in-time 로더.

## 빅카인즈 뉴스 전처리

1. `NewsResult_*.xlsx` 파일을 `backend/analysis/text/data/raw/{종목코드}/` 아래에 둔다.
   하위 디렉터리를 재귀 탐색하며, 파일명에 적힌 기간은 커버리지 계산에 사용하지 않는다.
2. `pip install -r analysis/text/requirements.txt`로 의존성을 설치한다.
3. 저장소의 `backend/` 디렉터리에서 실행한다.

```bash
python -m analysis.text.preprocess --ticker 005930 --out news_corpus.csv
```

상대 `--out` 경로는 `backend/analysis/text/data/processed/`를 기준으로 해석한다. 결과 CSV는
`news_id,date,title,body,press,ticker` 컬럼으로 고정되며, 실제 수록 기간과 뉴스가 0건인 날짜는
표준 출력 리포트에서 확인할 수 있다.

## 참고

- HuggingFace FinBERT (사전학습 금융 감성 모델)
