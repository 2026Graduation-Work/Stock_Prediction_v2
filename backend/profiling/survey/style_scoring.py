"""8축 스코어링·신뢰도·모순 검출 — profiling 블록.

전부 결정론이다. 같은 응답이면 항상 같은 값이 나오고 LLM을 쓰지 않는다
(AGENTS.md 정량/정성 분리). 산출물은 소프트 틸트이며 종목 제거에 쓰지 않는다.

축 점수
    응답값 1~5를 -2~+2로 중심화하고 문항 방향(`direction`)을 곱해 축 방향으로
    정렬한다. 가중평균을 극단값 2로 나눠 ratio(-1~+1)를 얻는다.

신뢰도
    `일관성 × 응답률`. 같은 축 문항끼리 답이 갈릴수록, 미응답이 많을수록 낮아진다.
    일관성은 축 안 응답들의 가중 평균절대편차(MAD)를 최대값 2로 정규화해 뒤집는다.
    한쪽 극단으로 모두 답하면 1, 절반씩 정반대로 답하면 0이다.

모순 검출
    축 간 상충을 규칙 테이블로만 잡는다. 점수를 보정하지 않고 관측 사실만 남긴다.
    해석과 후속 확인은 화면·상담이 맡는다(HITL).
"""

from __future__ import annotations

from typing import Any, Final

from style_questions import (
    AXIS_IDS,
    LIKERT_EXTREME,
    LIKERT_NEUTRAL,
    LIKERT_OPTIONS,
    TURNOVER_MONTH_RULES,
    questions_for_mode,
)

VALID_LIKERT_VALUES: Final = frozenset(option["value"] for option in LIKERT_OPTIONS)
ALL_STYLE_QUESTION_IDS: Final = frozenset(
    question["id"] for question in questions_for_mode("detailed")
)

# 모순 판정에 쓸 축의 최소 신뢰도. 답이 갈려 방향을 믿기 어려운 축으로는
# 모순을 주장하지 않는다.
MIN_CONFIDENCE_FOR_CONTRADICTION: Final = 0.30


class StyleAnswerError(ValueError):
    """리커트 응답이 스코어링 계약을 만족하지 못할 때."""


def score_style_axes(answers: dict[str, Any], mode: str) -> dict[str, Any]:
    """리커트 응답을 schema style_axes 블록 형태로 환산한다.

    미응답 문항은 허용한다. 대신 응답률이 신뢰도를 끌어내린다.
    """
    questions = questions_for_mode(mode)
    _reject_unknown_answers(answers, questions)

    per_axis: dict[str, list[dict[str, float]]] = {axis_id: [] for axis_id in AXIS_IDS}
    totals: dict[str, float] = dict.fromkeys(AXIS_IDS, 0.0)

    for question in questions:
        axis_id = str(question["axis"])
        weight = float(question["weight"])
        totals[axis_id] += weight

        raw = answers.get(question["id"])
        if raw is None:
            continue
        if raw not in VALID_LIKERT_VALUES:
            raise StyleAnswerError(
                f"{question['id']} must be one of {sorted(VALID_LIKERT_VALUES)}"
            )
        oriented = (int(raw) - LIKERT_NEUTRAL) * int(question["direction"])
        per_axis[axis_id].append({"oriented": float(oriented), "weight": weight})

    axes = [
        _axis_result(axis_id, per_axis[axis_id], totals[axis_id], questions)
        for axis_id in AXIS_IDS
    ]
    return {"assessment_mode": mode, "axes": axes}


def _axis_result(
    axis_id: str,
    entries: list[dict[str, float]],
    total_weight: float,
    questions: tuple[dict, ...],
) -> dict[str, Any]:
    question_count = sum(1 for q in questions if q["axis"] == axis_id)
    answered_count = len(entries)

    if not entries or total_weight <= 0:
        return {
            "axis_id": axis_id,
            "ratio": 0.0,
            "confidence": 0.0,
            "answered_count": answered_count,
            "question_count": question_count,
        }

    answered_weight = sum(entry["weight"] for entry in entries)
    mean = sum(entry["oriented"] * entry["weight"] for entry in entries) / answered_weight
    deviation = (
        sum(abs(entry["oriented"] - mean) * entry["weight"] for entry in entries)
        / answered_weight
    )

    ratio = mean / LIKERT_EXTREME
    consistency = 1.0 - deviation / LIKERT_EXTREME
    coverage = answered_weight / total_weight

    return {
        "axis_id": axis_id,
        "ratio": round(_clamp(ratio, -1.0, 1.0), 6),
        "confidence": round(_clamp(consistency * coverage, 0.0, 1.0), 6),
        "answered_count": answered_count,
        "question_count": question_count,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 모순 검출
# ─────────────────────────────────────────────────────────────────────────────
# `observation`은 관측 서술만 담는다. 행동 제안·권유 문구를 넣지 않는다
# (AGENTS.md 사용자 노출 표현 규칙).
CONTRADICTION_RULES: Final = (
    {
        "id": "loss_averse_but_concentrated",
        "axes": ("loss_tolerance", "concentration"),
        "conditions": {"loss_tolerance": ("<=", -0.20), "concentration": (">=", 0.30)},
        "severity": "high",
        "observation": "원금 보전을 우선한다고 답했으나 소수 종목 집중을 선호한다고도 답했습니다.",
        "follow_up_question": "한 종목이 전체의 몇 %를 넘으면 부담스럽게 느끼시나요?",
    },
    {
        "id": "long_horizon_but_reactive",
        "axes": ("turnover", "urgency", "drawdown_reaction"),
        "conditions": {
            "turnover": ("<=", -0.20),
            "urgency": (">=", 0.30),
            "drawdown_reaction": (">=", 0.20),
        },
        "severity": "caution",
        "observation": "투자 기간은 길게 잡았지만 조급함과 하락 시 이탈 경향이 함께 높게 나왔습니다.",
        "follow_up_question": "하락 폭이 어느 정도일 때 계획을 다시 보고 싶으신가요?",
    },
    {
        "id": "discretionary_but_loss_averse",
        "axes": ("rule_adherence", "loss_tolerance"),
        "conditions": {"rule_adherence": (">=", 0.30), "loss_tolerance": ("<=", -0.30)},
        "severity": "caution",
        "observation": "손실을 크게 부담스러워하면서도 미리 정한 기준보다 그때의 판단을 선호한다고 답했습니다.",
        "follow_up_question": "다시 점검할 기준을 미리 정해두는 것과 그때 판단하는 것 중 어느 쪽이 편하신가요?",
    },
    {
        "id": "herding_but_concentrated",
        "axes": ("information_reliance", "concentration"),
        "conditions": {
            "information_reliance": (">=", 0.40),
            "concentration": (">=", 0.40),
        },
        "severity": "high",
        "observation": "주변과 시장 분위기를 판단 근거로 삼는 편이면서 소수 종목 집중도 함께 선호합니다.",
        "follow_up_question": "그 종목을 담은 이유를 직접 확인한 자료로 설명할 수 있으신가요?",
    },
    {
        "id": "benchmark_focused_but_short_horizon",
        "axes": ("market_participation", "turnover"),
        "conditions": {
            "market_participation": ("<=", -0.30),
            "turnover": (">=", 0.30),
        },
        "severity": "caution",
        "observation": "시장 지수를 따라가는 성과를 중시하면서 보유 기간은 짧게 가져가려 합니다.",
        "follow_up_question": "성과를 어느 기간 단위로 지수와 비교해 보고 싶으신가요?",
    },
)

_COMPARATORS: Final = {
    "<=": lambda value, bound: value <= bound,
    ">=": lambda value, bound: value >= bound,
}


def detect_contradictions(style_axes: dict[str, Any]) -> list[dict[str, Any]]:
    """축 간 상충을 규칙 테이블로 검출한다. 점수를 바꾸지 않는다."""
    by_id = {axis["axis_id"]: axis for axis in style_axes["axes"]}
    found: list[dict[str, Any]] = []

    for rule in CONTRADICTION_RULES:
        axis_ids = rule["axes"]
        if any(
            by_id[axis_id]["confidence"] < MIN_CONFIDENCE_FOR_CONTRADICTION
            for axis_id in axis_ids
        ):
            continue
        conditions = rule["conditions"]
        if not all(
            _COMPARATORS[operator](by_id[axis_id]["ratio"], bound)
            for axis_id, (operator, bound) in conditions.items()
        ):
            continue
        found.append(
            {
                "id": rule["id"],
                "axes": list(axis_ids),
                "severity": rule["severity"],
                "observation": rule["observation"],
                "follow_up_question": rule["follow_up_question"],
            }
        )
    return found


# ─────────────────────────────────────────────────────────────────────────────
# v1.0 필드 축약
# ─────────────────────────────────────────────────────────────────────────────
# schema/profiling_output.schema.json의 style_axes 설명과 같은 규칙이어야 한다.
LEGACY_RATIO_FIELDS: Final = (
    ("risk_tolerance", "loss_tolerance"),
    ("fomo_index", "urgency"),
    ("panic_sell_tendency", "drawdown_reaction"),
    ("herding_score", "information_reliance"),
)


def reduce_to_legacy_fields(style_axes: dict[str, Any]) -> dict[str, float | int]:
    """8축에서 기존 v1.0 필드를 결정론적으로 되돌린다.

    v1.0 소비자(chart·text·platform)가 변경 없이 동작하게 하는 다리다.
    """
    by_id = {axis["axis_id"]: axis for axis in style_axes["axes"]}
    reduced: dict[str, float | int] = {
        field: round((by_id[axis_id]["ratio"] + 1) / 2, 6)
        for field, axis_id in LEGACY_RATIO_FIELDS
    }
    reduced["time_horizon_months"] = months_for_turnover(
        by_id["turnover"]["ratio"]
    )
    return reduced


def months_for_turnover(ratio: float) -> int:
    """turnover ratio를 투자 기간(개월)으로 옮긴다."""
    if not -1.0 <= ratio <= 1.0:
        raise StyleAnswerError("turnover ratio must be between -1 and 1")
    for rule in TURNOVER_MONTH_RULES:
        if ratio < rule["max_ratio"]:
            return int(rule["months"])
    raise AssertionError("horizon rules must cover the full -1..1 range")


def confidence_per_axis(style_axes: dict[str, Any]) -> dict[str, float]:
    """축 신뢰도를 v1.0 confidence_per_field 키로 옮긴다."""
    by_id = {axis["axis_id"]: axis for axis in style_axes["axes"]}
    return {
        field: by_id[axis_id]["confidence"] for field, axis_id in LEGACY_RATIO_FIELDS
    }


def _reject_unknown_answers(
    answers: dict[str, Any], questions: tuple[dict, ...]
) -> None:
    """빠른 진단에 정밀 진단 문항 응답이 섞여 들어오는 것을 막는다.

    설문과 무관한 키(user_id 등)는 그대로 통과시킨다. 이 함수가 보는 것은
    '문항 id인데 지금 모드에는 없는' 응답뿐이다.
    """
    allowed = {question["id"] for question in questions}
    out_of_mode = sorted(ALL_STYLE_QUESTION_IDS.intersection(answers) - allowed)
    if out_of_mode:
        raise StyleAnswerError(
            f"이 모드에 없는 문항 응답이 있습니다: {out_of_mode}. 모드를 확인하세요."
        )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
