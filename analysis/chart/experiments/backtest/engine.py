import os
import pandas as pd
import numpy as np
import vectorbt as vbt


def compute_custom_krx_composite(index: pd.DatetimeIndex) -> pd.Series:
    """
    커스텀 KRX 통합 지수 (Custom KRX Composite Index) 산출 함수
    
    KOSPI(^KS11)와 KOSDAQ(^KQ11)의 일별 수익률을 각 시장의
    연간 평균 유동 시가총액 비중으로 가중 평균하여 통합 지수를 구성합니다.
    """
    ANNUAL_WEIGHTS = {
        2016: (0.84, 0.16),
        2017: (0.84, 0.16),
        2018: (0.83, 0.17),
        2019: (0.83, 0.17),
        2020: (0.80, 0.20),
        2021: (0.78, 0.22),
        2022: (0.80, 0.20),
        2023: (0.82, 0.18),
        2024: (0.83, 0.17),
        2025: (0.83, 0.17),
    }
    DEFAULT_WEIGHT = (0.82, 0.18)
    
    try:
        import yfinance as yf
        yf_start = (index[0]  - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        yf_end   = (index[-1] + pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        
        print("[*] 커스텀 KRX 통합 지수 산출: KOSPI(^KS11) + KOSDAQ(^KQ11) 다운로드 중...")
        raw = yf.download(["^KS11", "^KQ11"], start=yf_start, end=yf_end,
                          progress=False, auto_adjust=True)
        
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"].copy()
        else:
            close = raw.copy()
        
        close.index = pd.to_datetime(close.index).tz_localize(None)
        
        ks_ret  = close["^KS11"].pct_change()
        kq_ret  = close["^KQ11"].pct_change()
        
        composite_returns = []
        for date in index:
            year = date.year
            w_ks, w_kq = ANNUAL_WEIGHTS.get(year, DEFAULT_WEIGHT)
            
            r_ks = ks_ret.get(date, 0.0) if date in ks_ret.index else 0.0
            r_kq = kq_ret.get(date, 0.0) if date in kq_ret.index else 0.0
            
            r_ks = 0.0 if pd.isna(r_ks) else float(r_ks)
            r_kq = 0.0 if pd.isna(r_kq) else float(r_kq)
            
            composite_returns.append(w_ks * r_ks + w_kq * r_kq)
        
        result = pd.Series(composite_returns, index=index, name='Benchmark_Custom_KRX')
        print(f"✅ 커스텀 KRX 통합 지수 산출 완료 (기간: {index[0].date()} ~ {index[-1].date()})")
        return result
        
    except Exception as e:
        print(f"⚠️ 커스텀 KRX 통합 지수 산출 실패 ({e}) - 빈 시리즈 반환")
        return pd.Series(0.0, index=index, name='Benchmark_Custom_KRX')
 

def calculate_soft_exits(entry_series, open_series, close_series, sigma_series, halt_series, holding_days, down_mult):
    """ Soft Stop 및 보유 기간 만기 청산 로직 (거래정지일 완벽 지원) """
    n = len(entry_series)
    soft_exits = pd.Series(False, index=entry_series.index)
    if halt_series is None:
        halt_series = pd.Series(0, index=entry_series.index)

    in_position = False
    entry_price = 0.0
    entry_sigma = 0.0
    trading_days_held = 0

    for i in range(n):
        is_halt = bool(halt_series.iloc[i])
        if in_position:
            if is_halt:
                continue
                
            trading_days_held += 1
            
            soft_stop_line = entry_price * (1.0 - down_mult * entry_sigma)
            if close_series.iloc[i] < soft_stop_line:
                if i + 1 < n:
                    soft_exits.iloc[i + 1] = True
                in_position = False
                trading_days_held = 0
                continue
                
            if trading_days_held >= holding_days:
                soft_exits.iloc[i] = True
                in_position = False
                trading_days_held = 0
                continue

        if entry_series.iloc[i] and not in_position and not is_halt:
            in_position = True
            entry_price = open_series.iloc[i]
            entry_sigma = sigma_series.iloc[i]
            trading_days_held = 0

    return soft_exits


class VectorBTEngine:
    """ VectorBT 기반의 고속 포트폴리오 백테스트 엔진 """
    def __init__(self, config: dict):
        self.config = config
        self.bt_cfg = config.get('backtest', {})
        self.init_cash = self.bt_cfg.get('initial_cash', 10000000)
        self.fee = self.bt_cfg.get('fee', 0.0025)
        self.up_mult = self.bt_cfg.get('up_mult', 3.5)
        self.down_mult = self.bt_cfg.get('down_mult', 2.0)
        self.hard_sl_mult = self.bt_cfg.get('hard_sl_mult', 2.5)
        self.holding_days = config.get('labels', {}).get('horizon', 5)
        
    def run(self, entries: pd.DataFrame, weights: pd.DataFrame, price_df: pd.DataFrame):
        print(f"[Backtest] 시뮬레이션 가동 (초기자금: {self.init_cash:,}원, 수수료: {self.fee*100}%)")
        
        price_df = price_df[price_df['Date'].isin(entries.index) & price_df['Code'].isin(entries.columns)]
        
        open_price    = price_df.pivot(index='Date', columns='Code', values='Open').ffill().bfill()
        high_price    = price_df.pivot(index='Date', columns='Code', values='High').ffill().bfill()
        low_price     = price_df.pivot(index='Date', columns='Code', values='Low').ffill().bfill()
        close_price   = price_df.pivot(index='Date', columns='Code', values='Close').ffill().bfill()
        trading_halt  = price_df.pivot(index='Date', columns='Code', values='Trading_Halt').fillna(0)
        sigma         = price_df.pivot(index='Date', columns='Code', values='Sigma').fillna(0.01)
        
        tp_stop = self.up_mult * sigma
        sl_stop = self.hard_sl_mult * sigma
        
        print("[Backtest] Soft Stop 및 시간 만기(Horizon) 시그널 계산 중...")
        soft_exits_dict = {}
        for col in entries.columns:
            soft_exits_dict[col] = calculate_soft_exits(
                entry_series   = entries[col],
                open_series    = open_price[col],
                close_series   = close_price[col],
                sigma_series   = sigma[col],
                halt_series    = trading_halt[col],
                holding_days   = self.holding_days,
                down_mult      = self.down_mult
            )
        exits = pd.DataFrame(soft_exits_dict, index=entries.index)
        
        print("[Backtest] 포트폴리오 성과 집계 중...")
        pf = vbt.Portfolio.from_signals(
            close=open_price,
            high=high_price,
            low=low_price,
            entries=entries,
            exits=exits,
            tp_stop=tp_stop,
            sl_stop=sl_stop,
            size=weights,
            size_type='percent',
            fees=self.fee,           
            init_cash=self.init_cash, 
            freq='D',
            group_by=True,
            cash_sharing=True
        )
        
        stats = pf.stats()
        print("\n" + "="*60)
        print("★ [VectorBT 퀀트 백테스트 결과 리포트] ★")
        print("="*60)
        print(stats)
        print("="*60)
        
        # 결과 저장 폴더 설정 (experiments/results 기준)
        exp_name = self.config.get('experiment_name', 'default_exp')
        current_dir = os.path.dirname(os.path.abspath(__file__))
        result_dir = os.path.abspath(os.path.join(current_dir, "..", "results", exp_name))
        os.makedirs(result_dir, exist_ok=True)
        
        try:
            trades_df = pf.trades.records_readable
            trades_df.to_csv(os.path.join(result_dir, "trades.csv"), index=False)
            
            daily_returns = pf.returns()
            ew_benchmark = pf.benchmark_returns()
            custom_krx_benchmark = compute_custom_krx_composite(open_price.index)
                
            returns_df = pd.DataFrame({
                'Portfolio':          daily_returns,
                'Benchmark_EW':       ew_benchmark,
                'Benchmark_CustomKRX': custom_krx_benchmark,
            })
            returns_df.to_csv(os.path.join(result_dir, "daily_returns.csv"), header=True)
            print("✅ 일일 수익률 CSV 저장 완료")
        except Exception as e:
            print(f"⚠️ CSV 저장 실패: {e}")
            ew_benchmark = pd.Series(dtype=float)
            
        try:
            html_path = os.path.join(result_dir, "equity_curve.html")
            pf.plot().write_html(html_path)
            print(f"✅ 인터랙티브 수익률 차트 저장 완료: {html_path}")
        except Exception as e:
            pass
            
        try:
            import quantstats as qs
            qs_report_path = os.path.join(result_dir, "quantstats_report.html")
            qs.reports.html(
                daily_returns,
                ew_benchmark,
                output=qs_report_path,
                title=f"QuantStats Report - {exp_name} (vs Universe EW B&H)"
            )
            qs_krx_path = os.path.join(result_dir, "quantstats_report_krx.html")
            qs.reports.html(
                daily_returns,
                custom_krx_benchmark,
                output=qs_krx_path,
                title=f"QuantStats Report - {exp_name} (vs Custom KRX Composite)"
            )
            print(f"✅ QuantStats 성과 보고서 저장 완료: {qs_report_path}")
        except Exception as e:
            print(f"⚠️ QuantStats 보고서 저장 실패: {e}")
            
        return pf
