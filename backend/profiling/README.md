# 🟡 Profiling Block — 사용자 내부 정보

담당: 중현

## 역할

사용자의 투자 심리와 성향을 설문으로 수집하고, 다음 블록(analysis)이
사용할 수 있는 표준 JSON으로 변환한다.

## 디렉토리

```
/survey   설문 문항 정의 + 답변→스키마 변환 로직
/schema   profiling 블록이 출력하는 JSON 스키마
```

## 입출력

- 입력: 사용자 설문 응답 (객관식 5문항 + 자유 텍스트 1문항)
- 출력: `schema/profiling_output.schema.json` 형식의 JSON
  - `investor_profile` — RRTTLLU 기반 (R·T·L)
  - `psychological_state` — FOMO·패닉셀·군집행동·과열
  - `context` — 종목, 금액, 행동 의도
  - `meta` — 버전, 신뢰도

## 다음 블록으로 넘기는 계약

analysis/chart · analysis/text 는 이 JSON을 모델 입력 컨텍스트로 사용한다.
스키마 변경 시 반드시 팀 공유 후 버전을 올린다.
