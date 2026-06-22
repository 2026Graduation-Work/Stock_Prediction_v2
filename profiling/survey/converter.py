"""
설문 답변 → profiling_output.schema.json 형식 변환기

사용법:
    from converter import survey_to_schema

    result = survey_to_schema({
        "user_id": "u_001",
        "Q1": "Q1_B",
        "Q2": "Q2_B",
        "Q3": "Q3_A",
        "Q4": ["Q4_A", "Q4_C"],
        "Q5": "Q5_B",
        "Q6": "손실이 나면 어떡하지 걱정돼요.",
        "investment_amount_krw": 500000,
        "action_intent": "buy_consideration",
    })
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from questions import Q1_MAP, Q2_MAP, Q3_MAP, Q4_BASE, Q4_MAP, Q5_MAP

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
_SCHEMA_VERSION = "0.2.0-draft"
_KST = timezone(timedelta(hours=9))

# TODO: confidence_per_field — 현재는 고정값(0.85).
#       답변 일관성(Q1↔Q3 cross-check 등) 분석 후 동적 계산으로 교체 예정.
_FIXED_CONFIDENCE = 0.85

# MVP에서 고정하는 필드
_TARGET_RETURN_ANNUAL = 0.10
_TARGET_TICKER = "TBD"
_BENCHMARK_INDEX = "TBD"  # TODO: 설문 문항 추가 후 사용자 입력값으로 교체 예정


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def survey_to_schema(answers: dict) -> dict:
    """
    설문 답변 dict를 profiling_output.schema.json 형식 dict로 변환한다.

    Parameters
    ----------
    answers : dict
        필수 키: Q1, Q2, Q3, Q4 (list), Q5
        선택 키: Q6 (str), user_id (str), session_id (str),
                 investment_amount_krw (int), action_intent (str)

    Returns
    -------
    dict
        profiling_output.schema.json v0.2.0-draft 규격 JSON (dict)
    """
    # ------------------------------------------------------------------
    # 1. investor_profile 계산
    # ------------------------------------------------------------------
    q1 = Q1_MAP[answers["Q1"]]
    risk_tolerance: float = q1["risk_tolerance"]
    panic_sell_tendency: float = q1["panic_sell_tendency"]

    q2 = Q2_MAP[answers["Q2"]]
    time_horizon_months: int = q2["time_horizon_months"]
    liquidity_need_ratio: float = q2["liquidity_need_ratio"]

    q5 = Q5_MAP[answers["Q5"]]
    investment_experience_years: float = q5["investment_experience_years"]

    # ------------------------------------------------------------------
    # 2. psychological_state 계산
    # ------------------------------------------------------------------

    # Q3: fomo_index, herding_score 기저값
    q3 = Q3_MAP[answers["Q3"]]
    fomo_index: float = q3["fomo_index"]
    herding_base: float = q3["herding_score"]

    # Q4: herding_score 증분, self_confidence 증분 (중복선택 → 가중합)
    q4_choices: list[str] = answers.get("Q4", [])
    herding_delta = 0.0
    self_confidence_delta = 0.0
    for choice_id in q4_choices:
        delta = Q4_MAP[choice_id]
        herding_delta += delta.get("herding_score", 0.0)
        self_confidence_delta += delta.get("self_confidence", 0.0)

    herding_score: float = _clamp(herding_base + herding_delta)
    self_confidence: float = _clamp(Q4_BASE["self_confidence"] + self_confidence_delta)

    # TODO: overheating_caution — 공식 측정 방식 미정 (회의 ② 안건).
    #       현재는 fomo / herding / 정보의존도(1-self_confidence) 단순 평균.
    #       교수님 코멘트 반영 후 공식 교체 예정.
    info_dependency: float = 1.0 - self_confidence
    overheating_caution: float = _clamp(
        round((fomo_index + herding_score + info_dependency) / 3, 6)
    )

    # TODO: current_market_anxiety — 노란색 설문 vs 초록색 FinBERT 역할 분담 미정.
    #       현재는 중립값 0.5 고정. 초록색 블록 연동 후 교체 예정.
    current_market_anxiety: float = 0.5

    # ------------------------------------------------------------------
    # 3. free_text_signal
    # ------------------------------------------------------------------
    raw_text: str = answers.get("Q6", "")
    free_text_signal = {
        "raw_text": raw_text,
        # TODO: extracted_signals — LLM 연동 후 fomo_index / panic_sell_tendency 등
        #       보정값 추출 예정. (다음 스프린트)
        "extracted_signals": {},
        # TODO: conflict_with_survey — LLM 분석 결과와 객관식 응답 비교 후 계산.
        "conflict_with_survey": False,
    }

    # ------------------------------------------------------------------
    # 4. confidence_per_field
    # ------------------------------------------------------------------
    # TODO: 각 필드별 신뢰도를 답변 일관성·응답 시간·역문항 크로스체크로 계산.
    #       현재는 전 필드 0.85 고정.
    _fields = [
        "risk_tolerance",
        "time_horizon_months",
        "liquidity_need_ratio",
        "fomo_index",
        "panic_sell_tendency",
        "herding_score",
        "self_confidence",
        "overheating_caution",
        "current_market_anxiety",
        "investment_experience_years",
    ]
    confidence_per_field: dict[str, float] = {f: _FIXED_CONFIDENCE for f in _fields}

    # ------------------------------------------------------------------
    # 5. 메타 조립
    # ------------------------------------------------------------------
    user_id: str = answers.get("user_id") or f"u_{uuid.uuid4().hex[:8]}"
    session_id: str = answers.get("session_id") or f"s_{uuid.uuid4().hex[:8]}"
    timestamp: str = datetime.now(tz=_KST).isoformat()

    return {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": timestamp,
        "investor_profile": {
            "risk_tolerance": risk_tolerance,
            "time_horizon_months": time_horizon_months,
            "liquidity_need_ratio": liquidity_need_ratio,
            "target_return_annual": _TARGET_RETURN_ANNUAL,  # MVP 고정
            "investment_experience_years": investment_experience_years,
        },
        "psychological_state": {
            "fomo_index": fomo_index,
            "panic_sell_tendency": panic_sell_tendency,
            "herding_score": herding_score,
            "self_confidence": self_confidence,
            "current_market_anxiety": current_market_anxiety,
            "overheating_caution": overheating_caution,
        },
        "free_text_signal": free_text_signal,
        "confidence_per_field": confidence_per_field,
        "context": {
            "target_ticker": _TARGET_TICKER,
            "investment_amount_krw": answers.get("investment_amount_krw", 0),
            "action_intent": answers.get("action_intent", "buy_consideration"),
            "benchmark_index": _BENCHMARK_INDEX,  # TODO: 설문 문항 추가 후 사용자 입력값으로 교체
        },
        "meta": {
            "schema_version": _SCHEMA_VERSION,
            "source": "profiling_block",
            "confidence": _FIXED_CONFIDENCE,
        },
    }


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """값을 [lo, hi] 범위로 제한한다."""
    return max(lo, min(hi, v))
