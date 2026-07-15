"""Shared evaluation functions for every comparison run."""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score


def expected_calibration_error(
    y_true: Iterable[int], probabilities: Iterable[float], bins: int = 10
) -> float:
    """Return equal-width expected calibration error (lower is better)."""
    if bins < 2:
        raise ValueError("calibration bins must be at least 2")

    actual = np.asarray(list(y_true), dtype=float)
    predicted = np.asarray(list(probabilities), dtype=float)
    if len(actual) == 0 or len(actual) != len(predicted):
        raise ValueError("calibration inputs must be non-empty and have equal length")

    boundaries = np.linspace(0.0, 1.0, bins + 1)
    bucket_ids = np.minimum(np.digitize(predicted, boundaries[1:-1], right=False), bins - 1)
    error = 0.0
    for bucket in range(bins):
        mask = bucket_ids == bucket
        if not mask.any():
            continue
        weight = mask.mean()
        error += weight * abs(predicted[mask].mean() - actual[mask].mean())
    return float(error)


def select_volatile_dates(
    frame: pd.DataFrame,
    *,
    date_column: str,
    volatility_column: str,
    fraction: float = 0.2,
) -> tuple[pd.DatetimeIndex, float]:
    """Select exactly the highest-volatility fraction of dates deterministically."""
    if not 0.0 < fraction <= 1.0:
        raise ValueError("volatile fraction must be in (0, 1]")

    daily_volatility = frame.groupby(date_column, sort=True)[volatility_column].mean()
    if daily_volatility.empty:
        raise ValueError("cannot select volatile dates from an empty test set")

    count = max(1, math.ceil(len(daily_volatility) * fraction))
    ranked = (
        daily_volatility.rename("volatility")
        .reset_index()
        .sort_values(
            ["volatility", date_column],
            ascending=[False, True],
            kind="stable",
        )
        .head(count)
    )
    dates = pd.DatetimeIndex(ranked[date_column].sort_values())
    return dates, float(ranked["volatility"].min())


def _trading_metrics(
    frame: pd.DataFrame,
    *,
    date_column: str,
    code_column: str,
    probability_column: str,
    return_column: str,
    probability_threshold: float,
    top_n: int,
    annualization: int,
) -> dict[str, float | int]:
    eligible = frame.loc[frame[probability_column] >= probability_threshold].copy()
    eligible = eligible.sort_values(
        [date_column, probability_column, code_column],
        ascending=[True, False, True],
        kind="stable",
    )
    selected = eligible.groupby(date_column, sort=True, group_keys=False).head(top_n)

    all_dates = pd.DatetimeIndex(frame[date_column].drop_duplicates().sort_values())
    daily_returns = (
        selected.groupby(date_column)[return_column]
        .mean()
        .reindex(all_dates, fill_value=0.0)
        .astype(float)
    )
    if (daily_returns <= -1.0).any():
        raise ValueError("next-day returns must be greater than -1.0")

    daily_std = daily_returns.std(ddof=1)
    if len(daily_returns) < 2 or daily_std == 0.0 or np.isnan(daily_std):
        sharpe = 0.0
    else:
        sharpe = float(daily_returns.mean() / daily_std * math.sqrt(annualization))

    equity = (1.0 + daily_returns).cumprod()
    running_peak = equity.cummax().clip(lower=1.0)
    drawdown = equity / running_peak - 1.0
    return {
        "sharpe": sharpe,
        "mdd": float(drawdown.min()),
        "cumulative_return": float(equity.iloc[-1] - 1.0),
        "trade_count": int(len(selected)),
    }


def evaluate_predictions(
    frame: pd.DataFrame,
    *,
    date_column: str,
    code_column: str,
    target_column: str,
    probability_column: str,
    return_column: str,
    classification_threshold: float,
    probability_threshold: float,
    top_n: int,
    calibration_bins: int = 10,
    annualization: int = 252,
) -> dict[str, float | int]:
    """Calculate the common ML and trading metrics for one run and sample."""
    if frame.empty:
        raise ValueError("cannot evaluate an empty prediction frame")
    if top_n < 1:
        raise ValueError("top_n must be positive")

    actual = frame[target_column].astype(int)
    probability = frame[probability_column].astype(float).clip(0.0, 1.0)
    auc = float("nan") if actual.nunique() < 2 else float(roc_auc_score(actual, probability))
    predicted = (probability >= classification_threshold).astype(int)

    result: dict[str, float | int] = {
        "sample_rows": int(len(frame)),
        "sample_dates": int(frame[date_column].nunique()),
        "positive_rate": float(actual.mean()),
        "auc": auc,
        "hit_rate": float((predicted == actual).mean()),
        "calibration_brier": float(brier_score_loss(actual, probability)),
        "calibration_ece": expected_calibration_error(actual, probability, bins=calibration_bins),
    }
    result.update(
        _trading_metrics(
            frame.assign(**{probability_column: probability}),
            date_column=date_column,
            code_column=code_column,
            probability_column=probability_column,
            return_column=return_column,
            probability_threshold=probability_threshold,
            top_n=top_n,
            annualization=annualization,
        )
    )
    return result
