#!/bin/bash
# H=10 selection 후보 3개를 순차 학습·평가한다.
# Run from any directory. Override PYTHON_BIN when a specific virtualenv is needed.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENTS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
cd "$EXPERIMENTS_DIR"

echo "Starting sequential H=10 selection experiments"

for config in \
  configs/tb_lgbm_h10_u225_d200_alpha158_current_sigma_selection2020_2022.yaml \
  configs/tb_lgbm_h10_u250_d225_alpha158_current_sigma_selection2020_2022.yaml \
  configs/tb_lgbm_h10_u275_d225_alpha158_current_sigma_selection2020_2022.yaml
do
  "$PYTHON_BIN" train.py --config "$config"
  "$PYTHON_BIN" run_experiment_analysis.py --config "$config"
done
