"""Merge and normalize manually downloaded BigKinds news workbooks."""

from __future__ import annotations

import argparse
import hashlib
import re
import unicodedata
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

TEXT_DIR = Path(__file__).resolve().parent
DEFAULT_PROCESSED_DIR = TEXT_DIR / "data" / "processed"
# 빅카인즈 원본 위치 — build_news_corpus(CSV 코퍼스)와 load_daily_news(하루치
# point-in-time)가 **같은 디렉터리·같은 파일명 규약**을 본다. 규약이 갈리면 한쪽만
# 파일을 못 찾고 조용히 폴백해 오염된 행이 나온다.
DEFAULT_NEWS_DIR = TEXT_DIR / "data" / "raw"
# 빅카인즈 원본 파일명. 기간은 다운로드 요청값일 뿐 실제 커버리지가 아니므로
# 종목별 디렉터리와 엑셀 일자 컬럼을 정본으로 사용한다.
INPUT_PATTERN = "NewsResult_*.xlsx"
# 이름을 바꿔 보관한 워크북도 하위 호환한다:
#   코드형: {종목코드}_{회사명}_{YYYYMMDD}-{YYYYMMDD}.xlsx
#          (예: 005930_삼성전자_20220101-20221231.xlsx)
#   이름형: {회사명}_{YYYYMMDD}-{YYYYMMDD}.xlsx
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


@lru_cache(maxsize=4)
def _read_workbook_cached(path: Path, mtime: float, size: int) -> pd.DataFrame:
    """_read_workbook의 캐시 래퍼. mtime·size를 키에 넣어 파일이 바뀌면 무효화된다.

    빅카인즈 워크북은 20~25MB라 파싱에 4초 넘게 걸리는데, 파이프라인 1회 실행에
    collect_news + collect_prior_news가 같은 파일을 여러 번 읽는다(실측 8.4초).
    반환 프레임을 호출자가 변형하면 캐시가 오염되므로 _read_workbook이 복사본을 준다.
    """
    return _read_workbook_uncached(path)


def _read_workbook(path: Path) -> pd.DataFrame:
    """빅카인즈 워크북 → 정규화 프레임. 같은 파일 재읽기는 캐시로 피한다."""
    try:
        stat = path.stat()
        return _read_workbook_cached(path, stat.st_mtime, stat.st_size).copy()
    except OSError:  # stat 실패 시 캐시 없이 직접
        return _read_workbook_uncached(path)


def _read_workbook_uncached(path: Path) -> pd.DataFrame:
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


def find_corpus_workbooks(
    raw_dir: Path, ticker: str = "", company_name: str = ""
) -> list[Path]:
    """해당 종목의 빅카인즈 워크북 목록 (하위 디렉터리 포함).

    파일명 규약은 load_daily_news와 동일하다 — 두 소비자가 같은 파일을 본다:
      정본  : raw/{종목코드}/NewsResult_*.xlsx
      호환  : {종목코드}_{회사명}_{YYYYMMDD}-{YYYYMMDD}.xlsx
      호환  : {회사명}_{YYYYMMDD}-{YYYYMMDD}.xlsx

    이름을 바꾼 파일은 종목코드/회사명이 일치하는 것만 고른다. NewsResult 파일은
    `raw/{종목코드}/NewsResult_*.xlsx`처럼 6자리 디렉터리에 있으면 해당 종목만,
    종목을 알 수 없는 루트/일반 디렉터리에 있으면 하위 호환을 위해 포함한다.
    """
    wanted_company = _normalize_company(company_name)
    wanted_code = (ticker or "").strip()
    found: list[Path] = []
    for path in sorted(raw_dir.glob("**/*.xlsx")):
        if path.name.startswith("~$"):
            continue
        if path.name.startswith("NewsResult_"):
            directory_codes = {
                match.group("code")
                for part in path.relative_to(raw_dir).parts[:-1]
                if (match := re.fullmatch(r"(?P<code>\d{6})(?:[_-].*)?", part))
            }
            if not wanted_code or not directory_codes or wanted_code in directory_codes:
                found.append(path)
            continue
        parsed = _parse_workbook_name(path.name)
        if parsed is None:
            continue
        code, company, _, _ = parsed
        code_match = bool(wanted_code) and code == wanted_code
        name_match = bool(wanted_company) and _normalize_company(company) == wanted_company
        if code_match or (not code and name_match) or (not wanted_code and name_match):
            found.append(path)
    return found


def build_news_corpus(
    ticker: str,
    out: Path,
    raw_dir: Path = DEFAULT_NEWS_DIR,
    company_name: str = "",
) -> PreprocessReport:
    """Build the deterministic FinBERT input CSV and return its coverage report.

    기본 입력 위치는 value_pipeline과 동일한 `analysis/text/data/raw/`다 — 두 소비자가
    경로 규약을 공유해야 한 쪽만 파일을 못 찾고 조용히 폴백하는 사고가 없다.
    """
    ticker = ticker.strip()
    if not ticker:
        raise ValueError("ticker는 빈 문자열일 수 없습니다.")

    input_files = find_corpus_workbooks(raw_dir, ticker, company_name)
    if not input_files:
        raise FileNotFoundError(
            f"입력 파일이 없습니다: {raw_dir} 에서 "
            f"'{{종목코드}}_{{회사명}}_{{YYYYMMDD}}-{{YYYYMMDD}}.xlsx'"
            f"(종목코드={ticker}) 또는 '{INPUT_PATTERN}' 을 찾지 못했습니다."
        )

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


@lru_cache(maxsize=64)
def _workbook_date_bounds_cached(
    path: Path, mtime: float, size: int
) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """파일명 대신 실제 수록 일자의 경계를 캐시한다."""
    del mtime, size
    dates = _read_workbook(path)["date"].dropna()
    if dates.empty:
        return None
    return dates.min().normalize(), dates.max().normalize()


def _workbook_date_bounds(path: Path) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    try:
        stat = path.stat()
        return _workbook_date_bounds_cached(path, stat.st_mtime, stat.st_size)
    except OSError:
        dates = _read_workbook(path)["date"].dropna()
        if dates.empty:
            return None
        return dates.min().normalize(), dates.max().normalize()


def find_news_workbooks(
    company_name: str,
    date: str,
    data_dir: Path = DEFAULT_NEWS_DIR,
    ticker: str = "",
) -> list[Path]:
    """실제 수록 기간이 date를 포함하는 해당 종목 워크북을 모두 반환한다.

    빅카인즈 파일명 기간은 다운로드 상한 때문에 실제 수록 기간과 다를 수 있다.
    따라서 파일명은 후보 탐색에만 쓰고, 커버리지는 정규화한 일자 컬럼의 min/max로
    판정한다. 여러 파일이 겹치면 호출자가 파일 간 중복을 제거한다.
    """
    target = pd.Timestamp(date).normalize()
    candidates = find_corpus_workbooks(Path(data_dir), ticker, company_name)
    covered: list[Path] = []
    for path in candidates:
        bounds = _workbook_date_bounds(path)
        if bounds is not None and bounds[0] <= target <= bounds[1]:
            covered.append(path)
    return covered


def find_news_workbook(
    company_name: str,
    date: str,
    data_dir: Path = DEFAULT_NEWS_DIR,
    ticker: str = "",
) -> Path | None:
    """실제 수록 기간이 date를 포함하는 첫 워크북을 반환하는 호환 API.

    겹치는 모든 파일이 필요한 소비자는 find_news_workbooks를 사용한다.
    """
    paths = find_news_workbooks(company_name, date, data_dir, ticker)
    return paths[0] if paths else None


def load_daily_news(
    company_name: str,
    date: str,
    data_dir: Path = DEFAULT_NEWS_DIR,
    limit: int | None = DEFAULT_DAILY_LIMIT,
    body_chars: int = 1000,
    ticker: str = "",
    workbooks: Sequence[Path] | None = None,
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

    workbooks는 같은 요청에서 이미 find_news_workbooks로 찾은 목록을 재사용할 때
    넘긴다. 파일 목록 자체를 전역 캐시하지 않아 실행 중 새 원본을 추가해도 반영된다.

    news_id는 (date, title, press) 해시 폴백까지 포함해 100% 채워지므로
    key_events의 출처 인용(그라운딩) 키로 쓸 수 있다.
    """
    paths = (
        list(workbooks)
        if workbooks is not None
        else find_news_workbooks(company_name, date, data_dir, ticker)
    )
    if not paths:
        return []

    target = pd.Timestamp(date).normalize()
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = _read_workbook(path)
        if "exclude" in frame.columns:
            frame = frame.loc[~frame["exclude"].fillna(False)]
        frame = frame.loc[frame["date"] == target]
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return []

    frame = pd.concat(frames, ignore_index=True)
    frame = _deduplicate(frame)
    frame = frame.sort_values(by="news_id", kind="stable", ignore_index=True)

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
        "--name",
        default="",
        help="회사명 (구버전 파일명 {회사명}_{기간}.xlsx 매칭용)",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_NEWS_DIR,
        help="빅카인즈 워크북을 재귀 탐색할 디렉터리 (기본: analysis/text/data/raw/)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = build_news_corpus(
        ticker=args.ticker, out=args.out, raw_dir=args.raw_dir, company_name=args.name
    )
    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
