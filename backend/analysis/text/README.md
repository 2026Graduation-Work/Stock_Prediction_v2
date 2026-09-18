# 🟢 Analysis · Text — 뉴스/재무제표

담당: 서환

## 역할

뉴스 감성과 재무제표(가치투자 펀더멘털)를 분석하여
시장 외부 정보를 정량화한다.
(SNS/소셜 심리는 데이터 확보 난이도로 파이프라인에서 제외됨 → News + Financial 2-에이전트.)

## 입력 데이터

- 과거 뉴스 — 빅카인즈 수동 다운로드 엑셀(`data/<종목코드>/{회사명}_{YYYYMMDD}-{YYYYMMDD}.xlsx`)
- 최근 뉴스 — NewsAPI.ai 한국어 기사(`NEWSAPI_AI_KEY` 필수). 여러 종목을 1회 OR 검색으로 묶음
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

## 뉴스 심리지수 2-track

두 트랙은 소스와 시간 창만 다르고, 관련성 필터와 `sentiment.score_texts()`
(KR-FinBERT 우선, 없으면 사전 폴백)를 공유한다. 이는 매수·매도 지시가 아니라
사용자가 현재 판단을 재점검하는 근거이다.

- `historical`: BigKinds 과거 기사 → 일별 평균 감성·의견 분산·기사 수 추이
- `live`: NewsAPI.ai 최근 7일 → 오늘/최근 7일 감성·최신 기사 시각·지연 분

`.env`:

```dotenv
NEWSAPI_AI_KEY=...
```

과거 트랙 생성:

```bash
cd backend/analysis/text
python -m value_pipeline.news_run historical \
  --target 005930:삼성전자 --start 2022-01-01 --end 2022-12-31
```

최근 뉴스를 즉시 1회 수집(종목 수와 무관하게 API 1회):

```bash
python -m value_pipeline.news_run live \
  --target 005930:삼성전자 --target 000660:SK하이닉스
```

1시간 주기 갱신:

```bash
python -m value_pipeline.news_run live \
  --target 005930:삼성전자 --target 000660:SK하이닉스 \
  --watch --interval-minutes 60
```

`live`는 보도 시각과 API 색인 지연이 있는 **1시간 갱신형(near-real-time)**이지,
틱 단위 실시간은 아니다. 산출 JSON은 기사 본문을 저장하지 않고 `news_id`, 제목,
언론사, URL, 시각, 사건 ID, 감성 결과만 보존한다.

## 빅카인즈 뉴스 전처리

1. 종목별로 저장소 루트 `data/<6자리 종목코드>/` 디렉터리를 만들고 그 종목의 빅카인즈 원본
   엑셀을 둔다. 예: 삼성전자는 `data/005930/삼성전자_20220101-20221231.xlsx`.
   이 `data/`는 value_pipeline의 point-in-time 로더(`load_daily_news`)와 **공유하는 기준
   디렉터리**(`preprocess.DEFAULT_NEWS_DIR`)이며, 두 소비자 모두 `<기준>/<종목코드>/`를 먼저
   해석하므로 다른 종목 뉴스가 섞이지 않는다. 파일명은 `{회사명}_{YYYYMMDD}-{YYYYMMDD}.xlsx`
   (신규 `{종목코드}_{회사명}_{기간}`·레거시 `NewsResult_*.xlsx`도 인식), 종목 폴더 안은 재귀
   탐색하며 파일명에 적힌 기간은 커버리지 계산에 쓰지 않는다. 종목 폴더가 하나도 없으면
   기준 디렉터리 평면 구조로 폴백한다(구버전 호환).
2. `pip install -r analysis/text/requirements.txt`로 의존성을 설치한다.
3. 저장소의 `backend/` 디렉터리에서 실행한다.

```bash
python -m analysis.text.preprocess --ticker 005930 --out news_corpus.csv
```

`--ticker`와 같은 이름의 종목 디렉터리가 있으면 그 폴더만 읽어 한 CSV에 다른 종목이 섞이지
않는다. 종목 디렉터리가 하나도 없으면 기존처럼 기준 디렉터리 평면 구조를 읽는다(단일 종목).

상대 `--out` 경로는 `backend/analysis/text/data/processed/`를 기준으로 해석한다. 결과 CSV는
`news_id,date,title,body,press,ticker` 컬럼으로 고정되며, 실제 수록 기간과 뉴스가 0건인 날짜는
표준 출력 리포트에서 확인할 수 있다.

## 참고

- [BigKinds 뉴스 수집 방식 결정](../../../docs/decisions/bigkinds-acquisition.md)
- HuggingFace FinBERT (사전학습 금융 감성 모델)
