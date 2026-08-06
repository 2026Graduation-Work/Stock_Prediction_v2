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

## 8축 진단 (schema v1.1 대응)

| 모듈 | 역할 |
| --- | --- |
| `survey/style_questions.py` | 8축 문항 은행(리커트 5점), 축 정의, 보유기간 구간표 |
| `survey/style_scoring.py` | 축 점수·신뢰도 산출, 모순 검출, v1.0 필드 축약 |
| `survey/style_personas.py` | 발표·데모용 고정 응답셋 |

축당 복수 문항을 두어 축 점수와 함께 **신뢰도(응답 일관성)** 를 산출한다.
기존 설문은 문항 하나가 축 하나에 대응해 일관성을 볼 수 없었고, 그래서
`confidence_per_field`를 실제로 계산할 근거가 없었다.

- 축마다 역채점 문항을 최소 1개 둔다. 무조건 동의하는 응답 습관을 잡아내야
  신뢰도가 의미를 갖는다.
- 신뢰도 = `일관성 × 응답률`. 같은 축 문항끼리 답이 갈릴수록, 미응답이 많을수록 낮아진다.
- `quick`(축당 3문항 · 24문항) / `detailed`(축당 5문항 · 40문항)은 문항 수만
  다르고 스코어링 규칙은 같다.

### v1.0 필드 축약

8축에서 기존 v1.0 필드를 결정론적으로 되돌려 소비자(chart·text·platform)가
변경 없이 동작하게 한다. 규칙은 `schema/profiling_output.schema.json`의
`style_axes` 설명과 `style_scoring.LEGACY_RATIO_FIELDS`가 일치해야 한다.

| v1.0 필드 | 원천 축 |
| --- | --- |
| `risk_tolerance` | `loss_tolerance` |
| `fomo_index` | `urgency` |
| `panic_sell_tendency` | `drawdown_reaction` |
| `herding_score` | `information_reliance` |
| `time_horizon_days` (v1.1 optional) | `turnover` (구간표는 `style_questions.TURNOVER_DAY_RULES`가 SSOT) |
| `time_horizon_months` | `round(time_horizon_days / 30)` |

### 모순 검출

축 간 상충을 규칙 테이블로만 잡는다. **점수를 보정하지 않고 관측 사실만 남긴다.**
해석과 후속 확인은 화면·상담이 맡는다(HITL).

- 규칙마다 전용 테스트가 있어야 한다. 없으면 `test_every_rule_has_a_dedicated_test`가 실패한다.
- 방향을 믿기 어려운 축(신뢰도 `MIN_CONFIDENCE_FOR_CONTRADICTION` 미만)으로는
  모순을 주장하지 않는다.
- `observation`·`follow_up_question`에 행동 제안 문구를 넣지 않는다
  (`AGENTS.md` 사용자 노출 표현 규칙). 테스트가 금지 표현을 검사한다.

### 아직 연결하지 않은 것

`converter.convert()`의 출력은 여전히 v1.0이다. `style_axes`·`contradictions`를
출력에 싣는 배선은 schema v1.1이 합의된 뒤 후속 PR에서 한다.
