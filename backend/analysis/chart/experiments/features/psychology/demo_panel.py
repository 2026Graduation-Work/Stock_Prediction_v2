"""검증·데모 전용 합성 가격 패널.

저장소에 커밋된 실제 가격 패널은 ``data/processed/005930.parquet`` 하나뿐이다.
다종목 결합·feature store 왕복·CLI 검증에는 종목이 여러 개 필요하므로, 시드를
고정한 합성 OHLCV 패널을 만든다.

여기서 나온 숫자는 **연구 결과가 아니다.** 형식·결정론·미래정보 부재를 확인하는
용도로만 쓰고, 실제 결론은 ``data/processed``를 채운 뒤 같은 스크립트를
``--price-dir``로 돌려서 얻는다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEMO_SEED = 20260817
DEMO_CODES = ("000001", "000002", "000003")


def build_demo_price_panel(
    codes: tuple[str, ...] = DEMO_CODES,
    periods: int = 180,
    start: str = "2024-01-02",
    seed: int = DEMO_SEED,
) -> pd.DataFrame:
    """시드 고정 합성 일별 OHLCV 패널을 만든다.

    종목마다 다른 추세·변동성·거래량 수준을 주어 심리 피처가 상수로 붕괴하지 않게
    한다. 같은 인자면 항상 같은 표가 나온다.
    """
    if periods < 2 or not codes:
        raise ValueError("periods는 2 이상, codes는 한 개 이상이어야 합니다.")

    dates = pd.bdate_range(start=start, periods=periods)
    frames = []
    for index, code in enumerate(codes):
        generator = np.random.default_rng(seed + index)
        drift = 0.0004 * (index - 1)
        volatility = 0.012 + 0.004 * index
        returns = generator.normal(drift, volatility, size=periods)
        close = 50_000.0 * (1.0 + 10_000.0 * index / 50_000.0) * np.exp(np.cumsum(returns))
        # 거래량은 당일 변동폭이 클수록 늘어나는 형태로 만들어 군집·처분효과 피처가
        # 의미 있는 분산을 갖게 한다.
        base_volume = 1_000_000.0 * (index + 1)
        volume = base_volume * (1.0 + 3.0 * np.abs(returns) / volatility)
        volume = np.round(volume * generator.uniform(0.8, 1.2, size=periods))
        intraday = np.abs(generator.normal(0.0, volatility / 2.0, size=periods))
        frames.append(
            pd.DataFrame(
                {
                    "Date": dates,
                    "Code": code,
                    "Open": close * (1.0 - intraday / 2.0),
                    "High": close * (1.0 + intraday),
                    "Low": close * (1.0 - intraday),
                    "Close": close,
                    "Volume": volume,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)
