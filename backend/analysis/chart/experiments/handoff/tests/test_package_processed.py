from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

import pandas as pd
import pytest
from experiments.handoff.package_processed import HandoffContractError, prepare_handoff_package


def _processed_frame(code: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "Code": [code, code],
            "Open": [10.0, 11.0],
            "High": [11.0, 12.0],
            "Low": [9.0, 10.0],
            "Close": [10.5, 11.5],
            "Volume": [100.0, 110.0],
            "Sigma": [0.01, 0.02],
            "Trading_Halt": [0, 0],
            "Y_Label": [1, 2],
            "alpha_feature": [0.1, 0.2],
        }
    )


def test_prepare_handoff_package_writes_manifest_checksums_and_archive(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    processed.mkdir()
    _processed_frame("000020").to_parquet(processed / "000020.parquet", index=False)
    _processed_frame("005930").to_parquet(processed / "005930.parquet", index=False)
    universe = tmp_path / "source_universe.csv"
    universe.write_text("ticker\n5930\n20\n", encoding="utf-8")
    output = tmp_path / "handoff"
    archive = tmp_path / "chart_processed.tar.gz"

    manifest = prepare_handoff_package(
        processed,
        universe,
        output,
        code_column="ticker",
        archive_path=archive,
    )

    assert manifest["universe"]["codes"] == ["000020", "005930"]
    assert manifest["processed_contract"]["feature_count"] == 1
    assert manifest["coverage"]["total_rows"] == 4
    assert manifest["coverage"]["has_common_date_range"] is True
    assert (output / "DATA_MANIFEST.json").is_file()
    assert (output / "SHA256SUMS").is_file()
    assert archive.is_file()
    assert archive.with_name(f"{archive.name}.sha256").is_file()
    with tarfile.open(archive, "r:gz") as handle:
        assert sorted(handle.getnames()) == [
            "DATA_MANIFEST.json",
            "README.md",
            "SHA256SUMS",
            "processed/000020.parquet",
            "processed/005930.parquet",
            "universe.csv",
        ]

    lines = (output / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    expected = hashlib.sha256((processed / "005930.parquet").read_bytes()).hexdigest()
    assert f"{expected}  processed/005930.parquet" in lines


def test_prepare_handoff_package_rejects_missing_universe_file(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    processed.mkdir()
    _processed_frame("005930").to_parquet(processed / "005930.parquet", index=False)
    universe = tmp_path / "universe.csv"
    universe.write_text("Code\n005930\n000020\n", encoding="utf-8")

    with pytest.raises(HandoffContractError, match="processed 파일이 없습니다"):
        prepare_handoff_package(processed, universe, tmp_path / "handoff")


def test_prepare_handoff_package_accepts_alphanumeric_krx_code(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    processed.mkdir()
    _processed_frame("45014K").to_parquet(processed / "45014K.parquet", index=False)
    universe = tmp_path / "universe.csv"
    universe.write_text("Code\n45014k\n", encoding="utf-8")

    manifest = prepare_handoff_package(processed, universe, tmp_path / "handoff")

    assert manifest["universe"]["codes"] == ["45014K"]


def test_prepare_handoff_package_rejects_code_mismatch(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    processed.mkdir()
    _processed_frame("000020").to_parquet(processed / "005930.parquet", index=False)
    universe = tmp_path / "universe.csv"
    universe.write_text("Code\n005930\n", encoding="utf-8")

    with pytest.raises(HandoffContractError, match="파일명 종목"):
        prepare_handoff_package(processed, universe, tmp_path / "handoff")
