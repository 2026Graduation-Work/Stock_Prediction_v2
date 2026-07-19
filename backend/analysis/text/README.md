# 🟢 Analysis · Text — 뉴스/재무제표

담당: 서환

## 역할

뉴스 감성과 재무제표(가치투자 펀더멘털)를 분석하여 시장 외부 정보를 정량화한다.
SNS 데이터는 현재 연구 범위에서 제외한다.

## 입력 데이터

- 뉴스 본문 — BigKinds UI에서 수동 다운로드한 Excel (한국어)
- 재무제표 — DART OpenAPI
- profiling 블록의 사용자 컨텍스트 JSON

## 핵심 원칙: 할루시네이션 = 즉사

- 정량 데이터(PER 등 수치)는 DB/API에서 직접 조회
- LLM은 핵심 사건과 설명 텍스트 정리만 담당하며, 점수 산출과 종목 필터링에 관여하지 않음

## 코드

- `value_pipeline/` — 가치투자 피처 전처리 파이프라인 (DART 재무제표 + 감성 → 구조화 JSON).
  실행: `backend/analysis/text/`에서 `python -m value_pipeline.run` (API 키 없으면 동봉 샘플·규칙 기반으로 동작).
- `gdelt_samsung.py` — 과거 대안 소스 조사 스크립트. 현재 입력 경로에는 사용하지 않음.
- `preprocess.py` — 빅카인즈 수동 다운로드 엑셀을 병합·정제하여 FinBERT 입력 CSV 생성.

## 빅카인즈 뉴스 전처리

1. 종목별로 `backend/analysis/text/data/raw/<6자리 종목코드>/` 디렉터리를 만들고 해당
   종목의 `NewsResult_*.xlsx` 파일을 둔다. 예: 삼성전자는 `data/raw/005930/`.
   같은 종목의 분할 파일은 모두 재귀 탐색하며, 파일명에 적힌 기간은 커버리지 계산에
   사용하지 않는다.
2. `pip install -r analysis/text/requirements-preprocess.txt`로 의존성을 설치한다.
3. 저장소의 `backend/` 디렉터리에서 실행한다.

```bash
python -m analysis.text.preprocess --ticker 005930 --out news_corpus.csv
```

`--ticker`와 같은 이름의 종목 디렉터리가 있으면 그 디렉터리만 읽으므로 다른 종목 뉴스가
한 CSV에 섞이지 않는다. 기존처럼 `raw/` 바로 아래에 파일을 둔 단일 종목 구조도 지원한다.

상대 `--out` 경로는 `backend/analysis/text/data/processed/`를 기준으로 해석한다. 결과 CSV는
`news_id,date,title,body,press,ticker` 컬럼으로 고정되며, 실제 수록 기간과 뉴스가 0건인 날짜는
표준 출력 리포트에서 확인할 수 있다.

## 참고

- [BigKinds 뉴스 수집 방식 결정](../../../docs/decisions/bigkinds-acquisition.md)
- HuggingFace FinBERT (사전학습 금융 감성 모델)
