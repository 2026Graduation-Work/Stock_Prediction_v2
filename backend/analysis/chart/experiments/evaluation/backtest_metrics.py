import numpy as np
import pandas as pd


def calculate_trading_metrics(daily_returns: pd.Series, trades_df: pd.DataFrame = None) -> dict:
    """
    일별 수익률 계열(daily_returns)과 체결 기록(trades_df)을 기반으로 핵심 트레이딩 성과 지표를 계산합니다.
    """
    metrics = {}

    if daily_returns.empty:
        return metrics

    # 1. 수익률 및 변동성 기반 지표
    total_ret = (1.0 + daily_returns).prod() - 1.0
    metrics["total_return"] = float(total_ret)

    # 연율화 팩터 (일별 데이터 가정)
    ann_factor = 252

    n_days = len(daily_returns)
    if n_days > 0:
        cagr = (total_ret + 1.0) ** (ann_factor / n_days) - 1.0
        metrics["cagr"] = float(cagr)
    else:
        metrics["cagr"] = np.nan

    ann_vol = daily_returns.std() * np.sqrt(ann_factor)
    metrics["annualized_volatility"] = float(ann_vol)

    # Sharpe Ratio (무위험 수익률 = 0 가정)
    if ann_vol > 0:
        metrics["sharpe_ratio"] = float((daily_returns.mean() * ann_factor) / ann_vol)
    else:
        metrics["sharpe_ratio"] = np.nan

    # Downside Volatility 및 Sortino Ratio
    downside_returns = daily_returns[daily_returns < 0]
    if not downside_returns.empty:
        downside_vol = downside_returns.std() * np.sqrt(ann_factor)
        if downside_vol > 0:
            metrics["sortino_ratio"] = float(
                (daily_returns.mean() * ann_factor) / downside_vol
            )
        else:
            metrics["sortino_ratio"] = np.nan
    else:
        metrics["sortino_ratio"] = np.nan

    # Max Drawdown (MDD)
    # Include the initial equity (1.0). Without it, a loss on day one becomes
    # the first running maximum and is incorrectly reported as zero drawdown.
    cum_returns = (1.0 + daily_returns).cumprod().to_numpy(dtype=float)
    equity = np.concatenate(([1.0], cum_returns))
    running_max = np.maximum.accumulate(equity)
    drawdowns = (equity - running_max) / running_max
    mdd = np.nanmin(drawdowns)
    metrics["max_drawdown"] = float(mdd)

    # 2. 거래 기록 기반 지표 (trades_df가 제공되었을 때)
    if trades_df is not None and not trades_df.empty:
        # trades_df가 vectorbt의 pf.trades.records_readable 형태이거나 유사한 스키마일 때
        # 보통 vectorbt records_readable 에는 'PnL', 'Return', 'Duration' 등이 들어있음
        # 컬럼 표준화
        pnl_col = "PnL" if "PnL" in trades_df.columns else "pnl"
        ret_col = "Return" if "Return" in trades_df.columns else "return"
        dur_col = "Duration" if "Duration" in trades_df.columns else "duration"

        # 컬럼이 존재하지 않는 경우를 대비한 가공
        returns_series = trades_df[ret_col] if ret_col in trades_df.columns else pd.Series()
        pnl_series = trades_df[pnl_col] if pnl_col in trades_df.columns else pd.Series()
        duration_series = trades_df[dur_col] if dur_col in trades_df.columns else pd.Series()

        n_trades = len(trades_df)
        metrics["number_of_trades"] = int(n_trades)

        if n_trades > 0:
            # 승률 (수익률 > 0인 비율)
            wins = returns_series > 0
            win_rate = wins.mean()
            metrics["win_rate"] = float(win_rate)

            # 평균 손익금
            avg_win = returns_series[wins].mean() if wins.any() else 0.0
            avg_loss = returns_series[~wins].mean() if (~wins).any() else 0.0
            metrics["average_win"] = float(avg_win)
            metrics["average_loss"] = float(avg_loss)

            # Payoff Ratio (평균 수익 / 평균 손실의 절대값)
            if abs(avg_loss) > 0:
                metrics["payoff_ratio"] = float(avg_win / abs(avg_loss))
            else:
                metrics["payoff_ratio"] = np.nan

            # Profit Factor (총 수익금 / 총 손실금의 절대값)
            total_win_val = pnl_series[pnl_series > 0].sum()
            total_loss_val = pnl_series[pnl_series < 0].sum()
            if abs(total_loss_val) > 0:
                metrics["profit_factor"] = float(total_win_val / abs(total_loss_val))
            else:
                metrics["profit_factor"] = np.nan

            # 평균 보유일수
            if not duration_series.empty:
                # vectorbt duration은 보통 timedelta 형식이나 float 일수일 수 있음
                if pd.api.types.is_timedelta64_dtype(duration_series):
                    avg_holding = duration_series.dt.total_seconds().mean() / (24 * 3600)
                else:
                    avg_holding = duration_series.mean()
                metrics["average_holding_days"] = float(avg_holding)
            else:
                metrics["average_holding_days"] = np.nan
        else:
            metrics["win_rate"] = np.nan
            metrics["average_win"] = np.nan
            metrics["average_loss"] = np.nan
            metrics["payoff_ratio"] = np.nan
            metrics["profit_factor"] = np.nan
            metrics["average_holding_days"] = np.nan
    else:
        metrics["number_of_trades"] = 0
        metrics["win_rate"] = np.nan
        metrics["average_win"] = np.nan
        metrics["average_loss"] = np.nan
        metrics["payoff_ratio"] = np.nan
        metrics["profit_factor"] = np.nan
        metrics["average_holding_days"] = np.nan

    # 회전율(Turnover) 계산 (trades_df 가 있고 자산 데이터 정보가 있을 시 추가 계산, 기본값 0.0)
    metrics["turnover"] = 0.0

    return metrics
