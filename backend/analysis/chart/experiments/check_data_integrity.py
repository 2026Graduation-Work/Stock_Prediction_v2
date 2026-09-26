import os

import pandas as pd
from tqdm import tqdm

try:
    from data_collectors.trading_calendar import get_krx_trading_days
    from point_in_time_universe import intervals_overlapping, load_security_master
except ImportError:  # 직접 스크립트 실행
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from data_collectors.trading_calendar import get_krx_trading_days
    from point_in_time_universe import intervals_overlapping, load_security_master

DATA_DIR = "./data/raw"
SECURITY_MASTER_PATH = "./data/universe/security_master.parquet"


def check_integrity():
    if not os.path.exists(SECURITY_MASTER_PATH):
        raise FileNotFoundError("security master가 없습니다. --mode master를 먼저 실행하세요.")

    master = load_security_master(SECURITY_MASTER_PATH)
    target_date = pd.Timestamp.now().normalize()
    start_check_date = target_date - pd.Timedelta(45, unit="D")
    all_stocks = intervals_overlapping(master, start_check_date, target_date)

    print(f"총 {len(all_stocks)}개 종목 검사 시작...")

    missing_files = []
    not_uptodate = []
    has_gaps = []

    actual_business_days = get_krx_trading_days(
        start_check_date.strftime("%Y-%m-%d"), target_date.strftime("%Y-%m-%d")
    )
    target_date = pd.Timestamp(max(actual_business_days))

    print(
        f"검사 대상 영업일 수 ({start_check_date.date()} ~ {target_date.date()}): "
        f"{len(actual_business_days)}일"
    )

    for _, row in tqdm(all_stocks.iterrows(), total=len(all_stocks)):
        code = row["Code"]
        name = row["Name"]
        delisting_date = row["DelistingDate"]
        is_active = pd.isna(delisting_date) or delisting_date > target_date

        file_path = os.path.join(DATA_DIR, f"{code}.parquet")

        if not os.path.exists(file_path):
            missing_files.append((code, name))
            continue

        try:
            df = pd.read_parquet(file_path)
            if df.empty:
                missing_files.append((code, name))
                continue

            df["Date"] = pd.to_datetime(df["Date"])
            last_date = df["Date"].max()

            # 활성 종목인데 최신일(2026-06-12)이 아니면 체크
            if is_active and last_date < target_date:
                not_uptodate.append((code, name, last_date.strftime("%Y-%m-%d")))

            # 최근 1개월(2026-05-01 이후) 내 중간 누락 영업일이 있는지 체크 (상장폐지 종목 제외)
            if is_active:
                recent_df = df[df["Date"] >= start_check_date]
                existing_dates = set(recent_df["Date"].dt.date)

                # 상장일이 2026-05-01 이후인 신규 상장 종목 고려 (최초 Date 이후만 비교)
                first_date = df["Date"].min()
                if first_date > start_check_date:
                    check_days = {d for d in actual_business_days if d >= first_date.date()}
                else:
                    check_days = actual_business_days

                missing_days = check_days - existing_dates
                if missing_days:
                    has_gaps.append((code, name, sorted(list(missing_days))))

        except Exception as e:
            print(f"에러 발생 [{code}]: {e}")

    print("\n=== 검증 결과 ===")
    print(f"1. 파일 누락 (기간 중 PIT 종목): {len(missing_files)}개")
    for c, n in missing_files[:10]:
        print(f"   - {c}: {n}")
    if len(missing_files) > 10:
        print(f"   ...외 {len(missing_files) - 10}개")

    print(f"\n2. 최신 거래일({target_date.date()}) 미달성 (활성 종목): {len(not_uptodate)}개")
    for c, n, ld in not_uptodate[:10]:
        print(f"   - {c}: {n} (최종일: {ld})")
    if len(not_uptodate) > 10:
        print(f"   ...외 {len(not_uptodate) - 10}개")

    print(f"\n3. 최근 1개월 내 중간 누락(Gap) 존재 (활성 종목): {len(has_gaps)}개")
    for c, n, gaps in has_gaps[:10]:
        gap_strs = [g.strftime("%Y-%m-%d") for g in gaps[:3]]
        print(f"   - {c}: {n} (누락: {gap_strs} 등 {len(gaps)}일)")
    if len(has_gaps) > 10:
        print(f"   ...외 {len(has_gaps) - 10}개")

    if missing_files or not_uptodate:
        raise RuntimeError(
            "PIT 원본 데이터가 불완전합니다: "
            f"파일 누락={len(missing_files)}, 최신일 미달={len(not_uptodate)}"
        )


if __name__ == "__main__":
    check_integrity()
