# BigKinds 뉴스 수집 방식 결정

- 상태: 채택
- 결정일: 2026-07-09
- 문서 정리: 2026-07-19
- 적용 범위: `backend/analysis/text/`

## 배경

FinBERT 감성 분석에 사용할 과거 뉴스를 확보해야 한다. BigKinds는 검색 결과를 Excel로
내려받을 수 있지만 한 번에 받을 수 있는 건수가 제한되어, 종목과 기간에 따라 여러 파일을
병합해야 한다.

초기 조사에서는 내부 검색 요청 재현과 브라우저 자동화를 포함한 자동 수집 가능성을
검토했다. 그러나 2026-07-09 확인 당시 BigKinds 이용약관은 사전 협의 없는 자동화 도구의
접근·수집을 제한하고 있었다. 기술적으로 가능하다는 이유만으로 내부 API를 제품 경로로
사용하지 않기로 했다.

이 문서는 팀의 데이터 취급 결정을 기록하며 법률 자문을 대신하지 않는다. 이용 조건은
변경될 수 있으므로 공식 경로 도입 전에는 최신 약관을 다시 확인한다.

## 결정

1. 현재 뉴스 원본은 사람이 BigKinds UI에서 직접 내려받은 `NewsResult_*.xlsx`만 사용한다.
2. 내부 JSON API 호출, 다운로드 요청 재현, Playwright 등 자동화 수집은 구현하지 않는다.
3. 자동 수집이 필요해지면 BigKinds 공식 OPEN API의 신청·승인을 먼저 받는다.
4. SNS 데이터는 현재 연구 범위에서 제외하고 뉴스 감성만 심리 피처로 사용한다.
5. LLM은 뉴스의 핵심 사건과 설명 텍스트를 정리하는 데만 사용한다. 감성 점수와 모델 입력
   수치는 결정론적 코드와 FinBERT 결과로 계산한다.

## 현재 파이프라인

원본 Excel은 `backend/analysis/text/data/raw/` 아래에 두며 하위 디렉터리도 허용한다.
파일명에 적힌 기간은 실제 수록 기간의 근거로 사용하지 않는다.

저장소의 `backend/`에서 다음 명령을 실행한다.

```bash
python -m analysis.text.preprocess --ticker 005930 --out news_corpus.csv
```

파이프라인은 파일을 재귀 탐색하고, 뉴스 ID 또는 제목·일자·언론사 키로 중복을 제거한 뒤
`news_id,date,title,body,press,ticker` 계약의 CSV를 만든다. 실제 수록 기간과 일자 구멍은
표준 출력 리포트에서 확인한다.

## 보안·저장 원칙

- 조사 중 생성된 세션 쿠키, 응답 헤더, 원본 HTML, 내부 API payload는 저장소에 커밋하지
  않는다.
- 뉴스 원문 Excel과 가공 데이터는 Git에 올리지 않고 팀이 합의한 데이터 저장소에서 관리한다.
- 저장소에는 재현 가능한 코드, 스키마, 컬럼 계약, 데이터 해시·기간·종목 manifest만 남긴다.

## 영향

- 수동 다운로드와 2만 건 단위 분할 작업이 필요하다.
- 파일 간 기간 중첩을 전제로 중복 제거와 실제 날짜 커버리지 검증이 필수다.
- 공식 OPEN API 승인을 받거나 데이터 제공 조건이 바뀌면 이 결정을 다시 검토한다.

## 근거

- [BigKinds 이용약관](https://www.bigkinds.or.kr/v2/account/agreement.do)
- [BigKinds 사용자 매뉴얼](https://www.bigkinds.or.kr/manual/%EB%B9%85%EC%B9%B4%EC%9D%B8%EC%A6%88_%EC%82%AC%EC%9A%A9%EC%9E%90%EB%A7%A4%EB%89%B4%EC%96%BC.pdf)
- [뉴스 전처리 실행 안내](../../backend/analysis/text/README.md)
