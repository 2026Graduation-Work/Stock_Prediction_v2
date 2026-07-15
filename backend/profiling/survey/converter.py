"""Convert survey answers into the frozen profiling output v1.0 contract."""

from __future__ import annotations

from typing import Any, Final

from questions import (
    AVOIDED_ASSET_LABELS,
    EXPERIENCE_ANSWER_MAP,
    FOMO_ANSWER_MAP,
    HORIZON_ANSWER_MAP,
    HORIZON_MODEL_RULES,
    INFORMATION_SOURCE_BASE,
    INFORMATION_SOURCE_MAP,
    PROFILE_TYPE_THRESHOLD,
    RISK_ANSWER_MAP,
)

SCHEMA_VERSION: Final = "1.0.0"
TARGET_RETURN_ANNUAL: Final = 0.08
CURRENT_MARKET_ANXIETY_INITIAL: Final = 0.50
# Downstream text/chart blocks replace this initialization with market measurements.
OVERHEATING_CAUTION_INITIAL: Final = 0.61

CONFIDENCE_PER_FIELD: Final = {
    "risk_tolerance": 0.92,
    "time_horizon_months": 0.95,
    "liquidity_need_ratio": 0.88,
    "fomo_index": 0.78,
    "panic_sell_tendency": 0.70,
    "herding_score": 0.85,
    "self_confidence": 0.60,
    "overheating_caution": 0.55,
}
META_CONFIDENCE: Final = 0.81

FREE_TEXT_SIGNAL_RULES: Final = (
    {
        "field": "fomo_index",
        "keywords": ("남들 다 버는데", "뒤처지는", "놓칠까"),
        "value": 0.80,
    },
    {
        "field": "panic_sell_tendency",
        "keywords": ("마이너스", "손실", "잠을 못"),
        "value": 0.75,
    },
)


class SurveyValidationError(ValueError):
    """Raised when survey answers cannot satisfy the explicit scoring contract."""


def profile_type_for_risk_score(risk_score: int) -> str:
    """Map the 0-100 risk axis to the stable/aggressive model split.

    The 60-point threshold keeps neutral and cautious respondents on the stable
    model while reserving aggressive for clearly risk-tolerant answers.
    """
    if not 0 <= risk_score <= 100:
        raise SurveyValidationError("risk_score must be between 0 and 100")
    return "aggressive" if risk_score >= PROFILE_TYPE_THRESHOLD else "stable"


def horizon_code_for_score(horizon_score: int) -> str:
    """Map aggressive/neutral/conservative horizon scores to H5/H10/H20."""
    if not 0 <= horizon_score <= 100:
        raise SurveyValidationError("horizon_score must be between 0 and 100")
    for rule in HORIZON_MODEL_RULES:
        if horizon_score >= rule["minimum"]:
            return str(rule["model_horizon"])
    raise AssertionError("horizon rules must cover the full 0-100 range")


def axis_scores(answers: dict[str, Any]) -> dict[str, int]:
    """Return the three dashboard axes using only explicit question mappings."""
    risk = _single_choice(answers, "Q1", RISK_ANSWER_MAP)
    horizon = _single_choice(answers, "Q2", HORIZON_ANSWER_MAP)
    fomo = _single_choice(answers, "Q3", FOMO_ANSWER_MAP)
    return {
        "risk": int(risk["risk_score"]),
        "fomo": int(fomo["fomo_score"]),
        "horizon": int(horizon["horizon_score"]),
    }


def convert(survey_answers: dict[str, Any]) -> dict[str, Any]:
    """Purely convert one complete survey response into schema v1.0 JSON."""
    risk = _single_choice(survey_answers, "Q1", RISK_ANSWER_MAP)
    horizon = _single_choice(survey_answers, "Q2", HORIZON_ANSWER_MAP)
    fomo = _single_choice(survey_answers, "Q3", FOMO_ANSWER_MAP)
    experience = _single_choice(survey_answers, "Q5", EXPERIENCE_ANSWER_MAP)
    information_sources = _multi_choice(
        survey_answers, "Q4", INFORMATION_SOURCE_MAP, allow_empty=False
    )
    avoided_assets = _multi_choice(
        survey_answers, "Q6", AVOIDED_ASSET_LABELS, allow_empty=True
    )

    risk_score = int(risk["risk_score"])
    fomo_score = int(fomo["fomo_score"])
    horizon_score = int(horizon["horizon_score"])
    if horizon_code_for_score(horizon_score) != horizon["model_horizon"]:
        raise SurveyValidationError("Q2 horizon mapping is internally inconsistent")

    herding_score = float(fomo["herding_score"])
    self_confidence = float(INFORMATION_SOURCE_BASE["self_confidence"])
    for choice_id in information_sources:
        mapping = INFORMATION_SOURCE_MAP[choice_id]
        herding_score += float(mapping["herding_delta"])
        self_confidence += float(mapping["self_confidence_delta"])

    raw_text = str(survey_answers.get("Q7", "")).strip()
    extracted_signals = _extract_free_text_signals(raw_text)
    portfolio_input = survey_answers.get("portfolio") or {}

    result = {
        "user_id": _required_text(survey_answers, "user_id"),
        "session_id": _required_text(survey_answers, "session_id"),
        "timestamp": _required_text(survey_answers, "timestamp"),
        "investor_profile": {
            "risk_tolerance": risk_score / 100,
            "time_horizon_months": int(horizon["time_horizon_months"]),
            "liquidity_need_ratio": float(horizon["liquidity_need_ratio"]),
            "target_return_annual": TARGET_RETURN_ANNUAL,
            "investment_experience_years": float(
                experience["investment_experience_years"]
            ),
            "profile_type": profile_type_for_risk_score(risk_score),
        },
        "psychological_state": {
            "fomo_index": fomo_score / 100,
            "panic_sell_tendency": float(risk["panic_sell_tendency"]),
            "herding_score": _clamp(herding_score),
            "self_confidence": _clamp(self_confidence),
            "current_market_anxiety": CURRENT_MARKET_ANXIETY_INITIAL,
            "overheating_caution": OVERHEATING_CAUTION_INITIAL,
        },
        "constraints": {
            "avoided_assets": avoided_assets,
            "preferred_sectors": list(survey_answers.get("preferred_sectors", [])),
        },
        "portfolio": {
            "holdings": list(portfolio_input.get("holdings", [])),
            "watchlist": list(portfolio_input.get("watchlist", [])),
        },
        "free_text_signal": {
            "raw_text": raw_text,
            "extracted_signals": extracted_signals,
            "conflict_with_survey": False,
        },
        "confidence_per_field": dict(CONFIDENCE_PER_FIELD),
        "context": _build_context(survey_answers),
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "source": "profiling_block",
            "confidence": META_CONFIDENCE,
        },
    }
    return result


def survey_to_schema(answers: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible alias for callers of the previous converter API."""
    return convert(answers)


def _single_choice(
    answers: dict[str, Any], question_id: str, mapping: dict[str, Any]
) -> dict[str, Any]:
    choice = answers.get(question_id)
    if choice not in mapping:
        raise SurveyValidationError(f"{question_id} must be one of {tuple(mapping)}")
    return mapping[choice]


def _multi_choice(
    answers: dict[str, Any],
    question_id: str,
    mapping: dict[str, Any],
    *,
    allow_empty: bool,
) -> list[str]:
    choices = answers.get(question_id, [])
    if not isinstance(choices, list):
        raise SurveyValidationError(f"{question_id} must be a list")
    if not allow_empty and not choices:
        raise SurveyValidationError(f"{question_id} requires at least one choice")
    invalid = [choice for choice in choices if choice not in mapping]
    if invalid:
        raise SurveyValidationError(f"{question_id} has invalid choices: {invalid}")
    return list(dict.fromkeys(choices))


def _required_text(answers: dict[str, Any], field: str) -> str:
    value = str(answers.get(field, "")).strip()
    if not value:
        raise SurveyValidationError(f"{field} is required")
    return value


def _extract_free_text_signals(raw_text: str) -> dict[str, float]:
    signals: dict[str, float] = {}
    for rule in FREE_TEXT_SIGNAL_RULES:
        if any(keyword in raw_text for keyword in rule["keywords"]):
            signals[str(rule["field"])] = float(rule["value"])
    return signals


def _build_context(answers: dict[str, Any]) -> dict[str, Any]:
    context = {
        "investment_amount_krw": int(answers.get("investment_amount_krw", 0)),
        "action_intent": answers.get("action_intent", "buy_consideration"),
    }
    for optional_field in ("target_ticker", "market_regime_hint", "benchmark_index"):
        if optional_field in answers:
            context[optional_field] = answers[optional_field]
    return context


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)
