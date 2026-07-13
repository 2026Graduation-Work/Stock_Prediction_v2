"""Merge and normalize manually downloaded BigKinds news workbooks."""

from __future__ import annotations

import argparse
import hashlib
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

TEXT_DIR = Path(__file__).resolve().parent
DEFAULT_RAW_DIR = TEXT_DIR / "data" / "raw"
DEFAULT_PROCESSED_DIR = TEXT_DIR / "data" / "processed"
INPUT_PATTERN = "NewsResult_*.xlsx"
OUTPUT_COLUMNS = ["news_id", "date", "title", "body", "press", "ticker"]

# BigKinds export headers have changed over time. Keep every supported spelling here.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "news_id": ("뉴스 식별자", "뉴스식별자", "뉴스 ID", "뉴스ID", "기사 식별자"),
    "date": ("일자", "날짜", "작성일", "게시일", "보도일"),
    "title": ("제목", "뉴스 제목", "기사 제목"),
    "body": ("본문", "뉴스 본문", "기사 본문", "내용"),
    "keywords": ("키워드", "뉴스 키워드", "특성추출(가중치순 상위 50개)"),
    "press": ("언론사", "매체명", "신문사", "뉴스 제공처"),
}


class BigKindsSchemaError(ValueError):
    """Raised when a BigKinds workbook cannot satisfy the input contract."""


@dataclass(frozen=True)
class PreprocessReport:
    input_files: int
    raw_rows: int
    deduplicated_rows: int
    date_min: str
    date_max: str
    missing_dates: tuple[str, ...]
    output_path: Path


def _normalized_columns(columns: pd.Index) -> dict[str, object]:
    return {str(column).strip(): column for column in columns}


def _find_column(columns: dict[str, object], field: str) -> object | None:
    return next((columns[alias] for alias in COLUMN_ALIASES[field] if alias in columns), None)


def _resolve_columns(frame: pd.DataFrame, source: Path) -> dict[str, object | None]:
    columns = _normalized_columns(frame.columns)
    resolved = {field: _find_column(columns, field) for field in COLUMN_ALIASES}

    missing = [field for field in ("date", "title", "press") if resolved[field] is None]
    if resolved["body"] is None and resolved["keywords"] is None:
        missing.append("body 또는 keywords")

    if missing:
        expected = "; ".join(
            f"{field}={COLUMN_ALIASES[field]}"
            for field in ("date", "title", "body", "keywords", "press")
        )
        available = ", ".join(repr(column) for column in frame.columns)
        raise BigKindsSchemaError(
            f"{source.name}: 필수 컬럼을 찾을 수 없습니다: {', '.join(missing)}. "
            f"지원 컬럼명: {expected}. 실제 컬럼: [{available}]"
        )

    return resolved


def _clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _read_workbook(path: Path) -> pd.DataFrame:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Workbook contains no default style")
        frame = pd.read_excel(path, engine="openpyxl", dtype=object)

    columns = _resolve_columns(frame, path)
    normalized = pd.DataFrame(index=frame.index)

    news_id_column = columns["news_id"]
    if news_id_column is None:
        normalized["news_id"] = ""
    else:
        normalized["news_id"] = frame[news_id_column].map(_clean_text)

    normalized["date"] = pd.to_datetime(
        frame[columns["date"]].map(_clean_text),
        errors="coerce",
        format="mixed",
        yearfirst=True,
    ).dt.normalize()
    invalid_dates = normalized["date"].isna()
    if invalid_dates.any():
        rows = [str(index + 2) for index in frame.index[invalid_dates][:5]]
        raise BigKindsSchemaError(
            f"{path.name}: 날짜로 변환할 수 없는 값이 있습니다(엑셀 행 {', '.join(rows)})."
        )

    normalized["title"] = frame[columns["title"]].map(_clean_text)
    normalized["press"] = frame[columns["press"]].map(_clean_text)

    body_column = columns["body"]
    keyword_column = columns["keywords"]
    if body_column is None:
        normalized["body"] = frame[keyword_column].map(_clean_text)
    else:
        normalized["body"] = frame[body_column].map(_clean_text)
        if keyword_column is not None:
            empty_body = normalized["body"].eq("")
            normalized.loc[empty_body, "body"] = frame.loc[empty_body, keyword_column].map(
                _clean_text
            )

    return normalized


def _fallback_key(frame: pd.DataFrame) -> pd.Series:
    dates = frame["date"].dt.strftime("%Y-%m-%d")
    return dates + "\x1f" + frame["title"] + "\x1f" + frame["press"]


def _generated_news_id(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"generated:{digest}"


def _deduplicate(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    working["_fallback_key"] = _fallback_key(working)
    has_news_id = working["news_id"].ne("")

    identified = working.loc[has_news_id].drop_duplicates(subset="news_id", keep="first")
    unidentified = working.loc[~has_news_id]

    # An unidentified copy of an article already retained by ID is still a duplicate.
    identified_fallback_keys = set(identified["_fallback_key"])
    unidentified = unidentified.loc[
        ~unidentified["_fallback_key"].isin(identified_fallback_keys)
    ].drop_duplicates(subset="_fallback_key", keep="first")
    unidentified = unidentified.copy()
    unidentified["news_id"] = unidentified["_fallback_key"].map(_generated_news_id)

    return pd.concat([identified, unidentified], ignore_index=True).drop(columns="_fallback_key")


def _resolve_output_path(out: Path) -> Path:
    return out if out.is_absolute() else DEFAULT_PROCESSED_DIR / out


def build_news_corpus(ticker: str, out: Path, raw_dir: Path = DEFAULT_RAW_DIR) -> PreprocessReport:
    """Build the deterministic FinBERT input CSV and return its coverage report."""
    ticker = ticker.strip()
    if not ticker:
        raise ValueError("ticker는 빈 문자열일 수 없습니다.")

    input_files = [
        path
        for path in sorted(raw_dir.glob(f"**/{INPUT_PATTERN}"))
        if not path.name.startswith("~$")
    ]
    if not input_files:
        raise FileNotFoundError(f"입력 파일이 없습니다: {raw_dir / '**' / INPUT_PATTERN}")

    frames = [_read_workbook(path) for path in input_files]
    raw_rows = sum(len(frame) for frame in frames)
    merged = pd.concat(frames, ignore_index=True)
    if merged.empty:
        raise ValueError("입력 엑셀에 뉴스 행이 없습니다.")

    deduplicated = _deduplicate(merged)
    deduplicated["ticker"] = ticker
    deduplicated["date"] = deduplicated["date"].dt.strftime("%Y-%m-%d")
    deduplicated = deduplicated[OUTPUT_COLUMNS].sort_values(
        by=["date", "news_id"], kind="stable", ignore_index=True
    )

    date_min = deduplicated["date"].min()
    date_max = deduplicated["date"].max()
    covered_dates = pd.DatetimeIndex(pd.to_datetime(deduplicated["date"].unique()))
    expected_dates = pd.date_range(date_min, date_max, freq="D")
    missing_dates = tuple(
        timestamp.strftime("%Y-%m-%d") for timestamp in expected_dates.difference(covered_dates)
    )

    output_path = _resolve_output_path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    deduplicated.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
    )

    return PreprocessReport(
        input_files=len(input_files),
        raw_rows=raw_rows,
        deduplicated_rows=len(deduplicated),
        date_min=date_min,
        date_max=date_max,
        missing_dates=missing_dates,
        output_path=output_path,
    )


def print_report(report: PreprocessReport) -> None:
    print(f"입력 파일 수: {report.input_files}")
    print(f"원본 총 건수: {report.raw_rows}")
    print(f"dedup 후 건수: {report.deduplicated_rows}")
    print(f"실제 수록 기간: {report.date_min} ~ {report.date_max}")
    print(f"일자 구멍 개수: {len(report.missing_dates)}")
    if report.missing_dates:
        print("경고: 뉴스가 0건인 일자가 있습니다. 파이프라인은 계속 진행합니다.")
        print(f"일자 구멍: {', '.join(report.missing_dates)}")
    print(f"산출물: {report.output_path}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="빅카인즈 엑셀을 FinBERT 입력 CSV로 변환")
    parser.add_argument("--ticker", required=True, help="모든 출력 행에 주입할 종목 코드")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("news_corpus.csv"),
        help="산출물 파일명 또는 절대 경로 (기본: data/processed/news_corpus.csv)",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="NewsResult_*.xlsx를 재귀 탐색할 원본 디렉터리",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = build_news_corpus(ticker=args.ticker, out=args.out, raw_dir=args.raw_dir)
    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
