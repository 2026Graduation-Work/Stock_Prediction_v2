"""KRX 종목 마스터와 point-in-time universe 공용 규칙.

``ListingDate``는 포함, ``DelistingDate``는 미포함 경계다.  이 모듈은
chart 내부 데이터 계약이며 동결된 ``schema/`` 출력 계약과는 독립적이다.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "Code",
    "Name",
    "Market",
    "SecuGroup",
    "ListingDate",
    "DelistingDate",
    "Source",
    "SnapshotDate",
}


class UniverseContractError(ValueError):
    """종목 마스터가 PIT 계약을 만족하지 않을 때 발생한다."""


def normalize_code(values: pd.Series) -> pd.Series:
    codes = values.astype("string").str.strip().str.upper().str.zfill(6)
    invalid = ~codes.fillna("").str.fullmatch(r"[0-9A-Z]{6}")
    if invalid.any():
        raise UniverseContractError(
            f"유효하지 않은 KRX 단축코드: {codes[invalid].head().tolist()}"
        )
    return codes


def validate_security_master(master: pd.DataFrame) -> pd.DataFrame:
    """형식과 상장 구간의 비중첩을 검증하고 정규화한 복사본을 반환한다."""
    missing = sorted(REQUIRED_COLUMNS - set(master.columns))
    if missing:
        raise UniverseContractError(f"security master 필수 컬럼 누락: {missing}")

    result = master.copy()
    result["Code"] = normalize_code(result["Code"])
    for column in ("ListingDate", "DelistingDate", "SnapshotDate"):
        result[column] = pd.to_datetime(result[column], errors="coerce").dt.normalize()

    if result["ListingDate"].isna().any():
        codes = result.loc[result["ListingDate"].isna(), "Code"].head().tolist()
        raise UniverseContractError(f"ListingDate가 없는 종목이 있습니다: {codes}")
    if result["SnapshotDate"].isna().any():
        raise UniverseContractError("SnapshotDate가 없거나 잘못된 행이 있습니다.")
    invalid_interval = result["DelistingDate"].notna() & result["DelistingDate"].le(
        result["ListingDate"]
    )
    if invalid_interval.any():
        codes = result.loc[invalid_interval, "Code"].head().tolist()
        raise UniverseContractError(f"상장 구간이 잘못된 종목이 있습니다: {codes}")

    result = result.drop_duplicates(
        ["Code", "ListingDate", "DelistingDate"], keep="last"
    ).sort_values(["Code", "ListingDate"], kind="stable")

    # 같은 코드가 재사용되더라도 비중첩 구간은 허용한다. 겹치는 구간은 날짜별
    # membership과 종목별 parquet를 모호하게 만들므로 fail closed 한다.
    for code, rows in result.groupby("Code", sort=False):
        previous_end = None
        for index, row in enumerate(rows.itertuples(index=False)):
            if index > 0 and previous_end is None:
                raise UniverseContractError(
                    f"현재 상장 구간 뒤에 추가 구간이 존재합니다: {code}"
                )
            if previous_end is not None and row.ListingDate < previous_end:
                raise UniverseContractError(f"상장 구간이 중첩된 종목입니다: {code}")
            previous_end = row.DelistingDate if pd.notna(row.DelistingDate) else None

    result = result.reset_index(drop=True)
    result.attrs["pit_validated"] = True
    return result


def _validated(master: pd.DataFrame) -> pd.DataFrame:
    return master if master.attrs.get("pit_validated") is True else validate_security_master(master)


def load_security_master(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"security master를 찾을 수 없습니다: {path}")
    if path.suffix.lower() == ".parquet":
        master = pd.read_parquet(path)
    elif path.suffix.lower() == ".csv":
        master = pd.read_csv(path, dtype={"Code": "string"})
    else:
        raise UniverseContractError("security master는 CSV 또는 Parquet이어야 합니다.")
    return validate_security_master(master)


def intervals_overlapping(
    master: pd.DataFrame, start_date: str | pd.Timestamp, end_date: str | pd.Timestamp
) -> pd.DataFrame:
    """닫힌 요청 기간과 한 번이라도 겹치는 상장 구간을 반환한다."""
    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()
    if start > end:
        raise ValueError("start_date는 end_date보다 늦을 수 없습니다.")
    normalized = _validated(master)
    mask = normalized["ListingDate"].le(end) & (
        normalized["DelistingDate"].isna()
        | normalized["DelistingDate"].gt(start)
    )
    return normalized.loc[mask].reset_index(drop=True)


def membership_mask(rows: pd.DataFrame, master: pd.DataFrame) -> pd.Series:
    """Date/Code 행이 해당 날짜의 상장 구간 안에 있는지 판정한다."""
    if not {"Date", "Code"}.issubset(rows.columns):
        raise UniverseContractError("membership 판정에는 Date와 Code가 필요합니다.")
    normalized = _validated(master)
    source = rows[["Date", "Code"]].copy()
    source["_row_id"] = range(len(source))
    source["Date"] = pd.to_datetime(source["Date"]).dt.tz_localize(None).dt.normalize()
    source["Code"] = normalize_code(source["Code"])
    joined = source.merge(
        normalized[["Code", "ListingDate", "DelistingDate"]], on="Code", how="left"
    )
    eligible = joined["Date"].ge(joined["ListingDate"]) & (
        joined["DelistingDate"].isna()
        | joined["Date"].lt(joined["DelistingDate"])
    )
    matched = joined.loc[eligible].groupby("_row_id").size()
    if (matched > 1).any():
        raise UniverseContractError("한 Date/Code가 여러 상장 구간에 동시에 속합니다.")
    return pd.Series(source["_row_id"].isin(matched.index).to_numpy(), index=rows.index)


def filter_point_in_time_rows(rows: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    return rows.loc[membership_mask(rows, master)].copy()


def membership_matrix(
    dates: pd.Index, codes: pd.Index, master: pd.DataFrame
) -> pd.DataFrame:
    index = pd.DatetimeIndex(pd.to_datetime(dates)).tz_localize(None)
    columns = pd.Index([str(code).strip().upper().zfill(6) for code in codes])
    long = pd.MultiIndex.from_product([index, columns], names=["Date", "Code"]).to_frame(
        index=False
    )
    values = membership_mask(long, master).to_numpy().reshape(len(index), len(columns))
    return pd.DataFrame(values, index=index, columns=columns, dtype=bool)
