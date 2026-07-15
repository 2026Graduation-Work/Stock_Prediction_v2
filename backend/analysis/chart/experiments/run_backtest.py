import argparse
import json
import os

import numpy as np
import pandas as pd
import yaml
from backtest.engine import VectorBTEngine, compute_custom_krx_composite
from evaluation.backtest_metrics import calculate_trading_metrics
from evaluation.baselines import (
    generate_ma_breakout_signals,
    generate_momentum_signals,
    generate_random_top_k_signals,
)
from experiment_utils import (
    build_fold_alignment,
    find_processed_dir,
    generate_predictions_hash,
    label_params_from_config,
    load_predictions,
    resolve_splits,
    result_dir,
    test_date_bounds,
    validate_embargo,
)
from train_src.loaders import load_parquet_data
from train_src.swing_strategy import SwingStrategy


def _json_safe(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if pd.isna(value):
        return None
    return value


def _slice_trades(trades_df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if trades_df is None or trades_df.empty:
        return pd.DataFrame()

    entry_time_col = "Entry Timestamp" if "Entry Timestamp" in trades_df.columns else "entry_time"
    if entry_time_col not in trades_df.columns:
        return trades_df.iloc[0:0].copy()

    sliced = trades_df.copy()
    sliced[entry_time_col] = pd.to_datetime(sliced[entry_time_col]).dt.tz_localize(None)
    return sliced[(sliced[entry_time_col] >= start) & (sliced[entry_time_col] <= end)]


def _format_pct(value: float) -> str:
    return "N/A" if pd.isna(value) else f"{value * 100:.2f}%"


def _format_float(value: float) -> str:
    return "N/A" if pd.isna(value) else f"{value:.4f}"


def main(config_path, predictions_path=None):
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"[ERROR] 설정을 불러올 수 없습니다. 경로를 확인해주세요: {config_path}"
        )

    print(f"[*] Loading config from {config_path}...")
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    exp_name = config.get("experiment_name", "default_exp")
    print(f"\n📈 [*] Starting Trading Backtest: {exp_name}")

    splits = resolve_splits(config)
    if not splits:
        raise ValueError("분할 폴드(Splits) 목록이 비어 있습니다. 설정을 확인하세요.")

    embargo_days = config.get("data", {}).get("embargo_days", 7)
    if not validate_embargo(splits, embargo_days):
        raise ValueError("Embargo 검증 실패: train/test 기간 간격을 확인하세요.")

    predictions_hash = generate_predictions_hash(config, splits)
    print(f"[*] Target Predictions Cache Hash: {predictions_hash}")

    final_predictions = load_predictions(config, splits, __file__, predictions_path)

    processed_dir = find_processed_dir(config, __file__)
    print(f"[*] 데이터 소스 디렉토리: {processed_dir}")

    full_test_start, full_test_end = test_date_bounds(splits)
    tickers_cfg = config.get("data", {}).get("tickers", None)

    price_cols = ["Date", "Code", "Open", "High", "Low", "Close", "Sigma", "Trading_Halt"]
    market_df = load_parquet_data(
        processed_dir,
        full_test_start,
        full_test_end,
        columns_only=price_cols,
        tickers=tickers_cfg,
        label_params=label_params_from_config(config),
    )
    market_df["Date"] = pd.to_datetime(market_df["Date"]).dt.tz_localize(None)

    alignment_df, alignment_status = build_fold_alignment(final_predictions, splits)
    if not alignment_status["is_exact_fold_match"]:
        raise ValueError(
            "예측 캐시가 config의 test fold들과 정확히 매칭되지 않습니다. "
            f"alignment={alignment_status}"
        )

    print("\n[1] 트레이딩 전략 매트릭스 변환 (Swing Strategy)...")
    strategy = SwingStrategy(config)
    entries, weights = strategy.generate_signals(final_predictions, market_df)

    print("\n[2] VectorBT 퀀트 시뮬레이터 가동 (Backtest Engine)...")
    bt_engine = VectorBTEngine(config)
    pf = bt_engine.run(entries, weights, market_df)

    daily_returns = pf.returns()
    daily_returns.index = pd.to_datetime(daily_returns.index).tz_localize(None)
    trades_all = pf.trades.records_readable if len(pf.trades.records) > 0 else pd.DataFrame()

    backtest_metrics = []
    for idx, split in enumerate(splits):
        fold_id = split.get("fold_id", idx)
        fold_name = split.get("name", f"Fold {fold_id}")
        test_start = pd.to_datetime(split["test_start"])
        test_end = pd.to_datetime(split["test_end"])

        fold_returns = daily_returns[(daily_returns.index >= test_start) & (daily_returns.index <= test_end)]
        fold_trades = _slice_trades(trades_all, test_start, test_end)
        metrics = calculate_trading_metrics(fold_returns, fold_trades)
        metrics["fold_id"] = fold_id
        metrics["Fold"] = fold_name
        metrics["test_start"] = split["test_start"]
        metrics["test_end"] = split["test_end"]
        backtest_metrics.append(metrics)

    backtest_metrics_df = pd.DataFrame(backtest_metrics)

    yearly_metrics = []
    for year in sorted(daily_returns.index.year.unique()):
        year_returns = daily_returns[daily_returns.index.year == year]
        if trades_all.empty:
            year_trades = pd.DataFrame()
        else:
            year_start = pd.Timestamp(year=year, month=1, day=1)
            year_end = pd.Timestamp(year=year, month=12, day=31)
            year_trades = _slice_trades(trades_all, year_start, year_end)
        metrics = calculate_trading_metrics(year_returns, year_trades)
        metrics["Year"] = int(year)
        yearly_metrics.append(metrics)

    backtest_by_year_df = pd.DataFrame(yearly_metrics)

    print("\n[3] Baseline 벤치마크 전략 시뮬레이션...")
    top_n = config.get("strategy", {}).get("top_n", 5)
    random_seeds = config.get("evaluation", {}).get("random_baseline_seeds", 5)
    random_returns = []
    random_mdds = []
    random_sharpes = []

    for seed in range(100, 100 + random_seeds):
        random_entries, random_weights = generate_random_top_k_signals(
            market_df, top_n=top_n, seed=seed
        )
        random_pf = bt_engine.run(random_entries, random_weights, market_df, generate_report=False)
        random_metrics = calculate_trading_metrics(
            random_pf.returns(),
            random_pf.trades.records_readable if len(random_pf.trades.records) > 0 else None,
        )
        random_returns.append(random_metrics.get("total_return", np.nan))
        random_mdds.append(random_metrics.get("max_drawdown", np.nan))
        random_sharpes.append(random_metrics.get("sharpe_ratio", np.nan))

    mom_entries, mom_weights = generate_momentum_signals(market_df, top_n=top_n, horizon=5)
    mom_pf = bt_engine.run(mom_entries, mom_weights, market_df, generate_report=False)
    mom_metrics = calculate_trading_metrics(
        mom_pf.returns(), mom_pf.trades.records_readable if len(mom_pf.trades.records) > 0 else None
    )

    ma_entries, ma_weights = generate_ma_breakout_signals(market_df, top_n=top_n, window=20)
    ma_pf = bt_engine.run(ma_entries, ma_weights, market_df, generate_report=False)
    ma_metrics = calculate_trading_metrics(
        ma_pf.returns(), ma_pf.trades.records_readable if len(ma_pf.trades.records) > 0 else None
    )

    krx_returns = compute_custom_krx_composite(daily_returns.index, market_df)
    krx_source = krx_returns.attrs.get("benchmark_source", "unknown")
    krx_reason = krx_returns.attrs.get("benchmark_reason", "")
    krx_valid = krx_returns.attrs.get("benchmark_valid", False)
    krx_validity_reason = krx_returns.attrs.get("benchmark_validity_reason", "")
    krx_metrics = calculate_trading_metrics(krx_returns)
    model_metrics = calculate_trading_metrics(daily_returns, trades_all)

    benchmark_comparison_df = pd.DataFrame(
        [
            {
                "Strategy": "LGBM Model",
                "Total Return": _format_pct(model_metrics.get("total_return", np.nan)),
                "Sharpe Ratio": _format_float(model_metrics.get("sharpe_ratio", np.nan)),
                "Max Drawdown": _format_pct(model_metrics.get("max_drawdown", np.nan)),
                "Win Rate": _format_pct(model_metrics.get("win_rate", np.nan)),
                "Benchmark Source": "",
            },
            {
                "Strategy": f"Random Top-{top_n} (Mean)",
                "Total Return": _format_pct(float(np.nanmean(random_returns))),
                "Sharpe Ratio": _format_float(float(np.nanmean(random_sharpes))),
                "Max Drawdown": _format_pct(float(np.nanmean(random_mdds))),
                "Win Rate": "N/A",
                "Benchmark Source": "",
            },
            {
                "Strategy": "5-Day Momentum",
                "Total Return": _format_pct(mom_metrics.get("total_return", np.nan)),
                "Sharpe Ratio": _format_float(mom_metrics.get("sharpe_ratio", np.nan)),
                "Max Drawdown": _format_pct(mom_metrics.get("max_drawdown", np.nan)),
                "Win Rate": _format_pct(mom_metrics.get("win_rate", np.nan)),
                "Benchmark Source": "",
            },
            {
                "Strategy": "20-Day MA Breakout",
                "Total Return": _format_pct(ma_metrics.get("total_return", np.nan)),
                "Sharpe Ratio": _format_float(ma_metrics.get("sharpe_ratio", np.nan)),
                "Max Drawdown": _format_pct(ma_metrics.get("max_drawdown", np.nan)),
                "Win Rate": _format_pct(ma_metrics.get("win_rate", np.nan)),
                "Benchmark Source": "",
            },
            {
                "Strategy": "Custom KRX Composite Index",
                "Total Return": _format_pct(krx_metrics.get("total_return", np.nan)),
                "Sharpe Ratio": _format_float(krx_metrics.get("sharpe_ratio", np.nan)),
                "Max Drawdown": _format_pct(krx_metrics.get("max_drawdown", np.nan)),
                "Win Rate": "N/A",
                "Benchmark Source": krx_source,
            },
        ]
    )

    summary = {f"trade_{key}": _json_safe(value) for key, value in model_metrics.items()}
    summary.update(
        {
            "prediction_hash": predictions_hash,
            "benchmark_custom_krx_source": krx_source,
            "benchmark_custom_krx_reason": krx_reason,
            "benchmark_custom_krx_valid": krx_valid,
            "benchmark_custom_krx_validity_reason": krx_validity_reason,
            **{f"benchmark_custom_krx_{key}": _json_safe(value) for key, value in krx_metrics.items()},
            "fold_alignment_exact": bool(alignment_status["is_exact_fold_match"]),
            **{f"fold_alignment_{key}": _json_safe(value) for key, value in alignment_status.items()},
        }
    )

    out_dir = result_dir(config, __file__)
    alignment_df.to_csv(os.path.join(out_dir, "fold_alignment.csv"), index=False)
    backtest_metrics_df.to_csv(os.path.join(out_dir, "backtest_metrics_by_fold.csv"), index=False)
    backtest_by_year_df.to_csv(os.path.join(out_dir, "backtest_metrics_by_year.csv"), index=False)
    benchmark_comparison_df.to_csv(os.path.join(out_dir, "benchmark_comparison.csv"), index=False)
    pd.DataFrame(
        [
            {
                "benchmark": "Custom KRX Composite Index",
                "source": krx_source,
                "reason": krx_reason,
                "valid": krx_valid,
                "validity_reason": krx_validity_reason,
            }
        ]
    ).to_csv(os.path.join(out_dir, "benchmark_metadata.csv"), index=False)
    with open(os.path.join(out_dir, "backtest_metrics_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4, ensure_ascii=False)
    with open(os.path.join(out_dir, "config_snapshot.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)

    print(
        f"\n🎉 백테스트 [{exp_name}] 완료. fold_alignment_exact={alignment_status['is_exact_fold_match']}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True, help="Path to config yaml")
    parser.add_argument(
        "--predictions-path",
        type=str,
        default=None,
        help="Path to pre-computed predictions parquet file",
    )
    args = parser.parse_args()
    main(args.config, args.predictions_path)
