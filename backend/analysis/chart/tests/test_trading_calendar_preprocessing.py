from datetime import date

import pandas as pd
import pytest
from core import features
from data_collectors import preprocess_data, trading_calendar


@pytest.fixture
def raw_prices():
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-09-24", "2026-09-29"]),
            "Open": [100.0, 102.0],
            "High": [101.0, 103.0],
            "Low": [99.0, 101.0],
            "Close": [100.0, 102.0],
            "Volume": [1000.0, 1200.0],
            "Code": ["005930", "005930"],
        }
    )


@pytest.mark.parametrize(
    "normalizer",
    [preprocess_data.normalize_trading_halts, features.normalize_trading_halts],
)
def test_normalizer_inserts_only_missing_krx_session_not_weekday_holiday(
    raw_prices, normalizer
):
    market_days = {
        date(2026, 9, 24),
        date(2026, 9, 25),
        date(2026, 9, 29),
    }

    normalized = normalizer(raw_prices, market_days)

    assert normalized["Date"].tolist() == list(
        pd.to_datetime(["2026-09-24", "2026-09-25", "2026-09-29"])
    )
    assert normalized["Trading_Halt"].tolist() == [0, 1, 0]
    assert pd.Timestamp("2026-09-28") not in set(normalized["Date"])
    assert normalized.loc[1, "Close"] == 100.0
    assert normalized.loc[1, "Volume"] == 0.0


def test_reindex_rejects_raw_row_on_non_trading_day(raw_prices):
    invalid = raw_prices.copy()
    invalid.loc[1, "Date"] = pd.Timestamp("2026-09-28")
    market_days = {date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 29)}

    with pytest.raises(trading_calendar.TradingCalendarError, match="2026-09-28"):
        trading_calendar.reindex_to_krx_trading_days(invalid, market_days)


def test_batch_calendar_covers_all_files_with_one_request(tmp_path, monkeypatch):
    first = tmp_path / "first.parquet"
    second = tmp_path / "second.parquet"
    pd.DataFrame({"Date": pd.to_datetime(["2024-01-02", "2024-01-03"])}).to_parquet(
        first, index=False
    )
    pd.DataFrame({"Date": pd.to_datetime(["2025-12-29", "2025-12-30"])}).to_parquet(
        second, index=False
    )
    calls = []

    def fake_calendar(start_date, end_date):
        calls.append((start_date, end_date))
        return {date(2024, 1, 2), date(2025, 12, 30)}

    monkeypatch.setattr(preprocess_data, "get_krx_trading_days", fake_calendar)

    result = preprocess_data._load_trading_days_for_files([str(first), str(second)])

    assert calls == [("2024-01-02", "2025-12-30")]
    assert result == {date(2024, 1, 2), date(2025, 12, 30)}
