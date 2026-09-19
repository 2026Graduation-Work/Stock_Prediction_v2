import numpy as np
import pandas as pd
import pytest
from experiments.comparison.metrics import expected_calibration_error, select_volatile_dates


def test_selects_exact_top_twenty_percent_dates_with_deterministic_ties() -> None:
    dates = pd.date_range("2025-01-01", periods=10, freq="D")
    frame = pd.DataFrame(
        {"Date": np.repeat(dates, 2), "Sigma": np.repeat([1, 2, 3, 4, 5, 6, 7, 8, 9, 9], 2)}
    )
    selected, threshold = select_volatile_dates(
        frame, date_column="Date", volatility_column="Sigma", fraction=0.2
    )
    assert selected.tolist() == [dates[8], dates[9]]
    assert threshold == 9.0


def test_expected_calibration_error() -> None:
    assert expected_calibration_error([0, 1], [0.1, 0.9], bins=10) == pytest.approx(0.1)
