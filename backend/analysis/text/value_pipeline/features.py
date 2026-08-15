"""학습용 피처 추출 — 파이프라인 JSON들 → 모델 입력 테이블(CSV).

"무엇을 모델에 넣고 무엇을 빼는가"의 SSOT. 다운스트림(LightGBM)이 JSON을 직접
읽지 않고 이 모듈을 거치게 해서, 피처 선택 규칙이 코드 한 곳에만 존재하게 한다.
일별(ValueSignal)·기간(PeriodValueSignal) 출력을 모두 지원하며, 한 테이블에
두 종류를 섞는 것은 거부한다(집계 단위가 달라 행이 비교 불가능해진다).

빼는 것과 이유:
- composite_score / value_investment_signal / confidence — 다른 피처들의 고정 공식
  조합이라 정보량이 0이다. 넣으면 모델이 수작업 공식을 복제하는 쪽으로 쏠린다.
  (사용자 화면 표시용으로만 쓴다.)
- key_events / reasoning / daily_metrics / validation — 사람이 읽는 텍스트·감사 메타.
- 기간 행의 기사 절대량(article_count 등) — 월 길이·종목별 언론 노출량에 오염.
  avg_daily_articles(일평균)·days_with_articles_ratio(비율)로 대체한다.
  일별 행의 article_count는 이미 '하루' 단위라 그대로 쓴다.

파생 피처:
- financial_age_months — 일별 행에는 스키마에 없으므로 date와 financial_fiscal_year
  로 계산해 붙인다(12월 결산 가정, 기간 행과 동일 정의).

규약:
- validation.ok == False 인 행은 테이블에서 제외한다 (오염 행 하나가 없는 것보다
  나쁘다 — 없으면 결측이지만, 오염 행은 모델이 학습해버린다).
- 결측(None)은 NaN으로 남긴다. 0으로 채우지 않는다 — LightGBM은 NaN을 네이티브로
  처리하며, 0 대치는 '적자'와 '데이터 없음'을 섞는다.

사용:
    python -m value_pipeline.features out/005930/*.json --out features_daily.csv
    python -m value_pipeline.features 005930_2022-01.json --out features_monthly.csv
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from collections.abc import Sequence
from pathlib import Path

_METRIC_COLUMNS = ["per", "pbr", "roe", "revenue_growth", "debt_ratio", "altman_z"]

# ── 기간(PeriodValueSignal) 테이블 ─────────────────────────────────
PERIOD_KEY_COLUMNS = ["ticker", "period", "period_start", "period_end"]
PERIOD_FEATURE_COLUMNS = [
    "news_sentiment",
    "news_impact_score",
    "news_sentiment_std",
    "news_staleness",
    "avg_daily_articles",
    "days_with_articles_ratio",  # 파생: days_with_articles / period_days
    "financial_health_score",
    "valuation_score",
    "financial_age_months",
    *_METRIC_COLUMNS,
]

# ── 일별(ValueSignal) 테이블 ───────────────────────────────────────
DAILY_KEY_COLUMNS = ["ticker", "date"]
DAILY_FEATURE_COLUMNS = [
    "news_sentiment",
    "news_impact_score",
    "news_sentiment_std",
    "news_staleness",
    "article_count",  # 하루 단위라 절대량 그대로 (일평균과 동일 의미)
    "financial_health_score",
    "valuation_score",
    "financial_age_months",  # 파생: date − 사업연도 종료월
    *_METRIC_COLUMNS,
]


def _nan_if_none(v: float | int | None) -> float:
    return float(v) if v is not None else math.nan


def _financial_age_months(asof_date: str, fiscal_year: int | None) -> float:
    """기준일과 사업연도(12월 결산) 종료월의 간격(개월). 결측이면 NaN."""
    if fiscal_year is None:
        return math.nan
    d = dt.date.fromisoformat(asof_date)
    return (d.year - int(fiscal_year)) * 12 + d.month - 12


def signal_kind(signal: dict) -> str:
    """'period' | 'daily' — 출력 JSON의 종류 판별."""
    return "period" if "period" in signal else "daily"


def columns_for(kind: str) -> tuple[list[str], list[str]]:
    if kind == "period":
        return PERIOD_KEY_COLUMNS, PERIOD_FEATURE_COLUMNS
    return DAILY_KEY_COLUMNS, DAILY_FEATURE_COLUMNS


def extract_row(signal: dict) -> dict | None:
    """ValueSignal/PeriodValueSignal dict → 조인 키 + 피처의 평탄 dict.

    validation.ok가 False면 None을 반환한다 — 호출자가 그 행을 버리게 한다.
    """
    validation = signal.get("validation") or {}
    if not validation.get("ok", False):
        return None

    kind = signal_kind(signal)
    key_columns, feature_columns = columns_for(kind)
    row: dict = {k: signal[k] for k in key_columns}

    period_days = signal.get("period_days") or 0
    metrics = signal.get("financial_metrics") or {}
    asof = signal["period_end"] if kind == "period" else signal["date"]
    for col in feature_columns:
        if col == "days_with_articles_ratio":
            value = (
                signal.get("days_with_articles", 0) / period_days if period_days else None
            )
        elif col == "financial_age_months" and col not in signal:
            value = _financial_age_months(asof, signal.get("financial_fiscal_year"))
        elif col in metrics:
            value = metrics.get(col)
        else:
            value = signal.get(col)
        row[col] = _nan_if_none(value)
    return row


def build_feature_table(paths: Sequence[Path]) -> tuple[list[dict], list[str], str]:
    """JSON 파일들 → (피처 행 리스트, 제외 사유 리스트, 테이블 종류).

    테이블 종류는 첫 파일로 정해지며, 다른 종류의 행은 제외된다 —
    일별과 기간 행은 집계 단위가 달라 한 테이블에서 비교 불가능하다.
    """
    rows: list[dict] = []
    skipped: list[str] = []
    mode = ""
    for p in sorted(paths):
        path = Path(p)
        signal = json.loads(path.read_text(encoding="utf-8"))
        kind = signal_kind(signal)
        if not mode:
            mode = kind
        elif kind != mode:
            skipped.append(f"{path.name}: {mode} 테이블에 {kind} 행 혼입 — 제외")
            continue
        row = extract_row(signal)
        if row is None:
            errors = (signal.get("validation") or {}).get("errors", [])
            skipped.append(f"{path.name}: 검증 실패 행 제외 — {errors[:1]}")
            continue
        rows.append(row)
    return rows, skipped, mode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="파이프라인 JSON(일별/기간) → 학습용 피처 테이블(CSV)"
    )
    ap.add_argument("inputs", nargs="+", help="ValueSignal/PeriodValueSignal JSON 파일들")
    ap.add_argument("--out", default="features.csv", help="출력 CSV 경로")
    args = ap.parse_args(argv)

    # 배치 manifest(_manifest_*.json)는 피처가 아니므로 자동 제외
    inputs = [Path(p) for p in args.inputs if not Path(p).name.startswith("_manifest")]
    rows, skipped, mode = build_feature_table(inputs)
    for msg in skipped:
        print(f"[제외] {msg}", file=sys.stderr)
    if not rows:
        print("[오류] 사용할 수 있는 행이 없습니다.", file=sys.stderr)
        return 1

    import pandas as pd

    key_columns, feature_columns = columns_for(mode)
    frame = pd.DataFrame(rows, columns=key_columns + feature_columns)
    frame.to_csv(args.out, index=False, encoding="utf-8")
    print(
        f"[저장] {Path(args.out).resolve()} — {mode} {len(rows)}행 × "
        f"피처 {len(feature_columns)}개 (제외 {len(skipped)}행)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
