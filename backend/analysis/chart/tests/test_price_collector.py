import json
from datetime import date

import pandas as pd
import pytest
from data_collectors import price_collector, trading_calendar


def _investor_flows(index):
    return pd.DataFrame(
        {
            "InstitutionBuyAmount": [300.0] * len(index),
            "InstitutionSellAmount": [200.0] * len(index),
            "InstitutionNetBuyAmount": [100.0] * len(index),
            "IndividualBuyAmount": [400.0] * len(index),
            "IndividualSellAmount": [500.0] * len(index),
            "IndividualNetBuyAmount": [-100.0] * len(index),
            "ForeignBuyAmount": [200.0] * len(index),
            "ForeignSellAmount": [200.0] * len(index),
            "ForeignNetBuyAmount": [0.0] * len(index),
        },
        index=index,
    )


def _write_calendar_cache(path, start, end, trading_days):
    path.write_text(
        json.dumps(
            {
                "source": trading_calendar._TRADING_CALENDAR_SOURCE,
                "coverage_start": start,
                "coverage_end": end,
                "fetched_at": "2026-09-02T18:00:00+09:00",
                "trading_days": trading_days,
            }
        ),
        encoding="utf-8",
    )


def test_get_krx_trading_days_uses_kospi_index_and_saves_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "krx_trading_calendar.json"
    monkeypatch.setattr(trading_calendar, "TRADING_CALENDAR_CACHE_PATH", str(cache_path))

    calls = []

    def fake_index_ohlcv(start, end):
        calls.append((start, end))
        return pd.DataFrame(
            {"종가": [2600.0, 2610.0]},
            index=pd.to_datetime(["2026-08-31", "2026-09-01"]),
        )

    monkeypatch.setattr(trading_calendar, "_fetch_fdr_index", fake_index_ohlcv)

    result = trading_calendar.get_krx_trading_days("2026-08-29", "2026-09-01")

    assert result == {date(2026, 8, 31), date(2026, 9, 1)}
    assert calls == [(pd.Timestamp("2026-08-29"), pd.Timestamp("2026-09-01"))]
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["coverage_start"] == "2026-08-29"
    assert payload["coverage_end"] == "2026-09-01"
    assert payload["provider"] == "FinanceDataReader KS11"
    assert payload["trading_days"] == ["2026-08-31", "2026-09-01"]


def test_get_krx_trading_days_falls_back_to_pykrx_index(tmp_path, monkeypatch):
    cache_path = tmp_path / "krx_trading_calendar.json"
    monkeypatch.setattr(trading_calendar, "TRADING_CALENDAR_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(
        trading_calendar,
        "_fetch_fdr_index",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("FDR unavailable")),
    )
    monkeypatch.setattr(
        trading_calendar,
        "_fetch_pykrx_index",
        lambda *args, **kwargs: pd.DataFrame(
            {"종가": [2600.0]}, index=pd.to_datetime(["2026-09-01"])
        ),
    )

    result = trading_calendar.get_krx_trading_days("2026-08-31", "2026-09-01")

    assert result == {date(2026, 9, 1)}
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["provider"] == "KRX KOSPI index 1001 via pykrx"


def test_get_krx_trading_days_uses_only_cache_covering_entire_range(
    tmp_path, monkeypatch
):
    cache_path = tmp_path / "krx_trading_calendar.json"
    _write_calendar_cache(
        cache_path,
        "2026-08-29",
        "2026-09-02",
        ["2026-08-31", "2026-09-01", "2026-09-02"],
    )
    monkeypatch.setattr(trading_calendar, "TRADING_CALENDAR_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(
        trading_calendar,
        "_fetch_fdr_index",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("FDR unavailable")),
    )
    monkeypatch.setattr(
        trading_calendar,
        "_fetch_pykrx_index",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("KRX unavailable")),
    )

    result = trading_calendar.get_krx_trading_days("2026-08-30", "2026-09-01")

    assert result == {date(2026, 8, 31), date(2026, 9, 1)}


def test_get_krx_trading_days_fails_closed_for_incomplete_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "krx_trading_calendar.json"
    _write_calendar_cache(cache_path, "2026-09-01", "2026-09-02", ["2026-09-01"])
    monkeypatch.setattr(trading_calendar, "TRADING_CALENDAR_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(
        trading_calendar,
        "_fetch_fdr_index",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("FDR unavailable")),
    )
    monkeypatch.setattr(
        trading_calendar,
        "_fetch_pykrx_index",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("KRX unavailable")),
    )

    with pytest.raises(trading_calendar.TradingCalendarError, match="캐시도 없습니다"):
        trading_calendar.get_krx_trading_days("2026-08-01", "2026-09-02")


def test_successful_refresh_replaces_overlap_and_preserves_outer_cache(
    tmp_path, monkeypatch
):
    cache_path = tmp_path / "krx_trading_calendar.json"
    _write_calendar_cache(
        cache_path,
        "2026-08-29",
        "2026-09-02",
        ["2026-08-31", "2026-09-01", "2026-09-02"],
    )
    monkeypatch.setattr(trading_calendar, "TRADING_CALENDAR_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(
        trading_calendar,
        "_fetch_fdr_index",
        lambda *args, **kwargs: pd.DataFrame(
            {"종가": [2610.0, 2620.0]},
            index=pd.to_datetime(["2026-09-01", "2026-09-03"]),
        ),
    )

    trading_calendar.get_krx_trading_days("2026-09-01", "2026-09-03")

    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["coverage_start"] == "2026-08-29"
    assert payload["coverage_end"] == "2026-09-03"
    assert payload["trading_days"] == ["2026-08-31", "2026-09-01", "2026-09-03"]


def test_daily_bulk_update_uses_exact_krx_snapshot_date(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    monkeypatch.setattr(price_collector, "DATA_DIR", str(raw_dir))
    monkeypatch.setattr(
        price_collector,
        "get_krx_trading_days",
        lambda start, end: {date(2026, 8, 31), date(2026, 9, 1)},
    )

    listing_calls = []

    def fake_stock_listing(market):
        listing_calls.append(market)
        return pd.DataFrame(
            {
                "Code": ["005930"] if market == "KOSPI" else [],
                "Open": [70000] if market == "KOSPI" else [],
                "High": [71000] if market == "KOSPI" else [],
                "Low": [69000] if market == "KOSPI" else [],
                "Close": [70500] if market == "KOSPI" else [],
                "Volume": [1000] if market == "KOSPI" else [],
                "Amount": [70400000] if market == "KOSPI" else [],
                "ChagesRatio": [0.5] if market == "KOSPI" else [],
            }
        )

    monkeypatch.setattr(price_collector.fdr, "StockListing", fake_stock_listing)
    monkeypatch.setattr(
        price_collector,
        "_fetch_daily_investor_snapshot",
        lambda trading_date: _investor_flows(pd.Index(["005930"], name="Code")),
    )
    stocks = pd.DataFrame(
        [{"Code": "005930", "Name": "삼성전자", "IsDelisted": False}]
    )

    updated = price_collector._update_ohlcv_bulk_fdr(stocks)

    assert updated == {"005930"}
    assert listing_calls == ["KOSPI", "KOSDAQ"]
    stored = pd.read_parquet(raw_dir / "005930.parquet")
    assert stored.loc[0, "Date"] == pd.Timestamp("2026-09-01")
    assert stored.loc[0, "Close"] == 70500
    assert stored.loc[0, "VWAP"] == 70400
    assert stored.loc[0, "Amount"] == 70400000
    assert stored.loc[0, "InstitutionNetBuyAmount"] == 100


def test_attach_actual_vwap_matches_adjusted_price_scale():
    dates = pd.to_datetime(["2018-04-27", "2018-05-04"])
    adjusted = pd.DataFrame(
        {
            "Open": [50.0, 52.0],
            "High": [52.0, 55.0],
            "Low": [49.0, 51.0],
            "Close": [50.0, 54.0],
            "Volume": [100.0, 200.0],
            "Change": [0.0, 8.0],
        },
        index=dates,
    )
    raw = pd.DataFrame(
        {
            "종가": [5000.0, 5400.0],
            "거래량": [100.0, 200.0],
            "거래대금": [510000.0, 1060000.0],
        },
        index=dates,
    )

    result = price_collector._attach_actual_vwap(adjusted, raw)

    assert result["AdjustmentFactor"].tolist() == pytest.approx([0.01, 0.01])
    assert result["VWAP"].tolist() == pytest.approx([51.0, 53.0])
    assert result["RawClose"].tolist() == [5000.0, 5400.0]
    assert result["RawVolume"].tolist() == [100.0, 200.0]


def test_attach_actual_vwap_rejects_missing_turnover_on_trading_day():
    adjusted = pd.DataFrame(
        {"Close": [100.0], "Volume": [10.0]},
        index=pd.to_datetime(["2026-09-01"]),
    )
    raw = pd.DataFrame(
        {"종가": [100.0], "거래량": [10.0], "거래대금": [0.0]},
        index=adjusted.index,
    )

    with pytest.raises(ValueError, match="거래대금/거래량"):
        price_collector._attach_actual_vwap(adjusted, raw)


def test_fdr_history_joins_unadjusted_krx_turnover(monkeypatch):
    index = pd.to_datetime(["2026-09-01"])
    adjusted = pd.DataFrame(
        {
            "Open": [99.0],
            "High": [102.0],
            "Low": [98.0],
            "Close": [100.0],
            "Volume": [10.0],
            "Change": [0.01],
        },
        index=index,
    )
    raw = pd.DataFrame(
        {"종가": [200.0], "거래량": [10.0], "거래대금": [2020.0]}, index=index
    )
    raw_calls = []
    monkeypatch.setattr(price_collector.fdr, "DataReader", lambda *args: adjusted)

    def fake_raw(fromdate, todate, code, adjusted):
        raw_calls.append((fromdate, todate, code, adjusted))
        return raw

    monkeypatch.setattr(price_collector.krx, "get_market_ohlcv_by_date", fake_raw)
    monkeypatch.setattr(
        price_collector,
        "_fetch_investor_flows_by_date",
        lambda *args: _investor_flows(index),
    )

    result = price_collector._fetch_ohlcv_fdr("005930", "2026-09-01", "2026-09-01")

    assert raw_calls == [("20260901", "20260901", "005930", False)]
    assert result.loc[index[0], "Change"] == pytest.approx(1.0)
    assert result.loc[index[0], "VWAP"] == pytest.approx(101.0)
    assert result.loc[index[0], "AdjustmentFactor"] == pytest.approx(0.5)
    assert result.loc[index[0], "IndividualNetBuyAmount"] == -100


def test_investor_history_fetches_buy_and_sell_and_derives_net(monkeypatch):
    index = pd.to_datetime(["2026-09-01"])
    calls = []

    def fake_trading_value(fromdate, todate, code, on):
        calls.append((fromdate, todate, code, on))
        multiplier = 1 if on == "매수" else 2
        return pd.DataFrame(
            {
                "기관합계": [300 * multiplier],
                "개인": [400 * multiplier],
                "외국인합계": [200 * multiplier],
            },
            index=index,
        )

    monkeypatch.setattr(
        price_collector.krx, "get_market_trading_value_by_date", fake_trading_value
    )

    result = price_collector._fetch_investor_flows_by_date(
        "005930", "2026-09-01", "2026-09-01"
    )

    assert calls == [
        ("20260901", "20260901", "005930", "매수"),
        ("20260901", "20260901", "005930", "매도"),
    ]
    assert result.loc[index[0], "InstitutionBuyAmount"] == 300
    assert result.loc[index[0], "InstitutionSellAmount"] == 600
    assert result.loc[index[0], "InstitutionNetBuyAmount"] == -300


def test_daily_investor_snapshot_uses_six_market_level_calls(monkeypatch):
    calls = []

    def fake_net_purchases(fromdate, todate, market, investor):
        calls.append((market, investor))
        code = "005930" if market == "KOSPI" else "035720"
        return pd.DataFrame(
            {"매수거래대금": [600], "매도거래대금": [400]},
            index=pd.Index([code], name="티커"),
        )

    monkeypatch.setattr(
        price_collector.krx,
        "get_market_net_purchases_of_equities_by_ticker",
        fake_net_purchases,
    )

    result = price_collector._fetch_daily_investor_snapshot(pd.Timestamp("2026-09-01"))

    assert len(calls) == 6
    assert set(calls) == {
        (market, investor)
        for market in ("KOSPI", "KOSDAQ")
        for investor in ("기관합계", "개인", "외국인")
    }
    assert result.loc["005930", "ForeignNetBuyAmount"] == 200


def test_actual_vwap_completeness_checks_values_not_only_columns():
    frame = pd.DataFrame(
        {
            "Volume": [100.0, 200.0],
            "Amount": [10000.0, pd.NA],
            "RawClose": [100.0, pd.NA],
            "RawVolume": [100.0, pd.NA],
            "AdjustmentFactor": [1.0, pd.NA],
            "VWAP": [100.0, pd.NA],
        }
    )

    assert not price_collector._has_complete_actual_vwap(frame)


def test_update_ohlcv_daily_reports_bulk_failure(monkeypatch):
    monkeypatch.setattr(price_collector, "get_all_tickers", lambda: pd.DataFrame())
    monkeypatch.setattr(price_collector, "_update_ohlcv_bulk_fdr", lambda stocks: set())

    with pytest.raises(RuntimeError, match="업데이트에 실패"):
        price_collector.update_ohlcv_daily()
