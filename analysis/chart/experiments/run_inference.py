import os
import glob
import argparse
import pandas as pd
import numpy as np
from tqdm import tqdm
from datetime import datetime
from multiprocessing import cpu_count
from concurrent.futures import ProcessPoolExecutor

# 프로젝트 루트 경로 설정 및 core 모듈 임포트
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from core.inference import predict_success_probability

# 각 워커 프로세스에서 재사용될 전역 모델 리스트
_models = []

def init_worker(model_paths):
    """
    워커 프로세스가 생성될 때 단 1회 실행되어 모델들을 로드합니다.
    """
    global _models
    import lightgbm as lgb
    _models = [lgb.Booster(model_file=p) for p in model_paths]

def process_ticker(file_path, target_date, threshold):
    """
    개별 종목 데이터를 로드하여 core.inference.predict_success_probability를 수행합니다.
    """
    global _models
    ticker = os.path.basename(file_path).replace(".parquet", "")
    try:
        df = pd.read_parquet(file_path)
        if df.empty:
            return None
            
        df['Date'] = pd.to_datetime(df['Date'])
        
        # --- 최적화: 피처 생성에 필요한 최근 85 영업일 분량만 슬라이스 ---
        if target_date:
            target_dt = pd.to_datetime(target_date)
            df_slice = df[df['Date'] <= target_dt].tail(85).copy()
            if df_slice.empty or df_slice['Date'].max() != target_dt:
                return None
        else:
            df_slice = df.tail(85).copy()
            
        if len(df_slice) < 65:
            return None
            
        # 3. core/inference.py에 내장된 추론 함수 직접 사용
        ticker_probs = []
        for model in _models:
            prob_series = predict_success_probability(df_slice, model)
            last_date = df_slice['Date'].max()
            prob_val = prob_series.loc[last_date]
            ticker_probs.append(prob_val)
            
        mean_prob = np.mean(ticker_probs)
        last_row = df_slice.iloc[-1]
        
        return {
            "Code": ticker,
            "Name": last_row.get("Name", ticker),
            "Date": last_row["Date"].strftime("%Y-%m-%d"),
            "Close": last_row["Close"],
            "Volume": last_row["Volume"],
            "Change": last_row.get("Change", 0.0),
            "Success_Prob": mean_prob,
            "Signal": "BUY" if mean_prob >= threshold else "HOLD"
        }
    except Exception as e:
        return None

def parse_args():
    parser = argparse.ArgumentParser(description="실서비스 환경 전체 종목 대상 병렬 추론 및 매수 시그널 생성 스크립트")
    parser.add_argument(
        "--model-path",
        type=str,
        default=os.path.join(project_root, "core", "models", "65dc5055_fold0_model.txt"),
        help="학습 완료된 단일 모델 파일 경로 (기본값: fold0)"
    )
    parser.add_argument(
        "--ensemble",
        action="store_true",
        help="활성화 시 core/models/ 디렉토리 내의 모든 fold 모델 예측값을 앙상블(평균)하여 추론합니다."
    )
    parser.add_argument(
        "--target-date",
        type=str,
        default=None,
        help="예측을 수행할 기준 영업일 (YYYY-MM-DD 포맷). 미지정 시 각 종목 데이터의 가장 최신 영업일을 기준으로 추론합니다."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="매수 시그널을 생성할 최소 상승 성공(Success) 확률 임계값 (0.0 ~ 1.0)"
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=30,
        help="터미널에 출력할 예측 확률 상위 종목 수"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(project_root, "experiments", "results"),
        help="추론 예측 결과를 저장할 디렉토리 경로"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="병렬 연산에 사용할 워커(프로세스) 수. 지정하지 않으면 CPU 코어 수에 맞춰 동적 결정됩니다."
    )
    return parser.parse_args()

def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    
    # 1. 로드할 모델 파일 경로 목록 수집
    if args.ensemble:
        model_dir = os.path.dirname(args.model_path)
        pattern = "65dc5055_fold*.txt"
        model_paths = glob.glob(os.path.join(model_dir, pattern))
        if not model_paths:
            print(f"❌ [Error] '{model_dir}'에서 패턴 '{pattern}'에 매칭되는 모델을 찾을 수 없습니다.")
            return
        print(f"📦 앙상블 모드: 총 {len(model_paths)}개의 Fold 모델을 로드하여 병렬 워커에 주입합니다...")
    else:
        model_paths = [args.model_path]
        if not os.path.exists(args.model_path):
            print(f"❌ [Error] 지정한 모델 파일 ({args.model_path})을 찾을 수 없습니다.")
            return
        print(f"📦 단일 모델 모드: {os.path.basename(args.model_path)}를 로드하여 병렬 워커에 주입합니다...")
        
    model_paths = sorted(model_paths)
    
    # 2. 데이터 파일 목록 수집
    raw_dir = os.path.join(project_root, "data", "raw")
    data_files = glob.glob(os.path.join(raw_dir, "*.parquet"))
    
    if not data_files:
        print(f"❌ [Error] 추론할 데이터 파일이 '{raw_dir}' 경로에 존재하지 않습니다.")
        return
        
    num_workers = args.workers if args.workers else max(1, cpu_count() - 1)
    print(f"📊 총 {len(data_files)}개 종목 추론 시작 (병렬 워커 수: {num_workers}, core.inference.predict_success_probability 활용)...")
    
    results = []
    
    # 3. ProcessPoolExecutor를 사용하여 병렬 추론 연산 수행
    with ProcessPoolExecutor(max_workers=num_workers, initializer=init_worker, initargs=(model_paths,)) as executor:
        futures = [
            executor.submit(process_ticker, f, args.target_date, args.threshold)
            for f in data_files
        ]
        
        for fut in tqdm(futures, desc="병렬 추론 진행 중"):
            res = fut.result()
            if res is not None:
                results.append(res)
                
    if not results:
        print("❌ [Error] 유효한 피처를 추출한 종목이 하나도 없습니다. 데이터 수집 상태나 기준일(--target-date)을 확인하세요.")
        return
        
    # 4. 결과 DataFrame 생성 및 정렬
    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values(by="Success_Prob", ascending=False).reset_index(drop=True)
    
    # 5. 파일 저장
    unique_dates = result_df['Date'].unique()
    file_date_suffix = unique_dates[0].replace("-", "") if len(unique_dates) == 1 else datetime.now().strftime("%Y%m%d")
    output_file = os.path.join(args.output_dir, f"inference_result_{file_date_suffix}.csv")
    result_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    
    print(f"\n💾 추론 결과 저장 완료: {output_file}")
    
    # 6. 상위 종목 화면 출력
    print("\n" + "="*85)
    print(f"📊 상승 예측 확률 상위 {args.top_n}개 종목 리스트 (기준 영업일: {unique_dates if len(unique_dates) > 1 else unique_dates[0]})")
    print("="*85)
    print(f"{'순위':<4} | {'종목코드':<8} | {'종목명':<16} | {'기준일':<10} | {'종가':<10} | {'전일대비':<8} | {'상승성공확률':<12} | {'시그널':<6}")
    print("-"*85)
    
    top_df = result_df.head(args.top_n)
    for idx, row in top_df.iterrows():
        change_pct = f"{row['Change']:+.2f}%" if 'Change' in row else "N/A"
        name_trunc = row['Name'][:12] if len(row['Name']) <= 12 else row['Name'][:10] + ".."
        print(f"{idx+1:<4} | {row['Code']:<8} | {name_trunc:<16} | {row['Date']:<10} | {int(row['Close']):,d}원 | {change_pct:<8} | {row['Success_Prob']*100:.2f}% | {row['Signal']:<6}")
    print("="*85)
    
    buy_signals = result_df[result_df['Signal'] == "BUY"]
    print(f"💡 총 {len(result_df)}개 종목 중, 매수 임계치({args.threshold*100:.1f}%)를 초과하여 'BUY' 시그널이 발생한 종목: {len(buy_signals)}개")
    print("="*85)

if __name__ == "__main__":
    main()
