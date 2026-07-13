import numpy as np
import pandas as pd
import pytest
from experiments.comparison.metrics import (
    evaluate_predictions,
    expected_calibration_error,
    select_volatile_dates,
)


def test_selects_exact_top_twenty_percent_dates_with_deterministic_ties() -> None:
    dates = pd.date_range("2025-01-01", periods=10, freq="D")
    frame = pd.DataFrame(
        {
            "Date": np.repeat(dates, 2),
            "Market_Volatility": np.repeat([1, 2, 3, 4, 5, 6, 7, 8, 9, 9], 2),
        }
    )

    selected, threshold = select_volatile_dates(
        frame,
        date_column="Date",
        volatility_column="Market_Volatility",
        fraction=0.2,
    )

    assert selected.tolist() == [dates[8], dates[9]]
    assert threshold == 9.0


def test_shared_evaluator_returns_ml_and_trading_metrics() -> None:
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-02"]),
            "Code": ["A", "B", "A", "B"],
            "Target": [1, 0, 1, 0],
            "Prob": [0.9, 0.1, 0.8, 0.2],
            "Next_Return": [0.02, -0.01, 0.01, -0.02],
        }
    )

    metrics = evaluate_predictions(
        frame,
        date_column="Date",
        code_column="Code",
        target_column="Target",
        probability_column="Prob",
        return_column="Next_Return",
        classification_threshold=0.5,
        probability_threshold=0.5,
        top_n=1,
    )

    assert metrics["auc"] == 1.0
    assert metrics["hit_rate"] == 1.0
    assert metrics["trade_count"] == 2
    assert metrics["cumulative_return"] == pytest.approx(1.02 * 1.01 - 1.0)
    assert metrics["mdd"] == 0.0
    assert expected_calibration_error([0, 1], [0.1, 0.9], bins=10) == pytest.approx(0.1)


def test_mdd_includes_initial_capital_peak() -> None:
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2025-01-01", "2025-01-02"]),
            "Code": ["A", "A"],
            "Target": [0, 1],
            "Prob": [0.9, 0.9],
            "Next_Return": [-0.1, 0.05],
        }
    )

    metrics = evaluate_predictions(
        frame,
        date_column="Date",
        code_column="Code",
        target_column="Target",
        probability_column="Prob",
        return_column="Next_Return",
        classification_threshold=0.5,
        probability_threshold=0.5,
        top_n=1,
    )

    assert metrics["mdd"] == pytest.approx(-0.1)
