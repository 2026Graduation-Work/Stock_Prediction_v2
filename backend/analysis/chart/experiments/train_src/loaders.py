import glob
import os

import numpy as np
import pandas as pd
from tqdm import tqdm


def apply_fixed_barrier_labeling(
    df: pd.DataFrame, horizon: int, tp_pct: float, sl_pct: float
) -> pd.Series:
    """단일 종목 데이터프레임에 대해 고속 고정 % 배리어 라벨링을 적용합니다. (NumPy 고속화)"""
    barrier_up = df["Close"] * (1 + tp_pct / 100.0)
    barrier_down = df["Close"] * (1 - sl_pct / 100.0)

    n = len(df)
    hit_up_day = np.full(n, 999, dtype=np.int16)
    hit_down_day = np.full(n, 999, dtype=np.int16)

    halt_flag = df.get("Trading_Halt", pd.Series(0, index=df.index)).values
    high_vals = df["High"].values
    close_vals = df["Close"].values
    up_barrier_vals = barrier_up.values
    down_barrier_vals = barrier_down.values

    for d in range(1, horizon + 1):
        future_high = np.zeros(n)
        future_close = np.zeros(n)
        future_halt = np.ones(n, dtype=np.int8)

        future_high[:-d] = high_vals[d:]
        future_close[:-d] = close_vals[d:]
        future_halt[:-d] = halt_flag[d:]

        active = future_halt == 0
        is_hit_up = active & (future_high >= up_barrier_vals)
        is_hit_down = active & (future_close <= down_barrier_vals)

        hit_up_day = np.where(is_hit_up & (hit_up_day == 999), d, hit_up_day)
        hit_down_day = np.where(is_hit_down & (hit_down_day == 999), d, hit_down_day)

    success_mask = (hit_up_day != 999) & (hit_up_day < hit_down_day)
    fail_mask = (hit_down_day != 999) & (hit_down_day <= hit_up_day)

    y_label = np.zeros(n, dtype=np.int8)
    y_label[success_mask] = 1
    y_label[fail_mask] = -1

    y_label_series = pd.Series(y_label, index=df.index)
    if n > horizon:
        y_label_series.iloc[-horizon:] = np.nan

    return y_label_series


def apply_dynamic_sigma_barrier_labeling(
    df: pd.DataFrame, horizon: int, up_mult: float, down_mult: float
) -> pd.Series:
    """단일 종목 데이터프레임에 대해 변동성(Sigma) 기반 동적 트리플 배리어 라벨링을 적용합니다. (NumPy 고속화)"""
    sigma_vals = df["Sigma"].values if "Sigma" in df.columns else np.full(len(df), 0.01)

    barrier_up = df["Close"] * (1 + up_mult * sigma_vals)
    barrier_down = df["Close"] * (1 - down_mult * sigma_vals)

    n = len(df)
    hit_up_day = np.full(n, 999, dtype=np.int16)
    hit_down_day = np.full(n, 999, dtype=np.int16)

    halt_flag = df.get("Trading_Halt", pd.Series(0, index=df.index)).values
    high_vals = df["High"].values
    close_vals = df["Close"].values
    up_barrier_vals = barrier_up.values if hasattr(barrier_up, "values") else barrier_up
    down_barrier_vals = barrier_down.values if hasattr(barrier_down, "values") else barrier_down

    trading_day_cumsum = np.cumsum(1 - halt_flag)
    max_search_days = int(horizon * 2.5)

    for d in range(1, max_search_days + 1):
        future_high = np.zeros(n)
        future_close = np.zeros(n)
        future_halt = np.ones(n, dtype=np.int8)
        passed_trading_days = np.full(n, 999, dtype=np.int16)

        future_high[:-d] = high_vals[d:]
        future_close[:-d] = close_vals[d:]
        future_halt[:-d] = halt_flag[d:]
        passed_trading_days[:-d] = trading_day_cumsum[d:] - trading_day_cumsum[:-d]

        active = (future_halt == 0) & (passed_trading_days <= horizon)
        is_hit_up = active & (future_high >= up_barrier_vals)
        is_hit_down = active & (future_close <= down_barrier_vals)

        hit_up_day = np.where(is_hit_up & (hit_up_day == 999), passed_trading_days, hit_up_day)
        hit_down_day = np.where(
            is_hit_down & (hit_down_day == 999), passed_trading_days, hit_down_day
        )

    success_mask = (hit_up_day != 999) & (hit_up_day < hit_down_day)
    fail_mask = (hit_down_day != 999) & (hit_down_day <= hit_up_day)

    y_label = np.zeros(n, dtype=np.int8)
    y_label[success_mask] = 1
    y_label[fail_mask] = -1

    y_label_series = pd.Series(y_label, index=df.index)
    if n > horizon:
        y_label_series.iloc[-horizon:] = np.nan

    return y_label_series


def load_parquet_data(
    data_dir: str,
    start_date: str = None,
    end_date: str = None,
    columns_only: list = None,
    tickers: str = None,
    label_params: dict = None,
    training: bool = False,
    keep_date: bool = False,
) -> pd.DataFrame:
    """
    Parquet 파일들을 디스크에서 읽어오는 로더입니다.
    메모리 절약을 위해 종목별 로딩 시점에 Y 라벨 생성 및 피처 분리를 즉시 수행합니다.
    """
    files = glob.glob(os.path.join(data_dir, "*.parquet"))

    if tickers == "KOSPI_TOP200":
        try:
            import FinanceDataReader as fdr

            print("[*] KOSPI TOP 200 종목 필터링 중...")
            kospi = fdr.StockListing("KOSPI")
            kospi = kospi.sort_values(by="Marcap", ascending=False)
            top_200_codes = set(kospi["Code"].head(200).tolist())

            filtered_files = []
            for f in files:
                basename = os.path.basename(f)
                code = basename.split(".")[0]
                if code in top_200_codes:
                    filtered_files.append(f)
            files = filtered_files
            print(f"[*] KOSPI TOP 200 매칭된 파일 수: {len(files)}개")
        except Exception as e:
            print(f"[!] KOSPI TOP 200 필터링 실패 (전체 로드로 대체): {e}")

    print(f"총 {len(files)}개 종목 데이터 로드 중... (날짜 필터: {start_date} ~ {end_date})")

    df_list = []
    for f in tqdm(files, desc="데이터 파일 로드 중", mininterval=0.5):
        try:
            if columns_only is not None:
                import pyarrow.parquet as pq

                file_schema_names = pq.read_schema(f).names
                required_cols = [
                    "Date",
                    "Code",
                    "Close",
                    "High",
                    "Low",
                    "Open",
                    "Volume",
                    "Trading_Halt",
                    "Sigma",
                ]
                cols_to_load = list(set(columns_only + required_cols) & set(file_schema_names))
                temp_df = pd.read_parquet(f, columns=cols_to_load)
            else:
                temp_df = pd.read_parquet(f)

            if temp_df.empty:
                continue

            temp_df["Date"] = pd.to_datetime(temp_df["Date"])
            temp_df = temp_df.sort_values("Date").reset_index(drop=True)
            if start_date is not None:
                temp_df = temp_df[temp_df["Date"] >= pd.to_datetime(start_date)]

            # 라벨은 t 이후 horizon 거래일의 가격을 참조한다. 요청 종료일에서
            # 즉시 자르면 마지막 horizon 행의 실제 라벨이 모두 사라진다. 따라서
            # 라벨 생성시에만 종목별 우측 버퍼를 함께 읽고, 생성 뒤 요청 기간으로
            # 다시 제한한다. dynamic barrier는 거래정지일을 건너뛸 수 있어 더 넉넉한
            # 탐색 범위를 사용한다.
            requested_end = pd.to_datetime(end_date) if end_date is not None else None
            if requested_end is not None:
                if label_params is None:
                    temp_df = temp_df[temp_df["Date"] <= requested_end]
                else:
                    horizon = int(label_params["horizon"])
                    label_type = label_params.get("type", "fixed")
                    buffer_rows = horizon
                    if label_type == "dynamic_sigma":
                        buffer_rows = int(np.ceil(horizon * 2.5))

                    in_requested_period = temp_df[temp_df["Date"] <= requested_end]
                    right_buffer = temp_df[temp_df["Date"] > requested_end].head(buffer_rows)
                    temp_df = pd.concat([in_requested_period, right_buffer], ignore_index=True)

            if temp_df.empty:
                continue

            # [실시간 고속 Y 라벨링] 로딩 시점에 종목별로 즉시 라벨 생성 (OOM 원천 방지)
            if label_params is not None:
                label_type = label_params.get("type", "fixed")
                horizon = label_params["horizon"]

                if label_type == "dynamic_sigma":
                    up_mult = label_params.get("up_mult", 1.5)
                    down_mult = label_params.get("down_mult", 1.2)
                    y_label_series = apply_dynamic_sigma_barrier_labeling(
                        temp_df, horizon, up_mult, down_mult
                    )
                else:
                    tp = label_params.get("tp", 3.5)
                    sl = label_params.get("sl", 2.0)
                    y_label_series = apply_fixed_barrier_labeling(temp_df, horizon, tp, sl)

                temp_df["Y_Label"] = y_label_series.map({-1: 0, 0: 1, 1: 2})
                temp_df = temp_df.dropna(subset=["Y_Label"])
                temp_df["Y_Label"] = temp_df["Y_Label"].astype(int)

                if requested_end is not None:
                    temp_df = temp_df[temp_df["Date"] <= requested_end]

            if temp_df.empty:
                continue

            # [훈련 피처 다이어트] 훈련 데이터셋 로딩 시 즉각 피처만 남겨서 peak 메모리 최소화
            if training:
                exclude_cols = [
                    "Code",
                    "Name",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume",
                    "IsDelisted",
                    "Log_Ret",
                    "Sigma",
                    "Y_Label",
                    "Trading_Halt",
                ]
                if not keep_date:
                    exclude_cols.append("Date")
                feature_cols = [c for c in temp_df.columns if c not in exclude_cols]
                temp_df = temp_df[feature_cols + ["Y_Label"]]

            # [메모리 최적화] 카테고리 캐스팅
            if "Code" in temp_df.columns:
                temp_df["Code"] = temp_df["Code"].astype("category")
            if "Name" in temp_df.columns:
                temp_df["Name"] = temp_df["Name"].astype("category")

            df_list.append(temp_df)
        except Exception as e:
            print(f"Error loading {f}: {e}")

    if not df_list:
        raise ValueError(f"해당 기간({start_date} ~ {end_date})에 로드된 데이터가 없습니다.")

    full_df = pd.concat(df_list, ignore_index=True)

    del df_list
    import gc

    gc.collect()

    # 만약 training용 데이터라면 sort_values 생략하여 peak 메모리 한 번 더 절감
    if not training:
        full_df = full_df.sort_values(by=["Date", "Code"]).reset_index(drop=True)

    print(f"로드 완료: {len(full_df):,}행, 컬럼 수: {len(full_df.columns)}개")
    return full_df
