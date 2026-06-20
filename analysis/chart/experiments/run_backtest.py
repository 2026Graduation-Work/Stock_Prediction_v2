import argparse
import hashlib
import json
import os

import pandas as pd
import yaml
from backtest.engine import VectorBTEngine
from train_src.loaders import load_parquet_data
from train_src.swing_strategy import SwingStrategy


def resolve_splits(config: dict) -> list:
    """config['data']의 split_strategy 에 따라 폴드 목록을 계산하여 반환합니다."""
    data_cfg = config.get("data", {})
    strategy = data_cfg.get("split_strategy", "single")
    embargo_days = data_cfg.get("embargo_days", 7)

    if strategy == "single":
        return data_cfg.get("splits", [])

    elif strategy == "sliding":
        cfg = data_cfg.get("sliding", {})
        tw = cfg.get("train_window_years", 3)
        te = cfg.get("test_window_years", 1)
        sy = cfg.get("start_year", 2016)
        ey = cfg.get("end_year", 2025)

        folds_info = []
        for y in range(sy + tw, ey - te + 1):
            ts = (pd.to_datetime(f"{y - 1}-12-31") + pd.Timedelta(days=embargo_days)).strftime(
                "%Y-%m-%d"
            )
            folds_info.append(
                {
                    "train_start": f"{y - tw}-01-01",
                    "train_end": f"{y - 1}-12-31",
                    "test_start": ts,
                    "test_end": f"{y}-12-31",
                }
            )
        return folds_info

    elif strategy == "expanding":
        cfg = data_cfg.get("expanding", {})
        iy = cfg.get("initial_train_years", 5)
        te = cfg.get("test_window_years", 1)
        sy = cfg.get("start_year", 2016)
        ey = cfg.get("end_year", 2025)

        folds_info = []
        for y in range(sy + iy, ey - te + 1):
            ts = (pd.to_datetime(f"{y - 1}-12-31") + pd.Timedelta(days=embargo_days)).strftime(
                "%Y-%m-%d"
            )
            folds_info.append(
                {
                    "train_start": f"{sy}-01-01",
                    "train_end": f"{y - 1}-12-31",
                    "test_start": ts,
                    "test_end": f"{y}-12-31",
                }
            )
        return folds_info
    else:
        raise ValueError(f"지원하지 않는 split 전략: {strategy}")


def generate_predictions_hash(config: dict, resolved_splits: list) -> str:
    """예측 확률 캐시 파일명을 결정하기 위한 해시를 산출합니다."""
    hash_dict = {
        "data": {
            "tickers": config.get("data", {}).get("tickers", None),
            "start_date": config.get("data", {}).get("start_date", None),
            "end_date": config.get("data", {}).get("end_date", None),
            "split_strategy": config.get("data", {}).get("split_strategy", "single"),
            "embargo_days": config.get("data", {}).get("embargo_days", 7),
            "splits": resolved_splits,
        },
        "features": config.get("features", {}),
        "labels": config.get("labels", {}),
        "model": config.get("model", {}),
    }
    hash_str = json.dumps(hash_dict, sort_keys=True)
    return hashlib.md5(hash_str.encode()).hexdigest()[:8]


def find_processed_dir() -> str:
    """
    실행 경로에 구애받지 않도록 data/processed 폴더의 위치를 유연하게 탐색합니다.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_paths = [
        os.path.abspath(os.path.join(current_dir, "..", "data", "processed")),
        os.path.abspath(os.path.join(current_dir, "..", "..", "..", "data", "processed")),
        os.path.abspath(os.path.join(os.getcwd(), "data", "processed")),
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            return p
    return candidate_paths[0]


def main(config_path):
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"[ERROR] 설정을 불러올 수 없습니다. 경로를 확인해주세요: {config_path}"
        )

    print(f"[*] Loading config from {config_path}...")
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    exp_name = config.get("experiment_name", "default_exp")
    print(f"\n📈 [*] Starting Single Backtesting: {exp_name}")

    # 데이터 분할 전략 기반 fold 계산
    splits = resolve_splits(config)
    if not splits:
        raise ValueError("분할 폴드(Splits) 목록이 비어 있습니다. 설정을 확인하세요.")

    predictions_hash = generate_predictions_hash(config, splits)
    print(f"[*] Target Predictions Cache Hash: {predictions_hash}")

    # 캐시된 예측 확률 확인
    current_dir = os.path.dirname(os.path.abspath(__file__))
    predictions_cache_path = os.path.join(
        current_dir, "cache", f"{predictions_hash}_predictions.parquet"
    )

    if not os.path.exists(predictions_cache_path):
        print("\n❌ [ERROR] 캐시된 예측 결과를 찾을 수 없습니다!")
        print(f"   -> 대상 파일: {os.path.basename(predictions_cache_path)}")
        print("   -> 백테스트를 돌리려면 먼저 모델 학습 및 OOS 예측 캐시를 생성해야 합니다.")
        print("   -> 해결방법: 먼저 아래 명령어를 수행하여 모델 예측 결과를 빌드해 주세요.")
        print(f"      python experiments/train.py --config {config_path}")
        return

    print("⚡ [CACHE HIT] 캐시된 OOS 예측 결과를 로드합니다.")
    final_predictions = pd.read_parquet(predictions_cache_path)

    # 데이터 소스 경로 탐색
    processed_dir = find_processed_dir()
    print(f"[*] 데이터 소스 디렉토리: {processed_dir}")

    # ---------------------------------------------------------
    # 1. 전략 시그널 생성 (Strategy)
    # ---------------------------------------------------------
    print("\n[1] 트레이딩 전략 매트릭스 변환 (Swing Strategy)...")
    strategy = SwingStrategy(config)

    full_test_start = splits[0]["test_start"]
    full_test_end = splits[-1]["test_end"]
    tickers_cfg = config.get("data", {}).get("tickers", None)

    # 시그널과 결합할 핵심 가격 데이터만 로드 (가볍고 고속)
    price_cols = ["Date", "Code", "Open", "High", "Low", "Close", "Sigma", "Trading_Halt"]
    market_df = load_parquet_data(
        processed_dir, full_test_start, full_test_end, columns_only=price_cols, tickers=tickers_cfg
    )

    # 전략 매트릭스 변환
    entries, weights = strategy.generate_signals(final_predictions, market_df)

    # ---------------------------------------------------------
    # 2. 백테스트 (Backtest Engine)
    # ---------------------------------------------------------
    print("\n[2] VectorBT 퀀트 시뮬레이터 가동 (Backtest Engine)...")
    bt_engine = VectorBTEngine(config)
    bt_engine.run(entries, weights, market_df)

    print(
        f"\n🎉 단독 백테스트 시뮬레이션 [{exp_name}] 완료! 결과가 experiments/results/ 하위에 업데이트되었습니다."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True, help="Path to config yaml")
    args = parser.parse_args()
    main(args.config)
