from datetime import date

import pandas as pd
import pytest
from core import features
from data_collectors import investor_flow_features, preprocess_data, trading_calendar


@pytest.fixture
def raw_prices():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-09-24", "2026-09-29"]),
            "Open": [100.0, 102.0],
            "High": [101.0, 103.0],
            "Low": [99.0, 101.0],
            "Close": [100.0, 102.0],
            "Volume": [1000.0, 1200.0],
            "Amount": [100000.0, 120000.0],
            "VWAP": [99.5, 101.5],
            "Code": ["005930", "005930"],
        }
    )
    for prefix, net_values in (
        ("Institution", [10000.0, 24000.0]),
        ("Individual", [-5000.0, -12000.0]),
        ("Foreign", [-5000.0, -12000.0]),
    ):
        frame[f"{prefix}BuyAmount"] = [50000.0, 60000.0]
        frame[f"{prefix}SellAmount"] = frame[f"{prefix}BuyAmount"] - net_values
        frame[f"{prefix}NetBuyAmount"] = net_values
    return frame


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


@pytest.mark.parametrize(
    "feature_generator",
    [preprocess_data.generate_full_alpha158_features, features.generate_full_alpha158_features],
)
def test_alpha158_uses_actual_vwap_column(feature_generator):
    frame = pd.DataFrame(
        {
            "Open": [99.0, 101.0],
            "High": [101.0, 103.0],
            "Low": [98.0, 100.0],
            "Close": [100.0, 102.0],
            "Volume": [1000.0, 1200.0],
            "VWAP": [105.0, 99.0],
        }
    )

    generated = feature_generator(frame)

    assert generated["vwap_0"].tolist() == pytest.approx([1.05, 99.0 / 102.0])


@pytest.mark.parametrize(
    "feature_generator",
    [preprocess_data.generate_full_alpha158_features, features.generate_full_alpha158_features],
)
def test_alpha158_rejects_hlc3_fallback(feature_generator):
    frame = pd.DataFrame(
        {"Open": [99.0], "High": [101.0], "Low": [98.0], "Close": [100.0], "Volume": [1.0]}
    )

    with pytest.raises(ValueError, match="실제 VWAP"):
        feature_generator(frame)


@pytest.mark.parametrize(
    "normalizer",
    [preprocess_data.normalize_trading_halts, features.normalize_trading_halts],
)
def test_normalizer_does_not_hide_missing_vwap_on_traded_row(raw_prices, normalizer):
    raw_prices.loc[1, "VWAP"] = pd.NA
    market_days = {date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 29)}

    with pytest.raises(ValueError, match="실제 VWAP 값이 없습니다"):
        normalizer(raw_prices, market_days)


def test_investor_flow_features_normalize_daily_and_rolling_amount():
    periods = 20
    frame = pd.DataFrame({"Amount": [1000.0] * periods})
    for prefix in ("Institution", "Individual", "Foreign"):
        frame[f"{prefix}BuyAmount"] = [600.0] * periods
        frame[f"{prefix}SellAmount"] = [400.0] * periods
        frame[f"{prefix}NetBuyAmount"] = [200.0] * periods

    frame["Date"] = pd.date_range("2026-08-03", periods=periods, freq="B")
    frame["Code"] = "005930"
    generated = investor_flow_features.generate_investor_flow_features(frame)

    assert generated.loc[0, "institution_buy_ratio"] == pytest.approx(0.6)
    assert generated.loc[0, "institution_sell_ratio"] == pytest.approx(0.4)
    assert generated.loc[0, "institution_net_buy_ratio"] == pytest.approx(0.2)
    assert generated.loc[4, "institution_net_buy_ratio_5"] == pytest.approx(0.2)
    assert generated.loc[19, "foreign_net_buy_ratio_20"] == pytest.approx(0.2)
    assert generated.loc[3, "individual_net_buy_ratio_5"] == pytest.approx(0.2)


def test_investor_flow_available_date_is_next_krx_session():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-09-25", "2026-09-28"]),
            "Code": ["005930", "005930"],
        }
    )
    trading_days = {
        date(2026, 9, 25),
        date(2026, 9, 28),
        date(2026, 9, 29),
    }

    result = investor_flow_features._attach_next_trading_day(frame, trading_days)

    assert result["AvailableDate"].tolist() == list(
        pd.to_datetime(["2026-09-28", "2026-09-29"])
    )


def test_build_investor_flow_file_writes_external_feature_contract(
    tmp_path, monkeypatch, raw_prices
):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw_prices.to_parquet(raw_dir / "005930.parquet", index=False)
    output_path = tmp_path / "external" / "investor_flows.parquet"
    monkeypatch.setattr(
        investor_flow_features,
        "get_krx_trading_days",
        lambda start, end: {
            date(2026, 9, 24),
            date(2026, 9, 25),
            date(2026, 9, 29),
            date(2026, 9, 30),
        },
    )

    result = investor_flow_features.build_investor_flow_feature_file(
        raw_dir, output_path
    )

    assert output_path.is_file()
    assert list(result.columns) == [
        "Date",
        "Code",
        "AvailableDate",
        *investor_flow_features.INVESTOR_FLOW_FEATURE_COLUMNS,
    ]
    assert result["AvailableDate"].tolist() == list(
        pd.to_datetime(["2026-09-25", "2026-09-30"])
    )


def test_preprocessor_rejects_missing_investor_flow_on_traded_row(raw_prices):
    raw_prices.loc[1, "ForeignBuyAmount"] = pd.NA
    market_days = {date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 29)}

    with pytest.raises(ValueError, match="투자자 수급 값이 없습니다"):
        preprocess_data.normalize_trading_halts(raw_prices, market_days)


def test_processed_market_feature_marker_distinguishes_legacy_file(tmp_path):
    legacy_path = tmp_path / "legacy.parquet"
    current_path = tmp_path / "current.parquet"
    pd.DataFrame({"vwap_0": [1.0]}).to_parquet(legacy_path, index=False)
    current = {"VWAP": [100.0], "vwap_0": [1.0]}
    current.update({column: [0.0] for column in preprocess_data.INVESTOR_FLOW_INPUT_COLUMNS})
    pd.DataFrame(current).to_parquet(current_path, index=False)

    assert not preprocess_data._processed_has_current_market_data(str(legacy_path))
    assert preprocess_data._processed_has_current_market_data(str(current_path))
