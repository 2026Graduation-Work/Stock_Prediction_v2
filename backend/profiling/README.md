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

- 입력: 화면 설문(`frontend/app/survey`) — 8축 빠른 진단 리커트 24문항 + 투자 경험 1 +
  제외할 종목 유형(선택, `avoided_assets`) + 자유 텍스트(선택)
- 출력: `schema/profiling_output.schema.json` v1.1 JSON (`style_axes`·`contradictions` 포함)

## 어디에 무엇이 있나 (채점 정본은 TS 한 벌)

| 파일 | 역할 |
| --- | --- |
| `frontend/lib/profiling/style-questions.json` | 8축 문항 정의(정본): 축, 리커트 40·빠른 진단 24, 보유기간 구간표, 데모 프리셋. 리커트와 시나리오형(선택지별 축 점수)을 모두 담을 수 있다 |
| `frontend/lib/profiling/style-scoring.ts` | 축 점수·신뢰도, 모순 검출, v1.0 필드 축약 |
| `frontend/lib/profiling/style-golden-cases.json` | 골든 10건. 삭제 전 Python `style_scoring.py`로 계산한 기대값이며 TS 채점기가 이 값과 같아야 한다 |
| `frontend/lib/profiling-rules.ts` | 설문 응답 → schema 출력 변환, 3축 요약(성향 카드) |
| `frontend/lib/profiling/bit.ts` | 8축 → BIT 유형(카드 순서·넛지) |
| `survey/test_question_bank.py` | 문항 JSON이 schema `style_axes` 계약과 맞는지 검사 |

Python 채점(`converter.py`, `questions.py`, `style_questions.py`, `style_scoring.py`,
`style_personas.py`)은 화면과 채점이 갈라지지 않도록 TS로 옮기고 삭제했다(2026-09-19).

## 8축 채점

축당 복수 문항을 두어 축 점수와 함께 **신뢰도(응답 일관성)** 를 산출한다.

- 축마다 역채점 문항을 최소 1개 둔다. 무조건 동의하는 응답 습관을 잡아내야
  신뢰도가 의미를 갖는다(골든 케이스 `reverse_keyed_mismatch_all_agree`).
- 신뢰도 = `일관성 × 응답률`. 같은 축 문항끼리 답이 갈릴수록, 미응답이 많을수록 낮아진다.
- 시나리오형 문항은 고른 선택지의 축 점수(-2~+2)를 그 축에 넣는다.

### 화면 3축 = 8축 묶음 요약

| 성향 카드 | 원천 축 |
| --- | --- |
| 위험 감수 | mean(`loss_tolerance`, `concentration`) |
| 흔들림 민감도 | mean(`urgency`, `drawdown_reaction`, `information_reliance`) |
| 투자 기간 | `turnover` |

값은 ratio(-1~1)를 0~100으로 옮긴 것이고 DB `ips_profiles.risk_score·fomo_score·horizon_score`에도
같은 값을 저장한다. 결과 이름은 BIT 유형명(자산 보존형·추종형·독립 분석형·적극 축적형)만 쓴다.

### v1.0 필드 축약

| v1.0 필드 | 원천 축 |
| --- | --- |
| `risk_tolerance` | `loss_tolerance` |
| `fomo_index` | `urgency` |
| `panic_sell_tendency` | `drawdown_reaction` |
| `herding_score` | `information_reliance` |
| `time_horizon_days` (v1.1 optional) | `turnover` (구간표는 `style-questions.json` `turnover_day_rules`) |
| `time_horizon_months` | `round(time_horizon_days / 30)` |

8축에 원천 문항이 없는 필드는 이렇게 채운다: `liquidity_need_ratio`는 투자 기간 구간표
(12개월 이하 0.7 · 60개월 이하 0.25 · 그 외 0.1), `self_confidence`는
`(1 - information_reliance.ratio) / 2`. `profile_type`은 `risk_tolerance × 100 ≥ 60`이면 aggressive.

### 모순 검출

축 간 상충을 규칙 테이블로만 잡는다. **점수를 보정하지 않고 관측 사실만 남긴다.**
결과 확인 화면이 관측과 확인 질문을 보여 주고, 사용자가 확정하거나 직접 조정한다(HITL).
방향을 믿기 어려운 축(신뢰도 0.3 미만)으로는 모순을 주장하지 않는다.
