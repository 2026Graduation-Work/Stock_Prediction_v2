from pathlib import Path

import pandas as pd
import pytest
from experiments.handoff.build_kospi_universe import build_kospi_snapshot
from experiments.handoff.package_processed import HandoffContractError


def _frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    active = pd.DataFrame(
        [
            {"Code": "5930", "Name": "기존", "Market": "KOSPI", "ListingDate": "2000-01-01"},
            {"Code": "123456", "Name": "신규", "Market": "KOSPI", "ListingDate": "2025-01-02"},
            {"Code": "654321", "Name": "코스닥", "Market": "KOSDAQ", "ListingDate": "2000-01-01"},
        ]
    )
    delisted = pd.DataFrame(
        [
            {
                "Symbol": "45014k",
                "Name": "상폐예정",
                "Market": "KOSPI",
                "SecuGroup": "주권",
                "ListingDate": "2023-01-01",
                "DelistingDate": "2025-02-01",
            },
            {
                "Symbol": "777777",
                "Name": "펀드",
                "Market": "KOSPI",
                "SecuGroup": "수익증권",
                "ListingDate": "2020-01-01",
                "DelistingDate": "2025-02-01",
            },
        ]
    )
    return active, delisted


def test_build_snapshot_keeps_cutoff_equities_and_post_cutoff_delistings(
    tmp_path: Path,
) -> None:
    for code in ("005930", "45014K"):
        (tmp_path / f"{code}.parquet").touch()
    active, delisted = _frames()

    snapshot = build_kospi_snapshot(active, delisted, cutoff="2024-12-30", processed_dir=tmp_path)

    assert snapshot["Code"].tolist() == ["005930", "45014K"]
    assert snapshot["Source"].tolist() == ["KOSPI-DESC", "KRX-DELISTING"]


def test_build_snapshot_rejects_missing_processed_file(tmp_path: Path) -> None:
    active, delisted = _frames()
    with pytest.raises(HandoffContractError, match="processed 파일이 없습니다"):
        build_kospi_snapshot(active, delisted, cutoff="2024-12-30", processed_dir=tmp_path)
