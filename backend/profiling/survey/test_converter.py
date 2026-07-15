"""Contract tests for the deterministic survey converter."""

from __future__ import annotations

import json
from pathlib import Path

from converter import (
    convert,
    horizon_code_for_score,
    profile_type_for_risk_score,
    survey_to_schema,
)
from jsonschema import Draft202012Validator, FormatChecker
from questions import PROFILE_TYPE_THRESHOLD

REPO_ROOT = Path(__file__).parents[3]
SCHEMA_PATH = REPO_ROOT / "schema" / "profiling_output.schema.json"
EXAMPLE_PATH = REPO_ROOT / "schema" / "profiling_output.example.json"

MINJI_ANSWERS = {
    "user_id": "u_minji_001",
    "session_id": "s_20260707_001",
    "timestamp": "2026-07-07T14:32:00+09:00",
    "Q1": "Q1_B",
    "Q2": "Q2_B",
    "Q3": "Q3_A",
    "Q4": ["Q4_A"],
    "Q5": "Q5_B",
    "Q6": ["spac", "managed_stock"],
    "Q7": "남들 다 버는데 나만 뒤처지는 것 같아서 조급해요. 그래도 마이너스 나면 잠을 못 자요.",
    "preferred_sectors": ["semiconductor", "healthcare"],
    "portfolio": {
        "holdings": [
            {
                "ticker": "005930",
                "name": "삼성전자",
                "quantity": 15,
                "avg_buy_price": 71200,
            },
            {
                "ticker": "035720",
                "name": "카카오",
                "quantity": 8,
                "avg_buy_price": 48500,
            },
            {
                "ticker": "068270",
                "name": "셀트리온",
                "quantity": 3,
                "avg_buy_price": 182000,
            },
            {
                "ticker": "005380",
                "name": "현대차",
                "quantity": 5,
                "avg_buy_price": 235000,
            },
        ],
        "watchlist": ["000660", "035420", "051910"],
    },
    "investment_amount_krw": 500000,
    "action_intent": "buy_consideration",
    "market_regime_hint": "high_volatility",
    "benchmark_index": "KOSPI",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_minji_answers_match_frozen_example() -> None:
    assert convert(MINJI_ANSWERS) == _load_json(EXAMPLE_PATH)


def test_output_validates_against_schema_v1() -> None:
    validator = Draft202012Validator(
        _load_json(SCHEMA_PATH), format_checker=FormatChecker()
    )
    validator.validate(convert(MINJI_ANSWERS))


def test_profile_type_switches_at_threshold_plus_or_minus_one() -> None:
    assert profile_type_for_risk_score(PROFILE_TYPE_THRESHOLD - 1) == "stable"
    assert profile_type_for_risk_score(PROFILE_TYPE_THRESHOLD) == "aggressive"
    assert profile_type_for_risk_score(PROFILE_TYPE_THRESHOLD + 1) == "aggressive"


def test_horizon_axis_maps_to_fixed_model_windows() -> None:
    assert horizon_code_for_score(80) == "H5"
    assert horizon_code_for_score(50) == "H10"
    assert horizon_code_for_score(20) == "H20"


def test_legacy_converter_name_delegates_to_convert() -> None:
    assert survey_to_schema(MINJI_ANSWERS) == convert(MINJI_ANSWERS)
