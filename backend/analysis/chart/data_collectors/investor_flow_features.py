"""KRX 투자자별 수급 원천값으로 누수 방지형 외부 feature 파일을 생성합니다."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .trading_calendar import get_krx_trading_days
except ImportError:  # 직접 스크립트 실행
    from trading_calendar import get_krx_trading_days


INVESTOR_FLOW_INPUT_COLUMNS = [
    f"{prefix}{side}Amount"
    for prefix in ("Institution", "Individual", "Foreign")
    for side in ("Buy", "Sell", "NetBuy")
]
INVESTOR_FLOW_FEATURE_COLUMNS = [
    f"{investor}_{metric}"
    for investor in ("institution", "individual", "foreign")
    for metric in (
        "buy_ratio",
        "sell_ratio",
        "net_buy_ratio",
        "net_buy_ratio_5",
        "net_buy_ratio_20",
    )
]


def generate_investor_flow_features(df: pd.DataFrame) -> pd.DataFrame:
    """순매수 대금을 당일 및 5·20일 거래대금으로 정규화합니다."""
    required = {"Date", "Code", "Amount", *INVESTOR_FLOW_INPUT_COLUMNS}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"투자자 수급 feature 필수 컬럼 누락: {sorted(missing)}")

    result = df.copy()
    result["Date"] = pd.to_datetime(result["Date"]).dt.normalize()
    result["Code"] = result["Code"].astype(str).str.zfill(6)
    result = result.sort_values(["Code", "Date"], kind="stable").reset_index(drop=True)
    if result.duplicated(["Code", "Date"]).any():
        raise ValueError("투자자 수급 원천 데이터에 (Code, Date) 중복 행이 있습니다.")

    amount = pd.to_numeric(result["Amount"], errors="coerce")
    if amount.isna().any() or amount.lt(0).any():
        raise ValueError("거래대금은 결측 또는 음수일 수 없습니다.")
    result["Amount"] = amount

    for prefix, feature_name in (
        ("Institution", "institution"),
        ("Individual", "individual"),
        ("Foreign", "foreign"),
    ):
        buy = pd.to_numeric(result[f"{prefix}BuyAmount"], errors="coerce")
        sell = pd.to_numeric(result[f"{prefix}SellAmount"], errors="coerce")
        net_buy = pd.to_numeric(result[f"{prefix}NetBuyAmount"], errors="coerce")
        if buy.isna().any() or sell.isna().any() or net_buy.isna().any():
            raise ValueError(f"{prefix} 매수/매도/순매수대금에 결측값이 있습니다.")
        if buy.lt(0).any() or sell.lt(0).any() or not (net_buy == buy - sell).all():
            raise ValueError(f"{prefix} 순매수대금이 매수대금-매도대금과 일치하지 않습니다.")

        denominator = amount.where(amount.gt(0))
        # 매수 비중: 전체 거래대금 중 해당 투자자 유형이 매수한 금액의 비율
        result[f"{feature_name}_buy_ratio"] = (buy / denominator).fillna(0.0)
        # 매도 비중: 전체 거래대금 중 해당 투자자 유형이 매도한 금액의 비율
        result[f"{feature_name}_sell_ratio"] = (sell / denominator).fillna(0.0)
        # 당일 순매수 강도: 양수면 해당 주체가 순매수, 음수면 순매도
        result[f"{feature_name}_net_buy_ratio"] = (net_buy / denominator).fillna(0.0)

        grouped_net = net_buy.groupby(result["Code"], observed=True)
        grouped_amount = amount.groupby(result["Code"], observed=True)
        for window in (5, 20):
            rolling_net = grouped_net.transform(
                lambda values, _window=window: values.rolling(
                    _window, min_periods=1
                ).sum()
            )
            rolling_amount = grouped_amount.transform(
                lambda values, _window=window: values.rolling(
                    _window, min_periods=1
                ).sum()
            )
            # 누적 순매수 강도: 최근 W일 수급의 방향·지속성을 같은 기간 거래대금으로 정규화
            result[f"{feature_name}_net_buy_ratio_{window}"] = (
                rolling_net / rolling_amount.replace(0, np.nan)
            ).fillna(0.0)

    return result


def _attach_next_trading_day(
    features: pd.DataFrame, trading_days: set
) -> pd.DataFrame:
    """장 마감 후 확정되는 수급값의 최초 사용일을 다음 KRX 개장일로 설정합니다."""
    sessions = pd.DatetimeIndex(sorted(pd.Timestamp(day) for day in trading_days))
    if sessions.empty:
        raise ValueError("AvailableDate 계산용 KRX 거래일이 없습니다.")
    positions = sessions.searchsorted(features["Date"], side="right")
    if (positions >= len(sessions)).any():
        raise ValueError("마지막 수급일 다음의 KRX 개장일을 확인할 수 없습니다.")
    result = features.copy()
    result["AvailableDate"] = sessions.take(positions).to_numpy()
    return result


def build_investor_flow_feature_file(
    raw_dir: str | Path, output_path: str | Path
) -> pd.DataFrame:
    """종목별 raw Parquet을 하나의 표준 외부 feature Parquet으로 변환합니다."""
    raw_paths = sorted(Path(raw_dir).glob("*.parquet"))
    if not raw_paths:
        raise FileNotFoundError(f"원본 Parquet이 없습니다: {raw_dir}")

    inputs = []
    selected_columns = ["Date", "Code", "Amount", *INVESTOR_FLOW_INPUT_COLUMNS]
    for path in raw_paths:
        try:
            inputs.append(pd.read_parquet(path, columns=selected_columns))
        except Exception as error:
            raise ValueError(f"{path.name}: 투자자 수급 원천 컬럼을 읽을 수 없습니다.") from error
    source = pd.concat(inputs, ignore_index=True)
    features = generate_investor_flow_features(source)

    start = features["Date"].min()
    calendar_end = features["Date"].max() + pd.Timedelta(days=14)
    trading_days = get_krx_trading_days(start.date().isoformat(), calendar_end.date().isoformat())
    features = _attach_next_trading_day(features, trading_days)
    output = features[["Date", "Code", "AvailableDate", *INVESTOR_FLOW_FEATURE_COLUMNS]]

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(destination, index=False)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KRX 투자자 수급 외부 feature 생성기")
    parser.add_argument("--raw-dir", default="./data/raw")
    parser.add_argument(
        "--output", default="./data/external/investor_flows.parquet"
    )
    arguments = parser.parse_args()
    built = build_investor_flow_feature_file(arguments.raw_dir, arguments.output)
    print(f"✅ 투자자 수급 feature 저장 완료: {arguments.output} ({len(built):,}행)")
