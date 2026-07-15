import numpy as np
import pandas as pd


def generate_random_top_k_signals(
    price_df: pd.DataFrame, top_n: int, seed: int = 42
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    동일 유니버스에서 매일 무작위로 top_n 종목을 선택하는 시그널 및 비중을 생성합니다. (T+1일 진입 반영)
    """
    open_price = price_df.pivot(index="Date", columns="Code", values="Open").ffill().bfill()
    trading_halt = price_df.pivot(index="Date", columns="Code", values="Trading_Halt").fillna(0)

    # 유효 종목 마스크 (가격이 존재하고 거래정지가 아님)
    valid_mask = (open_price > 1.0) & (trading_halt == 0)

    # 무작위 난수 매트릭스 생성
    np.random.seed(seed)
    random_scores = pd.DataFrame(
        np.random.rand(*open_price.shape),
        index=open_price.index,
        columns=open_price.columns,
    )

    # 유효한 종목만 점수 부여 후 랭킹
    random_scores = random_scores.where(valid_mask)
    rankings = random_scores.rank(axis=1, method="first", ascending=False)
    raw_entries = rankings <= top_n

    # 비중 설정 (Equal Weight)
    equal_weight = 1.0 / top_n
    weights = pd.DataFrame(
        np.where(raw_entries, equal_weight, 0.0),
        index=open_price.index,
        columns=open_price.columns,
    )

    # T일 시그널 -> T+1일 진입
    entries = raw_entries.shift(1).fillna(False)
    weights = weights.shift(1).fillna(0.0)

    # 진입일 거래정지 차단
    entries = entries & (trading_halt == 0)
    weights = weights.where(entries, np.nan)

    return entries, weights


def generate_momentum_signals(
    price_df: pd.DataFrame, top_n: int, horizon: int = 5
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    5일 단기 모멘텀 (close[t] / close[t-5] - 1) 상위 top_n 종목 진입 시그널을 생성합니다.
    """
    open_price = price_df.pivot(index="Date", columns="Code", values="Open").ffill().bfill()
    close_price = price_df.pivot(index="Date", columns="Code", values="Close").ffill().bfill()
    trading_halt = price_df.pivot(index="Date", columns="Code", values="Trading_Halt").fillna(0)

    # 5일 모멘텀 점수 계산
    momentum_score = close_price.pct_change(periods=horizon)

    valid_mask = (open_price > 1.0) & (trading_halt == 0)
    momentum_score = momentum_score.where(valid_mask)

    # 상위 top_n 랭킹
    rankings = momentum_score.rank(axis=1, method="first", ascending=False)
    raw_entries = rankings <= top_n

    # 비중 설정 (Equal Weight)
    equal_weight = 1.0 / top_n
    weights = pd.DataFrame(
        np.where(raw_entries, equal_weight, 0.0),
        index=open_price.index,
        columns=open_price.columns,
    )

    # T일 시그널 -> T+1일 진입
    entries = raw_entries.shift(1).fillna(False)
    weights = weights.shift(1).fillna(0.0)

    # 진입일 거래정지 차단
    entries = entries & (trading_halt == 0)
    weights = weights.where(entries, np.nan)

    return entries, weights


def generate_ma_breakout_signals(
    price_df: pd.DataFrame, top_n: int, window: int = 20
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    20일 이동평균선 돌파 종목 중 이격도 상위 top_n 종목 진입 시그널을 생성합니다.
    """
    open_price = price_df.pivot(index="Date", columns="Code", values="Open").ffill().bfill()
    close_price = price_df.pivot(index="Date", columns="Code", values="Close").ffill().bfill()
    trading_halt = price_df.pivot(index="Date", columns="Code", values="Trading_Halt").fillna(0)

    # 20일 이평선 및 이격도 계산
    ma = close_price.rolling(window=window).mean()
    breakout_mask = close_price > ma
    spread = close_price / ma - 1.0

    valid_mask = (open_price > 1.0) & (trading_halt == 0) & breakout_mask
    spread = spread.where(valid_mask)

    # 상위 top_n 랭킹
    rankings = spread.rank(axis=1, method="first", ascending=False)
    raw_entries = rankings <= top_n

    # 비중 설정 (Equal Weight)
    equal_weight = 1.0 / top_n
    weights = pd.DataFrame(
        np.where(raw_entries, equal_weight, 0.0),
        index=open_price.index,
        columns=open_price.columns,
    )

    # T일 시그널 -> T+1일 진입
    entries = raw_entries.shift(1).fillna(False)
    weights = weights.shift(1).fillna(0.0)

    # 진입일 거래정지 차단
    entries = entries & (trading_halt == 0)
    weights = weights.where(entries, np.nan)

    return entries, weights
