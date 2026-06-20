import argparse
import glob
import os

# 프로젝트 루트 경로 설정 및 core 모듈 임포트
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from multiprocessing import cpu_count

import pandas as pd
from tqdm import tqdm

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

# 각 워커 프로세스에서 재사용될 전역 모델 객체
_model = None


def init_worker(model_path):
    """
    워커 프로세스가 생성될 때 단 1회 실행되어 단일 모델을 로드합니다.
    """
    global _model
    import lightgbm as lgb

    _model = lgb.Booster(model_file=model_path)


def process_ticker(file_path, target_date, threshold):
    """
    개별 종목 데이터를 로드하여 core.inference.predict_success_probability를 수행합니다.
    전처리 및 피처 생성은 core.inference에 위임합니다.
    """
    global _model
    ticker = os.path.basename(file_path).replace(".parquet", "")
    try:
        df = pd.read_parquet(file_path)
        if df.empty:
            return None

        df["Date"] = pd.to_datetime(df["Date"])

        # 피처 생성에 필요한 최근 85 영업일 분량만 슬라이스 (성능 최적화)
        if target_date:
            target_dt = pd.to_datetime(target_date)
            df_slice = df[df["Date"] <= target_dt].tail(85).copy()
            if df_slice.empty or df_slice["Date"].max() != target_dt:
                return None
        else:
            df_slice = df.tail(85).copy()

        if len(df_slice) < 65:
            return None

        # core.inference에 전처리 및 예측을 위임 — 중복 로직 없음
        from core.inference import predict_success_probability

        prob_series = predict_success_probability(df_slice, _model)

        if prob_series.empty:
            return None

        # 기준일(마지막 날짜)의 Success 확률 추출
        success_prob = float(prob_series.iloc[-1])
        last_row = df_slice.iloc[-1]

        return {
            "Code": ticker,
            "Name": last_row.get("Name", ticker),
            "Date": last_row["Date"].strftime("%Y-%m-%d"),
            "Close": last_row["Close"],
            "Volume": last_row["Volume"],
            "Change": last_row.get("Change", 0.0),
            "Success_Prob": success_prob,
            "Signal": "BUY" if success_prob >= threshold else "HOLD",
        }
    except Exception:
        return None


def parse_args():
    parser = argparse.ArgumentParser(
        description="전체 종목 대상 병렬 추론 및 매수 시그널 생성 스크립트 (단일 모델)"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=os.path.join(project_root, "core", "models", "65dc5055_fold0_model.txt"),
        help="학습 완료된 모델 파일 경로 (기본값: core/models/65dc5055_fold0_model.txt)",
    )
    parser.add_argument(
        "--target-date",
        type=str,
        default=None,
        help="예측 기준 영업일 (YYYY-MM-DD). 미지정 시 각 종목의 최신 영업일 기준.",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.5, help="매수 시그널 최소 확률 임계값 (0.0 ~ 1.0)"
    )
    parser.add_argument("--top-n", type=int, default=30, help="터미널에 출력할 상위 종목 수")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(project_root, "experiments", "results"),
        help="추론 결과 저장 디렉토리",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="병렬 워커 수. 미지정 시 CPU 코어 수에 맞춰 동적 결정.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    # 1. 모델 파일 존재 확인
    if not os.path.exists(args.model_path):
        print(f"❌ [Error] 모델 파일을 찾을 수 없습니다: {args.model_path}")
        return
    print(f"📦 모델 로드: {os.path.basename(args.model_path)}")

    # 2. 데이터 파일 목록 수집
    raw_dir = os.path.join(project_root, "data", "raw")
    data_files = glob.glob(os.path.join(raw_dir, "*.parquet"))

    if not data_files:
        print(f"❌ [Error] 추론할 데이터 파일이 없습니다: {raw_dir}")
        return

    num_workers = args.workers if args.workers else max(1, cpu_count() - 1)
    print(f"📊 총 {len(data_files)}개 종목 추론 시작 (병렬 워커 수: {num_workers})...")

    results = []

    # 3. ProcessPoolExecutor로 병렬 추론 수행
    with ProcessPoolExecutor(
        max_workers=num_workers, initializer=init_worker, initargs=(args.model_path,)
    ) as executor:
        futures = [
            executor.submit(process_ticker, f, args.target_date, args.threshold) for f in data_files
        ]
        for fut in tqdm(futures, desc="병렬 추론 진행 중"):
            res = fut.result()
            if res is not None:
                results.append(res)

    if not results:
        print(
            "❌ [Error] 유효한 추론 결과가 없습니다. 데이터 수집 상태나 --target-date를 확인하세요."
        )
        return

    # 4. 결과 정렬 및 저장
    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values(by="Success_Prob", ascending=False).reset_index(drop=True)

    unique_dates = result_df["Date"].unique()
    file_date_suffix = (
        unique_dates[0].replace("-", "")
        if len(unique_dates) == 1
        else datetime.now().strftime("%Y%m%d")
    )
    output_file = os.path.join(args.output_dir, f"inference_result_{file_date_suffix}.csv")
    result_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\n💾 추론 결과 저장 완료: {output_file}")

    # 5. 상위 종목 출력
    print("\n" + "=" * 85)
    print(
        f"📊 상승 예측 확률 상위 {args.top_n}개 종목 (기준 영업일: {unique_dates[0] if len(unique_dates) == 1 else '복수'})"
    )
    print("=" * 85)
    print(
        f"{'순위':<4} | {'종목코드':<8} | {'종목명':<16} | {'기준일':<10} | {'종가':<10} | {'전일대비':<8} | {'상승성공확률':<12} | {'시그널':<6}"
    )
    print("-" * 85)

    for idx, row in result_df.head(args.top_n).iterrows():
        change_pct = f"{row['Change']:+.2f}%" if "Change" in row else "N/A"
        name_trunc = row["Name"][:12] if len(row["Name"]) <= 12 else row["Name"][:10] + ".."
        print(
            f"{idx + 1:<4} | {row['Code']:<8} | {name_trunc:<16} | {row['Date']:<10} | {int(row['Close']):,d}원 | {change_pct:<8} | {row['Success_Prob'] * 100:.2f}% | {row['Signal']:<6}"
        )

    print("=" * 85)
    buy_signals = result_df[result_df["Signal"] == "BUY"]
    print(
        f"💡 총 {len(result_df)}개 종목 중 'BUY' 시그널 발생: {len(buy_signals)}개 (임계치: {args.threshold * 100:.1f}%)"
    )
    print("=" * 85)


if __name__ == "__main__":
    main()
