from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from analysis.text.value_pipeline import news_run, news_tracks

KST = ZoneInfo("Asia/Seoul")


def _articles() -> list[dict]:
    return [
        {
            "news_id": "s1",
            "title": "삼성전자 반도체 실적 개선",
            "summary": "영업이익이 증가했다.",
            "url": "https://example.com/s1",
            "press": "한국경제",
            "date": "2026-09-18",
            "published_at": "2026-09-18T01:20:00Z",
            "event_id": "event-1",
        },
        {
            "news_id": "s2",
            "title": "삼성전자 수요 둔화 우려",
            "summary": "메모리 가격 약세가 이어졌다.",
            "url": "https://example.com/s2",
            "press": "연합뉴스",
            "date": "2026-09-17",
            "published_at": "2026-09-17T04:00:00Z",
            "event_id": "event-2",
        },
        {
            "news_id": "h1",
            "title": "SK하이닉스 신규 공장 투자",
            "summary": "생산능력을 확대한다.",
            "url": "https://example.com/h1",
            "press": "매일경제",
            "date": "2026-09-18",
            "published_at": "2026-09-18T00:30:00Z",
            "event_id": "event-3",
        },
    ]


def _fixed_scores(texts: list[str]) -> tuple[list[float], str]:
    scores = []
    for text in texts:
        scores.append(0.8 if "개선" in text else -0.2)
    return scores, "kr-finbert"


def _assert_no_raw_text_fields(value: object) -> None:
    if isinstance(value, dict):
        assert "body" not in value
        assert "summary" not in value
        assert "content" not in value
        for child in value.values():
            _assert_no_raw_text_fields(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_raw_text_fields(child)


def test_live_track_uses_shared_sentiment_and_omits_article_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API 본문은 추론에만 쓰고 저장 결과에는 남기지 않는다."""
    monkeypatch.setattr(news_tracks.sentiment, "score_texts", _fixed_scores)
    as_of = datetime(2026, 9, 18, 12, 0, tzinfo=KST)

    out = news_tracks.build_live_track(
        _articles(), "005930", "삼성전자", as_of=as_of
    )

    assert out["track"] == "live"
    assert out["source"] == "newsapi_ai"
    assert out["backend"] == "kr-finbert"
    assert out["status"] == "ok"
    assert out["coverage"]["fetched_count"] == 3
    assert out["coverage"]["relevant_count"] == 2
    assert out["coverage"]["publisher_count"] == 2
    assert out["today"]["article_count"] == 1
    assert out["today"]["sentiment_mean"] == 0.8
    assert out["recent_7d"]["article_count"] == 2
    assert out["recent_7d"]["sentiment_mean"] == pytest.approx(0.3)
    assert [row["news_id"] for row in out["articles"]] == ["s1", "s2"]
    assert out["articles"][0]["sentiment_score"] == 0.8
    _assert_no_raw_text_fields(out)


def test_historical_track_groups_daily_points_with_the_same_scoring_core(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """과거/실시간 트랙의 숫자가 서로 다른 산식으로 갈라지는 회귀를 막는다."""
    monkeypatch.setattr(news_tracks.sentiment, "score_texts", _fixed_scores)

    out = news_tracks.build_historical_track(
        _articles(),
        "005930",
        "삼성전자",
        date_start="2026-09-17",
        date_end="2026-09-18",
    )

    assert out["track"] == "historical"
    assert out["source"] == "bigkinds"
    assert out["backend"] == "kr-finbert"
    assert [point["date"] for point in out["timeline"]] == [
        "2026-09-17",
        "2026-09-18",
    ]
    assert out["timeline"][0]["sentiment_mean"] == -0.2
    assert out["timeline"][1]["sentiment_mean"] == 0.8
    _assert_no_raw_text_fields(out)


def test_write_track_json_never_persists_transient_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(news_tracks.sentiment, "score_texts", _fixed_scores)
    out = news_tracks.build_live_track(
        _articles(),
        "005930",
        "삼성전자",
        as_of=datetime(2026, 9, 18, 12, 0, tzinfo=KST),
    )
    path = tmp_path / "live.json"

    news_tracks.write_track_json(out, path)

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted == out
    _assert_no_raw_text_fields(persisted)


class _CountingFetcher:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(
        self,
        keywords: list[str],
        date_start: str,
        date_end: str,
        *,
        page_size: int,
    ) -> object:
        self.calls.append(
            {
                "keywords": keywords,
                "date_start": date_start,
                "date_end": date_end,
                "page_size": page_size,
            }
        )
        return news_run.newsapi_ai.ArticleBatch(
            articles=_articles(),
            total_results=150,
            returned_count=3,
            pages=2,
            truncated=True,
        )


def test_live_cycle_fetches_once_for_multiple_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """한 시간 주기마다 종목 수만큼 토큰을 쓰는 회귀를 막는다."""
    monkeypatch.setattr(news_tracks.sentiment, "score_texts", _fixed_scores)
    fetcher = _CountingFetcher()

    outputs = news_run.run_live_cycle(
        {"005930": "삼성전자", "000660": "SK하이닉스"},
        fetcher=fetcher,
        as_of=datetime(2026, 9, 18, 12, 0, tzinfo=KST),
    )

    assert len(fetcher.calls) == 1
    assert fetcher.calls[0]["keywords"] == ["삼성전자", "SK하이닉스"]
    assert fetcher.calls[0]["date_start"] == "2026-09-11"
    assert fetcher.calls[0]["date_end"] == "2026-09-18"
    assert set(outputs) == {"005930", "000660"}
    assert outputs["005930"]["coverage"]["relevant_count"] == 2
    assert outputs["000660"]["coverage"]["relevant_count"] == 1
    assert outputs["005930"]["coverage"]["provider_total_results"] == 150
    assert outputs["005930"]["coverage"]["provider_truncated"] is True
    assert outputs["005930"]["status"] == "partial"


def test_live_track_groups_utc_boundary_by_kst_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """00:00~08:59 KST 기사를 UTC 전날이 아닌 한국의 오늘로 센다."""
    monkeypatch.setattr(news_tracks.sentiment, "score_texts", _fixed_scores)
    article = {
        "news_id": "midnight",
        "title": "삼성전자 실적 개선",
        "summary": "실적이 개선됐다.",
        "url": "https://example.com/midnight",
        "press": "한국경제",
        "date": "2026-09-17",
        "published_at": "2026-09-17T15:30:00Z",
        "event_id": "event-midnight",
    }

    out = news_tracks.build_live_track(
        [article],
        "005930",
        "삼성전자",
        as_of=datetime(2026, 9, 18, 0, 45, tzinfo=KST),
    )

    assert out["today"]["article_count"] == 1
    assert out["timeline"][-1]["date"] == "2026-09-18"
    assert out["articles"][0]["date"] == "2026-09-18"


def test_live_command_retries_transient_failure_without_overwriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    sleeps: list[int] = []

    def fake_cycle(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise news_run.newsapi_ai.NewsApiAiError("HTTP 429")
        raise KeyboardInterrupt

    monkeypatch.setattr(news_run, "run_live_cycle", fake_cycle)
    monkeypatch.setattr(news_run.time, "sleep", sleeps.append)
    args = type(
        "Args",
        (),
        {
            "target": [("005930", "삼성전자")],
            "page_size": 100,
            "out_dir": tmp_path,
            "watch": True,
            "interval_minutes": 60,
        },
    )()

    with pytest.raises(KeyboardInterrupt):
        news_run._live_command(args)

    assert calls == 2
    assert sleeps == [60]
    assert list(tmp_path.iterdir()) == []


def test_live_command_rejects_nonpositive_interval(tmp_path: Path) -> None:
    args = type(
        "Args",
        (),
        {
            "target": [("005930", "삼성전자")],
            "page_size": 100,
            "out_dir": tmp_path,
            "watch": True,
            "interval_minutes": 0,
        },
    )()

    with pytest.raises(ValueError, match="interval-minutes"):
        news_run._live_command(args)


def test_historical_cycle_loads_bigkinds_days_and_builds_one_track(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(news_tracks.sentiment, "score_texts", _fixed_scores)
    calls: list[str] = []

    def loader(company, date_start, date_end, data_dir, *, ticker):
        calls.append(f"{date_start}:{date_end}")
        return _articles()

    out = news_run.run_historical_cycle(
        "005930",
        "삼성전자",
        "2026-09-17",
        "2026-09-18",
        loader=loader,
        data_dir=tmp_path,
    )

    assert calls == ["2026-09-17:2026-09-18"]
    assert out["track"] == "historical"
    assert out["coverage"]["fetched_count"] == 3
    assert out["coverage"]["relevant_count"] == 2
