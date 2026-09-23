"""데모 4종목·시장 지수 실데이터 스냅샷: FinanceDataReader → frontend/lib/providers/demo-snapshot.json

기준일 2025-12-30(2025년 마지막 거래일). 감성 코퍼스 기간(2025-10-29~12-31)과 맞춘다.
받은 원자료는 저장하지 않고, 화면에 필요한 열만 출처·기준일과 함께 JSON으로 남긴다.

원천 (FinanceDataReader 0.9.x 코드에서 확인):
  - 종목 일봉: 네이버 금융 차트 API (fdr.DataReader('005930') → NaverDailyReader).
    네이버 값은 **수정주가**다. 조회일까지의 배당·권리락이 과거 가격에 소급 반영되므로
    (예: 셀트리온 주식배당) 호가 단위에 맞지 않는 종가가 나올 수 있다. KRX 원시 종가(KRX:코드)는
    인증이 필요해 쓰지 않았다.
  - 지수(KS11·KQ11·KS200): KRX 지수 데이터를 FDR이 GitHub에 캐시한 파일
    (fdr.DataReader('KS11') → KrxIndexReaderCache, FinanceData/fdr_krx_data_cache)

시장 분위기 점수 산식 (결정론, 튜닝 없음):
  - 변동성 = KOSPI 20거래일 실현변동성(일간 로그수익률 표준편차 × √252)의
            기준일 값이 직전 252거래일(약 1년) 같은 값들 중 몇 번째 백분위인지
  - 거래량 = KOSPI 20거래일 평균 거래대금의 같은 방식 백분위
  - 화면 구간 말: 백분위 < 1/3 낮음, < 2/3 보통, 그 이상 높음
  - 시장 상태(condition): 변동성 백분위 < 0.6 stable, < 0.9 caution, 그 이상 high_volatility

투자자별 순매수(누가 사고팔았나): 네이버 금융 종목 투자자별 매매동향(m.stock.naver.com
  /api/stock/{code}/trend). 기준일까지 최근 20영업일, 개인·외국인·기관 순매수 **수량(주)**.
  기타법인과 금액(원)은 이 경로에 없어 비워 둔다. pykrx(KRX)는 로그인이 필요해 쓰지 않았다.

가격 흐름으로 본 분위기: backend psychology_market_v1의 요약축 psych_greed_fear_axis
  = (psych_fear_greed + psych_disposition) / 2, 범위 -1~+1. 기준일까지의 종가·거래량만 쓴다.
  구간 말: ≥0.5 많이 들뜸, ≥0.2 조금 들뜸, >-0.2 차분함, >-0.5 조금 움츠러듦, 그 외 많이 움츠러듦.

실행 (저장소 루트):
    pip install finance-datareader pandas numpy requests
    python frontend/scripts/build_demo_snapshot.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FinanceDataReader as fdr
import requests
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/analysis/chart/experiments/features"))
from psychology.market_psychology import build_psychology_features  # noqa: E402

AS_OF = "2025-12-30"
STOCKS = {"005930": "삼성전자", "005380": "현대차", "035720": "카카오", "068270": "셀트리온"}
INDICES = {"KS11": ("KOSPI", "KOSPI"), "KQ11": ("KOSDAQ", "KOSDAQ"), "KS200": ("KOSPI200", "KOSPI 200")}
PRICE_DAYS = 60  # 상세 화면 주가 흐름
WINDOW = 20
LOOKBACK = 252
OUT = ROOT / "frontend/lib/providers/demo-snapshot.json"

STOCK_SOURCE = "네이버 금융 수정주가(FinanceDataReader)"
SUPPLY_SOURCE = "네이버 금융 투자자별 매매동향"
SUPPLY_DAYS = 20
INDEX_SOURCE = "KRX(FinanceDataReader 캐시)"


def percentile_of_last(series: pd.Series, lookback: int = LOOKBACK) -> float:
    """기준일 값이 직전 lookback개 값 중 어디쯤인지(0~1). 같은 값은 절반으로 센다."""
    values = series.dropna()
    current, history = values.iloc[-1], values.iloc[-lookback - 1 : -1]
    if len(history) < lookback:
        raise ValueError(f"백분위 계산에 필요한 과거 값이 부족합니다: {len(history)} < {lookback}")
    below = (history < current).sum() + 0.5 * (history == current).sum()
    return round(float(below / len(history)), 4)


def level_word(percentile: float) -> str:
    return "낮음" if percentile < 1 / 3 else "보통" if percentile < 2 / 3 else "높음"


def mood_word(axis: float) -> str:
    if axis >= 0.5:
        return "많이 들뜸"
    if axis >= 0.2:
        return "조금 들뜸"
    if axis > -0.2:
        return "차분함"
    if axis > -0.5:
        return "조금 움츠러듦"
    return "많이 움츠러듦"


def market_snapshot() -> dict:
    quotes = []
    for symbol, (key, label) in INDICES.items():
        frame = fdr.DataReader(symbol, "2025-12-01", AS_OF)
        last, prev = frame["Close"].iloc[-1], frame["Close"].iloc[-2]
        assert frame.index[-1].strftime("%Y-%m-%d") == AS_OF, symbol
        quotes.append(
            {
                "symbol": key,
                "label": label,
                "value": round(float(last), 2),
                "change": round(float(last - prev), 2),
                "changePercent": round(float((last / prev - 1) * 100), 2),
            }
        )

    kospi = fdr.DataReader("KS11", "2023-06-01", AS_OF)
    assert kospi.index[-1].strftime("%Y-%m-%d") == AS_OF
    log_return = np.log(kospi["Close"] / kospi["Close"].shift(1))
    realized = log_return.rolling(WINDOW).std(ddof=1) * np.sqrt(252)
    amount = kospi["Amount"].rolling(WINDOW).mean()
    volatility_pct = percentile_of_last(realized)
    volume_pct = percentile_of_last(amount)
    condition = (
        "stable" if volatility_pct < 0.6 else "caution" if volatility_pct < 0.9 else "high_volatility"
    )
    return {
        "date": AS_OF,
        "source": INDEX_SOURCE,
        "condition": condition,
        "volatility": {
            "percentile": volatility_pct,
            "word": level_word(volatility_pct),
            "value": round(float(realized.iloc[-1]), 4),  # 연환산 실현변동성
        },
        "volume": {
            "percentile": volume_pct,
            "word": level_word(volume_pct),
            "value": int(amount.iloc[-1]),  # 20거래일 평균 거래대금(원)
        },
        "indexQuotes": quotes,
    }


def stock_snapshot() -> dict:
    frames = []
    result = {}
    for code, name in STOCKS.items():
        frame = fdr.DataReader(code, "2024-10-01", AS_OF)
        assert frame.index[-1].strftime("%Y-%m-%d") == AS_OF, code
        close = frame["Close"]
        result[code] = {
            "name": name,
            "close": int(close.iloc[-1]),
            "changePercent": round(float((close.iloc[-1] / close.iloc[-2] - 1) * 100), 2),
            "prices": [
                {"date": date.strftime("%Y-%m-%d"), "close": int(value)}
                for date, value in close.iloc[-PRICE_DAYS:].items()
            ],
        }
        frames.append(
            pd.DataFrame({"Date": frame.index, "Code": code, "Close": close.values, "Volume": frame["Volume"].values})
        )

    features, _meta = build_psychology_features(pd.concat(frames, ignore_index=True))
    for code in STOCKS:
        row = features[(features["Code"] == code) & (features["Date"] == pd.Timestamp(AS_OF))]
        if row.empty:
            raise ValueError(f"{code} 기준일 심리 피처가 없습니다(워밍업 부족).")
        axis = float(row["psych_greed_fear_axis"].iloc[0])
        result[code]["psychology"] = {"axis": round(axis, 4), "word": mood_word(axis)}
    return result


def _quantity(text: str) -> int:
    return int(text.replace(",", "").replace("+", ""))


def supply_snapshot() -> dict:
    """종목별 최근 20영업일 개인·외국인·기관 순매수 수량(주). 날짜 오름차순."""
    next_day = (pd.Timestamp(AS_OF) + pd.Timedelta(days=1)).strftime("%Y%m%d")  # bizdate는 그날을 빼고 앞으로 준다
    result = {}
    for code in STOCKS:
        response = requests.get(
            f"https://m.stock.naver.com/api/stock/{code}/trend",
            params={"pageSize": SUPPLY_DAYS, "bizdate": next_day},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        response.raise_for_status()
        rows = sorted(response.json(), key=lambda row: row["bizdate"])
        days = [
            {
                "date": f"{row['bizdate'][:4]}-{row['bizdate'][4:6]}-{row['bizdate'][6:]}",
                "retail": _quantity(row["individualPureBuyQuant"]),
                "foreign": _quantity(row["foreignerPureBuyQuant"]),
                "institution": _quantity(row["organPureBuyQuant"]),
            }
            for row in rows
        ]
        assert len(days) == SUPPLY_DAYS and days[-1]["date"] == AS_OF, (code, days[-1:])
        result[code] = days
    return {"source": SUPPLY_SOURCE, "unit": "주", "stocks": result}


def main() -> None:
    snapshot = {
        "$comment": "frontend/scripts/build_demo_snapshot.py가 만든 파일. 손으로 고치지 않는다.",
        "asOf": AS_OF,
        "stockSource": STOCK_SOURCE,
        "market": market_snapshot(),
        "stocks": stock_snapshot(),
        "supply": supply_snapshot(),
    }
    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(json.dumps(snapshot["market"], ensure_ascii=False))
    for code, stock in snapshot["stocks"].items():
        print(code, stock["name"], stock["close"], stock["changePercent"], stock["psychology"])


if __name__ == "__main__":
    main()
