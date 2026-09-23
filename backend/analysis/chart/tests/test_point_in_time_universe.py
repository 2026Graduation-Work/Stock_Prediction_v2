import pandas as pd
import pytest
from point_in_time_universe import (
    UniverseContractError,
    filter_point_in_time_rows,
    intervals_overlapping,
    membership_matrix,
    validate_security_master,
)


def _master() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["A", "A", "KOSPI", "주권", "2010-01-01", "2019-01-01", "test", "2026-01-01"],
            ["B", "B", "KOSPI", "주권", "2015-01-01", None, "test", "2026-01-01"],
            ["C", "C", "KOSDAQ", "주권", "2022-01-01", None, "test", "2026-01-01"],
        ],
        columns=[
            "Code", "Name", "Market", "SecuGroup", "ListingDate", "DelistingDate",
            "Source", "SnapshotDate",
        ],
    )


def test_membership_reconstructs_each_historical_date() -> None:
    master = validate_security_master(_master())
    matrix = membership_matrix(
        pd.to_datetime(["2018-01-02", "2023-01-02"]), master["Code"], master
    )

    assert set(matrix.columns[matrix.iloc[0]]) == {"00000A", "00000B"}
    assert set(matrix.columns[matrix.iloc[1]]) == {"00000B", "00000C"}


def test_filter_uses_inclusive_listing_and_exclusive_delisting() -> None:
    rows = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2009-12-31", "2010-01-01", "2018-12-31", "2019-01-01"]),
            "Code": ["A"] * 4,
            "Close": [1.0] * 4,
        }
    )
    filtered = filter_point_in_time_rows(rows, _master())
    assert filtered["Date"].tolist() == pd.to_datetime(["2010-01-01", "2018-12-31"]).tolist()


def test_period_overlap_keeps_delisted_and_later_listings() -> None:
    result = intervals_overlapping(_master(), "2016-01-01", "2023-12-31")
    assert set(result["Code"]) == {"00000A", "00000B", "00000C"}


def test_overlapping_intervals_fail_closed() -> None:
    master = pd.concat([_master(), _master().iloc[[0]].assign(ListingDate="2018-01-01")])
    with pytest.raises(UniverseContractError, match="중첩"):
        validate_security_master(master)
