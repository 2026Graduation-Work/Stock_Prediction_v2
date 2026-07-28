"""8축 스코어링·신뢰도·모순 검출 계약 테스트."""

from __future__ import annotations

import pytest
from style_personas import PERSONA_IDS, persona_answers
from style_questions import (
    AXES,
    AXIS_IDS,
    LIKERT_NEUTRAL,
    STYLE_QUESTIONS,
    questions_for_mode,
)
from style_scoring import (
    CONTRADICTION_RULES,
    MIN_CONFIDENCE_FOR_CONTRADICTION,
    StyleAnswerError,
    confidence_per_axis,
    detect_contradictions,
    months_for_holding_horizon,
    reduce_to_legacy_fields,
    score_style_axes,
)


def _ratios(style_axes):
    return {axis["axis_id"]: axis["ratio"] for axis in style_axes["axes"]}


def _answers_for_ratios(mode: str, targets: dict[str, float]) -> dict[str, int]:
    """축별 목표 ratio를 만드는 응답을 조립한다.

    ratio는 (응답-3)*direction 의 평균을 2로 나눈 값이므로, 축의 모든 문항에
    같은 강도를 주면 ratio = 강도/2 가 된다.
    """
    answers: dict[str, int] = {}
    for question in questions_for_mode(mode):
        target = targets.get(str(question["axis"]), 0.0)
        strength = round(target * 2)
        answers[str(question["id"])] = LIKERT_NEUTRAL + strength * int(
            question["direction"]
        )
    return answers


# ── 문항 은행 자체의 계약 ────────────────────────────────────────────────────


def test_every_axis_has_a_reverse_keyed_question():
    """역채점 문항이 없으면 묵종 경향을 못 잡아 신뢰도가 무의미해진다."""
    for axis_id in AXIS_IDS:
        directions = {
            int(q["direction"]) for q in STYLE_QUESTIONS if q["axis"] == axis_id
        }
        assert directions == {1, -1}, f"{axis_id}에 정·역채점 문항이 모두 있어야 한다"


def test_question_ids_are_unique():
    ids = [question["id"] for question in STYLE_QUESTIONS]
    assert len(ids) == len(set(ids))


def test_quick_mode_is_a_strict_subset_of_detailed():
    quick = {q["id"] for q in questions_for_mode("quick")}
    detailed = {q["id"] for q in questions_for_mode("detailed")}
    assert quick < detailed


def test_quick_mode_still_covers_all_axes_in_both_directions():
    for axis_id in AXIS_IDS:
        directions = {
            int(q["direction"]) for q in questions_for_mode("quick") if q["axis"] == axis_id
        }
        assert directions == {1, -1}, f"빠른 진단에서도 {axis_id}는 양방향 문항이 필요하다"


def test_axis_metadata_matches_axis_ids():
    assert tuple(axis["id"] for axis in AXES) == AXIS_IDS


# ── 스코어링 ────────────────────────────────────────────────────────────────


def test_all_neutral_answers_give_zero_ratio_and_full_confidence():
    answers = {q["id"]: LIKERT_NEUTRAL for q in questions_for_mode("detailed")}
    result = score_style_axes(answers, "detailed")
    for axis in result["axes"]:
        assert axis["ratio"] == 0.0
        assert axis["confidence"] == 1.0


def test_reverse_keyed_questions_are_oriented_before_scoring():
    """정·역채점 문항에 반대로 답하면 같은 방향으로 합쳐져야 한다."""
    answers = {}
    for question in questions_for_mode("detailed"):
        answers[question["id"]] = 5 if question["direction"] == 1 else 1
    result = score_style_axes(answers, "detailed")
    for axis in result["axes"]:
        assert axis["ratio"] == 1.0, axis["axis_id"]
        assert axis["confidence"] == 1.0


def test_scoring_is_deterministic():
    answers = persona_answers("anxious_chaser", "detailed")
    assert score_style_axes(answers, "detailed") == score_style_axes(answers, "detailed")


def _split_axis_answers(mode: str, axis_id: str, base: dict[str, int]) -> dict[str, int]:
    """한 축 안에서 응답을 정반대로 갈라 신뢰도를 떨어뜨린다.

    문항 방향이 교대로 배치돼 있으므로 원시 응답값을 교대로 주면 오히려
    방향 정렬 후 완전히 일관된 응답이 된다. 정렬 후 기준으로 갈라야 한다.
    """
    answers = dict(base)
    axis_questions = [q for q in questions_for_mode(mode) if q["axis"] == axis_id]
    for index, question in enumerate(axis_questions):
        strength = 2 if index % 2 == 0 else -2
        answers[str(question["id"])] = LIKERT_NEUTRAL + strength * int(
            question["direction"]
        )
    return answers


def test_split_answers_within_an_axis_drop_confidence():
    """같은 축에서 절반씩 정반대로 답하면 방향을 믿을 수 없다."""
    base = {q["id"]: LIKERT_NEUTRAL for q in questions_for_mode("detailed")}
    answers = _split_axis_answers("detailed", "urgency", base)
    result = score_style_axes(answers, "detailed")
    urgency = next(a for a in result["axes"] if a["axis_id"] == "urgency")
    assert urgency["confidence"] < 0.5


def test_unanswered_questions_lower_confidence_through_coverage():
    """방향이 일관된 응답에서 일부를 빼면 응답률만큼 신뢰도가 내려간다."""
    full = _answers_for_ratios("detailed", {"urgency": 1.0})
    partial = dict(full)
    dropped = [
        q["id"] for q in questions_for_mode("detailed") if q["axis"] == "urgency"
    ][:2]
    for question_id in dropped:
        del partial[question_id]

    full_axis = next(
        a for a in score_style_axes(full, "detailed")["axes"] if a["axis_id"] == "urgency"
    )
    partial_axis = next(
        a
        for a in score_style_axes(partial, "detailed")["axes"]
        if a["axis_id"] == "urgency"
    )
    assert full_axis["confidence"] == 1.0
    assert partial_axis["answered_count"] == full_axis["answered_count"] - 2
    assert partial_axis["confidence"] < full_axis["confidence"]
    # 방향은 그대로 유지된다 — 응답률만 떨어졌을 뿐이다.
    assert partial_axis["ratio"] == full_axis["ratio"]


def test_axis_with_no_answers_is_neutral_and_zero_confidence():
    result = score_style_axes({}, "quick")
    for axis in result["axes"]:
        assert axis["ratio"] == 0.0
        assert axis["confidence"] == 0.0
        assert axis["answered_count"] == 0


def test_invalid_likert_value_is_rejected():
    answers = {q["id"]: LIKERT_NEUTRAL for q in questions_for_mode("quick")}
    answers[questions_for_mode("quick")[0]["id"]] = 9
    with pytest.raises(StyleAnswerError):
        score_style_axes(answers, "quick")


def test_detailed_only_answers_are_rejected_in_quick_mode():
    detailed_only = next(
        q for q in questions_for_mode("detailed") if not q["quick"]
    )
    answers = {q["id"]: LIKERT_NEUTRAL for q in questions_for_mode("quick")}
    answers[detailed_only["id"]] = 5
    with pytest.raises(StyleAnswerError):
        score_style_axes(answers, "quick")


def test_unrelated_keys_are_ignored():
    answers = {q["id"]: LIKERT_NEUTRAL for q in questions_for_mode("quick")}
    answers["user_id"] = "u_demo"
    score_style_axes(answers, "quick")


def test_both_modes_produce_all_eight_axes():
    for mode in ("quick", "detailed"):
        result = score_style_axes({}, mode)
        assert [axis["axis_id"] for axis in result["axes"]] == list(AXIS_IDS)
        assert result["assessment_mode"] == mode


# ── 모순 검출 (규칙별 1개 이상) ──────────────────────────────────────────────


def _detect_for(targets: dict[str, float]) -> set[str]:
    answers = _answers_for_ratios("detailed", targets)
    axes = score_style_axes(answers, "detailed")
    return {item["id"] for item in detect_contradictions(axes)}


def test_rule_loss_averse_but_concentrated():
    assert "loss_averse_but_concentrated" in _detect_for(
        {"loss_tolerance": -0.5, "concentration": 0.5}
    )


def test_rule_long_horizon_but_reactive():
    assert "long_horizon_but_reactive" in _detect_for(
        {"holding_horizon": -0.5, "urgency": 0.5, "drawdown_reaction": 0.5}
    )


def test_rule_discretionary_but_loss_averse():
    assert "discretionary_but_loss_averse" in _detect_for(
        {"rule_adherence": 0.5, "loss_tolerance": -0.5}
    )


def test_rule_herding_but_concentrated():
    assert "herding_but_concentrated" in _detect_for(
        {"information_reliance": 0.5, "concentration": 0.5}
    )


def test_rule_benchmark_focused_but_short_horizon():
    assert "benchmark_focused_but_short_horizon" in _detect_for(
        {"market_participation": -0.5, "holding_horizon": 0.5}
    )


def test_every_rule_has_a_dedicated_test():
    """규칙을 추가하면 테스트도 추가하도록 강제한다."""
    tested = {
        name.removeprefix("test_rule_")
        for name in globals()
        if name.startswith("test_rule_")
    }
    assert {rule["id"] for rule in CONTRADICTION_RULES} == tested


def test_neutral_answers_produce_no_contradictions():
    answers = {q["id"]: LIKERT_NEUTRAL for q in questions_for_mode("detailed")}
    assert detect_contradictions(score_style_axes(answers, "detailed")) == []


def test_low_confidence_axes_do_not_raise_contradictions():
    """답이 갈려 방향을 믿기 어려운 축으로는 모순을 주장하지 않는다."""
    base = _answers_for_ratios(
        "detailed", {"loss_tolerance": -0.5, "concentration": 0.5}
    )
    answers = _split_axis_answers("detailed", "concentration", base)

    axes = score_style_axes(answers, "detailed")
    concentration = next(a for a in axes["axes"] if a["axis_id"] == "concentration")
    assert concentration["confidence"] < MIN_CONFIDENCE_FOR_CONTRADICTION
    assert "loss_averse_but_concentrated" not in {
        item["id"] for item in detect_contradictions(axes)
    }


def test_contradiction_observations_carry_no_action_advice():
    """AGENTS.md 사용자 노출 표현 규칙 — 관측 서술만 담는다."""
    banned = ("권장", "하세요", "매수", "매도", "손절", "익절", "추천")
    for rule in CONTRADICTION_RULES:
        for field in ("observation", "follow_up_question"):
            text = str(rule[field])
            assert not any(word in text for word in banned), (rule["id"], field, text)


# ── v1.0 필드 축약 ──────────────────────────────────────────────────────────


def test_reduction_matches_the_documented_formula():
    answers = _answers_for_ratios(
        "detailed",
        {
            "loss_tolerance": -0.3,
            "urgency": 0.44,
            "drawdown_reaction": 0.3,
            "information_reliance": 0.16,
        },
    )
    axes = score_style_axes(answers, "detailed")
    ratios = _ratios(axes)
    reduced = reduce_to_legacy_fields(axes)

    assert reduced["risk_tolerance"] == pytest.approx((ratios["loss_tolerance"] + 1) / 2)
    assert reduced["fomo_index"] == pytest.approx((ratios["urgency"] + 1) / 2)
    assert reduced["panic_sell_tendency"] == pytest.approx(
        (ratios["drawdown_reaction"] + 1) / 2
    )
    assert reduced["herding_score"] == pytest.approx(
        (ratios["information_reliance"] + 1) / 2
    )


def test_reduced_values_stay_inside_the_v1_0_range():
    for extreme in (1, 5):
        answers = {q["id"]: extreme for q in questions_for_mode("detailed")}
        reduced = reduce_to_legacy_fields(score_style_axes(answers, "detailed"))
        for field, value in reduced.items():
            if field == "time_horizon_months":
                assert value >= 0
            else:
                assert 0.0 <= value <= 1.0


def test_longer_holding_horizon_means_more_months():
    months = [months_for_holding_horizon(r) for r in (-1.0, -0.5, 0.0, 0.5, 1.0)]
    assert months == sorted(months, reverse=True)


def test_holding_horizon_rules_cover_the_whole_range():
    for ratio in (-1.0, -0.6, -0.2, 0.0, 0.2, 0.6, 1.0):
        assert months_for_holding_horizon(ratio) > 0


def test_out_of_range_horizon_ratio_is_rejected():
    with pytest.raises(StyleAnswerError):
        months_for_holding_horizon(1.5)


def test_confidence_per_axis_maps_to_legacy_field_names():
    answers = {q["id"]: 5 for q in questions_for_mode("detailed")}
    axes = score_style_axes(answers, "detailed")
    mapped = confidence_per_axis(axes)
    assert set(mapped) == {
        "risk_tolerance",
        "fomo_index",
        "panic_sell_tendency",
        "herding_score",
    }
    assert all(0.0 <= value <= 1.0 for value in mapped.values())


# ── 페르소나 프리셋 ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
@pytest.mark.parametrize("mode", ("quick", "detailed"))
def test_persona_answers_score_without_error(persona_id, mode):
    axes = score_style_axes(persona_answers(persona_id, mode), mode)
    assert len(axes["axes"]) == len(AXIS_IDS)


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_persona_patterns_are_internally_consistent(persona_id):
    """프리셋은 축마다 한 방향으로만 답하므로 신뢰도가 최대여야 한다."""
    axes = score_style_axes(persona_answers(persona_id, "detailed"), "detailed")
    for axis in axes["axes"]:
        assert axis["confidence"] == 1.0, axis["axis_id"]


def test_anxious_chaser_surfaces_the_intended_contradictions():
    """발표에서 보여줄 유형이므로 모순이 실제로 잡혀야 한다."""
    axes = score_style_axes(persona_answers("anxious_chaser", "detailed"), "detailed")
    found = {item["id"] for item in detect_contradictions(axes)}
    assert "herding_but_concentrated" in found
    assert "loss_averse_but_concentrated" in found


def test_systematic_investor_has_no_contradictions():
    axes = score_style_axes(
        persona_answers("systematic_investor", "detailed"), "detailed"
    )
    assert detect_contradictions(axes) == []


def test_persona_quick_and_detailed_agree_on_direction():
    """빠른 진단이 정밀 진단과 반대 방향을 내놓으면 안 된다."""
    for persona_id in PERSONA_IDS:
        quick = _ratios(score_style_axes(persona_answers(persona_id, "quick"), "quick"))
        detailed = _ratios(
            score_style_axes(persona_answers(persona_id, "detailed"), "detailed")
        )
        for axis_id in AXIS_IDS:
            assert quick[axis_id] == pytest.approx(detailed[axis_id]), (
                persona_id,
                axis_id,
            )
