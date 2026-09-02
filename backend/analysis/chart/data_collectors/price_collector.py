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

# 데이터 저장 경로 설정
DATA_DIR = "./data/raw"
os.makedirs(DATA_DIR, exist_ok=True)

# 기본 전체 수집 시작일 (최근 10년 기준, 실행 연도 자동 반영)
_DEFAULT_START_DATE = f"{datetime.now().year - 10}-01-01"


def get_all_tickers() -> pd.DataFrame:
    """
    KOSPI, KOSDAQ 활성 종목 및 KRX-DELISTING(상장폐지) 종목 리스트를 병합합니다.
    """
    print("수집 대상 종목 리스트 구성 중...")

    # 1. 활성 상장 종목 (KOSPI & KOSDAQ)
    try:
        kospi = fdr.StockListing("KOSPI")
        kosdaq = fdr.StockListing("KOSDAQ")
        active = pd.concat([kospi, kosdaq], ignore_index=True)
        active = active[["Code", "Name"]].drop_duplicates()
        active["IsDelisted"] = False
        print(f"  [활성] KOSPI/KOSDAQ 총 {len(active)}개")
    except Exception as e:
        print(f"  [활성] 리스트 수집 실패: {e}")
        active = pd.DataFrame(columns=["Code", "Name", "IsDelisted"])

    # 2. 상장폐지 종목 (KRX-DELISTING)
    try:
        raw_delisted = fdr.StockListing("KRX-DELISTING")
        delisted = raw_delisted.rename(columns={"Symbol": "Code"})[
            ["Code", "Name"]
        ].drop_duplicates()
        delisted["IsDelisted"] = True
        print(f"  [상폐] KRX-DELISTING 총 {len(delisted)}개")
    except Exception as e:
        print(f"  [상폐] 리스트 수집 실패: {e}")
        delisted = pd.DataFrame(columns=["Code", "Name", "IsDelisted"])

    # 3. 병합
    all_stocks = pd.concat([active, delisted], ignore_index=True)
    all_stocks = all_stocks.drop_duplicates(subset=["Code"], keep="first")
    all_stocks["Code"] = all_stocks["Code"].str.zfill(6)
    print(f"  [합계] 총 {len(all_stocks)}개 종목")

    all_stocks.to_csv("./data/ticker_metadata.csv", index=False, encoding="utf-8-sig")
    print("  종목 메타데이터 저장 완료 (./data/ticker_metadata.csv)")
    return all_stocks


def _fetch_ohlcv_pykrx(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    pykrx로 수정주가(adjusted=True) 기준 일봉 OHLCV를 가져옵니다.
    등락률(Change)은 % 단위를 유지합니다.
    """
    start_yyyymmdd = start_date.replace("-", "")
    end_yyyymmdd = end_date.replace("-", "")

    df = krx.get_market_ohlcv_by_date(
        start_yyyymmdd,
        end_yyyymmdd,
        code,
        adjusted=True,
    )
    if df.empty:
        return df

    df = df.rename(
        columns={
            "시가": "Open",
            "고가": "High",
            "저가": "Low",
            "종가": "Close",
            "거래량": "Volume",
            "등락률": "Change",
        }
    )
    df.index.name = "Date"
    # 등락률의 NaN 값 보정
    if "Change" in df.columns:
        df["Change"] = df["Change"].fillna(0.0)
    return df


def _fetch_ohlcv_fdr(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    FinanceDataReader로 수정주가 기준 일봉 OHLCV를 가져옵니다.
    FDR의 Change(소수점 단위)를 퍼센트(%) 단위로 변환하여 pykrx와 스케일을 통일합니다.
    """
    try:
        df = fdr.DataReader(code, start_date, end_date)
        if df.empty:
            return df

        # 필요한 컬럼만 추출 및 리네임
        df = df[["Open", "High", "Low", "Close", "Volume", "Change"]]
        # 등락률 단위를 %로 변환 (FDR은 0.0132 형태, pykrx는 1.32 형태)
        df["Change"] = df["Change"].fillna(0.0) * 100.0
        df.index.name = "Date"
        return df
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
        required_columns = {"Code", "Open", "High", "Low", "Close", "Volume", "Change"}
        missing_columns = required_columns - set(market_snapshot.columns)
        if missing_columns:
            raise RuntimeError(f"FDR 전 종목 시세 필수 컬럼 누락: {sorted(missing_columns)}")
        market_snapshot = market_snapshot[market_snapshot["Volume"] > 0].copy()
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

            new_row = pd.DataFrame(
                [
                    {
                        "Date": actual_date,
                        "Open": float(row["Open"]),
                        "High": float(row["High"]),
                        "Low": float(row["Low"]),
                        "Close": float(row["Close"]),
                        "Volume": float(row["Volume"]),
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

                    if actual_date in existing["Date"].values:
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


def download_ohlcv_full(start_date: str = _DEFAULT_START_DATE, repair_only: bool = False):
    """
    [전체 이력 수집 및 정밀 보정 함수]
    지정된 start_date부터 오늘까지 전체 종목의 과거 가격 이력을 다운로드하여 구축합니다.
    또한, 이미 구축된 파일 중 중간 영업일(Gap) 누락을 감지하고 메워줍니다.
    속도와 안정성을 위해 FDR DataReader를 기본으로 사용하고 pykrx를 백업으로 사용합니다.
    """
    all_stocks = get_all_tickers()
    today_str = datetime.now().strftime("%Y-%m-%d")

    # 개별 종목이 아닌 KRX 시장 메타데이터로 실제 개장일을 확정합니다.
    actual_business_days = get_krx_trading_days(start_date, today_str)

    print(f"\n[*] OHLCV 전체 이력 수집/보정 가동 | 시작일: {start_date} | 종료일: {today_str}")
    failed = []

    dict(zip(all_stocks["Code"], all_stocks["Name"], strict=False))

    for _, row in tqdm(all_stocks.iterrows(), total=len(all_stocks), desc="전체 수집 및 갭 복구"):
        code = row["Code"]
        name = row["Name"]
        is_delisted = row["IsDelisted"]

        if is_delisted:
            continue

        file_path = os.path.join(DATA_DIR, f"{code}.parquet")

        try:
            existing_df = None
            needs_download = True
            fetch_start_str = start_date

            if os.path.exists(file_path):
                existing_df = pd.read_parquet(file_path)
                if not existing_df.empty:
                    existing_df["Date"] = pd.to_datetime(existing_df["Date"])

                    # 1. 중간 누락(Gap) 탐지
                    first_date = existing_df["Date"].min()
                    check_start = max(first_date, pd.to_datetime(start_date))
                    check_days = {d for d in actual_business_days if d >= check_start.date()}
                    existing_dates = set(existing_df["Date"].dt.date)
                    missing_days = check_days - existing_dates

                    last_date = existing_df["Date"].max()
                    fetch_start_str = (last_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

                    # 2. 업데이트 및 보정 필요성 판단
                    if not is_delisted and (fetch_start_str <= today_str or missing_days):
                        needs_download = True
                        # 누락이 많거나 업데이트 범위가 넓으면 해당 종목만 start_date부터 전체를 다시 받아 머지
                        fetch_start_str = start_date
                    else:
                        if repair_only:
                            continue
                        needs_download = False

            if not needs_download:
                continue

            # FDR DataReader로 먼저 고속 시도
            df = _fetch_ohlcv_fdr(code, fetch_start_str, today_str)
            # FDR 실패 시 pykrx로 백업 시도
            if df.empty:
                df = _fetch_ohlcv_pykrx(code, fetch_start_str, today_str)

            if df.empty:
                if existing_df is not None:
                    # 기존 데이터는 보존
                    continue
                else:
                    failed.append((code, name, is_delisted, "No data fetched"))
                    continue

            df = df.reset_index()
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
            failed.append((code, name, is_delisted, str(e)))
            time.sleep(0.1)

    if failed:
        pd.DataFrame(failed, columns=["Code", "Name", "IsDelisted", "Error"]).to_csv(
            "./data/failed_downloads.csv", index=False, encoding="utf-8-sig"
        )
        print(f"\n⚠️ 수집/보정 중 실패: {len(failed)}개 → ./data/failed_downloads.csv 참고")

    print("\n✅ 전체 가격 데이터 다운로드 및 갭 보정 완료.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="KRX OHLCV 하이브리드 고속 수집기 (기능 분리 버전)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # [최초 구축 / 전체 갭 복구] 특정 날짜부터 전체 수집 및 중간 갭 완벽 복구
  python price_collector.py --mode full --start-date 2020-01-01

  # [매일 자동화] 최신일 시세 일괄 동기화 (10초 소요)
  python price_collector.py --mode update
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["full", "update"],
        default="update",
        help="full: 전체 이력 다운로드 및 갭 보정 | update: 데일리 초고속 덧붙이기 (기본값)",
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
    args = parser.parse_args()

    if args.mode == "full":
        start = args.start_date if args.start_date else _DEFAULT_START_DATE
        print(f"[실행] 전체 이력 구축 및 갭 복구 모드 (Full) | 시작일: {start}")
        download_ohlcv_full(start_date=start, repair_only=args.repair_only)
    else:
        print("[실행] 데일리 업데이트 모드 (Update)")
        update_ohlcv_daily()
