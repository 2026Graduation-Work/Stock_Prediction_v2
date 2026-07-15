"""Merge and normalize manually downloaded BigKinds news workbooks."""

from __future__ import annotations

import argparse
import hashlib
import re
import unicodedata
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

TEXT_DIR = Path(__file__).resolve().parent
DEFAULT_RAW_DIR = TEXT_DIR / "data" / "raw"
DEFAULT_PROCESSED_DIR = TEXT_DIR / "data" / "processed"
# 빅카인즈 원본을 회사·연도별로 저장하는 저장소 루트의 data/ 폴더.
# (파일명 규약: {회사명}_{YYYYMMDD}-{YYYYMMDD}.xlsx)
DEFAULT_NEWS_DIR = TEXT_DIR.parents[2] / "data"
INPUT_PATTERN = "NewsResult_*.xlsx"
# 뉴스 워크북 파일명 규약 (신규 우선, 구버전 호환):
#   신규 : {종목코드}_{회사명}_{YYYYMMDD}-{YYYYMMDD}.xlsx
#          (예: 005930_삼성전자_20220101-20221231.xlsx)
#   구버전: {회사명}_{YYYYMMDD}-{YYYYMMDD}.xlsx
#          (예: 삼성전자_20220101-20221231.xlsx)
_NEWS_WORKBOOK_RE_CODE = re.compile(
    r"(?P<code>[^_]+)_(?P<company>.+)_(?P<start>\d{8})-(?P<end>\d{8})\.xlsx$"
)
_NEWS_WORKBOOK_RE_PLAIN = re.compile(
    r"(?P<company>.+)_(?P<start>\d{8})-(?P<end>\d{8})\.xlsx$"
)
OUTPUT_COLUMNS = ["news_id", "date", "title", "body", "press", "ticker"]
# point-in-time 로더가 하루치로 반환하는 기사 최대 건수(감성 안정성용).
DEFAULT_DAILY_LIMIT = 30
# "분석제외 여부" 컬럼에서 제외로 간주하는 표기(소문자 비교).
_EXCLUDE_TOKENS = {"y", "1", "true", "제외", "분석제외", "exclude", "o"}

# BigKinds export headers have changed over time. Keep every supported spelling here.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "news_id": ("뉴스 식별자", "뉴스식별자", "뉴스 ID", "뉴스ID", "기사 식별자"),
    "date": ("일자", "날짜", "작성일", "게시일", "보도일"),
    "title": ("제목", "뉴스 제목", "기사 제목"),
    "body": ("본문", "뉴스 본문", "기사 본문", "내용"),
    "keywords": ("키워드", "뉴스 키워드", "특성추출(가중치순 상위 50개)"),
    "press": ("언론사", "매체명", "신문사", "뉴스 제공처"),
    # 아래 두 개는 선택 컬럼(있으면 활용, 없으면 무시) — 필수 검증에서 제외됨.
    "url": ("URL", "url", "주소", "링크"),
    "exclude": ("분석제외 여부", "분석제외여부", "분석 제외 여부"),
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

    # 선택 컬럼: URL과 분석제외 여부(있으면 활용, 없으면 기본값).
    url_column = columns["url"]
    normalized["url"] = (
        frame[url_column].map(_clean_text) if url_column is not None else ""
    )
    exclude_column = columns["exclude"]
    if exclude_column is None:
        normalized["exclude"] = False
    else:
        normalized["exclude"] = (
            frame[exclude_column].map(_clean_text).str.lower().isin(_EXCLUDE_TOKENS)
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


# ── Point-in-time 뉴스 로더 ────────────────────────────────────────
# value_pipeline(News Agent)이 "특정 회사·특정 날짜 하루치" 뉴스를 빅카인즈
# 원본에서 바로 뽑아 쓰기 위한 공개 API. build_news_corpus와 동일한 컬럼
# 정규화(_read_workbook)·중복 제거(_deduplicate) 로직을 재사용해 전처리 규칙을
# 한 곳에서 관리한다.


def _normalize_company(name: str) -> str:
    return unicodedata.normalize("NFC", (name or "").strip())


def _parse_workbook_name(name: str) -> tuple[str, str, str, str] | None:
    """파일명 → (종목코드, 회사명, 시작일, 종료일). 코드가 없는 구버전이면 코드는 ""."""
    match = _NEWS_WORKBOOK_RE_CODE.fullmatch(name)
    if match:
        return (
            match.group("code"),
            match.group("company"),
            match.group("start"),
            match.group("end"),
        )
    match = _NEWS_WORKBOOK_RE_PLAIN.fullmatch(name)
    if match:
        return "", match.group("company"), match.group("start"), match.group("end")
    return None


def find_news_workbook(
    company_name: str,
    date: str,
    data_dir: Path = DEFAULT_NEWS_DIR,
    ticker: str = "",
) -> Path | None:
    """뉴스 워크북 중 date가 기간에 포함되고, 종목코드 또는 회사명이 일치하는 파일 반환.

    파일명은 신규({코드}_{명}_{기간})·구버전({명}_{기간})을 모두 인식한다.
    ticker(종목코드)가 주어지면 코드 일치를, 아니면 회사명(NFC) 일치를 사용한다.
    """
    target_day = date.replace("-", "")
    wanted_company = _normalize_company(company_name)
    wanted_code = (ticker or "").strip()
    for path in sorted(Path(data_dir).glob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        parsed = _parse_workbook_name(path.name)
        if parsed is None:
            continue
        code, company, start, end = parsed
        if not (start <= target_day <= end):
            continue
        code_match = bool(wanted_code) and code == wanted_code
        name_match = bool(wanted_company) and _normalize_company(company) == wanted_company
        if code_match or name_match:
            return path
    return None


def load_daily_news(
    company_name: str,
    date: str,
    data_dir: Path = DEFAULT_NEWS_DIR,
    limit: int | None = DEFAULT_DAILY_LIMIT,
    body_chars: int = 1000,
    ticker: str = "",
) -> list[dict]:
    """해당 회사·날짜(YYYY-MM-DD) 하루치 뉴스를 표준 dict 리스트로 반환.

    각 항목: {news_id, title, summary(=본문 일부), url, press, date}.
    - _read_workbook로 빅카인즈 컬럼을 정규화하고,
    - '분석제외 여부'가 켜진 기사를 제거한 뒤,
    - _deduplicate로 중복(식별자/폴백키)을 정리하고,
    - 해당 날짜만 남겨 news_id 순으로 상위 limit건을 돌려준다.
    파일이 없으면 빈 리스트(→ 상위 호출자가 다음 소스로 폴백).

    limit=None이면 그날 기사를 전부 돌려준다. news_id 정렬순 상위 N건은
    관련성과 무관한 사실상 임의 표본이므로, 하루치를 전부 받아 관련성으로
    거르는 호출자(news_agent)가 상한을 직접 적용한다.

    news_id는 (date, title, press) 해시 폴백까지 포함해 100% 채워지므로
    key_events의 출처 인용(그라운딩) 키로 쓸 수 있다.
    """
    path = find_news_workbook(company_name, date, data_dir, ticker)
    if path is None:
        return []

    frame = _read_workbook(path)
    if "exclude" in frame.columns:
        frame = frame.loc[~frame["exclude"].fillna(False)]
    if frame.empty:
        return []

    frame = _deduplicate(frame)
    day_str = frame["date"].dt.strftime("%Y-%m-%d")
    frame = frame.loc[day_str == date].sort_values(
        by="news_id", kind="stable", ignore_index=True
    )

    items: list[dict] = []
    for _, row in frame.iterrows():
        title = str(row.get("title", "")).strip()
        if not title:
            continue
        body = str(row.get("body", "")).strip()
        items.append(
            {
                "news_id": str(row.get("news_id", "")).strip(),
                "title": title,
                "summary": body[:body_chars],
                "url": str(row.get("url", "")).strip(),
                "press": str(row.get("press", "")).strip(),
                "date": date,
            }
        )
        if limit is not None and len(items) >= limit:
            break
    return items


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
