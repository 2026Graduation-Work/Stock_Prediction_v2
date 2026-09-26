# ruff: noqa: I001

import pandas as pd
import pytest

from experiments.train_src import loaders


def test_loader_enforces_point_in_time_master(tmp_path) -> None:
    source = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2017-01-02", "2018-01-02", "2019-01-01"]),
            "Code": ["000001"] * 3,
            "Open": [100.0] * 3,
            "High": [100.0] * 3,
            "Low": [100.0] * 3,
            "Close": [100.0] * 3,
            "Volume": [1] * 3,
            "Trading_Halt": [0] * 3,
        }
    )
    source.to_parquet(tmp_path / "000001.parquet", index=False)
    master = pd.DataFrame(
        {
            "Code": ["000001"],
            "Name": ["A"],
            "Market": ["KOSPI"],
            "SecuGroup": ["주권"],
            "ListingDate": ["2018-01-01"],
            "DelistingDate": ["2019-01-01"],
            "Source": ["test"],
            "SnapshotDate": ["2026-01-01"],
        }
    )
    master_path = tmp_path / "master.parquet"
    master.to_parquet(master_path, index=False)

    loaded = loaders.load_parquet_data(
        str(tmp_path), "2017-01-01", "2019-12-31", universe_file=str(master_path)
    )
    assert loaded["Date"].tolist() == [pd.Timestamp("2018-01-02")]


def test_loader_labels_reused_codes_within_each_listing_interval(tmp_path) -> None:
    source = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                ["2010-01-01", "2010-01-02", "2020-01-01", "2020-01-02"]
            ),
            "Code": ["000001"] * 4,
            "Open": [100.0, 100.0, 200.0, 200.0],
            "High": [100.0, 100.0, 200.0, 200.0],
            "Low": [100.0, 100.0, 200.0, 200.0],
            "Close": [100.0, 100.0, 200.0, 200.0],
            "Volume": [1] * 4,
            "Trading_Halt": [0] * 4,
            "Sigma": [0.01] * 4,
        }
    )
    source.to_parquet(tmp_path / "000001.parquet", index=False)
    master = pd.DataFrame(
        {
            "Code": ["000001", "000001"],
            "Name": ["Old", "New"],
            "Market": ["KOSPI", "KOSPI"],
            "SecuGroup": ["주권", "주권"],
            "ListingDate": ["2010-01-01", "2020-01-01"],
            "DelistingDate": ["2010-01-03", None],
            "Source": ["test", "test"],
            "SnapshotDate": ["2026-01-01", "2026-01-01"],
        }
    )
    master_path = tmp_path / "master.parquet"
    master.to_parquet(master_path, index=False)

    loaded = loaders.load_parquet_data(
        str(tmp_path),
        "2010-01-01",
        "2020-01-02",
        label_params={"type": "fixed", "horizon": 1, "tp": 3.5, "sl": 2.0},
        universe_file=str(master_path),
    )

    assert loaded["Date"].tolist() == [
        pd.Timestamp("2010-01-01"),
        pd.Timestamp("2020-01-01"),
    ]
    assert loaded["Y_Label"].tolist() == [1, 1]


def test_delisted_partial_horizon_uses_last_observed_close() -> None:
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2020-01-01", "2020-01-02"]),
            "Close": [100.0, 90.0],
            "High": [100.0, 91.0],
            "Trading_Halt": [0, 0],
        }
    )
    interval = pd.Series({"DelistingDate": pd.Timestamp("2020-01-03")})
    labels = pd.Series([float("nan"), float("nan")])

    resolved = loaders._resolve_delisting_tail_labels(
        frame,
        labels,
        {"type": "fixed", "horizon": 3, "tp": 3.5, "sl": 2.0},
        interval,
    )

    assert resolved.iloc[0] == -1.0
    assert pd.isna(resolved.iloc[1])


def test_loader_fails_if_any_selected_file_cannot_be_loaded(monkeypatch) -> None:
    source = pd.DataFrame(
        {
            "Date": [pd.Timestamp("2024-01-02")],
            "Code": ["000001"],
            "Open": [100.0],
            "High": [100.0],
            "Low": [100.0],
            "Close": [100.0],
            "Volume": [1],
            "Trading_Halt": [0],
            "Sigma": [0.01],
        }
    )
    paths = ["/fixtures/000001.parquet", "/fixtures/000002.parquet"]
    monkeypatch.setattr(loaders.glob, "glob", lambda _: paths)

    def read_parquet(path, columns=None):
        if path.endswith("000002.parquet"):
            raise OSError("corrupt parquet")
        return source.copy() if columns is None else source[columns].copy()

    monkeypatch.setattr(loaders.pd, "read_parquet", read_parquet)

    with pytest.raises(RuntimeError, match="로드/검증 실패 1개"):
        loaders.load_parquet_data("/fixtures")


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


def test_label_observation_end_purges_anchors_that_need_later_prices(monkeypatch) -> None:
    source = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=8, freq="B"),
            "Code": ["000001"] * 8,
            "Open": [100.0] * 8,
            "High": [100.0] * 8,
            "Low": [100.0] * 8,
            "Close": [100.0] * 8,
            "Volume": [1] * 8,
            "Trading_Halt": [0] * 8,
        }
    )
    monkeypatch.setattr(loaders.glob, "glob", lambda _: ["/fixtures/000001.parquet"])
    monkeypatch.setattr(loaders.pd, "read_parquet", lambda _: source.copy())

    loaded = loaders.load_parquet_data(
        "/fixtures",
        start_date="2024-01-01",
        end_date="2024-01-05",
        label_observation_end="2024-01-05",
        label_params={"type": "fixed", "horizon": 2, "tp": 3.5, "sl": 2.0},
    )

    assert loaded["Date"].max() == pd.Timestamp("2024-01-03")


def test_label_observation_end_can_precede_requested_end(monkeypatch) -> None:
    source = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=8, freq="B"),
            "Code": ["000001"] * 8,
            "Open": [100.0] * 8,
            "High": [100.0] * 8,
            "Low": [100.0] * 8,
            "Close": [100.0] * 8,
            "Volume": [1] * 8,
            "Trading_Halt": [0] * 8,
        }
    )
    monkeypatch.setattr(loaders.glob, "glob", lambda _: ["/fixtures/000001.parquet"])
    monkeypatch.setattr(loaders.pd, "read_parquet", lambda _: source.copy())

    loaded = loaders.load_parquet_data(
        "/fixtures",
        start_date="2024-01-01",
        end_date="2024-01-05",
        label_observation_end="2024-01-04",
        label_params={"type": "fixed", "horizon": 2, "tp": 3.5, "sl": 2.0},
    )

    assert loaded["Date"].max() == pd.Timestamp("2024-01-02")


def test_live_top200_alias_is_rejected_for_reproducibility(monkeypatch) -> None:
    monkeypatch.setattr(loaders.glob, "glob", lambda _: ["/fixtures/005930.parquet"])

    with pytest.raises(ValueError, match="재현"):
        loaders.load_parquet_data("/fixtures", tickers="KOSPI_TOP200")
