import pandas as pd

from experiments.train_src import loaders


def test_label_loading_keeps_requested_last_horizon_rows_with_right_buffer(monkeypatch) -> None:
    source = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=7, freq="B"),
            "Code": ["000001"] * 7,
            "Open": [100.0] * 7,
            "High": [100.0] * 7,
            "Low": [100.0] * 7,
            "Close": [100.0] * 7,
            "Volume": [1] * 7,
            "Trading_Halt": [0] * 7,
        }
    )
    monkeypatch.setattr(loaders.glob, "glob", lambda _: ["/fixtures/000001.parquet"])
    monkeypatch.setattr(loaders.pd, "read_parquet", lambda _: source.copy())

    loaded = loaders.load_parquet_data(
        "/fixtures",
        start_date="2024-01-01",
        end_date="2024-01-05",
        label_params={"type": "fixed", "horizon": 2, "tp": 3.5, "sl": 2.0},
    )

    # 1/4 and 1/5 need the source's 1/8 and 1/9 prices to form labels. They
    # must remain in the requested output while the buffer rows themselves do not.
    assert loaded["Date"].max() == pd.Timestamp("2024-01-05")
    assert loaded["Date"].tolist() == list(pd.date_range("2024-01-01", periods=5, freq="B"))
    assert loaded["Y_Label"].notna().all()
