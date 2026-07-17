# ruff: noqa: I001

import pandas as pd
import pytest

from experiments.train import _evaluate_validation


class _FixedProbModel:
    def predict(self, features: pd.DataFrame):
        # The halted row receives the highest score on every day.  If validation
        # substitutes Trading_Halt=0, it would incorrectly be selected instead.
        return [0.99 if code == "HALTED" else 0.80 for code in features.index]


def _validation_frame() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=5, freq="B")
    rows = []
    for date in dates:
        rows.extend(
            [
                {"Date": date, "Code": "HALTED", "Close": 100.0, "Trading_Halt": 1, "Y_Label": 2, "feature": 1.0},
                {"Date": date, "Code": "TRADEABLE", "Close": 100.0, "Trading_Halt": 0, "Y_Label": 1, "feature": 2.0},
            ]
        )
    return pd.DataFrame(rows).set_index("Code", drop=False)


def test_validation_excludes_halted_high_probability_signals() -> None:
    metrics = _evaluate_validation(
        {"strategy": {"prob_threshold": 0.65, "top_n": 1}},
        {"fold_id": 0, "name": "fold", "train_start": "2023-01-01", "train_end": "2023-12-31"},
        0,
        _FixedProbModel(),
        _validation_frame(),
        ["feature"],
    )

    assert metrics["selected_signal_count"] == 5
    assert metrics["selected_success_count"] == 0


def test_validation_rejects_missing_trade_metadata() -> None:
    frame = _validation_frame().drop(columns=["Trading_Halt"])
    with pytest.raises(ValueError, match="메타데이터"):
        _evaluate_validation(
            {"strategy": {}},
            {"fold_id": 0, "name": "fold", "train_start": "2023-01-01", "train_end": "2023-12-31"},
            0,
            _FixedProbModel(),
            frame,
            ["feature"],
        )
