import argparse
import os
import time
from datetime import datetime, timedelta

import FinanceDataReader as fdr
import pandas as pd
from pykrx import stock as krx
from tqdm import tqdm

try:
    from .trading_calendar import get_krx_trading_days
except ImportError:  # 직접 스크립트 실행: python data_collectors/price_collector.py
    from trading_calendar import get_krx_trading_days

try:
    from point_in_time_universe import intervals_overlapping, validate_security_master
except ImportError:  # 직접 스크립트 실행 시 chart 루트를 import path에 추가
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from point_in_time_universe import intervals_overlapping, validate_security_master

# 데이터 저장 경로 설정
DATA_DIR = "./data/raw"
SECURITY_MASTER_PATH = "./data/universe/security_master.parquet"
TICKER_METADATA_PATH = "./data/ticker_metadata.csv"
os.makedirs(DATA_DIR, exist_ok=True)

# 기본 전체 수집 시작일 (최근 10년 기준, 실행 연도 자동 반영)
_DEFAULT_START_DATE = f"{datetime.now().year - 10}-01-01"
_VWAP_COLUMNS = {"Amount", "RawClose", "RawVolume", "AdjustmentFactor", "VWAP"}


def _has_complete_actual_vwap(df: pd.DataFrame) -> bool:
    """거래량이 있는 모든 행에 실제 VWAP 산출 필드가 유효한지 확인합니다."""
    if not _VWAP_COLUMNS.issubset(df.columns) or "Volume" not in df.columns:
        return False
    traded = pd.to_numeric(df["Volume"], errors="coerce").fillna(0) > 0
    if not traded.any():
        return True
    numeric = df.loc[traded, sorted(_VWAP_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    return bool(numeric.notna().all().all() and numeric.gt(0).all().all())


def _attach_actual_vwap(adjusted_df: pd.DataFrame, raw_df: pd.DataFrame) -> pd.DataFrame:
    """KRX 거래대금 기반 일별 VWAP을 수정주가 스케일로 변환합니다."""
    if adjusted_df.empty or raw_df.empty:
        return pd.DataFrame()

    adjusted = adjusted_df.copy()
    raw = raw_df.rename(
        columns={
            "종가": "RawClose",
            "거래량": "RawVolume",
            "거래대금": "Amount",
        }
    ).copy()
    required_raw_columns = {"RawClose", "RawVolume", "Amount"}
    missing_columns = required_raw_columns - set(raw.columns)
    if missing_columns:
        raise ValueError(f"실제 VWAP 계산용 KRX 컬럼 누락: {sorted(missing_columns)}")

    adjusted.index = pd.to_datetime(adjusted.index).normalize()
    raw.index = pd.to_datetime(raw.index).normalize()
    raw_fields = raw[["RawClose", "RawVolume", "Amount"]].apply(
        pd.to_numeric, errors="coerce"
    )
    combined = adjusted.join(raw_fields, how="left")

    traded = pd.to_numeric(combined["Volume"], errors="coerce").fillna(0) > 0
    invalid = traded & (
        combined["RawClose"].isna()
        | combined["RawClose"].le(0)
        | combined["RawVolume"].isna()
        | combined["RawVolume"].le(0)
        | combined["Amount"].isna()
        | combined["Amount"].le(0)
    )
    if invalid.any():
        invalid_dates = ", ".join(
            timestamp.strftime("%Y-%m-%d") for timestamp in combined.index[invalid][:5]
        )
        raise ValueError(f"거래일의 KRX 거래대금/거래량이 유효하지 않습니다: {invalid_dates}")

    valid_raw_close = combined["RawClose"].where(combined["RawClose"] > 0)
    combined["AdjustmentFactor"] = combined["Close"] / valid_raw_close
    raw_vwap = combined["Amount"] / combined["RawVolume"]
    combined["VWAP"] = raw_vwap * combined["AdjustmentFactor"]
    combined.loc[~traded, "VWAP"] = float("nan")
    return combined


def _active_master_frame(frame: pd.DataFrame, market: str, snapshot_date: pd.Timestamp) -> pd.DataFrame:
    required = {"Code", "Name", "ListingDate"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise RuntimeError(f"{market}-DESC 필수 컬럼 누락: {missing}")
    result = frame.copy()
    result["Market"] = market
    result["SecuGroup"] = result.get("SecuGroup", "주권")
    result["DelistingDate"] = pd.NaT
    result["Source"] = f"{market}-DESC"
    result["ListingDateSource"] = "FDR_DESC"
    result["SnapshotDate"] = snapshot_date
    return result[
        list(
            sorted(
                {
                    *required,
                    "Market",
                    "SecuGroup",
                    "DelistingDate",
                    "Source",
                    "SnapshotDate",
                    "ListingDateSource",
                }
            )
        )
    ]


def _delisted_master_frame(frame: pd.DataFrame, snapshot_date: pd.Timestamp) -> pd.DataFrame:
    result = frame.rename(columns={"Symbol": "Code"}).copy()
    required = {"Code", "Name", "Market", "SecuGroup", "ListingDate", "DelistingDate"}
    missing = sorted(required - set(result.columns))
    if missing:
        raise RuntimeError(f"KRX-DELISTING 필수 컬럼 누락: {missing}")
    result = result[
        result["Market"].isin(["KOSPI", "KOSDAQ"]) & result["SecuGroup"].eq("주권")
    ].copy()
    result["Source"] = "KRX-DELISTING"
    result["ListingDateSource"] = "FDR_DELISTING"
    result["SnapshotDate"] = snapshot_date
    return result[[*sorted(required), "Source", "SnapshotDate", "ListingDateSource"]]


def _fetch_stock_listing(name: str, attempts: int = 3) -> pd.DataFrame:
    errors = []
    for attempt in range(1, attempts + 1):
        try:
            frame = fdr.StockListing(name)
            if frame.empty:
                raise ValueError("응답이 비어 있습니다.")
            return frame
        except Exception as exc:
            errors.append(str(exc))
            if attempt < attempts:
                time.sleep(attempt)
    raise RuntimeError(f"{name} 조회 {attempts}회 실패: {'; '.join(errors)}")


def _infer_missing_listing_dates(master: pd.DataFrame) -> pd.DataFrame:
    """최초 거래일을 조회해 DESC의 이전상장일과 누락 상장일을 보정한다.

    KOSPI-DESC의 ListingDate는 KOSPI 이전상장일일 수 있다. KOSPI+KOSDAQ
    전체 universe에서는 시장 이전 뒤에도 같은 상장 구간이 이어져야 하므로
    최초 거래일과 비교해 더 이른 날짜를 사용한다.
    """
    result = master.copy()
    result["ListingDate"] = pd.to_datetime(result["ListingDate"], errors="coerce")
    if os.path.isfile(SECURITY_MASTER_PATH):
        previous = pd.read_parquet(SECURITY_MASTER_PATH)
        previous["Code"] = previous["Code"].astype("string").str.upper().str.zfill(6)
        previous = previous.sort_values("ListingDate").drop_duplicates("Code", keep="last")
        previous_dates = previous.set_index("Code")["ListingDate"]
        previous_sources = previous.set_index("Code").get("ListingDateSource")
        normalized_codes = result["Code"].astype("string").str.upper().str.zfill(6)
        reusable = result["ListingDate"].isna() & normalized_codes.isin(previous_dates.index)
        result.loc[reusable, "ListingDate"] = normalized_codes[reusable].map(previous_dates)
        if previous_sources is not None:
            result.loc[reusable, "ListingDateSource"] = normalized_codes[reusable].map(
                previous_sources
            )
    # 누락값은 물론 KOSPI-DESC 날짜도 최초 거래일과 비교한다. 한 종목이
    # KOSPI와 KOSDAQ 응답에 중복될 가능성에 대비해 코드별 조회 결과를 재사용한다.
    candidate_rows = result.index[
        result["ListingDate"].isna()
        | (result["Source"].eq("KOSPI-DESC") & result["ListingDate"].notna())
    ]
    failures = []
    first_trade_by_code = {}
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    for row_index in candidate_rows:
        code = str(result.at[row_index, "Code"]).strip().upper().zfill(6)
        if code not in first_trade_by_code:
            errors = []
            for attempt in range(1, 4):
                try:
                    history = fdr.DataReader(code, "1980-01-01", today)
                    dates = pd.to_datetime(history.index, errors="coerce").dropna()
                    if len(dates) == 0:
                        raise ValueError("OHLCV 응답이 비어 있습니다.")
                    first_trade_by_code[code] = dates.min().normalize()
                    break
                except Exception as exc:
                    errors.append(str(exc))
                    if attempt < 3:
                        time.sleep(attempt)
            if code not in first_trade_by_code:
                failures.append(f"{code}: {'; '.join(errors)}")
                continue

        first_trade = first_trade_by_code[code]
        current_listing = result.at[row_index, "ListingDate"]
        if pd.isna(current_listing) or first_trade < current_listing:
            result.at[row_index, "ListingDate"] = first_trade
            result.at[row_index, "ListingDateSource"] = "FDR_FIRST_TRADE"
    if failures:
        raise RuntimeError(
            "상장일 보정용 최초 거래일 조회에 실패했습니다: " + "; ".join(failures[:10])
        )
    return result


def build_security_master() -> pd.DataFrame:
    """현재 활성 목록과 전체 상폐 이력을 상장 구간 마스터로 병합한다."""
    snapshot_date = pd.Timestamp.now().normalize()
    active_frames = []
    for market in ("KOSPI", "KOSDAQ"):
        active_frames.append(
            _active_master_frame(_fetch_stock_listing(f"{market}-DESC"), market, snapshot_date)
        )
    delisted = _delisted_master_frame(_fetch_stock_listing("KRX-DELISTING"), snapshot_date)
    master = pd.concat([*active_frames, delisted], ignore_index=True)
    master = validate_security_master(_infer_missing_listing_dates(master))
    return master


def _write_security_master(master: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(SECURITY_MASTER_PATH), exist_ok=True)
    master.to_parquet(SECURITY_MASTER_PATH, index=False)

    # 기존 점검/대시보드 소비자를 위한 1-code-1-row 파생 파일이다. PIT의 SSOT는
    # security_master.parquet이며 이 CSV를 universe 판정에 사용하지 않는다.
    latest = master.sort_values(["Code", "ListingDate"]).drop_duplicates("Code", keep="last")
    latest = latest.copy()
    latest["IsDelisted"] = latest["DelistingDate"].notna()
    latest.to_csv(TICKER_METADATA_PATH, index=False, encoding="utf-8-sig")


def get_all_tickers(start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """기간 중 한 번이라도 KOSPI/KOSDAQ 주권이었던 모든 상장 구간을 반환한다."""
    print("수집 대상 종목 리스트 구성 중...")
    try:
        master = build_security_master()
    except Exception as e:
        raise RuntimeError(f"PIT 종목 마스터 구성 실패: {e}") from e
    _write_security_master(master)
    selected = master
    if start_date is not None or end_date is not None:
        selected = intervals_overlapping(
            master,
            start_date or master["ListingDate"].min(),
            end_date or pd.Timestamp.now().normalize(),
        )
    selected = selected.copy()
    selected["IsDelisted"] = selected["DelistingDate"].notna()
    print(
        f"  [합계] 상장 구간 {len(selected)}개 / 종목 {selected['Code'].nunique()}개 "
        f"(상폐 구간 {int(selected['IsDelisted'].sum())}개)"
    )
    print(f"  PIT 종목 마스터 저장 완료 ({SECURITY_MASTER_PATH})")
    return selected


# krx -> 한국 거래소 정보데이터 시스템에서 직접 post 요청 날려서 긁어옴.
def _fetch_ohlcv_pykrx(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    pykrx로 수정주가(adjusted=True) 기준 일봉 OHLCV를 가져옵니다.
    등락률(Change)은 % 단위를 유지합니다.
    """
    start_yyyymmdd = start_date.replace("-", "")
    end_yyyymmdd = end_date.replace("-", "")

    adjusted_df = krx.get_market_ohlcv_by_date(
        start_yyyymmdd,
        end_yyyymmdd,
        code,
        adjusted=True,
    )
    raw_df = krx.get_market_ohlcv_by_date(
        start_yyyymmdd,
        end_yyyymmdd,
        code,
        adjusted=False,
    )
    if adjusted_df.empty or raw_df.empty:
        return pd.DataFrame()

    adjusted_df = adjusted_df.rename(
        columns={
            "시가": "Open",
            "고가": "High",
            "저가": "Low",
            "종가": "Close",
            "거래량": "Volume",
            "등락률": "Change",
        }
    )
    required_adjusted_columns = ["Open", "High", "Low", "Close", "Volume", "Change"]
    missing_columns = set(required_adjusted_columns) - set(adjusted_df.columns)
    if missing_columns:
        raise ValueError(f"수정주가 필수 컬럼 누락: {sorted(missing_columns)}")
    adjusted_df = adjusted_df[required_adjusted_columns].copy()
    adjusted_df.index.name = "Date"
    # 등락률의 NaN 값 보정 -> 이거 첫날 상장때는 등락률 계산이 불가능해서 0으로 처리
    if "Change" in adjusted_df.columns:
        adjusted_df["Change"] = adjusted_df["Change"].fillna(0.0)
    return _attach_actual_vwap(adjusted_df, raw_df)


def _fetch_ohlcv_fdr(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    FinanceDataReader로 수정주가 기준 일봉 OHLCV를 가져옵니다.
    FDR의 Change(소수점 단위)를 퍼센트(%) 단위로 변환하여 pykrx와 스케일을 통일합니다.
    """
    try:
        adjusted_df = fdr.DataReader(code, start_date, end_date)
        raw_df = krx.get_market_ohlcv_by_date(
            start_date.replace("-", ""),
            end_date.replace("-", ""),
            code,
            adjusted=False,
        )
        if adjusted_df.empty or raw_df.empty:
            return pd.DataFrame()

        # 필요한 컬럼만 추출 및 리네임
        adjusted_df = adjusted_df[
            ["Open", "High", "Low", "Close", "Volume", "Change"]
        ].copy()
        # 등락률 단위를 %로 변환 (FDR은 0.0132 형태, pykrx는 1.32 형태)
        adjusted_df["Change"] = adjusted_df["Change"].fillna(0.0) * 100.0
        adjusted_df.index.name = "Date"
        return _attach_actual_vwap(adjusted_df, raw_df)
    except Exception:
        # print(f"  [FDR Fetch Error] {code}: {e}")
        return pd.DataFrame()


def _update_ohlcv_bulk_fdr(all_stocks: pd.DataFrame) -> set:
    """
    KOSPI 지수로 확정한 최신 거래일의 FDR 전 종목 시세를 일괄 업데이트합니다.

    날짜가 없는 StockListing 값을 실행일로 간주하지 않고, 동일 공급자의 KOSPI
    지수에 존재하는 최신 거래일을 기준일로 사용합니다.
    """
    print("\n⚡ [FDR 벌크 업데이트] 최신 거래일 시세 일괄 수집 진행...")

    try:
        today = datetime.now().date()
        calendar_start = today - timedelta(days=14)
        trading_days = get_krx_trading_days(calendar_start.isoformat(), today.isoformat())
        actual_date = pd.Timestamp(max(trading_days))
        actual_date_str = actual_date.strftime("%Y-%m-%d")

        kospi = fdr.StockListing("KOSPI")
        kosdaq = fdr.StockListing("KOSDAQ")
        market_snapshot = pd.concat([kospi, kosdaq], ignore_index=True).rename(
            columns={
                "ChagesRatio": "Change",
            }
        )
        required_columns = {
            "Code",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
            "Amount",
            "Change",
        }
        missing_columns = required_columns - set(market_snapshot.columns)
        if missing_columns:
            raise RuntimeError(f"FDR 전 종목 시세 필수 컬럼 누락: {sorted(missing_columns)}")
        market_snapshot = market_snapshot[market_snapshot["Volume"] > 0].copy()
        if market_snapshot["Amount"].isna().any() or market_snapshot["Amount"].le(0).any():
            raise RuntimeError("FDR 전 종목 시세에 유효하지 않은 거래대금이 있습니다.")
        market_snapshot["Code"] = market_snapshot["Code"].astype(str).str.zfill(6)
        print(f"  📅 수집된 실제 영업일 기준일: {actual_date_str}")

        ticker_to_name = dict(zip(all_stocks["Code"], all_stocks["Name"]))
        ticker_to_delisted = dict(zip(all_stocks["Code"], all_stocks["IsDelisted"]))

        updated_tickers = set()

        for _, row in market_snapshot.iterrows():
            code = row["Code"]
            file_path = os.path.join(DATA_DIR, f"{code}.parquet")

            name = ticker_to_name.get(code, "")
            is_delisted = ticker_to_delisted.get(code, False)

            # FDR StockListing의 ChagesRatio는 퍼센트(%) 단위입니다.
            change_val = float(row["Change"]) if not pd.isna(row["Change"]) else 0.0
            volume = float(row["Volume"])
            amount = float(row["Amount"])
            close = float(row["Close"])
            vwap = amount / volume

            new_row = pd.DataFrame(
                [
                    {
                        "Date": actual_date,
                        "Open": float(row["Open"]),
                        "High": float(row["High"]),
                        "Low": float(row["Low"]),
                        "Close": close,
                        "Volume": volume,
                        "Amount": amount,
                        "RawClose": close,
                        "RawVolume": volume,
                        "AdjustmentFactor": 1.0,
                        "VWAP": vwap,
                        "Change": change_val,
                        "Code": code,
                        "Name": name,
                        "IsDelisted": is_delisted,
                    }
                ]
            )

            if os.path.exists(file_path):
                try:
                    existing = pd.read_parquet(file_path)
                    existing["Date"] = pd.to_datetime(existing["Date"])

                    actual_rows = existing.loc[existing["Date"].eq(actual_date)]
                    has_actual_vwap = _has_complete_actual_vwap(actual_rows)
                    if actual_date in existing["Date"].values and has_actual_vwap:
                        updated_tickers.add(code)
                        continue

                    merged = pd.concat([existing, new_row], ignore_index=True)
                    merged = (
                        merged.drop_duplicates(subset=["Date"], keep="last")
                        .sort_values(by="Date")
                        .reset_index(drop=True)
                    )
                    merged.to_parquet(file_path, index=False)
                    updated_tickers.add(code)
                except Exception:
                    new_row.to_parquet(file_path, index=False)
                    updated_tickers.add(code)
            else:
                new_row.to_parquet(file_path, index=False)
                updated_tickers.add(code)

        print(f"  ✅ FDR 벌크 반영 성공: {len(updated_tickers)}개 활성 종목 최신 시세 주입 완료.")
        return updated_tickers
    except Exception as e:
        print(f"  ⚠️ FDR 벌크 업데이트 실패: {e}")
        return set()


def update_ohlcv_daily():
    """
    [데일리 증분 업데이트 함수]
    매일 장 마감 후 실행되어 당일 최신 1일치 시세(FDR 벌크)를 초고속으로 수집 및 업데이트합니다.
    개별 종목 API 루프를 돌지 않아 10초 내로 끝납니다.
    """
    all_stocks = get_all_tickers()
    updated_tickers = _update_ohlcv_bulk_fdr(all_stocks)
    if not updated_tickers:
        raise RuntimeError("KRX 일일 가격 업데이트에 실패했습니다.")
    print("\n✅ 일일 가격 데일리 업데이트 완료.")


def _collection_bounds(row: pd.Series, start_date: str, end_date: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """전역 요청 범위를 한 상장 구간의 inclusive 수집 범위로 제한한다."""
    listing_date = pd.Timestamp(row["ListingDate"]).normalize()
    delisting_date = pd.to_datetime(row["DelistingDate"], errors="coerce")
    interval_start = max(pd.Timestamp(start_date).normalize(), listing_date)
    interval_end = pd.Timestamp(end_date).normalize()
    if pd.notna(delisting_date):
        interval_end = min(interval_end, delisting_date.normalize() - pd.Timedelta(days=1))
    return None if interval_start > interval_end else (interval_start, interval_end)


def download_ohlcv_full(
    start_date: str = _DEFAULT_START_DATE,
    repair_only: bool = False,
    codes: list[str] | None = None,
):
    """
    [전체 이력 수집 및 정밀 보정 함수]
    지정된 start_date부터 오늘까지 전체 종목의 과거 가격 이력을 다운로드하여 구축합니다.
    또한, 이미 구축된 파일 중 중간 영업일(Gap) 누락을 감지하고 메워줍니다.
    속도와 안정성을 위해 FDR DataReader를 기본으로 사용하고 pykrx를 백업으로 사용합니다.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    all_stocks = get_all_tickers(start_date, today_str)
    if codes:
        requested_codes = {str(code).strip().upper().zfill(6) for code in codes}
        all_stocks = all_stocks[all_stocks["Code"].isin(requested_codes)].copy()
        missing_codes = requested_codes - set(all_stocks["Code"])
        if missing_codes:
            raise ValueError(f"PIT 종목 마스터에 없는 --codes 값: {sorted(missing_codes)}")

    # 개별 종목이 아닌 KRX 시장 메타데이터로 실제 개장일을 확정합니다.
    actual_business_days = get_krx_trading_days(start_date, today_str)

    print(f"\n[*] OHLCV 전체 이력 수집/보정 가동 | 시작일: {start_date} | 종료일: {today_str}")
    failed = []

    for _, row in tqdm(all_stocks.iterrows(), total=len(all_stocks), desc="전체 수집 및 갭 복구"):
        code = row["Code"]
        name = row["Name"]
        is_delisted = row["IsDelisted"]
        delisting_date = pd.to_datetime(row["DelistingDate"], errors="coerce")
        bounds = _collection_bounds(row, start_date, today_str)
        if bounds is None:
            continue
        interval_start, interval_end = bounds
        interval_start_str = interval_start.strftime("%Y-%m-%d")
        interval_end_str = interval_end.strftime("%Y-%m-%d")

        file_path = os.path.join(DATA_DIR, f"{code}.parquet")

        try:
            existing_df = None
            needs_download = True
            fetch_start_str = interval_start_str

            if os.path.exists(file_path):
                existing_df = pd.read_parquet(file_path)
                if not existing_df.empty:
                    existing_df["Date"] = pd.to_datetime(existing_df["Date"])

                    # 1. 중간 누락(Gap) 탐지
                    first_date = existing_df["Date"].min()
                    check_start = max(first_date, interval_start)
                    vwap_incomplete = not _has_complete_actual_vwap(
                        existing_df.loc[existing_df["Date"] >= check_start]
                    )
                    check_days = {
                        d
                        for d in actual_business_days
                        if check_start.date() <= d <= interval_end.date()
                    }
                    existing_dates = set(existing_df["Date"].dt.date)
                    missing_days = check_days - existing_dates

                    last_date = existing_df["Date"].max()
                    fetch_start_str = (last_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

                    # 2. 업데이트 및 보정 필요성 판단
                    if fetch_start_str <= interval_end_str or missing_days or vwap_incomplete:
                        needs_download = True
                        fetch_start_str = interval_start_str
                    else:
                        if repair_only:
                            continue
                        needs_download = False

            if not needs_download:
                continue

            # FDR DataReader로 먼저 고속 시도
            df = _fetch_ohlcv_fdr(code, fetch_start_str, interval_end_str)
            # FDR 실패 시 pykrx로 백업 시도
            if df.empty:
                df = _fetch_ohlcv_pykrx(code, fetch_start_str, interval_end_str)

            if df.empty:
                if existing_df is not None:
                    failed.append(
                        (
                            code,
                            name,
                            is_delisted,
                            interval_start_str,
                            interval_end_str,
                            "No data fetched; existing file preserved",
                        )
                    )
                    continue
                else:
                    failed.append(
                        (
                            code,
                            name,
                            is_delisted,
                            interval_start_str,
                            interval_end_str,
                            "No data fetched",
                        )
                    )
                    continue

            df = df.reset_index()
            df["Date"] = pd.to_datetime(df["Date"])
            df = df[
                df["Date"].ge(interval_start)
                & (pd.isna(delisting_date) | df["Date"].lt(delisting_date))
            ]
            if df.empty:
                failed.append(
                    (
                        code,
                        name,
                        is_delisted,
                        interval_start_str,
                        interval_end_str,
                        "No rows inside listing interval",
                    )
                )
                continue
            df["Code"] = code
            df["Name"] = name
            df["IsDelisted"] = is_delisted

            if existing_df is not None:
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                combined_df["Date"] = pd.to_datetime(combined_df["Date"])
                combined_df = (
                    combined_df.drop_duplicates(subset=["Date"], keep="last")
                    .sort_values(by="Date")
                    .reset_index(drop=True)
                )
            else:
                combined_df = df

            combined_df.to_parquet(file_path, index=False)
            time.sleep(0.05)  # FDR 중심이라 슬립 시간을 줄여 고속 처리 가능

        except Exception as e:
            failed.append(
                (
                    code,
                    name,
                    is_delisted,
                    interval_start_str,
                    interval_end_str,
                    str(e),
                )
            )
            time.sleep(0.1)

    if failed:
        pd.DataFrame(
            failed,
            columns=[
                "Code",
                "Name",
                "IsDelisted",
                "RequestedStart",
                "RequestedEnd",
                "Error",
            ],
        ).to_csv(
            "./data/failed_downloads.csv", index=False, encoding="utf-8-sig"
        )
        print(f"\n⚠️ 수집/보정 중 실패: {len(failed)}개 → ./data/failed_downloads.csv 참고")
        raise RuntimeError(
            "PIT 가격 데이터셋이 불완전합니다. failed_downloads.csv를 해결한 뒤 재실행하세요."
        )

    print("\n✅ 전체 PIT 가격 데이터 다운로드 및 갭 보정 완료.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="KRX OHLCV 하이브리드 고속 수집기 (기능 분리 버전)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # [종목 마스터만 갱신] OHLCV를 받기 전에 PIT 계약 확인
  python price_collector.py --mode master

  # [최초 구축 / 전체 갭 복구] 특정 날짜부터 전체 수집 및 중간 갭 완벽 복구
  python price_collector.py --mode full --start-date 2020-01-01

  # [매일 자동화] 최신일 시세 일괄 동기화 (10초 소요)
  python price_collector.py --mode update
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["master", "full", "update"],
        default="update",
        help="master: PIT 종목 마스터 생성 | full: 전체 이력 다운로드 및 갭 보정 | update: 데일리 초고속 덧붙이기 (기본값)",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        metavar="YYYY-MM-DD",
        help="--mode full 전용: 수집 및 보정 시작일. 미지정 시 실행 연도 기준 최근 10년 적용.",
    )
    parser.add_argument(
        "--repair-only",
        action="store_true",
        help="--mode full 전용: 누락된 갭이 있는 종목만 골라서 복구 작업을 수행합니다.",
    )
    parser.add_argument(
        "--codes",
        default="",
        help="--mode full 전용: 쉼표로 구분한 6자리 코드만 수집/보정",
    )
    args = parser.parse_args()

    if args.mode == "master":
        get_all_tickers()
    elif args.mode == "full":
        start = args.start_date if args.start_date else _DEFAULT_START_DATE
        print(f"[실행] 전체 이력 구축 및 갭 복구 모드 (Full) | 시작일: {start}")
        requested_codes = [code for code in args.codes.split(",") if code.strip()]
        download_ohlcv_full(
            start_date=start,
            repair_only=args.repair_only,
            codes=requested_codes or None,
        )
    else:
        print("[실행] 데일리 업데이트 모드 (Update)")
        update_ohlcv_daily()
