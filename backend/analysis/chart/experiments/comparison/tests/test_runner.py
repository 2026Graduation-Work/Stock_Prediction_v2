import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from experiments.comparison.runner import (
    ComparisonConfigError,
    resolve_feature_sets,
    run_comparison,
)

CHART_DIR = Path(__file__).resolve().parents[3]


def _fixture(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=90, freq="B")
    codes = ["000001", "000002", "000003", "000004", "000005", "000006"]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    frame = index.to_frame(index=False)
    size = len(frame)
    frame["technical_momentum"] = rng.normal(size=size)
    frame["technical_volume"] = rng.normal(size=size)
    frame["synthetic_psychology_index"] = rng.normal(size=size)
    frame["news_sentiment"] = rng.normal(size=size)
    stable_score = (
        frame["technical_momentum"]
        + 0.8 * frame["synthetic_psychology_index"]
        + 0.4 * frame["news_sentiment"]
    )
    aggressive_score = (
        frame["technical_volume"]
        + 0.6 * frame["synthetic_psychology_index"]
        + 0.7 * frame["news_sentiment"]
    )
    frame["Target_Stable"] = (stable_score > stable_score.median()).astype(int)
    frame["Target_Aggressive"] = (aggressive_score > aggressive_score.median()).astype(int)
    frame["Next_Day_Return"] = (frame["Target_Aggressive"] * 2 - 1) * 0.004 + rng.normal(
        0, 0.01, size
    )
    daily_volatility = pd.Series(np.linspace(0.01, 0.05, len(dates)), index=dates)
    frame["Market_Volatility"] = frame["Date"].map(daily_volatility)
    return frame


def _config(input_path: Path, output_path: Path) -> dict:
    return {
        "seed": 42,
        "data": {
            "input_path": str(input_path),
            "date_column": "Date",
            "code_column": "Code",
            "train_start": "2024-01-01",
            "train_end": "2024-03-15",
            "test_start": "2024-03-18",
            "test_end": "2024-05-03",
            "return_column": "Next_Day_Return",
            "volatility_column": "Market_Volatility",
            "universe": [],
        },
        "features": {
            "baseline": ["technical_momentum", "technical_volume"],
            "treatment": ["synthetic_psychology_index", "news_sentiment"],
        },
        "profiles": {
            "stable": {
                "target_column": "Target_Stable",
                "probability_threshold": 0.5,
                "top_n": 2,
            },
            "aggressive": {
                "target_column": "Target_Aggressive",
                "probability_threshold": 0.5,
                "top_n": 3,
            },
        },
        "model": {
            "params": {
                "n_estimators": 30,
                "learning_rate": 0.1,
                "num_leaves": 7,
                "min_child_samples": 10,
            }
        },
        "evaluation": {
            "classification_threshold": 0.5,
            "calibration_bins": 5,
            "volatile_fraction": 0.2,
            "annualization": 252,
        },
        "output_dir": str(output_path),
    }


def test_example_config_resolves_tracked_baseline_model() -> None:
    config_path = CHART_DIR / "experiments" / "comparison" / "config.example.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    baseline, treatment = resolve_feature_sets(config, config_path.parent)

    assert baseline
    assert treatment == ["synthetic_psychology_index", "news_sentiment"]


def test_runs_four_models_and_writes_both_required_tables(tmp_path: Path) -> None:
    input_path = tmp_path / "comparison.parquet"
    output_path = tmp_path / "results"
    _fixture().to_parquet(input_path, index=False)

    four_runs, volatile, deltas, manifest = run_comparison(
        _config(input_path, output_path), config_dir=tmp_path
    )

    assert list(zip(four_runs["profile"], four_runs["variant"], strict=True)) == [
        ("stable", "A"),
        ("stable", "B"),
        ("aggressive", "A"),
        ("aggressive", "B"),
    ]
    assert len(volatile) == 4
    assert len(deltas) == 4
    assert set(volatile["sample_dates"]) == {7}
    assert set(four_runs.loc[four_runs["variant"] == "B", "feature_count"]) == {4}
    assert set(four_runs.loc[four_runs["variant"] == "A", "feature_count"]) == {2}
    assert manifest["invariants"]["only_A_B_difference"] == "features.treatment"
    assert len(manifest["data"]["dataset_hash"]) == 64
    assert len({run["test_key_hash"] for run in manifest["runs"]}) == 1

    expected_files = {
        "four_run_metrics.csv",
        "volatile_subsample_metrics.csv",
        "comparison_deltas.csv",
        "comparison_results.json",
        "experiment_manifest.json",
    }
    assert expected_files <= {path.name for path in output_path.iterdir()}
    payload = json.loads((output_path / "comparison_results.json").read_text(encoding="utf-8"))
    assert len(payload["four_run_metrics"]) == 4


def test_repeated_runs_are_deterministic(tmp_path: Path) -> None:
    input_path = tmp_path / "comparison.parquet"
    _fixture().to_parquet(input_path, index=False)

    first = run_comparison(_config(input_path, tmp_path / "first"), config_dir=tmp_path)[:3]
    second = run_comparison(_config(input_path, tmp_path / "second"), config_dir=tmp_path)[:3]

    for first_table, second_table in zip(first, second, strict=True):
        pd.testing.assert_frame_equal(first_table, second_table)


def test_rejects_missing_treatment_values_instead_of_changing_sample(tmp_path: Path) -> None:
    frame = _fixture()
    frame.loc[0, "news_sentiment"] = np.nan
    input_path = tmp_path / "incomplete.parquet"
    frame.to_parquet(input_path, index=False)

    with pytest.raises(ComparisonConfigError, match="identical rows"):
        run_comparison(_config(input_path, tmp_path / "results"), config_dir=tmp_path)


def test_reports_missing_input_columns_before_training(tmp_path: Path) -> None:
    frame = _fixture().drop(columns="news_sentiment")
    input_path = tmp_path / "missing_column.parquet"
    frame.to_parquet(input_path, index=False)

    with pytest.raises(ComparisonConfigError, match="missing columns.*news_sentiment"):
        run_comparison(_config(input_path, tmp_path / "results"), config_dir=tmp_path)
