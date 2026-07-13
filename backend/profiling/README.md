# 🟡 Profiling Block — 사용자 내부 정보

담당: 중현

## 역할

사용자의 투자 심리와 성향을 설문으로 수집하고, 다음 블록(analysis)이
사용할 수 있는 표준 JSON으로 변환한다.

## 디렉토리

```
/survey   설문 문항 정의 + 답변→스키마 변환 로직
schema/   저장소 루트의 profiling_output.schema.json v1.0 계약
```

## 입출력

- 입력: 사용자 설문 응답 (객관식 5문항 + 회피 체크 Q6 + 자유 텍스트 Q7)
- 출력: `schema/profiling_output.schema.json` 형식의 JSON
  - `investor_profile` — RRTTLLU 기반 (R·T·L)
  - `psychological_state` — FOMO·패닉셀·군집행동·과열
  - `context` — 종목, 금액, 행동 의도
  - `meta` — 버전, 신뢰도

## 다음 블록으로 넘기는 계약

backend/analysis/chart · backend/analysis/text 는 이 JSON을 모델 입력 컨텍스트로 사용한다.
스키마 변경 시 반드시 팀 공유 후 버전을 올린다.

## 변환

`survey/`에서 `from converter import convert`로 사용한다. 문항별 3축 점수표와
`stable/aggressive` 임계값, `H5/H10/H20` 매핑은 `survey/questions.py`가 정본이다.
동일 입력은 항상 동일 JSON을 반환하며 ID와 완료 시각도 입력으로 전달해야 한다.
