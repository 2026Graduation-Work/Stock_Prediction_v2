"""NewsAPI.ai(Event Registry) 한국어 뉴스 수집 어댑터.

여러 종목 키워드를 OR 한 번으로 묶어 API 토큰 소모를 제한한다. 본문은
FinBERT 추론을 위한 일시 필드(`summary`)로만 반환하며, 저장 계약은
``news_tracks``에서 별도로 강제한다.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import requests

from .config import SETTINGS

API_URL = "https://eventregistry.org/api/v1/article/getArticles"


class NewsApiAiError(RuntimeError):
    """NewsAPI.ai 호출/응답 오류."""


class NewsApiAiConfigurationError(NewsApiAiError):
    """필수 설정 누락."""


def _iso_date(value: str, field_name: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise NewsApiAiConfigurationError(
            f"{field_name}는 YYYY-MM-DD 형식이어야 합니다."
        ) from exc


def _error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("msg") or error)
    return str(error or "NewsAPI.ai 알 수 없는 오류")


def _normalize_article(row: dict[str, Any]) -> dict[str, str] | None:
    news_id = str(row.get("uri") or "").strip()
    title = str(row.get("title") or "").strip()
    if not news_id or not title:
        return None
    published_at = str(
        row.get("dateTimePub") or row.get("dateTime") or row.get("date") or ""
    ).strip()
    article_date = str(row.get("date") or published_at[:10]).strip()
    source = row.get("source") if isinstance(row.get("source"), dict) else {}
    return {
        "news_id": news_id,
        "title": title,
        "summary": str(row.get("body") or "").strip(),
        "url": str(row.get("url") or "").strip(),
        "press": str(source.get("title") or source.get("uri") or "").strip(),
        "date": article_date,
        "published_at": published_at,
        "event_id": str(row.get("eventUri") or "").strip(),
    }


def fetch_articles(
    keywords: list[str],
    date_start: str,
    date_end: str,
    *,
    page_size: int = 100,
    api_key: str | None = None,
    session: Any = requests,
    timeout: int = 20,
) -> list[dict[str, str]]:
    """한국어 뉴스를 최대 100건 수집해 기존 뉴스 내부 형식으로 반환한다."""
    key = (api_key if api_key is not None else SETTINGS.newsapi_ai_key) or ""
    key = key.strip()
    if not key:
        raise NewsApiAiConfigurationError("NEWSAPI_AI_KEY가 필요합니다.")

    cleaned = list(dict.fromkeys(k.strip() for k in keywords if k and k.strip()))
    if not cleaned:
        raise NewsApiAiConfigurationError("최소 하나의 뉴스 검색어가 필요합니다.")
    start = _iso_date(date_start, "date_start")
    end = _iso_date(date_end, "date_end")
    if start > end:
        raise NewsApiAiConfigurationError("date_start는 date_end보다 늦을 수 없습니다.")
    if not 1 <= page_size <= 100:
        raise NewsApiAiConfigurationError("page_size는 1~100 사이여야 합니다.")

    payload: dict[str, Any] = {
        "action": "getArticles",
        "keyword": cleaned,
        "keywordOper": "or",
        "keywordLoc": "body,title",
        "lang": "kor",
        "dateStart": start,
        "dateEnd": end,
        "dataType": ["news"],
        "isDuplicateFilter": "skipDuplicates",
        "articlesPage": 1,
        "articlesCount": page_size,
        "articlesSortBy": "date",
        "articlesSortByAsc": False,
        "resultType": "articles",
        "articleBodyLen": -1,
        "apiKey": key,
    }
    try:
        response = session.post(API_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        raw = response.json()
    except Exception as exc:
        raise NewsApiAiError(f"NewsAPI.ai 호출에 실패했습니다: {exc}") from exc

    if not isinstance(raw, dict):
        raise NewsApiAiError("NewsAPI.ai 응답이 JSON 객체가 아닙니다.")
    if raw.get("error"):
        raise NewsApiAiError(_error_message(raw))
    articles = raw.get("articles")
    if not isinstance(articles, dict) or not isinstance(articles.get("results"), list):
        raise NewsApiAiError("NewsAPI.ai 응답에 articles.results가 없습니다.")

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in articles["results"]:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_article(item)
        if normalized is None or normalized["news_id"] in seen:
            continue
        seen.add(normalized["news_id"])
        result.append(normalized)
    return result
