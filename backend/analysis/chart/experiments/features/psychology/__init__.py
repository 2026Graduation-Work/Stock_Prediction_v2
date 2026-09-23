"""가격·거래량만으로 계산하는 시장 심리 피처(Treatment 후보).

이 패키지는 A/B 비교실험의 Treatment 조건에 넣을 시장 심리 피처를 만든다.
개인 설문 기반 IPS는 여기에 들어오지 않는다. 정의와 한계는
``experiments/features/PSYCHOLOGY_FEATURES.md``를 따른다.
"""

from .market_psychology import (
    FEATURE_COLUMNS,
    FEATURE_PROFILE,
    GENERATOR_VERSION,
    OUTPUT_COLUMNS,
    RAW_FEATURES,
    SUMMARY_AXES,
    TREATMENT_FEATURES,
    PsychologyFeatureConfig,
    PsychologyInputError,
    build_psychology_features,
)

__all__ = [
    "FEATURE_COLUMNS",
    "FEATURE_PROFILE",
    "GENERATOR_VERSION",
    "OUTPUT_COLUMNS",
    "RAW_FEATURES",
    "SUMMARY_AXES",
    "TREATMENT_FEATURES",
    "PsychologyFeatureConfig",
    "PsychologyInputError",
    "build_psychology_features",
]
