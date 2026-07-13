"""Run the four fixed psychology feature comparison experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from lightgbm import LGBMClassifier

from .metrics import evaluate_predictions, select_volatile_dates

PROFILE_ORDER = ("stable", "aggressive")
VARIANTS = (("A", "baseline"), ("B", "treatment"))
PROBABILITY_COLUMN = "probability"
METRIC_COLUMNS = (
    "auc",
    "hit_rate",
    "calibration_brier",
    "calibration_ece",
    "sharpe",
    "mdd",
    "cumulative_return",
    "trade_count",
)


class ComparisonConfigError(ValueError):
    """Raised when the experiment contract or invariant is violated."""


def _resolve_path(value: str | Path, base_dir: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base_dir / path).resolve()


def _features_from_model(model_path: Path) -> list[str]:
    if not model_path.exists():
        raise ComparisonConfigError(f"baseline feature model does not exist: {model_path}")
    with model_path.open(encoding="utf-8") as model_file:
        for line in model_file:
            if line.startswith("feature_names="):
                return line.removeprefix("feature_names=").strip().split()
    raise ComparisonConfigError(f"feature_names entry not found in model: {model_path}")


def resolve_feature_sets(config: dict[str, Any], config_dir: Path) -> tuple[list[str], list[str]]:
    feature_config = config.get("features", {})
    baseline = list(feature_config.get("baseline", []))
    model_file = feature_config.get("baseline_model_file")
    if bool(baseline) == bool(model_file):
        raise ComparisonConfigError(
            "configure exactly one of features.baseline or features.baseline_model_file"
        )
    if model_file:
        baseline = _features_from_model(_resolve_path(model_file, config_dir))

    treatment = list(feature_config.get("treatment", []))
    if len(treatment) != 2:
        raise ComparisonConfigError(
            "features.treatment must contain exactly two columns: synthetic psychology and news sentiment"
        )
    overlap = sorted(set(baseline) & set(treatment))
    if overlap:
        raise ComparisonConfigError(f"baseline and treatment features overlap: {overlap}")
    if len(baseline) != len(set(baseline)) or len(treatment) != len(set(treatment)):
        raise ComparisonConfigError("feature lists must not contain duplicates")
    return baseline, treatment


def _read_input(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"comparison input not found: {path}. Build the feature table before running results."
        )
    try:
        if path.is_dir() or path.suffix.lower() in {".parquet", ".pq"}:
            import pyarrow.dataset as pyarrow_dataset

            available = pyarrow_dataset.dataset(path, format="parquet").schema.names
            missing = [column for column in columns if column not in available]
            if missing:
                raise ComparisonConfigError(
                    f"comparison input missing columns: {missing}. Available: {available}"
                )
            return pd.read_parquet(path, columns=columns)
        if path.suffix.lower() == ".csv":
            available = pd.read_csv(path, nrows=0).columns.tolist()
            missing = [column for column in columns if column not in available]
            if missing:
                raise ComparisonConfigError(
                    f"comparison input missing columns: {missing}. Available: {available}"
                )
            return pd.read_csv(path, usecols=columns)
    except ComparisonConfigError:
        raise
    except Exception as exc:
        raise ComparisonConfigError(f"failed to read comparison input {path}: {exc}") from exc
    raise ComparisonConfigError("data.input_path must be a parquet file/directory or CSV")


def _profile_config(config: dict[str, Any], profile: str) -> dict[str, Any]:
    profiles = config.get("profiles", {})
    if profile not in profiles:
        raise ComparisonConfigError(f"profiles.{profile} is required")
    profile_config = profiles[profile]
    required = ("target_column", "probability_threshold", "top_n")
    missing = [key for key in required if key not in profile_config]
    if missing:
        raise ComparisonConfigError(f"profiles.{profile} missing keys: {missing}")
    threshold = float(profile_config["probability_threshold"])
    if not 0.0 <= threshold <= 1.0:
        raise ComparisonConfigError(f"profiles.{profile}.probability_threshold must be in [0, 1]")
    if int(profile_config["top_n"]) < 1:
        raise ComparisonConfigError(f"profiles.{profile}.top_n must be positive")
    return profile_config


def prepare_common_data(
    config: dict[str, Any],
    *,
    config_dir: Path,
    input_override: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str], dict[str, Any]]:
    """Load and validate one common row universe for all four runs."""
    data_config = config.get("data", {})
    required_data_keys = (
        "input_path",
        "date_column",
        "code_column",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "return_column",
        "volatility_column",
    )
    missing_keys = [key for key in required_data_keys if key not in data_config]
    if missing_keys:
        raise ComparisonConfigError(f"data config missing keys: {missing_keys}")

    baseline_features, treatment_features = resolve_feature_sets(config, config_dir)
    profile_configs = {profile: _profile_config(config, profile) for profile in PROFILE_ORDER}
    date_column = data_config["date_column"]
    code_column = data_config["code_column"]
    target_columns = [profile_configs[profile]["target_column"] for profile in PROFILE_ORDER]
    required_columns = list(
        dict.fromkeys(
            [
                date_column,
                code_column,
                data_config["return_column"],
                data_config["volatility_column"],
                *target_columns,
                *baseline_features,
                *treatment_features,
            ]
        )
    )
    input_path = input_override or _resolve_path(data_config["input_path"], config_dir)
    frame = _read_input(input_path, required_columns)

    absent = [column for column in required_columns if column not in frame.columns]
    if absent:
        raise ComparisonConfigError(f"comparison input missing columns: {absent}")
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
    if frame[date_column].isna().any():
        raise ComparisonConfigError("comparison input contains invalid dates")
    frame[code_column] = frame[code_column].astype("string")

    universe = [str(code) for code in data_config.get("universe", [])]
    if universe:
        frame = frame.loc[frame[code_column].isin(universe)]

    train_start = pd.Timestamp(data_config["train_start"])
    train_end = pd.Timestamp(data_config["train_end"])
    test_start = pd.Timestamp(data_config["test_start"])
    test_end = pd.Timestamp(data_config["test_end"])
    if not train_start <= train_end < test_start <= test_end:
        raise ComparisonConfigError(
            "date ranges must satisfy train_start <= train_end < test_start <= test_end"
        )

    frame = frame.loc[frame[date_column].between(train_start, test_end)].copy()
    frame = frame.sort_values([date_column, code_column], kind="stable", ignore_index=True)
    duplicate_keys = frame.duplicated([date_column, code_column])
    if duplicate_keys.any():
        sample = frame.loc[duplicate_keys, [date_column, code_column]].head(5).to_dict("records")
        raise ComparisonConfigError(f"duplicate date/code rows found: {sample}")
    if frame.empty:
        raise ComparisonConfigError("comparison input has no rows in the configured period")

    numeric_columns = [
        data_config["return_column"],
        data_config["volatility_column"],
        *target_columns,
        *baseline_features,
        *treatment_features,
    ]
    frame[numeric_columns] = frame[numeric_columns].apply(pd.to_numeric, errors="coerce")
    invalid_values = frame[required_columns].isna().any(axis=1)
    finite_values = np.isfinite(frame[numeric_columns].to_numpy(dtype=float)).all(axis=1)
    if invalid_values.any() or not finite_values.all():
        bad_count = int((invalid_values | ~finite_values).sum())
        raise ComparisonConfigError(
            f"{bad_count} rows have missing/non-finite values. Impute upstream so all four runs use identical rows."
        )

    for profile, profile_config in profile_configs.items():
        target = frame[profile_config["target_column"]]
        values = set(target.astype(int).unique())
        if values - {0, 1}:
            raise ComparisonConfigError(
                f"profiles.{profile}.target_column must be binary 0/1; found {sorted(values)}"
            )
        frame[profile_config["target_column"]] = target.astype(int)

    train = frame.loc[frame[date_column].between(train_start, train_end)].copy()
    test = frame.loc[frame[date_column].between(test_start, test_end)].copy()
    if train.empty or test.empty:
        raise ComparisonConfigError("configured train or test period has no rows")
    for profile, profile_config in profile_configs.items():
        target_column = profile_config["target_column"]
        if train[target_column].nunique() < 2:
            raise ComparisonConfigError(f"training target for {profile} contains only one class")

    metadata = {
        "input_path": str(input_path),
        "dataset_hash": _fingerprint(frame, required_columns),
        "input_rows": int(len(frame)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_dates": int(train[date_column].nunique()),
        "test_dates": int(test[date_column].nunique()),
        "universe_size": int(frame[code_column].nunique()),
    }
    return train, test, baseline_features, treatment_features, metadata


def _make_model(config: dict[str, Any], seed: int) -> LGBMClassifier:
    defaults: dict[str, Any] = {
        "objective": "binary",
        "n_estimators": 500,
        "learning_rate": 0.03,
        "max_depth": 5,
        "num_leaves": 20,
        "min_child_samples": 200,
        "class_weight": "balanced",
        "verbosity": -1,
    }
    defaults.update(config.get("model", {}).get("params", {}))
    defaults.update(
        {
            "objective": "binary",
            "random_state": seed,
            "bagging_seed": seed,
            "feature_fraction_seed": seed,
            "data_random_seed": seed,
            "deterministic": True,
            "force_col_wise": True,
            "n_jobs": 1,
        }
    )
    return LGBMClassifier(**defaults)


def _fingerprint(frame: pd.DataFrame, columns: list[str]) -> str:
    hashes = pd.util.hash_pandas_object(frame[columns], index=False).to_numpy()
    return hashlib.sha256(hashes.tobytes()).hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    return value


def _delta_table(metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for profile in PROFILE_ORDER:
        for sample in ("all", "volatile_top_20pct"):
            pair = metrics.loc[(metrics["profile"] == profile) & (metrics["sample"] == sample)]
            baseline = pair.loc[pair["variant"] == "A"].iloc[0]
            treatment = pair.loc[pair["variant"] == "B"].iloc[0]
            row: dict[str, Any] = {"profile": profile, "sample": sample}
            for metric in METRIC_COLUMNS:
                row[f"delta_B_minus_A_{metric}"] = treatment[metric] - baseline[metric]
            rows.append(row)
    return pd.DataFrame(rows)


def run_comparison(
    config: dict[str, Any],
    *,
    config_dir: Path,
    input_override: Path | None = None,
    output_override: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    seed = int(config.get("seed", 42))
    np.random.seed(seed)
    train, test, baseline_features, treatment_features, data_metadata = prepare_common_data(
        config, config_dir=config_dir, input_override=input_override
    )

    data_config = config["data"]
    evaluation_config = config.get("evaluation", {})
    date_column = data_config["date_column"]
    code_column = data_config["code_column"]
    return_column = data_config["return_column"]
    volatility_column = data_config["volatility_column"]
    volatile_fraction = float(evaluation_config.get("volatile_fraction", 0.2))
    if not np.isclose(volatile_fraction, 0.2):
        raise ComparisonConfigError("evaluation.volatile_fraction is fixed at 0.2")
    volatile_dates, volatility_threshold = select_volatile_dates(
        test,
        date_column=date_column,
        volatility_column=volatility_column,
        fraction=volatile_fraction,
    )

    output_path = output_override or _resolve_path(
        config.get("output_dir", "../results/psychology_ab"), config_dir
    )
    output_path.mkdir(parents=True, exist_ok=True)
    prediction_dir = output_path / "predictions"
    prediction_dir.mkdir(exist_ok=True)

    metric_rows: list[dict[str, Any]] = []
    run_manifest: list[dict[str, Any]] = []
    train_key_hash = _fingerprint(train, [date_column, code_column])
    test_key_hash = _fingerprint(test, [date_column, code_column])
    for profile in PROFILE_ORDER:
        profile_config = _profile_config(config, profile)
        target_column = profile_config["target_column"]
        for variant, feature_set in VARIANTS:
            features = (
                baseline_features if variant == "A" else baseline_features + treatment_features
            )
            model = _make_model(config, seed)
            model.fit(train[features], train[target_column])
            probabilities = model.predict_proba(test[features])[:, 1]
            predictions = test[
                [date_column, code_column, target_column, return_column, volatility_column]
            ].copy()
            predictions[PROBABILITY_COLUMN] = probabilities
            predictions.to_parquet(
                prediction_dir / f"{profile}_{variant.lower()}_predictions.parquet",
                index=False,
            )

            run_manifest.append(
                {
                    "profile": profile,
                    "variant": variant,
                    "feature_set": feature_set,
                    "feature_count": len(features),
                    "features": features,
                    "train_key_hash": train_key_hash,
                    "test_key_hash": test_key_hash,
                }
            )
            samples = {
                "all": predictions,
                "volatile_top_20pct": predictions.loc[
                    predictions[date_column].isin(volatile_dates)
                ],
            }
            for sample_name, sample in samples.items():
                metrics = evaluate_predictions(
                    sample,
                    date_column=date_column,
                    code_column=code_column,
                    target_column=target_column,
                    probability_column=PROBABILITY_COLUMN,
                    return_column=return_column,
                    classification_threshold=float(
                        evaluation_config.get("classification_threshold", 0.5)
                    ),
                    probability_threshold=float(profile_config["probability_threshold"]),
                    top_n=int(profile_config["top_n"]),
                    calibration_bins=int(evaluation_config.get("calibration_bins", 10)),
                    annualization=int(evaluation_config.get("annualization", 252)),
                )
                metric_rows.append(
                    {
                        "profile": profile,
                        "variant": variant,
                        "feature_set": feature_set,
                        "sample": sample_name,
                        "feature_count": len(features),
                        **metrics,
                    }
                )

    all_metrics = pd.DataFrame(metric_rows)
    four_run_metrics = all_metrics.loc[all_metrics["sample"] == "all"].reset_index(drop=True)
    volatile_metrics = all_metrics.loc[all_metrics["sample"] == "volatile_top_20pct"].reset_index(
        drop=True
    )
    deltas = _delta_table(all_metrics)

    four_run_metrics.to_csv(
        output_path / "four_run_metrics.csv", index=False, float_format="%.10g", lineterminator="\n"
    )
    volatile_metrics.to_csv(
        output_path / "volatile_subsample_metrics.csv",
        index=False,
        float_format="%.10g",
        lineterminator="\n",
    )
    deltas.to_csv(
        output_path / "comparison_deltas.csv",
        index=False,
        float_format="%.10g",
        lineterminator="\n",
    )

    manifest = {
        "seed": seed,
        "data": data_metadata,
        "date_ranges": {
            key: data_config[key] for key in ("train_start", "train_end", "test_start", "test_end")
        },
        "model_params": _make_model(config, seed).get_params(),
        "evaluation": {
            **evaluation_config,
            "volatile_fraction": volatile_fraction,
            "volatile_date_count": len(volatile_dates),
            "volatile_threshold": volatility_threshold,
            "volatile_dates": [date.strftime("%Y-%m-%d") for date in volatile_dates],
        },
        "invariants": {
            "common_train_rows": True,
            "common_test_rows": True,
            "test_key_hash": test_key_hash,
            "only_A_B_difference": "features.treatment",
            "baseline_features": baseline_features,
            "treatment_features": treatment_features,
        },
        "runs": run_manifest,
    }
    with (output_path / "experiment_manifest.json").open("w", encoding="utf-8") as output_file:
        json.dump(_json_value(manifest), output_file, ensure_ascii=False, indent=2, sort_keys=True)
        output_file.write("\n")
    with (output_path / "comparison_results.json").open("w", encoding="utf-8") as output_file:
        payload = {
            "four_run_metrics": four_run_metrics.to_dict("records"),
            "volatile_subsample_metrics": volatile_metrics.to_dict("records"),
            "comparison_deltas": deltas.to_dict("records"),
        }
        json.dump(_json_value(payload), output_file, ensure_ascii=False, indent=2, sort_keys=True)
        output_file.write("\n")

    return four_run_metrics, volatile_metrics, deltas, manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run fixed A/B psychology feature experiments")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--input", type=Path, help="override data.input_path")
    parser.add_argument("--out", type=Path, help="override output_dir")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config_path = args.config.resolve()
    try:
        with config_path.open(encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file)
        if not isinstance(config, dict):
            raise ComparisonConfigError("config root must be a mapping")
        four_runs, volatile, deltas, _ = run_comparison(
            config,
            config_dir=config_path.parent,
            input_override=args.input.resolve() if args.input else None,
            output_override=args.out.resolve() if args.out else None,
        )
    except (ComparisonConfigError, FileNotFoundError) as exc:
        parser.exit(2, f"comparison experiment error: {exc}\n")
    print(f"4런 지표 행 수: {len(four_runs)}")
    print(f"급변구간 지표 행 수: {len(volatile)}")
    print(f"A/B 비교 행 수: {len(deltas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
