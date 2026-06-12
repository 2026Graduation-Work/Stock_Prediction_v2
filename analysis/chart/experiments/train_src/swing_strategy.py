import pandas as pd
import numpy as np

class SwingStrategy:
    """
    모델의 예측 확률(Prob)과 가격/변동성(Sigma) 데이터를 받아 
    최종 트레이딩 진입(Entries) 및 비중(Weights) 시그널 매트릭스를 생성합니다.
    (기존 05_backtest.py의 시그널 생성 및 리스크 패리티 로직 통합)
    """
    def __init__(self, config: dict):
        self.strat_cfg = config.get('strategy', {})
        self.prob_threshold = self.strat_cfg.get('prob_threshold', 0.75)
        self.top_n = self.strat_cfg.get('top_n', 5)
        
    def generate_signals(self, predictions: pd.DataFrame, price_df: pd.DataFrame) -> tuple:
        """
        predictions: ['Date', 'Code', 'Prob'] 데이터프레임
        price_df: ['Date', 'Code', 'Open', 'Sigma', 'Trading_Halt'] 데이터프레임
        
        Returns:
            entries: 매수 진입 시그널 (2D Matrix: Date x Code)
            weights: 진입 비중 매트릭스 (2D Matrix) - 리스크 패리티 적용
        """
        print(f"[Strategy] 시그널 생성 중... (Threshold: {self.prob_threshold}, Top-N: {self.top_n})")
        
        # 1. 시그널과 가격 데이터 병합
        df = pd.merge(predictions, price_df, on=['Date', 'Code'], how='inner')
        
        # 2D 매트릭스로 피벗 (VectorBT가 요구하는 포맷)
        open_price    = df.pivot(index='Date', columns='Code', values='Open').ffill().bfill()
        trading_halt  = df.pivot(index='Date', columns='Code', values='Trading_Halt').fillna(0)
        prob          = df.pivot(index='Date', columns='Code', values='Prob').fillna(0.0)
        sigma         = df.pivot(index='Date', columns='Code', values='Sigma').fillna(0.01)
        
        # 3. 매수 진입 유효성 검사 (확률 컷 통과 + 거래정지 아님 + 상장됨)
        valid_mask = (
            (prob >= self.prob_threshold) &
            (open_price > 1.0) &
            (trading_halt == 0)
        )
        
        # 4. Top N 랭킹 (행 단위로 매일 가장 유망한 종목 선별)
        rankings = prob.where(valid_mask).rank(axis=1, method='first', ascending=False)
        raw_entries = rankings <= self.top_n
        
        # 5. 동일 비중 (Equal Weight) 할당
        # 매일 선택된 최대 N개의 종목에 대해 각각 1/N 만큼의 동일한 비중을 할당
        equal_weight = 1.0 / self.top_n
        weights = pd.DataFrame(np.where(raw_entries, equal_weight, 0.0), index=prob.index, columns=prob.columns)
        
        # 6. 미래 참조(Look-ahead bias) 원천 차단
        # T일 모델 예측을 바탕으로 -> 실제 매수는 T+1일 Open 가격에 진입
        entries = raw_entries.shift(1).fillna(False)
        weights = weights.shift(1).fillna(0.0)
        
        # T+1일이 거래정지일이면 진입 차단 (shift 후에도 방어해야 함)
        halt_next = trading_halt.shift(1).fillna(0)
        entries = entries & (halt_next == 0)
        
        # 7. 강제 리밸런싱 및 수수료 폭탄 방지
        # VectorBT는 빈칸이 아니면 매일 비중을 조절하려 하므로, 매수 진입일 외에는 NaN으로 둠
        weights = weights.where(entries, np.nan)
        
        return entries, weights
