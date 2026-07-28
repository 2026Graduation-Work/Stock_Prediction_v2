"""발표·데모용 고정 응답셋 — profiling 블록.

발표 중에 40문항을 다 풀 수 없다. 프리셋을 고르면 곧바로 결과 화면까지
갈 수 있어야 리허설과 시연이 안정된다.

각 프리셋은 축별 리커트 응답 패턴만 정의하고, 실제 문항 id는
`style_questions`에서 조립한다. 문항을 더하거나 빼도 프리셋이 깨지지 않는다.

응답 패턴은 축 방향 기준이다. `+2`는 축의 positive_label 쪽으로 강하게,
`-2`는 negative_label 쪽으로 강하게라는 뜻이며, 문항의 역채점 여부는
조립 단계에서 자동으로 반영된다.
"""

from __future__ import annotations

from typing import Any, Final

from style_questions import AXIS_IDS, LIKERT_NEUTRAL, questions_for_mode

# 축 방향 기준 강도. 조립 시 direction을 곱해 실제 리커트 값으로 바꾼다.
PERSONAS: Final = (
    {
        "id": "cautious_saver",
        "label": "예금 중심 전환기형",
        "summary": (
            "원금 보전을 가장 중요하게 보면서 시장 참여는 일부만 원하는 유형입니다. "
            "장기 보유를 전제하지만 하락에는 민감합니다."
        ),
        "pattern": {
            "market_participation": -1,
            "loss_tolerance": -2,
            "holding_horizon": -2,
            "concentration": -2,
            "rule_adherence": -2,
            "information_reliance": -1,
            "urgency": -1,
            "drawdown_reaction": 1,
        },
    },
    {
        "id": "anxious_chaser",
        "label": "조급한 추종형",
        "summary": (
            "주변 이야기에 따라 움직이고 조급함이 큰 유형입니다. "
            "손실은 부담스러워하면서 집중투자를 선호해 상충이 드러납니다."
        ),
        "pattern": {
            "market_participation": -1,
            "loss_tolerance": -1,
            "holding_horizon": 1,
            "concentration": 2,
            "rule_adherence": 2,
            "information_reliance": 2,
            "urgency": 2,
            "drawdown_reaction": 2,
        },
    },
    {
        "id": "systematic_investor",
        "label": "규칙 기반 분산형",
        "summary": (
            "사전에 정한 기준을 지키며 폭넓게 분산하는 유형입니다. "
            "시장 지수와 비교해 성과를 점검하고 하락에도 계획을 유지합니다."
        ),
        "pattern": {
            "market_participation": -2,
            "loss_tolerance": 1,
            "holding_horizon": -2,
            "concentration": -2,
            "rule_adherence": -2,
            "information_reliance": -2,
            "urgency": -2,
            "drawdown_reaction": -2,
        },
    },
)

PERSONA_IDS: Final = tuple(persona["id"] for persona in PERSONAS)


def persona_answers(persona_id: str, mode: str) -> dict[str, int]:
    """프리셋을 해당 모드의 리커트 응답 dict로 조립한다.

    역채점 문항에는 반대 부호를 넣으므로, 조립된 응답을 스코어링하면
    패턴에 적힌 축 방향이 그대로 나온다.
    """
    persona = _persona(persona_id)
    pattern = persona["pattern"]
    answers: dict[str, int] = {}
    for question in questions_for_mode(mode):
        strength = int(pattern[question["axis"]])
        answers[str(question["id"])] = LIKERT_NEUTRAL + strength * int(
            question["direction"]
        )
    return answers


def _persona(persona_id: str) -> dict[str, Any]:
    for persona in PERSONAS:
        if persona["id"] == persona_id:
            return persona
    raise ValueError(f"persona_id must be one of {PERSONA_IDS}")


def _assert_patterns_cover_axes() -> None:
    """프리셋이 8축을 빠짐없이 덮는지 import 시점에 검사한다."""
    for persona in PERSONAS:
        missing = set(AXIS_IDS) - set(persona["pattern"])
        if missing:
            raise AssertionError(
                f"persona {persona['id']} is missing axes: {sorted(missing)}"
            )


_assert_patterns_cover_axes()
