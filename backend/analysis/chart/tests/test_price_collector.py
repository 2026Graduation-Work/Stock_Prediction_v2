import json
from datetime import date

import pandas as pd
import pytest
from data_collectors import price_collector


def _write_calendar_cache(path, start, end, trading_days):
    path.write_text(
        json.dumps(
            {
                "source": price_collector._TRADING_CALENDAR_SOURCE,
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
    monkeypatch.setattr(price_collector, "TRADING_CALENDAR_CACHE_PATH", str(cache_path))

    calls = []

    def fake_index_ohlcv(ticker, fromdate, todate):
        calls.append((ticker, fromdate, todate))
        return pd.DataFrame(
            {"종가": [2600.0, 2610.0]},
            index=pd.to_datetime(["2026-08-31", "2026-09-01"]),
        )

    monkeypatch.setattr(price_collector.fdr, "DataReader", fake_index_ohlcv)

    result = price_collector.get_krx_trading_days("2026-08-29", "2026-09-01")

    assert result == {date(2026, 8, 31), date(2026, 9, 1)}
    assert calls == [("KS11", "2026-08-29", "2026-09-01")]
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["coverage_start"] == "2026-08-29"
    assert payload["coverage_end"] == "2026-09-01"
    assert payload["provider"] == "FinanceDataReader KS11"
    assert payload["trading_days"] == ["2026-08-31", "2026-09-01"]


def test_get_krx_trading_days_falls_back_to_pykrx_index(tmp_path, monkeypatch):
    cache_path = tmp_path / "krx_trading_calendar.json"
    monkeypatch.setattr(price_collector, "TRADING_CALENDAR_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(
        price_collector.fdr,
        "DataReader",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("FDR unavailable")),
    )
    monkeypatch.setattr(
        price_collector.krx,
        "get_index_ohlcv_by_date",
        lambda *args, **kwargs: pd.DataFrame(
            {"종가": [2600.0]}, index=pd.to_datetime(["2026-09-01"])
        ),
    )

    result = price_collector.get_krx_trading_days("2026-08-31", "2026-09-01")

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
    monkeypatch.setattr(price_collector, "TRADING_CALENDAR_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(
        price_collector.fdr,
        "DataReader",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("FDR unavailable")),
    )
    monkeypatch.setattr(
        price_collector.krx,
        "get_index_ohlcv_by_date",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("KRX unavailable")),
    )

    result = price_collector.get_krx_trading_days("2026-08-30", "2026-09-01")

    assert result == {date(2026, 8, 31), date(2026, 9, 1)}


def test_get_krx_trading_days_fails_closed_for_incomplete_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "krx_trading_calendar.json"
    _write_calendar_cache(cache_path, "2026-09-01", "2026-09-02", ["2026-09-01"])
    monkeypatch.setattr(price_collector, "TRADING_CALENDAR_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(
        price_collector.fdr,
        "DataReader",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("FDR unavailable")),
    )
    monkeypatch.setattr(
        price_collector.krx,
        "get_index_ohlcv_by_date",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("KRX unavailable")),
    )

    with pytest.raises(price_collector.TradingCalendarError, match="캐시도 없습니다"):
        price_collector.get_krx_trading_days("2026-08-01", "2026-09-02")


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
    monkeypatch.setattr(price_collector, "TRADING_CALENDAR_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(
        price_collector.fdr,
        "DataReader",
        lambda *args, **kwargs: pd.DataFrame(
            {"종가": [2610.0, 2620.0]},
            index=pd.to_datetime(["2026-09-01", "2026-09-03"]),
        ),
    )

    price_collector.get_krx_trading_days("2026-09-01", "2026-09-03")

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
                "ChagesRatio": [0.5] if market == "KOSPI" else [],
            }
        )

    monkeypatch.setattr(price_collector.fdr, "StockListing", fake_stock_listing)
    stocks = pd.DataFrame(
        [{"Code": "005930", "Name": "삼성전자", "IsDelisted": False}]
    )

    updated = price_collector._update_ohlcv_bulk_fdr(stocks)

    assert updated == {"005930"}
    assert listing_calls == ["KOSPI", "KOSDAQ"]
    stored = pd.read_parquet(raw_dir / "005930.parquet")
    assert stored.loc[0, "Date"] == pd.Timestamp("2026-09-01")
    assert stored.loc[0, "Close"] == 70500


def test_update_ohlcv_daily_reports_bulk_failure(monkeypatch):
    monkeypatch.setattr(price_collector, "get_all_tickers", lambda: pd.DataFrame())
    monkeypatch.setattr(price_collector, "_update_ohlcv_bulk_fdr", lambda stocks: set())

    with pytest.raises(RuntimeError, match="업데이트에 실패"):
        price_collector.update_ohlcv_daily()
