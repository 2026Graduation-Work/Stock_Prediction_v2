"""학습 종료일 기준 KOSPI 주권 universe 스냅샷을 생성한다."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .package_processed import HandoffContractError


def _codes(values: pd.Series) -> pd.Series:
    codes = values.astype("string").str.strip().str.upper().str.zfill(6)
    invalid = ~codes.fillna("").str.fullmatch(r"[0-9A-Z]{6}")
    if invalid.any():
        raise HandoffContractError(f"유효하지 않은 KRX 단축코드: {codes[invalid].head().tolist()}")
    return codes


def build_kospi_snapshot(
    active: pd.DataFrame,
    delisted: pd.DataFrame,
    *,
    cutoff: str,
    processed_dir: str | Path,
) -> pd.DataFrame:
    """현재 활성 목록과 상폐 이력으로 cutoff 당시 KOSPI 주권을 복원한다."""
    cutoff_date = pd.Timestamp(cutoff).normalize()
    active_required = {"Code", "Name", "Market", "ListingDate"}
    delisted_required = {
        "Symbol",
        "Name",
        "Market",
        "SecuGroup",
        "ListingDate",
        "DelistingDate",
    }
    if missing := sorted(active_required - set(active.columns)):
        raise HandoffContractError(f"KOSPI-DESC 필수 컬럼 누락: {missing}")
    if missing := sorted(delisted_required - set(delisted.columns)):
        raise HandoffContractError(f"KRX-DELISTING 필수 컬럼 누락: {missing}")

    active = active.copy()
    active["ListingDate"] = pd.to_datetime(active["ListingDate"], errors="coerce")
    active = active[
        active["Market"].eq("KOSPI") & active["ListingDate"].le(cutoff_date)
    ].copy()
    active["Code"] = _codes(active["Code"])
    active = active[["Code", "Name", "ListingDate"]]
    active["DelistingDate"] = pd.NaT
    active["Source"] = "KOSPI-DESC"

    delisted = delisted.copy()
    delisted["ListingDate"] = pd.to_datetime(delisted["ListingDate"], errors="coerce")
    delisted["DelistingDate"] = pd.to_datetime(delisted["DelistingDate"], errors="coerce")
    delisted = delisted[
        delisted["Market"].eq("KOSPI")
        & delisted["SecuGroup"].eq("주권")
        & delisted["ListingDate"].le(cutoff_date)
        & delisted["DelistingDate"].gt(cutoff_date)
    ].copy()
    delisted["Code"] = _codes(delisted["Symbol"])
    delisted = delisted[["Code", "Name", "ListingDate", "DelistingDate"]]
    delisted["Source"] = "KRX-DELISTING"

    snapshot = pd.concat([active, delisted], ignore_index=True)
    snapshot = snapshot.sort_values(["Code", "Source"], kind="stable")
    snapshot = snapshot.drop_duplicates("Code", keep="first").reset_index(drop=True)
    processed_codes = {path.stem.upper() for path in Path(processed_dir).glob("*.parquet")}
    missing_processed = sorted(set(snapshot["Code"]) - processed_codes)
    if missing_processed:
        raise HandoffContractError(
            "KOSPI snapshot에 대응하는 processed 파일이 없습니다: "
            f"{missing_processed[:20]} (총 {len(missing_processed)}개)"
        )
    if snapshot.empty:
        raise HandoffContractError("KOSPI snapshot이 비어 있습니다.")
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(
        description="학습 종료일 기준 KOSPI 전 주권 universe.csv를 생성합니다."
    )
    parser.add_argument("--cutoff", default="2024-12-30")
    parser.add_argument("--processed-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    import FinanceDataReader as fdr

    snapshot = build_kospi_snapshot(
        fdr.StockListing("KOSPI-DESC"),
        fdr.StockListing("KRX-DELISTING"),
        cutoff=args.cutoff,
        processed_dir=args.processed_dir,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"기존 universe를 덮어쓰지 않습니다: {output}")
    snapshot.to_csv(output, index=False, date_format="%Y-%m-%d", encoding="utf-8")
    print(f"KOSPI snapshot: {len(snapshot)}개 -> {output.resolve()}")


if __name__ == "__main__":
    main()
