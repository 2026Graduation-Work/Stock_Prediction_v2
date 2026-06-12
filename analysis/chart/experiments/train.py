import argparse
import gc
import hashlib
import json
import os

import pandas as pd
import yaml
from train_src.lgbm_wrapper import LGBMWrapper
from train_src.loaders import load_parquet_data


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


def generate_dataset_hash(config: dict, resolved_splits: list) -> str:
    """Dataset(.bin) 캐시용 해시: 데이터/피처/라벨 세팅의 변경사항만 감지하여 생성합니다."""
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
    }
    hash_str = json.dumps(hash_dict, sort_keys=True)
    return hashlib.md5(hash_str.encode()).hexdigest()[:8]


def generate_predictions_hash(config: dict, resolved_splits: list) -> str:
    """예측 확률 및 모델 캐시용 해시: 데이터/피처/라벨 + 모델 하이퍼파라미터를 감지하여 생성합니다."""
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
        os.path.abspath(
            os.path.join(current_dir, "..", "data", "processed")
        ),  # 블록 내부 data/processed
        os.path.abspath(
            os.path.join(current_dir, "..", "..", "..", "data", "processed")
        ),  # 프로젝트 루트 data/processed
        os.path.abspath(os.path.join(os.getcwd(), "data", "processed")),  # 현재 CWD 기준
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            return p
    # 기본값으로 첫 번째 후보군 반환
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
    print(f"\n🚀 [*] Starting Quant Experiment: {exp_name}")

    # 데이터 분할 전략에 따른 fold 목록 결정
    splits = resolve_splits(config)
    if not splits:
        raise ValueError("분할 폴드(Splits) 목록이 비어 있습니다. 설정을 확인하세요.")

    print(
        f"[*] 데이터 분할 전략: {config.get('data', {}).get('split_strategy', 'single')} (총 {len(splits)}개 폴드)"
    )
    for idx, split_info in enumerate(splits):
        print(
            f"    - [Fold {idx + 1}] Train: {split_info['train_start']} ~ {split_info['train_end']} | Test: {split_info['test_start']} ~ {split_info['test_end']}"
        )

    # 캐시용 해시 생성
    dataset_hash = generate_dataset_hash(config, splits)
    predictions_hash = generate_predictions_hash(config, splits)
    print(f"[*] Dataset Cache Hash: {dataset_hash} | Predictions Cache Hash: {predictions_hash}")

    # 데이터 경로 자동 탐색
    processed_dir = find_processed_dir()
    print(f"[*] 데이터 소스 디렉토리: {processed_dir}")
    if not os.path.exists(processed_dir) or not os.listdir(processed_dir):
        print(
            f"[!] 경고: {processed_dir}가 비어있거나 존재하지 않습니다. 먼저 수집 및 전처리를 실행해야 할 수 있습니다."
        )

    tickers_cfg = config.get("data", {}).get("tickers", None)

    # OOS 예측 확률 캐시 확인
    current_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(current_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    predictions_cache_path = os.path.join(cache_dir, f"{predictions_hash}_predictions.parquet")

    if os.path.exists(predictions_cache_path):
        print("\n⚡ [CACHE HIT] 기존 설정 기반 예측 캐시를 찾았습니다!")
        print(f"   -> 캐시 파일: {os.path.basename(predictions_cache_path)}")
        final_predictions = pd.read_parquet(predictions_cache_path)
    else:
        all_predictions = []

        for idx, split_info in enumerate(splits):
            print(f"\n{'=' * 60}")
            print(f"▶ [데이터 분할 Fold {idx + 1}/{len(splits)}] 학습 및 추론 진행 중...")
            print(f"{'=' * 60}")

            train_start = split_info["train_start"]
            train_end = split_info["train_end"]
            test_start = split_info["test_start"]
            test_end = split_info["test_end"]

            fold_pred_hash = f"{predictions_hash}_fold{idx}"
            models_dir = os.path.join(cache_dir, "models")
            os.makedirs(models_dir, exist_ok=True)
            model_save_path = os.path.join(models_dir, f"{fold_pred_hash}_model.txt")

            if os.path.exists(model_save_path):
                print(
                    f"\n⚡ [MODEL CACHE HIT] 기존 학습된 모델 파라미터 발견! -> {os.path.basename(model_save_path)}"
                )
                import lightgbm as lgb

                model_wrapper = LGBMWrapper(config)
                model_wrapper.model = lgb.Booster(model_file=model_save_path)
                feature_cols = model_wrapper.model.feature_name()
            else:
                # 검증을 위해 Train의 마지막 6개월을 Validation으로 사용
                train_end_dt = pd.to_datetime(train_end)
                pure_train_end_dt = train_end_dt - pd.DateOffset(months=6)
                embargo_days = config.get("data", {}).get("embargo_days", 7)
                val_start_dt = pure_train_end_dt + pd.Timedelta(days=embargo_days)
                pure_train_end = pure_train_end_dt.strftime("%Y-%m-%d")
                val_start = val_start_dt.strftime("%Y-%m-%d")

                # ---------------------------------------------------------
                # 1. 학습 데이터 (Train) 준비 및 라벨링
                # ---------------------------------------------------------
                print("\n[1] Train 데이터 로딩 및 동적 라벨(Y) 생성...")
                label_params = {
                    "type": config["labels"].get("type", "dynamic_sigma"),
                    "horizon": config["labels"]["horizon"],
                    "up_mult": config["labels"].get("up_mult", 1.5),
                    "down_mult": config["labels"].get("down_mult", 1.2),
                }

                # 순수 Alpha158 학습 (노이즈 필터링 배제)
                train_df = load_parquet_data(
                    processed_dir,
                    train_start,
                    pure_train_end,
                    tickers=tickers_cfg,
                    label_params=label_params,
                    training=True,
                    keep_date=False,
                )

                exclude_cols = ["Y_Label", "Date", "Code"]
                feature_cols = [c for c in train_df.columns if c not in exclude_cols]

                X_train, y_train = train_df[feature_cols], train_df["Y_Label"]

                # ---------------------------------------------------------
                # 2. 모델 학습 시작 및 Train 데이터셋 빌드 (RAM 즉시 해제)
                # ---------------------------------------------------------
                print("\n[2] 모델 학습 준비 (LGBM Wrapper)...")
                model_wrapper = LGBMWrapper(config)
                fold_data_hash = f"{dataset_hash}_fold{idx}"

                train_bin_path = os.path.join(
                    model_wrapper.cache_dir, f"{fold_data_hash}_train.bin"
                )
                train_data = model_wrapper._build_dataset(X_train, y_train, train_bin_path)

                del train_df, X_train, y_train
                gc.collect()

                # ---------------------------------------------------------
                # 2.5. 검증 데이터 (Val) 준비 및 라벨링
                # ---------------------------------------------------------
                print("\n[2.5] Val 데이터 로딩 및 동적 라벨(Y) 생성...")
                val_df = load_parquet_data(
                    processed_dir,
                    val_start,
                    train_end,
                    tickers=tickers_cfg,
                    label_params=label_params,
                    training=False,
                )

                val_cols = ["Date", "Code", "Y_Label", "Close", "Trading_Halt"] + feature_cols
                val_df = val_df[[c for c in val_cols if c in val_df.columns]].copy()

                X_val, y_val = val_df[feature_cols], val_df["Y_Label"]

                print("[LGBM] Validation 데이터셋 준비 중...")
                import lightgbm as lgb
                from sklearn.utils.class_weight import compute_sample_weight

                sample_weights_val = compute_sample_weight("balanced", y_val)
                valid_data = lgb.Dataset(
                    X_val,
                    label=y_val,
                    weight=sample_weights_val,
                    reference=train_data,
                    free_raw_data=False,
                )

                # 모델 학습
                model_wrapper.fit(train_data, valid_data, cache_hash=fold_pred_hash)

                # ---------------------------------------------------------
                # 2.6. 검증 데이터에 대한 통계적 검정 (OOS 과적합 통제)
                # ---------------------------------------------------------
                print("\n[2.6] Validation 셋에 대한 통계적 신뢰성 검증 진행...")
                import numpy as np
                import scipy.stats as stats

                val_probs = model_wrapper.predict(X_val)
                val_eval_df = val_df[["Date", "Code", "Y_Label"]].copy()
                val_eval_df["Prob"] = val_probs
                val_eval_df["Close"] = val_df.get("Close", 10.0)
                val_eval_df["Trading_Halt"] = val_df.get("Trading_Halt", 0)

                # Rank IC
                def get_spearman(group):
                    if len(group) < 5:
                        return np.nan
                    if group["Prob"].std() == 0 or group["Y_Label"].std() == 0:
                        return np.nan
                    return group["Prob"].corr(group["Y_Label"], method="spearman")

                daily_ic = val_eval_df.groupby("Date").apply(get_spearman).dropna()

                if len(daily_ic) < 5:
                    raise ValueError(
                        f"[-] Validation 기간의 유효 거래일 수({len(daily_ic)})가 너무 적어 통계 검정이 불가능합니다."
                    )

                mean_ic = daily_ic.mean()
                std_ic = daily_ic.std()
                n_days = len(daily_ic)

                # IC t-test
                t_stat = 0.0 if std_ic == 0 else mean_ic / (std_ic / np.sqrt(n_days))
                p_val_t = stats.t.sf(t_stat, df=n_days - 1)

                # 이항검정
                prob_threshold = config.get("strategy", {}).get("prob_threshold", 0.65)
                top_n = config.get("strategy", {}).get("top_n", 5)

                val_eval_df["Is_Valid"] = (
                    (val_eval_df["Prob"] >= prob_threshold)
                    & (val_eval_df["Close"] > 1.0)
                    & (val_eval_df["Trading_Halt"] == 0)
                )

                def select_top_signals(group, top_n=top_n):
                    valid_group = group[group["Is_Valid"]]
                    if valid_group.empty:
                        return pd.DataFrame()
                    return valid_group.nlargest(top_n, "Prob")

                selected_signals = val_eval_df.groupby("Date", group_keys=False).apply(
                    select_top_signals
                )
                n_signals = len(selected_signals)
                base_rate = (val_eval_df["Y_Label"] == 2).mean()

                if n_signals == 0:
                    n_success = 0
                    success_rate = 0.0
                    p_val_binom = 1.0
                else:
                    n_success = (selected_signals["Y_Label"] == 2).sum()
                    success_rate = n_success / n_signals
                    p_val_binom = (
                        1.0 - stats.binom.cdf(n_success - 1, n_signals, base_rate)
                        if n_success > 0
                        else 1.0
                    )

                ic_passed = mean_ic >= 0.02
                t_stat_passed = t_stat >= 2.0 and p_val_t <= 0.05
                binom_passed = p_val_binom <= 0.05

                print("=" * 85)
                print(f"📊 [VALIDATION REPORT] Fold {idx + 1} Validation Summary")
                print("=" * 85)
                print(
                    f"  - Mean Rank IC:   {mean_ic:.4f}  (Threshold: >= 0.02) -> {'PASSED ✅' if ic_passed else 'FAILED ❌'}"
                )
                print(
                    f"  - t-statistic:    {t_stat:.4f}  (Threshold: >= 2.0)  -> {'PASSED ✅' if t_stat >= 2.0 else 'FAILED ❌'}"
                )
                print(
                    f"  - Success Rate:   {success_rate * 100:.2f}% (Base Rate: {base_rate * 100:.2f}%)"
                )
                print(
                    f"  - Binomial p-val: {p_val_binom:.6f}  (Threshold: <= 0.05) -> {'PASSED ✅' if binom_passed else 'FAILED ❌'}"
                )
                print("=" * 85)

                if not (ic_passed and t_stat_passed and binom_passed):
                    print(
                        f"\n❌ [VALIDATION FAILED] Fold {idx + 1} 통계적 검정 미통과 (과적합 위험)."
                    )
                    raise RuntimeError("Validation Statistical Test Failed.")

                del val_df, X_val, y_val, val_probs, val_eval_df, daily_ic, valid_data
                gc.collect()

            # ---------------------------------------------------------
            # 3. 테스트(OOS) 추론
            # ---------------------------------------------------------
            print("\n[3] Test(Out-of-Sample) 데이터 로딩 및 추론...")
            test_df = load_parquet_data(
                processed_dir,
                test_start,
                test_end,
                columns_only=feature_cols + ["Date", "Code"],
                tickers=tickers_cfg,
            )
            X_test = test_df[feature_cols]

            probs = model_wrapper.predict(X_test)

            test_preds = test_df[["Date", "Code"]].copy()
            test_preds["Prob"] = probs
            all_predictions.append(test_preds)

            del test_df, X_test
            gc.collect()

        final_predictions = pd.concat(all_predictions, ignore_index=True)
        final_predictions.to_parquet(predictions_cache_path, index=False)
        print(
            f"\n💾 [CACHE SAVE] 예측 결과 캐시 완료 -> {os.path.basename(predictions_cache_path)}"
        )
    print(f"\n🎉 모델 학습 및 예측 캐시 빌드 [{exp_name}] 완료!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True, help="Path to config yaml")
    args = parser.parse_args()
    main(args.config)
