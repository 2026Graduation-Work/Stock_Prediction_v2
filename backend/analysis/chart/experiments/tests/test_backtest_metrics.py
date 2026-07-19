import pandas as pd
import pytest
from experiments.evaluation.backtest_metrics import calculate_trading_metrics


def test_max_drawdown_includes_loss_from_initial_equity() -> None:
    metrics = calculate_trading_metrics(pd.Series([-0.10, 0.05]))

    assert metrics["max_drawdown"] == pytest.approx(-0.10)
