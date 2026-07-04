"""
pytest 테스트 — survey_to_schema() 검증

테스트 항목:
  1. 김민지 페르소나 → 스키마 구조 일치 (example.json 키셋 비교)
  2. 모든 0~1 제약 필드가 [0, 1] 범위 안에 있는지
  3. jsonschema 라이브러리로 profiling_output.schema.json 검증
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from converter import survey_to_schema

# ---------------------------------------------------------------------------
# 경로
# ---------------------------------------------------------------------------
# backend/profiling/survey/ → 레포 루트는 3단계 위
_REPO_ROOT = Path(__file__).parents[3]
_SCHEMA_PATH = _REPO_ROOT / "schema" / "profiling_output.schema.json"
_EXAMPLE_PATH = _REPO_ROOT / "schema" / "profiling_output.example.json"


# ---------------------------------------------------------------------------
# 김민지 페르소나 — 사회초년생, FOMO 중간, 정보 커뮤니티 의존
# Q1: 며칠 지켜봄  → risk=0.5,  panic=0.5
# Q2: 3~5년 후     → horizon=48, liquidity=0.25
# Q3: 부럽지만 내 기준 → fomo=0.4,  herd=0.3
# Q4: [유튜브, 뉴스·공시] → herd+0.3, self_conf+0.1 → herd=0.6, conf=0.4
# Q5: 6개월~2년    → experience=1.0
# Q6: 자유 텍스트
# ---------------------------------------------------------------------------
MINJI_ANSWERS = {
    "user_id": "u_minji_test",
    "session_id": "s_test_001",
    "Q1": "Q1_B",
    "Q2": "Q2_B",
    "Q3": "Q3_B",
    "Q4": ["Q4_A", "Q4_C"],
    "Q5": "Q5_B",
    "Q6": "손실이 날까봐 너무 걱정돼요. 남들 다 버는데 나만 뒤처지는 것 같아요.",
    "investment_amount_krw": 500_000,
    "action_intent": "buy_consideration",
}


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def example() -> dict:
    return json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def minji_output() -> dict:
    return survey_to_schema(MINJI_ANSWERS)


# ---------------------------------------------------------------------------
# 테스트 1: 최상위 키 구조가 example.json 과 일치하는지
# ---------------------------------------------------------------------------
class TestStructure:
    def test_top_level_keys_match_example(self, minji_output: dict, example: dict):
        """최상위 키셋이 example.json 과 동일해야 한다."""
        assert set(minji_output.keys()) == set(example.keys()), (
            f"키 불일치:\n"
            f"  변환 결과: {sorted(minji_output.keys())}\n"
            f"  example:  {sorted(example.keys())}"
        )

    def test_investor_profile_keys(self, minji_output: dict, example: dict):
        assert set(minji_output["investor_profile"].keys()) == set(
            example["investor_profile"].keys()
        )

    def test_psychological_state_keys(self, minji_output: dict, example: dict):
        assert set(minji_output["psychological_state"].keys()) == set(
            example["psychological_state"].keys()
        )

    def test_free_text_signal_keys(self, minji_output: dict, example: dict):
        assert set(minji_output["free_text_signal"].keys()) == set(
            example["free_text_signal"].keys()
        )

    def test_context_keys(self, minji_output: dict):
        # market_regime_hint 는 스키마에서 선택(optional) 필드 — required 키만 검증한다.
        required = {"target_ticker", "investment_amount_krw", "action_intent"}
        assert required.issubset(minji_output["context"].keys())

    def test_meta_keys(self, minji_output: dict, example: dict):
        assert set(minji_output["meta"].keys()) == set(example["meta"].keys())


# ---------------------------------------------------------------------------
# 테스트 2: 0~1 범위 필드 검증
# ---------------------------------------------------------------------------
class TestValueRanges:
    """schema 에서 minimum:0 / maximum:1 이 명시된 필드들을 검증한다."""

    _INVESTOR_01 = ["risk_tolerance", "liquidity_need_ratio"]
    _PSYCH_01 = [
        "fomo_index",
        "panic_sell_tendency",
        "herding_score",
        "self_confidence",
        "current_market_anxiety",
        "overheating_caution",
    ]

    @pytest.mark.parametrize("field", _INVESTOR_01)
    def test_investor_profile_range(self, minji_output: dict, field: str):
        val = minji_output["investor_profile"][field]
        assert 0.0 <= val <= 1.0, f"investor_profile.{field} = {val} out of [0, 1]"

    @pytest.mark.parametrize("field", _PSYCH_01)
    def test_psychological_state_range(self, minji_output: dict, field: str):
        val = minji_output["psychological_state"][field]
        assert 0.0 <= val <= 1.0, f"psychological_state.{field} = {val} out of [0, 1]"

    def test_confidence_per_field_all_in_range(self, minji_output: dict):
        cpf = minji_output["confidence_per_field"]
        for field, val in cpf.items():
            assert 0.0 <= val <= 1.0, f"confidence_per_field.{field} = {val} out of [0, 1]"

    def test_meta_confidence_in_range(self, minji_output: dict):
        val = minji_output["meta"]["confidence"]
        assert 0.0 <= val <= 1.0, f"meta.confidence = {val} out of [0, 1]"

    def test_time_horizon_positive(self, minji_output: dict):
        val = minji_output["investor_profile"]["time_horizon_months"]
        assert val > 0

    def test_investment_experience_nonneg(self, minji_output: dict):
        val = minji_output["investor_profile"]["investment_experience_years"]
        assert val >= 0


# ---------------------------------------------------------------------------
# 테스트 3: jsonschema 공식 검증
# ---------------------------------------------------------------------------
class TestJsonSchema:
    def test_minji_validates_against_schema(self, minji_output: dict, schema: dict):
        """jsonschema 로 스키마 검증이 통과해야 한다."""
        jsonschema.validate(instance=minji_output, schema=schema)

    def test_action_intent_enum(self, minji_output: dict):
        allowed = {"buy_consideration", "sell_consideration", "hold_consideration"}
        assert minji_output["context"]["action_intent"] in allowed

    def test_source_const(self, minji_output: dict):
        assert minji_output["meta"]["source"] == "profiling_block"

    def test_target_ticker_is_tbd(self, minji_output: dict):
        assert minji_output["context"]["target_ticker"] == "TBD"

    def test_target_return_annual_fixed(self, minji_output: dict):
        assert minji_output["investor_profile"]["target_return_annual"] == pytest.approx(0.10)

    def test_free_text_raw_preserved(self, minji_output: dict):
        """Q6 자유 텍스트가 raw_text 에 그대로 들어가야 한다."""
        assert minji_output["free_text_signal"]["raw_text"] == MINJI_ANSWERS["Q6"]

    def test_extracted_signals_empty_dict(self, minji_output: dict):
        """LLM 연동 전: extracted_signals 는 빈 dict 여야 한다."""
        assert minji_output["free_text_signal"]["extracted_signals"] == {}

    def test_q4_multi_select_herding_clamped(self):
        """Q4 에서 모든 항목을 선택해도 herding_score 가 1.0 을 넘지 않아야 한다."""
        answers = {**MINJI_ANSWERS, "Q4": ["Q4_A", "Q4_B", "Q4_C", "Q4_D"]}
        out = survey_to_schema(answers)
        assert out["psychological_state"]["herding_score"] <= 1.0

    def test_q4_empty_self_confidence_base(self):
        """Q4 를 하나도 선택하지 않으면 self_confidence = 0.3 (base) 이어야 한다."""
        answers = {**MINJI_ANSWERS, "Q4": []}
        out = survey_to_schema(answers)
        assert out["psychological_state"]["self_confidence"] == pytest.approx(0.3)

    def test_benchmark_index_key_exists(self, minji_output: dict):
        """context 에 benchmark_index 키가 존재해야 한다 (schema 필드 추가 확인)."""
        assert "benchmark_index" in minji_output["context"]
