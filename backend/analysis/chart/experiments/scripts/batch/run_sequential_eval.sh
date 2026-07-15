#!/bin/bash
# H10/H20 holdout 및 robustness 평가를 순차 실행한다.
# Run from any directory. Override PYTHON_BIN when a specific virtualenv is needed.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENTS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
cd "$EXPERIMENTS_DIR"

echo "[1/3] H10 holdout backtests"
for config in \
  configs/tb_lgbm_h10_u225_d200_alpha158_current_sigma_holdout2024.yaml \
  configs/tb_lgbm_h10_u250_d225_alpha158_current_sigma_holdout2024.yaml
do
  "$PYTHON_BIN" run_backtest.py --config "$config"
done

echo "[2/3] H20 holdout ML evaluations"
for config in \
  configs/tb_lgbm_h20_u375_d300_alpha158_current_sigma_holdout2024.yaml \
  configs/tb_lgbm_h20_u400_d300_alpha158_current_sigma_holdout2024.yaml
do
  "$PYTHON_BIN" run_ml_evaluation.py --config "$config"
done

echo "[3/3] H20 robustness training and analysis"
ROBUSTNESS_CONFIG="configs/tb_lgbm_h20_u375_d300_alpha158_current_sigma_robustness2019_2023_2024.yaml"
"$PYTHON_BIN" train.py --config "$ROBUSTNESS_CONFIG"
"$PYTHON_BIN" run_experiment_analysis.py --config "$ROBUSTNESS_CONFIG"
