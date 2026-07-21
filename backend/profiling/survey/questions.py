"""Survey questions and deterministic question-to-score mappings.

This module is the profiling scoring SSOT. Frontend constants must be kept in
sync with these tables.
"""

from __future__ import annotations

from typing import Final

PROFILE_TYPE_THRESHOLD: Final = 60
"""Risk score 60+ selects the aggressive chart model; below 60 selects stable."""

RISK_ANSWER_MAP: Final = {
    "Q1_A": {"risk_score": 15, "panic_sell_tendency": 0.85},
    "Q1_B": {"risk_score": 35, "panic_sell_tendency": 0.65},
    "Q1_C": {"risk_score": 75, "panic_sell_tendency": 0.20},
}

HORIZON_ANSWER_MAP: Final = {
    "Q2_A": {
        "horizon_score": 80,
        "time_horizon_months": 12,
        "liquidity_need_ratio": 0.70,
        "model_horizon": "H5",
    },
    "Q2_B": {
        "horizon_score": 50,
        "time_horizon_months": 48,
        "liquidity_need_ratio": 0.25,
        "model_horizon": "H10",
    },
    "Q2_C": {
        "horizon_score": 20,
        "time_horizon_months": 120,
        "liquidity_need_ratio": 0.10,
        "model_horizon": "H20",
    },
}

FOMO_ANSWER_MAP: Final = {
    "Q3_A": {"fomo_score": 72, "herding_score": 0.38},
    "Q3_B": {"fomo_score": 40, "herding_score": 0.30},
    "Q3_C": {"fomo_score": 15, "herding_score": 0.20},
}

INFORMATION_SOURCE_BASE: Final = {"self_confidence": 0.30}
INFORMATION_SOURCE_MAP: Final = {
    "Q4_A": {"herding_delta": 0.20, "self_confidence_delta": 0.00},
    "Q4_B": {"herding_delta": 0.15, "self_confidence_delta": 0.00},
    "Q4_C": {"herding_delta": 0.00, "self_confidence_delta": 0.20},
    "Q4_D": {"herding_delta": 0.00, "self_confidence_delta": 0.40},
}

EXPERIENCE_ANSWER_MAP: Final = {
    "Q5_A": {"investment_experience_years": 0.3},
    "Q5_B": {"investment_experience_years": 1.0},
    "Q5_C": {"investment_experience_years": 3.5},
    "Q5_D": {"investment_experience_years": 7.0},
}

AVOIDED_ASSET_LABELS: Final = {
    "spac": "SPAC",
    "managed_stock": "관리종목",
    "low_liquidity": "저유동성 종목",
    "penny_stock": "동전주",
    "high_volatility": "고변동성 종목",
    "preferred_stock": "우선주",
}

HORIZON_MODEL_RULES: Final = (
    {"minimum": 67, "model_horizon": "H5", "style": "aggressive"},
    {"minimum": 34, "model_horizon": "H10", "style": "neutral"},
    {"minimum": 0, "model_horizon": "H20", "style": "conservative"},
)

Q1 = {
    "id": "Q1",
    "text": "투자한 종목이 15% 하락했다면 어떻게 하시겠어요?",
    "type": "single",
    "choices": [
        {"id": "Q1_A", "text": "더 떨어지기 전에 바로 정리해요."},
        {"id": "Q1_B", "text": "며칠 지켜보고 원인을 확인한 뒤 결정해요."},
        {"id": "Q1_C", "text": "판단이 그대로라면 추가 매수를 검토해요."},
    ],
}

Q2 = {
    "id": "Q2",
    "text": "이 투자금은 언제 다시 사용할 가능성이 큰가요?",
    "type": "single",
    "choices": [
        {"id": "Q2_A", "text": "1년 안에 사용할 수 있어요."},
        {"id": "Q2_B", "text": "3~5년 뒤 사용할 계획이에요."},
        {"id": "Q2_C", "text": "10년 이상 투자해도 괜찮아요."},
    ],
}

Q3 = {
    "id": "Q3",
    "text": "주변 종목이 단기간에 크게 올랐다는 소식을 들으면 어떤가요?",
    "type": "single",
    "choices": [
        {"id": "Q3_A", "text": "나만 놓칠까 봐 빨리 따라 사고 싶어져요."},
        {"id": "Q3_B", "text": "부럽지만 내 기준에 맞는지 먼저 확인해요."},
        {"id": "Q3_C", "text": "이미 오른 종목보다 다른 기회를 찾아봐요."},
    ],
}

Q4 = {
    "id": "Q4",
    "text": "투자 아이디어를 주로 어디에서 얻나요?",
    "type": "multi",
    "choices": [
        {"id": "Q4_A", "text": "유튜브·온라인 커뮤니티"},
        {"id": "Q4_B", "text": "친구·지인"},
        {"id": "Q4_C", "text": "뉴스·공시"},
        {"id": "Q4_D", "text": "재무제표·기업 분석"},
    ],
}

Q5 = {
    "id": "Q5",
    "text": "직접 투자한 경험은 얼마나 되나요?",
    "type": "single",
    "choices": [
        {"id": "Q5_A", "text": "6개월 미만"},
        {"id": "Q5_B", "text": "6개월~2년"},
        {"id": "Q5_C", "text": "2~5년"},
        {"id": "Q5_D", "text": "5년 이상"},
    ],
}

Q6 = {
    "id": "Q6",
    "text": "추천에서 반드시 제외할 종목 유형을 선택해 주세요.",
    "type": "multi",
    "choices": [
        {"id": value, "text": label} for value, label in AVOIDED_ASSET_LABELS.items()
    ],
}

Q7 = {
    "id": "Q7",
    "text": "투자하면서 요즘 가장 걱정되는 점을 적어주세요.",
    "type": "text",
}

QUESTIONS = [Q1, Q2, Q3, Q4, Q5, Q6, Q7]
