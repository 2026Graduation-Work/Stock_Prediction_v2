"""데이터 수집기 (무료 소스 우선).

뉴스   : 빅카인즈 엑셀(data/, preprocess) → 네이버 검색 OpenAPI(키 있으면)
         → HTML 크롤(키 없을 때)
시세   : FinanceDataReader                   (키 불필요)
재무제표: OpenDartReader / Open DART API      (무료 키 필요)

재무는 폴백이 없다. 밸류에이션이 종합점수의 60%를 차지하므로 재무를 못 구하면
FinancialsUnavailableError로 중단한다 — 결측을 중립값으로 메워 그럴듯한 시그널을
만들어내는 것이 아무 시그널도 없는 것보다 나쁘기 때문이다(가짜 SELL 방지).

소셜(SNS/종목토론) 수집은 데이터 확보 난이도로 파이프라인에서 제외되었다
(News + Financial 2개 에이전트만 오케스트레이션).
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import warnings
from email.utils import parsedate_to_datetime
from functools import lru_cache
from pathlib import Path

from .config import SETTINGS

# 빅카인즈 전처리 파이프라인(preprocess.py)의 point-in-time 로더 재사용.
# `python -m value_pipeline.run`(top-level)와 `analysis.text.value_pipeline`
# (namespace 패키지) 두 실행 방식을 모두 지원한다.
try:  # 패키지로 임포트된 경우
    from .. import preprocess
except (ImportError, ValueError):  # text/ 디렉터리에서 top-level 실행된 경우
    import preprocess

SAMPLE_DIR = Path(__file__).parent / "sample_data"
DATA_DIR = Path(__file__).resolve().parents[4] / "data"


class FinancialsUnavailableError(RuntimeError):
    """재무 데이터 확보 실패 (DART 키 없음/조회 실패이며 샘플도 없음)."""


def _load_sample(name: str):
    p = SAMPLE_DIR / name
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


# ── 공통: 날짜 필터 ──────────────────────────────────────────────
def _filter_by_date(items: list[dict], date: str) -> list[dict]:
    """게시일이 해당 날짜(YYYY-MM-DD)인 항목만 남긴다 (point-in-time)."""
    return [it for it in items if str(it.get("date", "")).startswith(date)]


# ── 뉴스 ────────────────────────────────────────────────────────
def collect_news(ticker: str, company_name: str, date: str) -> tuple[list[dict], str]:
    """해당 날짜 '하루치' 기사 전량과 출처 반환.
    각 항목: {news_id, title, summary, url, press, date}.

    빅카인즈 엑셀(data/, preprocess)이 정본이다. 워크북을 찾았는데 그날 기사가
    없으면 그대로 빈 리스트를 준다 — 네이버로 폴백하지 않는다.

    네이버는 과거 날짜 조회가 불안정하고(OpenAPI는 최근 1,000건까지만) news_id도
    없어 그라운딩이 안 된다. 백테스트 행마다 소스가 다르면 피처가 비교 불가능해진다.
    그래서 워크북이 아예 없을 때(=오늘 날짜 조회 같은 실시간 용도)만 폴백한다.

    빅카인즈 경로는 상한 없이(limit=None) 전량을 돌려준다 — 상한은 관련성 필터
    뒤에 news_agent가 적용한다. news_id 정렬순 상위 N건은 임의 표본이기 때문이다.
    """
    query = company_name or ticker
    workbook = None
    try:
        workbook = preprocess.find_news_workbook(query, date, DATA_DIR, ticker)
    except Exception as e:
        warnings.warn(f"빅카인즈 워크북 탐색 실패: {e}", stacklevel=2)

    if workbook is not None:
        try:
            items = preprocess.load_daily_news(
                query, date, DATA_DIR, limit=None, ticker=ticker
            )
            # 워크북이 이 날짜를 커버하므로, 0건이어도 그것이 사실이다.
            # 여기서 네이버로 폴백하면 point-in-time이 깨진다.
            return items, "bigkinds"
        except Exception as e:
            warnings.warn(
                f"빅카인즈 엑셀 뉴스 로드 실패({workbook.name}): {e}", stacklevel=2
            )
    else:
        warnings.warn(
            f"'{query}' {date}를 커버하는 빅카인즈 워크북이 {DATA_DIR}/{ticker}/ "
            f"(또는 평면 {DATA_DIR})에 없습니다. "
            f"기대 위치·파일명: {DATA_DIR}/{ticker}/{{회사명}}_{{YYYYMMDD}}-{{YYYYMMDD}}.xlsx. "
            f"네이버로 폴백하지만 과거 날짜는 신뢰할 수 없습니다.",
            stacklevel=2,
        )

    if SETTINGS.has_naver:
        try:
            items = _fetch_naver_news_api(query, date)
            if items:
                return items, "naver_api"
        except Exception:
            pass
    try:
        items = _crawl_naver_news(query, date)
        if items:
            return items, "naver"
    except Exception:
        pass
    sample = _load_sample(f"{ticker}_news.json") or _load_sample("default_news.json") or []
    return _filter_by_date(sample, date)[:10], "sample"


def _published_at(item: dict) -> str:
    """정렬용 발행 시각 키. 빅카인즈 news_id는 '{언론사코드}.{YYYYMMDDHHMMSS}{일련}'.

    news_id를 그대로 정렬하면 점 앞 언론사 코드가 먼저 비교되어 시간순이 아니라
    언론사 코드순이 된다. 점 뒤를 써야 시간순이 된다.
    포맷이 다르면(generated: 해시 등) 날짜로만 정렬한다.
    """
    nid = str(item.get("news_id", ""))
    if "." in nid:
        tail = nid.rsplit(".", 1)[1]
        if tail[:8].isdigit():
            return tail
    return str(item.get("date", "")).replace("-", "")


def collect_prior_news(
    ticker: str, company_name: str, date: str, count: int
) -> list[dict]:
    """기준일 '직전' 기사를 최신순으로 최대 count건 반환 (staleness 비교용).

    Tetlock(2011)의 staleness는 '직전 10건'과의 단어 중복률이므로 날짜가 아니라
    건수 기준으로 거슬러 올라간다. 기준일 당일은 포함하지 않는다(point-in-time).
    빅카인즈 엑셀만 지원 — 네이버 경로는 과거 조회가 불가능해 빈 리스트를 준다.

    하루치를 다 모은 뒤 발행 시각 역순으로 잘라야 진짜 '직전 N건'이 된다.
    load_daily_news가 news_id(=언론사 코드) 순으로 주므로 그대로 자르면 임의 표본이다.
    """
    query = company_name or ticker
    out: list[dict] = []
    day = dt.date.fromisoformat(date)
    for back in range(1, SETTINGS.staleness_lookback_days + 1):
        prev_day = (day - dt.timedelta(days=back)).isoformat()
        try:
            items = preprocess.load_daily_news(
                query, prev_day, DATA_DIR, limit=None, ticker=ticker
            )
        except Exception as e:
            warnings.warn(f"직전 뉴스 로드 실패({prev_day}): {e}", stacklevel=2)
            continue
        # 그날 안에서 최신순으로 정렬한 뒤 누적 (날짜는 이미 최신 → 과거 순회)
        out.extend(sorted(items, key=_published_at, reverse=True))
        if len(out) >= count:
            break
    return out[:count]


def _strip_tags(s: str) -> str:
    """네이버 API 제목/요약의 <b> 태그·HTML 엔티티 제거."""
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _fetch_naver_news_api(query: str, date: str, limit: int = 10) -> list[dict]:
    """네이버 검색 OpenAPI로 해당 날짜 상위 limit건 수집.

    API는 기간 필터를 지원하지 않으므로 sort=date(최신순)로 페이지를 넘기며
    pubDate가 해당 날짜인 기사만 모으고, 해당 날짜보다 과거가 되면 중단한다.
    (주의: API는 최근 1,000건까지만 반환 → 너무 오래된 날짜는 도달 못 할 수 있음.)
    """
    import requests

    headers = {
        "X-Naver-Client-Id": SETTINGS.naver_client_id,
        "X-Naver-Client-Secret": SETTINGS.naver_client_secret,
    }
    items: list[dict] = []
    for start in range(1, 1001, 100):  # 최대 1,000건(100건 × 10페이지)
        r = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            params={"query": query, "display": 100, "start": start, "sort": "date"},
            headers=headers,
            timeout=10,
        )
        r.raise_for_status()
        arr = r.json().get("items", [])
        if not arr:
            break
        page_days: list[str] = []
        for it in arr:
            try:
                day = parsedate_to_datetime(it["pubDate"]).date().isoformat()
            except Exception:
                continue
            page_days.append(day)
            if day == date:
                items.append({
                    "title": _strip_tags(it.get("title", "")),
                    "summary": _strip_tags(it.get("description", "")),
                    "url": it.get("originallink") or it.get("link", ""),
                    "press": "", "date": date,
                })
                if len(items) >= limit:
                    return items
        if page_days and all(d < date for d in page_days):
            break  # 최신순이라 이 페이지부터 전부 과거 → 해당 날짜 없음
    if not items:
        raise RuntimeError("OpenAPI: 해당 날짜 뉴스 없음")
    return items


def _crawl_naver_news(query: str, date: str, limit: int = 10) -> list[dict]:
    """네이버 뉴스 검색을 해당 날짜 1일로 기간 지정(pd=3, ds=de)해 상위 10건 제목 수집."""
    import requests
    from bs4 import BeautifulSoup

    d_dot = date.replace("-", ".")   # 2026.05.17
    d_num = date.replace("-", "")    # 20260517
    r = requests.get(
        "https://search.naver.com/search.naver",
        params={
            "where": "news", "query": query, "sort": "1",
            "pd": "3", "ds": d_dot, "de": d_dot,          # 기간: 해당 날짜 하루
            "nso": f"so:r,p:from{d_num}to{d_num},a:all",
        },
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    items: list[dict] = []
    for a in soup.select("a.news_tit")[:limit]:
        title = a.get("title") or a.get_text(strip=True)
        if title:
            items.append({"title": title, "summary": "", "url": a.get("href"),
                          "press": "", "date": date})
    if not items:
        raise RuntimeError("해당 날짜 뉴스 없음/파싱 실패 (마크업 변경 가능)")
    return items


# ── 재무제표 + 시세 ─────────────────────────────────────────────
def collect_financials(ticker: str, date: str) -> tuple[dict, str]:
    """표준화 재무 dict와 출처('dart'/'sample') 반환. 시세는 가능하면 FDR로 덮어쓴다.

    재무를 못 구하면 FinancialsUnavailableError. 중립값으로 메우면
    valuation=3.0(결측을 적자로 오인)·health=5.0 → 종합 3.8 → 가짜 SELL이 나온다.
    """
    data: dict | None = None
    source = "sample"
    if SETTINGS.has_dart:
        try:
            data = _fetch_dart_financials(ticker, date)
            source = "dart"
        except Exception as e:
            warnings.warn(f"DART 재무 조회 실패({ticker} {date}): {e}", stacklevel=2)
            data = None
    if not data:
        sample = (
            _load_sample(f"{ticker}_financials.json")
            or _load_sample("default_financials.json")
        )
        if not sample:
            raise FinancialsUnavailableError(
                f"{ticker} {date}: DART 조회 실패/키 없음이며 샘플 재무도 없습니다. "
                f"밸류에이션이 종합점수의 60%를 차지하므로 재무 없이 시그널을 만들지 않습니다."
            )
        data = dict(sample)  # 복사
        source = "sample"

    price = _fetch_price(ticker, date)
    if price is not None:
        data["price"] = price
        data["_price_source"] = "fdr"
    return data, source


# 사업보고서 법정 제출기한: 사업연도 종료(12/31) 후 90일 이내 → 익년 3/31.
# 따라서 4/1부터 직전 사업연도(Y-1) 보고서가 공시되어 있다고 본다.
_REPORT_AVAILABLE_MONTH = 4
_REPORT_AVAILABLE_DAY = 1


def select_fiscal_year(date: str) -> int:
    """기준일(date) 시점에 이미 공시된 가장 최근 사업연도를 반환 (point-in-time).

    12월 결산 법인 기준. 기준일이 4/1 이후면 직전 연도(Y-1), 이전이면 그 전년도(Y-2).
    예) 2022-06-15 → 2021, 2022-02-15 → 2020.

    이게 없으면 과거 시점 피처에 미래 재무가 섞인다(look-ahead bias).
    (ticker, date)로 OHLCV와 조인하는 피처라 미래 정보가 새면 모델 평가가 무효가 된다.

    한계: DART는 해당 사업연도의 '최신 정정본'을 반환하므로 기준일 이후 제출된
    정정공시는 여전히 새어들 수 있다(2차 오차).
    """
    d = dt.date.fromisoformat(date)
    cutoff = dt.date(d.year, _REPORT_AVAILABLE_MONTH, _REPORT_AVAILABLE_DAY)
    return d.year - 1 if d >= cutoff else d.year - 2


@lru_cache(maxsize=16)
def _price_history(ticker: str):
    """종목 전체 시세를 프로세스당 1회만 받는다.

    배치(날짜 루프)에서 날짜마다 120일 창을 재요청하면 수천 콜이 되는데,
    전체 이력은 한 번에 ~수천 행이라 1콜로 끝난다. 실패는 캐시되지 않는다
    (lru_cache는 예외를 저장하지 않음) — 일시 장애가 배치 전체를 오염시키지 않는다.
    """
    import FinanceDataReader as fdr

    return fdr.DataReader(ticker, "2010-01-01")


def _fetch_price(ticker: str, date: str) -> float | None:
    """date 이전(120일 창 안) 마지막 종가 (FinanceDataReader, 키 불필요)."""
    try:
        df = _price_history(ticker)
        if df is None or len(df) == 0:
            return None
        end = dt.date.fromisoformat(date)
        start = end - dt.timedelta(days=SETTINGS.price_lookback_days)
        window = df.loc[start.isoformat() : end.isoformat()]
        if len(window) == 0:
            return None
        return float(window["Close"].iloc[-1])
    except Exception:
        return None


# DART 표준계정 → 표준 키 매핑 (best-effort)
_DART_MAP = {
    "매출액": "revenue", "수익(매출액)": "revenue", "영업수익": "revenue",
    "영업이익": "operating_profit", "영업이익(손실)": "operating_profit",
    "당기순이익": "net_income", "당기순이익(손실)": "net_income",
    "자산총계": "total_assets", "부채총계": "total_liabilities", "자본총계": "total_equity",
    "유동자산": "current_assets", "유동부채": "current_liabilities",
    "재고자산": "inventories", "이익잉여금": "retained_earnings",
}


def _fetch_dart_financials(ticker: str, date: str) -> dict:
    """OpenDartReader로 기준일 시점 공시된 사업보고서 재무제표를 표준 dict로 변환.

    재무는 (종목, 사업연도)당 하나뿐이므로 실제 API 호출은 연도 키로 캐시한다 —
    배치(날짜 루프)에서 같은 사업연도를 날짜마다 재요청하면 10년×365일이
    수만 콜이 되지만, 캐시하면 (종목 × 사업연도) 수만큼만 호출된다.
    호출자가 dict를 변형하므로(price 주입) 캐시 원본은 복사해서 준다.
    """
    year = select_fiscal_year(date)  # 기준일 시점 공시된 사업연도 (look-ahead 방지)
    return dict(_fetch_dart_by_fiscal_year(ticker, year))


@lru_cache(maxsize=64)
def _fetch_dart_by_fiscal_year(ticker: str, year: int) -> dict:
    """DART 사업보고서 1건 조회 (프로세스당 (종목, 연도) 1회).

    DART 계정명/구조가 회사마다 달라 best-effort 매핑이며,
    매핑 실패 항목은 결측(None)으로 남아 지표가 부분 계산된다.
    """
    import OpenDartReader

    dart = OpenDartReader(SETTINGS.dart_api_key)
    fs = dart.finstate_all(ticker, year)  # 연결재무제표 전체 계정
    if fs is None or len(fs) == 0:
        raise RuntimeError("DART 재무제표 없음")

    out: dict = {}
    for _, row in fs.iterrows():
        name = str(row.get("account_nm", "")).strip()
        key = _DART_MAP.get(name)
        if not key or key in out:
            continue
        raw = str(row.get("thstrm_amount", "")).replace(",", "")
        try:
            out[key] = float(raw)
        except ValueError:
            continue
    if "revenue" not in out:
        raise RuntimeError("DART 매핑 실패")

    # 전년 동기 (성장률용). frmtrm_amount는 같은 fs 프레임의 컬럼이라
    # 구조적으로 FY(year-1)이다 — year와의 일관성이 자동 보장된다.
    for _, row in fs.iterrows():
        name = str(row.get("account_nm", "")).strip()
        key = _DART_MAP.get(name)
        if key in ("revenue", "operating_profit", "net_income"):
            raw = str(row.get("frmtrm_amount", "")).replace(",", "")
            try:
                out.setdefault(f"{key}_prev", float(raw))
            except ValueError:
                pass

    # 발행주식수 — 보고서 연도가 아니라 '가장 최근 공시된' 주식총수를 쓴다.
    # FDR 주가는 액면분할이 소급 수정(adjusted)된 값이라, 분할 전 연도의 주식수를
    # 곱하면 시총·per·pbr이 분할 비율만큼 왜곡된다(삼성 50:1 → per 0.28로 계산되는
    # 실사고). 최신 주식수는 수정주가와 같은 분할 기준이므로 정합적이다.
    # 주식수는 시그널이 아니라 단위 환산자라 point-in-time 원칙과 충돌하지 않는다.
    # 한계: 이후 자사주 소각·증자분만큼 오차가 남는다(삼성 2017~18 구간 ±20% 수준
    # — 기존 5,000% 왜곡 대비 허용 가능. VALIDATION 문서 '알려진 한계' 참조).
    shares = _fetch_latest_shares(ticker)
    if shares is not None:
        out["shares_outstanding"] = shares

    # 업종 평균 PER/PBR은 별도 소스 필요 → 샘플 기본값 유지
    sample = _load_sample(f"{ticker}_financials.json") or {}
    out.setdefault("sector_per", sample.get("sector_per"))
    out.setdefault("sector_pbr", sample.get("sector_pbr"))
    out["fiscal_year"] = year  # 감사용: 어느 사업연도를 썼는지 출력에 남긴다
    return out


def _parse_common_shares(frame) -> float | None:
    """DART '주식총수' 응답에서 보통주(없으면 합계) 발행주식수를 뽑는다.

    연도에 따라 응답 포맷이 다르다 — FY2015는 값 없이 '-'만 온다(실측).
    비수치('-', 빈 값) 행은 건너뛰고, 보통주 행을 우선, 없으면 합계 행을 쓴다.
    구분(se) 컬럼 자체가 없는 변형 포맷은 첫 번째 유효 숫자 행으로 폴백한다.
    """
    if frame is None or len(frame) == 0:
        return None

    def _numeric(row) -> float | None:
        raw = str(row.get("istc_totqy", "")).replace(",", "").strip()
        try:
            value = float(raw)
        except ValueError:
            return None
        return value if value > 0 else None

    rows = [row for _, row in frame.iterrows()]
    for want in ("보통주", "합계"):
        for row in rows:
            if want in str(row.get("se", "")) and _numeric(row) is not None:
                return _numeric(row)
    for row in rows:  # se 컬럼이 없는 변형 포맷
        if _numeric(row) is not None:
            return _numeric(row)
    return None


@lru_cache(maxsize=64)
def _fetch_latest_shares(ticker: str) -> float | None:
    """가장 최근 공시된 발행주식수(보통주). 최근 연도부터 6개 연도를 거슬러 찾는다.

    '최근'을 쓰는 이유는 _fetch_dart_by_fiscal_year의 주석 참조(수정주가 정합).
    유효값이 하나도 없으면 None → per/pbr/altman_z가 결측으로 남는다(정직한 결측).
    """
    import OpenDartReader

    dart = OpenDartReader(SETTINGS.dart_api_key)
    start = dt.date.today().year - 1  # 직전 연도 보고서부터 (당해년도는 미공시)
    for year in range(start, start - 6, -1):
        try:
            frame = dart.report(ticker, "주식총수", year)
        except Exception:
            continue
        shares = _parse_common_shares(frame)
        if shares is not None:
            return shares
    warnings.warn(
        f"발행주식수 조회 실패({ticker}): 최근 6개 연도 주식총수에 유효값 없음 "
        f"→ per/pbr/altman_z가 결측이 됩니다.",
        stacklevel=2,
    )
    return None
