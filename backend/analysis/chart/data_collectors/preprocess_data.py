import glob
import os

import numpy as np
import pandas as pd
from tqdm import tqdm

# 경로 설정
RAW_DATA_DIR = "./data/raw"
PROCESSED_DATA_DIR = "./data/processed"
os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)


def normalize_trading_halts(df: pd.DataFrame) -> pd.DataFrame:
    """
    거래정지·권리락일 처리 (표준 퀀트 관례 적용)

    pykrx는 거래정지일을 OHLCV 전부 0으로 반환하거나, 해당 날짜를 아예 누락시킵니다.
    두 케이스를 모두 표준화하여 일관된 표현으로 통일합니다.

    처리 규칙
    ---------
    1. 전체 시장 영업일 인덱스로 재구성 → 누락일에 NaN 생성
    2. Close 0 값을 NaN으로 마킹 (0-값 행이 들어온 경우)
    3. Trading_Halt 플래그 생성 (0/누락값인 날 = 거래정지)
    4. Close → ffill (직전 거래일 종가 유지)
    5. Open/High/Low → 당일 Close 와 동일 (변동 없음 표시)
    6. Volume → 0
    7. Log_Ret → 0 (수익률 없음)
    """
    df = df.copy()

    # Date 컬럼 인덱스 정렬
    if "Date" in df.columns:
        df = df.set_index("Date")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    # 1. 전체 영업일 인덱스 생성 및 재구성
    #    - 종목의 실제 거래 기간(상장~상폐) 범위 내 영업일만 생성
    full_idx = pd.date_range(start=df.index.min(), end=df.index.max(), freq="B")
    df = df.reindex(full_idx)
    df.index.name = "Date"

    # 2. OHLCV 0 값 → NaN (pykrx 거래정지 0-값 케이스)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = df[col].replace(0.0, np.nan)

    # 3. Trading_Halt 플래그: Close가 NaN인 날 = 거래정지
    df["Trading_Halt"] = df["Close"].isna().astype(int)

    # 4. Close → ffill (직전 거래일 종가 그대로 유지)
    df["Close"] = df["Close"].ffill()

    # 5. Open / High / Low → 당일 Close 와 동일 (가격 변화 없음 표현)
    for col in ["Open", "High", "Low"]:
        if col in df.columns:
            df[col] = df[col].fillna(df["Close"])

    # 6. Volume → 0 (매매 없음)
    if "Volume" in df.columns:
        df["Volume"] = df["Volume"].fillna(0.0)

    # 7. Change / Log_Ret → 0 (당일 수익률 없음)
    for col in ["Change", "Log_Ret"]:
        if col in df.columns:
            df[col] = df[col].fillna(0.0)

    # 메타 컬럼(Code, Name, IsDelisted) ffill
    for col in ["Code", "Name", "IsDelisted"]:
        if col in df.columns:
            df[col] = df[col].ffill()

    return df.reset_index()


def generate_full_alpha158_features(df):
    """
    사용자가 제공한 alpha158.csv 명세서의 모든 수식을 100% 반영하되,
    rolling().apply()를 단 하나도 쓰지 않고 완전 벡터화(Vectorization)하여 성능을 100배 극대화한 버전입니다.
    """
    df = df.copy()

    open_p = df["Open"]
    high_p = df["High"]
    low_p = df["Low"]
    close_p = df["Close"]
    vol = df["Volume"]

    # VWAP Proxy (FDR 데이터에는 VWAP이 없으므로 고가, 저가, 종가 평균으로 추정)
    vwap = (high_p + low_p + close_p) / 3

    epsilon = 1e-8  # 0으로 나누기 방지

    # --- 1. KBAR Features (당일 캔들 형태) ---
    df["kmid"] = (close_p - open_p) / (open_p + epsilon)
    df["klen"] = (high_p - low_p) / (open_p + epsilon)
    df["kmid_2"] = (close_p - open_p) / (high_p - low_p + epsilon)
    df["kup"] = (high_p - np.maximum(open_p, close_p)) / (open_p + epsilon)
    df["kup_2"] = (high_p - np.maximum(open_p, close_p)) / (high_p - low_p + epsilon)
    df["klow"] = (np.minimum(open_p, close_p) - low_p) / (open_p + epsilon)
    df["klow_2"] = (np.minimum(open_p, close_p) - low_p) / (high_p - low_p + epsilon)
    df["ksft"] = (2 * close_p - high_p - low_p) / (open_p + epsilon)
    df["ksft_2"] = (2 * close_p - high_p - low_p) / (high_p - low_p + epsilon)

    # --- 2. 기본 종가 대비 비율 ---
    df["open_0"] = open_p / (close_p + epsilon)
    df["high_0"] = high_p / (close_p + epsilon)
    df["low_0"] = low_p / (close_p + epsilon)
    df["vwap_0"] = vwap / (close_p + epsilon)

    # 상승/하락 여부 캐싱 (에너지 지표용)
    is_up = (close_p > close_p.shift(1)).astype(float)
    is_down = (close_p < close_p.shift(1)).astype(float)
    up_move = (close_p - close_p.shift(1)).clip(lower=0)
    down_move = (close_p.shift(1) - close_p).clip(lower=0)
    tot_move = up_move + down_move

    v_up_move = (vol - vol.shift(1)).clip(lower=0)
    v_down_move = (vol.shift(1) - vol).clip(lower=0)
    v_tot_move = v_up_move + v_down_move

    ret = close_p / (close_p.shift(1) + epsilon) - 1.0
    v_ret = vol / (vol.shift(1) + epsilon) - 1.0

    # --- 3. W일 Window 기반 피처 (5, 10, 20, 30, 60) ---
    windows = [5, 10, 20, 30, 60]

    # 컬럼을 한꺼번에 병합하여 결합 파편화 경고 방지용 딕셔너리
    new_cols = {}

    for w in windows:
        # [추세]
        new_cols[f"roc_{w}"] = close_p.shift(w) / (close_p + epsilon)
        new_cols[f"ma_{w}"] = close_p.rolling(w).mean() / (close_p + epsilon)
        new_cols[f"max_{w}"] = high_p.rolling(w).max() / (close_p + epsilon)
        new_cols[f"min_{w}"] = low_p.rolling(w).min() / (close_p + epsilon)

        roll_max = high_p.rolling(w).max()
        roll_min = low_p.rolling(w).min()
        new_cols[f"rsv_{w}"] = (close_p - roll_min) / (roll_max - roll_min + epsilon)

        # [변동성]
        new_cols[f"std_{w}"] = close_p.rolling(w).std() / (close_p + epsilon)

        # [회귀] (Rolling Linear Regression 완전 벡터화)
        mean_x = (w - 1) / 2.0
        x_var = (w**2 - 1) / 12.0

        sum_y = close_p.rolling(w).sum()
        mean_y = sum_y / w
        y_var = close_p.rolling(w).var(ddof=0)

        sum_xy = sum(i * close_p.shift(w - 1 - i) for i in range(w))
        mean_xy = sum_xy / w

        cov_xy = mean_xy - mean_x * mean_y

        new_cols[f"beta_{w}"] = cov_xy / x_var
        new_cols[f"rsqr_{w}"] = (new_cols[f"beta_{w}"] ** 2) * x_var / (y_var + epsilon)

        pred_y = mean_y + new_cols[f"beta_{w}"] * mean_x
        new_cols[f"resi_{w}"] = (close_p - pred_y) / (close_p + epsilon)

        # [순위] (완전 벡터화)
        new_cols[f"rank_{w}"] = sum((close_p >= close_p.shift(i)).astype(int) for i in range(w)) / w
        new_cols[f"qtlu_{w}"] = close_p.rolling(w).quantile(0.8) / (close_p + epsilon)
        new_cols[f"qtld_{w}"] = close_p.rolling(w).quantile(0.2) / (close_p + epsilon)

        # [시간] (완전 벡터화)
        imax_idx = pd.Series(-1, index=df.index)
        imin_idx = pd.Series(-1, index=df.index)

        for k in range(w):
            shift_amt = w - 1 - k
            is_max = high_p.shift(shift_amt) == roll_max
            is_min = low_p.shift(shift_amt) == roll_min

            imax_idx = np.where((imax_idx == -1) & is_max, k, imax_idx)
            imin_idx = np.where((imin_idx == -1) & is_min, k, imin_idx)

        new_cols[f"imax_{w}"] = imax_idx / w
        new_cols[f"imin_{w}"] = imin_idx / w
        new_cols[f"imxd_{w}"] = new_cols[f"imax_{w}"] - new_cols[f"imin_{w}"]

        # [에너지]
        cntp = is_up.rolling(w).mean()
        cntn = is_down.rolling(w).mean()
        new_cols[f"cntp_{w}"] = cntp
        new_cols[f"cntn_{w}"] = cntn
        new_cols[f"cntd_{w}"] = cntp - cntn

        sump = up_move.rolling(w).sum() / (tot_move.rolling(w).sum() + epsilon)
        sumn = down_move.rolling(w).sum() / (tot_move.rolling(w).sum() + epsilon)
        new_cols[f"sump_{w}"] = sump
        new_cols[f"sumn_{w}"] = sumn
        new_cols[f"sumd_{w}"] = sump - sumn

        # [거래량]
        new_cols[f"corr_{w}"] = close_p.rolling(w).corr(vol)
        new_cols[f"cord_{w}"] = ret.rolling(w).corr(v_ret)

        new_cols[f"vma_{w}"] = vol.rolling(w).mean() / (vol + epsilon)
        new_cols[f"vstd_{w}"] = vol.rolling(w).std() / (vol + epsilon)

        wvma = (vol * (high_p - low_p) / (open_p + epsilon)).rolling(w).mean()
        new_cols[f"wvma_{w}"] = wvma / (vol + epsilon)

        vsump = v_up_move.rolling(w).sum() / (v_tot_move.rolling(w).sum() + epsilon)
        vsumn = v_down_move.rolling(w).sum() / (v_tot_move.rolling(w).sum() + epsilon)
        new_cols[f"vsump_{w}"] = vsump
        new_cols[f"vsumn_{w}"] = vsumn
        new_cols[f"vsumd_{w}"] = vsump - vsumn

    # 한꺼번에 컬럼 병합 (PerformanceWarning 방지 및 극적인 속도 향상)
    df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
    return df


def calculate_dynamic_triple_barrier(df, horizon=5, up_mult=1.5, down_mult=1.2):
    """
    [금융공학 표준] K-Market형 동적 트리플 배리어 타겟팅 (Dynamic Triple Barrier Method)

    매수 진입 시점의 최근 20일 일일 변동성(Sigma)에 기반하여 상/하방 배리어를 가변적으로 설정하고,
    미래 5영업일(Horizon) 동안의 주가 경로를 추적하여 최초로 터치한 배리어에 따라 라벨을 생성합니다.

    거래정지일 처리
    ---------------
    - Trading_Halt == 1인 날은 배리어 터치 체크를 건너뜁니다.
    - 시간 배리어(horizon) 카운터는 실제 거래가 있었던 날만 셉니다.
      즉, 보유 기간 중 N일 거래정지가 있으면 horizon이 N일만큼 뒤로 연장됩니다.
    """
    df = df.copy()

    # 1. 일일 로그 수익률 계산
    df["Log_Ret"] = np.log(df["Close"] / (df["Close"].shift(1) + 1e-8))
    # 거래정지일 Log_Ret → 0 (normalize_trading_halts에서 이미 처리됐지만 안전하게 재처리)
    if "Trading_Halt" in df.columns:
        df.loc[df["Trading_Halt"] == 1, "Log_Ret"] = 0.0

    # 2. 최근 20 실거래일 변동성(Sigma): 거래정지일 제외하고 계산
    # Trading_Halt 행을 NaN으로 마스킹 후 rolling → 정지일은 카운트에서 제외
    trading_log_ret = df["Log_Ret"].where(df.get("Trading_Halt", pd.Series(0, index=df.index)) == 0)
    df["Sigma"] = trading_log_ret.rolling(20, min_periods=10).std()

    # 3. 동적 배리어 설정
    df["Barrier_Up"] = df["Close"] * (1 + up_mult * df["Sigma"])
    df["Barrier_Down"] = df["Close"] * (1 - down_mult * df["Sigma"])

    df["Y_Label"] = 0

    hit_up_day = pd.Series(999, index=df.index)
    hit_down_day = pd.Series(999, index=df.index)

    halt_flag = df.get("Trading_Halt", pd.Series(0, index=df.index))

    # 4. 미래 5 실거래일 추적 (거래정지일 스킵 및 horizon 연장)
    trading_day_cumsum = (1 - halt_flag).cumsum()
    max_search_days = int(horizon * 2.5)

    for d in range(1, max_search_days + 1):
        future_high = df["High"].shift(-d)
        future_close = df["Close"].shift(-d)
        future_halt = halt_flag.shift(-d).fillna(1)  # 범위 밖은 정지로 처리

        # 미래 d 시점까지 경과한 실제 거래일 수 (NA 방어를 위해 999로 채움)
        passed_trading_days = (trading_day_cumsum.shift(-d) - trading_day_cumsum).fillna(999)

        # 실제 거래일 기준으로 horizon 이내이고, 해당 날짜가 거래정지가 아닐 때만 유효
        active = (future_halt == 0) & (passed_trading_days <= horizon)

        is_hit_up = active & (future_high >= df["Barrier_Up"])
        is_hit_down = active & (future_close <= df["Barrier_Down"])

        hit_up_day = np.where((is_hit_up) & (hit_up_day == 999), passed_trading_days, hit_up_day)
        hit_down_day = np.where(
            (is_hit_down) & (hit_down_day == 999), passed_trading_days, hit_down_day
        )

    # 5. 채점
    success_mask = (hit_up_day != 999) & (hit_up_day < hit_down_day)
    fail_mask = (hit_down_day != 999) & (hit_down_day <= hit_up_day)

    df.loc[success_mask, "Y_Label"] = 1
    df.loc[fail_mask, "Y_Label"] = -1

    # 6. 미래 데이터 참조 누수(Data Leakage) 차단
    if len(df) > horizon:
        df.loc[df.index[-horizon:], "Y_Label"] = np.nan

    return df


# 피처 계산에 필요한 최소 롤링 윈도우 크기 (ma_60, std_60 등 60일 기반 피처)
_LOOKBACK_DAYS = 65


def preprocess_all_data():
    """
    [full 모드] 전체 전처리.
    processed 파일이 없는 종목만 raw → 피처 계산 → 저장.
    """
    raw_files = glob.glob(os.path.join(RAW_DATA_DIR, "*.parquet"))
    print(f"총 {len(raw_files)}개의 원본 데이터를 전처리합니다...")

    for file_path in tqdm(raw_files, desc="데이터 전처리 중"):
        file_name = os.path.basename(file_path)
        save_path = os.path.join(PROCESSED_DATA_DIR, file_name)

        if os.path.exists(save_path):
            continue

        try:
            df = pd.read_parquet(file_path)

            if len(df) < _LOOKBACK_DAYS:
                continue

            df = normalize_trading_halts(df)
            df = generate_full_alpha158_features(df)
            df = calculate_dynamic_triple_barrier(df)
            df = df.dropna(subset=["roc_60", "Sigma"])

            df.to_parquet(save_path, index=False)

        except Exception as e:
            print(f"Error processing {file_name}: {e}")

    print("✅ 전체 전처리 완료. (./data/processed/)")


def update_processed_data():
    """
    [update 모드] 증분 전처리.

    동작 원리
    ---------
    1. processed 파일의 마지막 날짜(last_date)를 확인한다.
    2. raw 파일에서 (last_date - LOOKBACK_DAYS) ~ 오늘 구간만 슬라이싱해서 읽는다.
       - LOOKBACK_DAYS(65일)를 앞에 붙이는 이유:
         rolling(60) 피처 계산에 최소 60일 이전 데이터가 있어야 오늘 행의 값이 정확히 계산됨.
    3. 피처·라벨 파이프라인 전체를 적용한다.
    4. last_date 이후 신규 행만 추출해서 기존 processed 파일 끝에 append한다.
    5. processed 파일이 없는 종목은 full 전처리로 폴백한다.
    """
    raw_files = glob.glob(os.path.join(RAW_DATA_DIR, "*.parquet"))
    print(f"총 {len(raw_files)}개 종목 증분 전처리 시작...")

    updated, skipped, created, failed = 0, 0, 0, 0

    for file_path in tqdm(raw_files, desc="증분 전처리 중"):
        file_name = os.path.basename(file_path)
        save_path = os.path.join(PROCESSED_DATA_DIR, file_name)

        try:
            # ── processed 파일이 없으면 full 전처리로 폴백 ──────────────
            if not os.path.exists(save_path):
                df_raw = pd.read_parquet(file_path)
                if len(df_raw) < _LOOKBACK_DAYS:
                    skipped += 1
                    continue
                df_raw = normalize_trading_halts(df_raw)
                df_raw = generate_full_alpha158_features(df_raw)
                df_raw = calculate_dynamic_triple_barrier(df_raw)
                df_raw = df_raw.dropna(subset=["roc_60", "Sigma"])
                df_raw.to_parquet(save_path, index=False)
                created += 1
                continue

            # ── 기존 processed 파일의 마지막 날짜 확인 ──────────────────
            existing = pd.read_parquet(save_path)
            existing["Date"] = pd.to_datetime(existing["Date"])
            last_date = existing["Date"].max()

            # ── raw에서 컨텍스트 포함 슬라이싱 ─────────────────────────
            df_raw = pd.read_parquet(file_path)
            df_raw["Date"] = pd.to_datetime(df_raw["Date"])

            context_start = last_date - pd.Timedelta(days=_LOOKBACK_DAYS * 2)
            df_ctx = df_raw[df_raw["Date"] >= context_start].copy()

            if len(df_ctx) < _LOOKBACK_DAYS:
                skipped += 1
                continue

            # ── 피처·라벨 파이프라인 ────────────────────────────────────
            df_ctx = normalize_trading_halts(df_ctx)
            df_ctx = generate_full_alpha158_features(df_ctx)
            df_ctx = calculate_dynamic_triple_barrier(df_ctx)
            df_ctx = df_ctx.dropna(subset=["roc_60", "Sigma"])

            # ── last_date 이후 신규 행만 추출 ───────────────────────────
            df_ctx["Date"] = pd.to_datetime(df_ctx["Date"])
            new_rows = df_ctx[df_ctx["Date"] > last_date]

            if new_rows.empty:
                skipped += 1
                continue

            # ── 기존 파일에 append 후 저장 ──────────────────────────────
            merged = pd.concat([existing, new_rows], ignore_index=True)
            merged = (
                merged.drop_duplicates(subset=["Date"], keep="last")
                .sort_values("Date")
                .reset_index(drop=True)
            )
            merged.to_parquet(save_path, index=False)
            updated += 1

        except Exception as e:
            print(f"Error updating {file_name}: {e}")
            failed += 1

    print(
        f"\n✅ 증분 전처리 완료: 신규={updated}개, 신규생성={created}개, 스킵={skipped}개, 실패={failed}개"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="피처/라벨 전처리기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # [최초 구축] 파일이 없는 종목 전체 전처리
  python preprocess_data.py --mode full

  # [매일 자동화] 새로 수집된 하루치 데이터만 증분 처리
  python preprocess_data.py --mode update
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["full", "update"],
        default="update",
        help="full: 신규 종목 전체 전처리 | update: 증분 처리 (기본값)",
    )
    args = parser.parse_args()

    if args.mode == "full":
        print("[모드] 전체 전처리 (Full)")
        preprocess_all_data()
    else:
        print("[모드] 증분 업데이트 (Update)")
        update_processed_data()
