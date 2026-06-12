import numpy as np
import pandas as pd


def normalize_trading_halts(df: pd.DataFrame) -> pd.DataFrame:
    """
    거래정지·권리락일 처리 (표준 퀀트 관례 적용)

    1. 전체 시장 영업일 인덱스로 재구성 -> 누락일에 NaN 생성
    2. Close 0 값을 NaN으로 마킹 (0-값 행이 들어온 경우)
    3. Trading_Halt 플래그 생성 (0/누락값인 날 = 거래정지)
    4. Close -> ffill (직전 거래일 종가 유지)
    5. Open/High/Low -> 당일 Close 와 동일 (변동 없음 표시)
    6. Volume -> 0
    7. Log_Ret -> 0 (수익률 없음)
    """
    df = df.copy()

    # Date 컬럼 인덱스 정렬
    if "Date" in df.columns:
        df = df.set_index("Date")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    # 1. 전체 영업일 인덱스 생성 및 재구성 (상장~상폐 범위)
    full_idx = pd.date_range(start=df.index.min(), end=df.index.max(), freq="B")
    df = df.reindex(full_idx)
    df.index.name = "Date"

    # 2. OHLCV 0 값 -> NaN
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = df[col].replace(0.0, np.nan)

    # 3. Trading_Halt 플래그: Close가 NaN인 날 = 거래정지
    df["Trading_Halt"] = df["Close"].isna().astype(int)

    # 4. Close -> ffill (직전 거래일 종가 유지)
    df["Close"] = df["Close"].ffill()

    # 5. Open / High / Low -> 당일 Close 와 동일 (가격 변화 없음)
    for col in ["Open", "High", "Low"]:
        if col in df.columns:
            df[col] = df[col].fillna(df["Close"])

    # 6. Volume -> 0
    if "Volume" in df.columns:
        df["Volume"] = df["Volume"].fillna(0.0)

    # 7. Change / Log_Ret -> 0
    for col in ["Change", "Log_Ret"]:
        if col in df.columns:
            df[col] = df[col].fillna(0.0)

    # 메타 컬럼(Code, Name, IsDelisted) ffill
    for col in ["Code", "Name", "IsDelisted"]:
        if col in df.columns:
            df[col] = df[col].ffill()

    return df.reset_index()


def generate_full_alpha158_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    alpha158 팩터 생성 (수식 완전 벡터화 버전)
    """
    df = df.copy()

    open_p = df["Open"]
    high_p = df["High"]
    low_p = df["Low"]
    close_p = df["Close"]
    vol = df["Volume"]

    # VWAP Proxy (고가, 저가, 종가 평균)
    vwap = (high_p + low_p + close_p) / 3
    epsilon = 1e-8

    # --- 1. KBAR Features (캔들 형태) ---
    df["kmid"] = (close_p - open_p) / (open_p + epsilon)
    df["klen"] = (high_p - low_p) / (open_p + epsilon)
    df["kmid_2"] = (close_p - open_p) / (high_p - low_p + epsilon)
    df["kup"] = (high_p - np.maximum(open_p, close_p)) / (open_p + epsilon)
    df["kup_2"] = (high_p - np.maximum(open_p, close_p)) / (high_p - low_p + epsilon)
    df["klow"] = (np.minimum(open_p, close_p) - low_p) / (open_p + epsilon)
    df["klow_2"] = (np.minimum(open_p, close_p) - low_p) / (high_p - low_p + epsilon)
    df["ksft"] = (2 * close_p - high_p - low_p) / (open_p + epsilon)
    df["ksft_2"] = (2 * close_p - high_p - low_p) / (high_p - low_p + epsilon)

    # --- 2. 기본 비율 ---
    df["open_0"] = open_p / (close_p + epsilon)
    df["high_0"] = high_p / (close_p + epsilon)
    df["low_0"] = low_p / (close_p + epsilon)
    df["vwap_0"] = vwap / (close_p + epsilon)

    # 상승/하락 여부 캐싱
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

    df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
    return df


def calculate_dynamic_triple_barrier(
    df: pd.DataFrame, horizon=5, up_mult=1.5, down_mult=1.2
) -> pd.DataFrame:
    """
    동적 트리플 배리어 타겟팅 (Dynamic Triple Barrier Method)

    매수 시점의 최근 20일 로그수익률의 변동성(Sigma)에 기반하여 상/하방 배리어를 가변 설정하고,
    미래 N영업일(horizon) 동안 주가가 어디에 먼저 닿았는지 라벨(1, 0, -1)을 부여합니다.
    """
    df = df.copy()

    # 1. 일일 로그 수익률
    df["Log_Ret"] = np.log(df["Close"] / (df["Close"].shift(1) + 1e-8))
    if "Trading_Halt" in df.columns:
        df.loc[df["Trading_Halt"] == 1, "Log_Ret"] = 0.0

    # 2. 최근 20 실거래일 변동성 (거래정지일 제외)
    trading_log_ret = df["Log_Ret"].where(df.get("Trading_Halt", pd.Series(0, index=df.index)) == 0)
    df["Sigma"] = trading_log_ret.rolling(20, min_periods=10).std()

    # 3. 동적 배리어 설정
    df["Barrier_Up"] = df["Close"] * (1 + up_mult * df["Sigma"])
    df["Barrier_Down"] = df["Close"] * (1 - down_mult * df["Sigma"])

    df["Y_Label"] = 0

    hit_up_day = pd.Series(999, index=df.index)
    hit_down_day = pd.Series(999, index=df.index)
    halt_flag = df.get("Trading_Halt", pd.Series(0, index=df.index))

    # 4. 미래 horizon 영업일 추적 (거래정지일 스킵 및 horizon 연장)
    trading_day_cumsum = (1 - halt_flag).cumsum()
    max_search_days = int(horizon * 2.5)

    for d in range(1, max_search_days + 1):
        future_high = df["High"].shift(-d)
        future_close = df["Close"].shift(-d)
        future_halt = halt_flag.shift(-d).fillna(1)

        # 미래 d 시점까지 경과한 실제 거래일 수
        passed_trading_days = (trading_day_cumsum.shift(-d) - trading_day_cumsum).fillna(999)

        # 실제 거래일 기준 horizon 이내이고 거래정지가 아닌 날짜만 유효
        active = (future_halt == 0) & (passed_trading_days <= horizon)

        is_hit_up = active & (future_high >= df["Barrier_Up"])
        is_hit_down = active & (future_close <= df["Barrier_Down"])

        hit_up_day = np.where((is_hit_up) & (hit_up_day == 999), passed_trading_days, hit_up_day)
        hit_down_day = np.where(
            (is_hit_down) & (hit_down_day == 999), passed_trading_days, hit_down_day
        )

    # 5. 최종 라벨링
    success_mask = (hit_up_day != 999) & (hit_up_day < hit_down_day)
    fail_mask = (hit_down_day != 999) & (hit_down_day <= hit_up_day)

    df.loc[success_mask, "Y_Label"] = 1
    df.loc[fail_mask, "Y_Label"] = -1

    # 6. 미래 참조 누수 차단
    if len(df) > horizon:
        df.loc[df.index[-horizon:], "Y_Label"] = np.nan

    return df
