"""value_pipeline 오케스트레이션 검증.

- 빅카인즈 point-in-time 뉴스 로더(preprocess.load_daily_news)
- 소셜 제거 후 News + Financial 2-에이전트 + 규칙 기반 validation LangGraph
- AGENTS.md 계약: 점수 산출 100% 결정론, LLM은 라벨·추출·설명만

검증 기준 전문: backend/analysis/text/VALUE_PIPELINE_VALIDATION.md
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest
from analysis.text import preprocess as pp
from analysis.text.value_pipeline import agents as agents_mod
from analysis.text.value_pipeline import collectors as collectors_mod
from analysis.text.value_pipeline import graph as graph_mod
from analysis.text.value_pipeline import metrics as metrics_mod
from analysis.text.value_pipeline import schema as schema_mod
from analysis.text.value_pipeline import staleness as staleness_mod


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """테스트는 .env의 실제 GEMINI_API_KEY에 영향받지 않아야 한다(헤르메틱).

    환경변수 patch로는 안 된다 — config.load_dotenv()가 import 시점에 .env를
    주입하고, SETTINGS는 frozen dataclass, get_llm()은 lru_cache라서 무력하다.
    agents가 부르는 structured 자체를 막아야 한다.
    """
    monkeypatch.setattr(agents_mod, "structured", lambda prompt, schema: None)


def _write_bigkinds(path: Path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_excel(path, index=False, engine="openpyxl")


def _fin(**over) -> dict:
    """정합적인 표준 재무 dict (항등식 자산=부채+자본 성립)."""
    base = {
        "revenue": 3.0e14, "revenue_prev": 2.7e14, "net_income": 4.0e13,
        "total_assets": 4.0e14, "total_liabilities": 1.0e14, "total_equity": 3.0e14,
        "current_assets": 2.0e14, "current_liabilities": 5.0e13,
        "shares_outstanding": 5.97e9, "price": 60000.0,
        "sector_per": 15.0, "sector_pbr": 1.5, "company_name": "삼성전자",
        "fiscal_year": 2021,
    }
    base.update(over)
    return base


def _patch_collectors(monkeypatch: pytest.MonkeyPatch, news: list, fin: dict) -> None:
    monkeypatch.setattr(
        graph_mod.collectors, "collect_news", lambda t, n, d: (news, "bigkinds")
    )
    monkeypatch.setattr(
        graph_mod.collectors, "collect_prior_news", lambda t, n, d, c: []
    )
    monkeypatch.setattr(
        graph_mod.collectors, "collect_financials", lambda t, d: (fin, "dart")
    )


# ── Point-in-time 뉴스 로더 ────────────────────────────────────────
def test_load_daily_news_filters_date_dedup_and_exclusion(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_bigkinds(
        data_dir / "005930_삼성전자_20220101-20221231.xlsx",
        [
            {"뉴스 식별자": "n1", "일자": 20220615, "언론사": "매일경제",
             "제목": "삼성전자 흑자 전환", "본문": "영업이익이 크게 늘었다.",
             "URL": "http://x/n1", "분석제외 여부": ""},
            {"뉴스 식별자": "n2", "일자": 20220615, "언론사": "한국경제",
             "제목": "메모리 시황 개선", "본문": "가격 반등.",
             "URL": "http://x/n2", "분석제외 여부": ""},
            # 같은 식별자 중복 → dedup
            {"뉴스 식별자": "n1", "일자": 20220615, "언론사": "매일경제",
             "제목": "삼성전자 흑자 전환", "본문": "영업이익이 크게 늘었다.",
             "URL": "http://x/n1", "분석제외 여부": ""},
            # 다른 날짜 → 필터
            {"뉴스 식별자": "n3", "일자": 20220616, "언론사": "서울경제",
             "제목": "다음날 기사", "본문": "본문", "URL": "http://x/n3",
             "분석제외 여부": ""},
            # 분석제외 → 제거
            {"뉴스 식별자": "n4", "일자": 20220615, "언론사": "이데일리",
             "제목": "제외 대상 기사", "본문": "본문", "URL": "http://x/n4",
             "분석제외 여부": "Y"},
        ],
    )

    items = pp.load_daily_news("삼성전자", "2022-06-15", data_dir=data_dir)

    assert [it["title"] for it in items] == ["삼성전자 흑자 전환", "메모리 시황 개선"]
    assert all(it["date"] == "2022-06-15" for it in items)
    assert items[0]["summary"] == "영업이익이 크게 늘었다."  # 본문이 summary로 매핑
    assert items[0]["url"] == "http://x/n1"
    assert items[0]["press"] == "매일경제"


def test_load_daily_news_emits_news_id_for_grounding(tmp_path: Path) -> None:
    """key_events 출처 인용(그라운딩)의 앵커 — 100% 채워져야 한다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_bigkinds(
        data_dir / "005930_삼성전자_20220101-20221231.xlsx",
        [
            {"뉴스 식별자": "n1", "일자": 20220615, "언론사": "매일경제",
             "제목": "삼성전자 흑자", "본문": "본문", "URL": "", "분석제외 여부": ""},
            # 식별자 없음 → generated: 해시 폴백
            {"뉴스 식별자": "", "일자": 20220615, "언론사": "한국경제",
             "제목": "식별자 없는 기사", "본문": "본문", "URL": "", "분석제외 여부": ""},
        ],
    )
    items = pp.load_daily_news("삼성전자", "2022-06-15", data_dir=data_dir)
    assert len(items) == 2
    assert all(it["news_id"] for it in items)  # 결측 없음
    assert any(it["news_id"].startswith("generated:") for it in items)


def test_load_daily_news_limit_none_returns_all(tmp_path: Path) -> None:
    """관련성 필터가 전량을 봐야 하므로 limit=None 지원이 필요하다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_bigkinds(
        data_dir / "005930_삼성전자_20220101-20221231.xlsx",
        [
            {"뉴스 식별자": f"n{i}", "일자": 20220615, "언론사": "매일경제",
             "제목": f"기사 {i}", "본문": "본문", "URL": "", "분석제외 여부": ""}
            for i in range(40)
        ],
    )
    assert len(pp.load_daily_news("삼성전자", "2022-06-15", data_dir=data_dir)) == 30
    assert len(
        pp.load_daily_news("삼성전자", "2022-06-15", data_dir=data_dir, limit=None)
    ) == 40


def test_load_daily_news_nfc_company_match_and_missing_file(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_bigkinds(
        data_dir / "005930_삼성전자_20220101-20221231.xlsx",
        [{"뉴스 식별자": "n1", "일자": 20220301, "언론사": "매일경제",
          "제목": "기사", "본문": "본문", "URL": "", "분석제외 여부": ""}],
    )
    # 정규화 형태가 달라도(NFC) 회사명 매칭
    assert pp.find_news_workbook("삼성전자", "2022-03-01", data_dir) is not None
    # 종목코드(ticker)로도 매칭 — 회사명이 비어도 코드로 파일을 찾는다
    assert pp.find_news_workbook("", "2022-03-01", data_dir, ticker="005930") is not None
    assert pp.load_daily_news("", "2022-03-01", data_dir=data_dir, ticker="005930")
    # 기간 밖 날짜 → 파일 없음 → 빈 리스트
    assert pp.load_daily_news("삼성전자", "2019-01-01", data_dir=data_dir) == []
    # 다른 회사/코드 → 빈 리스트
    assert pp.load_daily_news("SK하이닉스", "2022-03-01", data_dir=data_dir) == []
    assert pp.find_news_workbook("", "2022-03-01", data_dir, ticker="000660") is None


def test_load_daily_news_supports_legacy_filename(tmp_path: Path) -> None:
    """구버전 파일명({회사명}_{기간}.xlsx)도 계속 인식되어야 한다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_bigkinds(
        data_dir / "삼성전자_20220101-20221231.xlsx",
        [{"뉴스 식별자": "n1", "일자": 20220301, "언론사": "매일경제",
          "제목": "구버전 파일 기사", "본문": "본문", "URL": "", "분석제외 여부": ""}],
    )
    items = pp.load_daily_news("삼성전자", "2022-03-01", data_dir=data_dir)
    assert [it["title"] for it in items] == ["구버전 파일 기사"]


def test_parse_workbook_name_new_and_legacy() -> None:
    assert pp._parse_workbook_name("005930_삼성전자_20220101-20221231.xlsx") == (
        "005930", "삼성전자", "20220101", "20221231",
    )
    assert pp._parse_workbook_name("삼성전자_20220101-20221231.xlsx") == (
        "", "삼성전자", "20220101", "20221231",
    )
    assert pp._parse_workbook_name("아무거나.xlsx") is None


# ── Point-in-time 재무 (look-ahead 방지) ──────────────────────────
def test_select_fiscal_year_is_point_in_time() -> None:
    """사업보고서는 사업연도 종료 후 90일(익년 3/31) 내 제출 → 4/1부터 공시."""
    f = collectors_mod.select_fiscal_year
    assert f("2022-06-15") == 2021
    assert f("2022-04-01") == 2021   # 경계: 제출기한 익일
    assert f("2022-03-31") == 2020   # 아직 FY2021 미공시
    assert f("2022-01-01") == 2020
    assert f("2022-12-31") == 2021


def test_select_fiscal_year_does_not_depend_on_today() -> None:
    """회귀 못박기: 과거엔 today().year-1 을 써서 4년 룩어헤드가 났다."""
    assert collectors_mod.select_fiscal_year("2022-06-15") == 2021
    assert collectors_mod.select_fiscal_year("2022-06-15") != dt.date.today().year - 1


class _FakeDart:
    """OpenDartReader 대역. 함수 내 지역 import라 sys.modules 치환이 먹는다."""

    seen: dict = {}

    def __init__(self, key):
        pass

    def finstate_all(self, corp, bsns_year, **kw):
        _FakeDart.seen["finstate_year"] = bsns_year
        return pd.DataFrame([
            {"account_nm": "매출액", "thstrm_amount": "300", "frmtrm_amount": "270"},
            {"account_nm": "자산총계", "thstrm_amount": "400", "frmtrm_amount": "380"},
        ])

    def report(self, corp, kind, year, **kw):
        _FakeDart.seen["report_year"] = year
        return pd.DataFrame([{"istc_totqy": "1000"}])


def test_fetch_dart_financials_uses_point_in_time_fiscal_year(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeDart.seen = {}
    monkeypatch.setitem(sys.modules, "OpenDartReader", _FakeDart)
    monkeypatch.setattr(
        collectors_mod, "SETTINGS",
        dataclasses.replace(collectors_mod.SETTINGS, dart_api_key="x"),
    )
    out = collectors_mod._fetch_dart_financials("005930", "2022-06-15")

    assert _FakeDart.seen["finstate_year"] == 2021
    assert _FakeDart.seen["report_year"] == 2021   # 발행주식수도 같은 사업연도
    assert out["fiscal_year"] == 2021


def test_collect_financials_raises_when_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """재무 결측 → 가짜 SELL 대신 명시적 중단."""
    monkeypatch.setattr(
        collectors_mod, "SETTINGS",
        dataclasses.replace(collectors_mod.SETTINGS, dart_api_key=None),
    )
    monkeypatch.setattr(collectors_mod, "_load_sample", lambda name: None)
    with pytest.raises(collectors_mod.FinancialsUnavailableError):
        collectors_mod.collect_financials("005930", "2022-06-15")


# ── 결정론 계약 (AGENTS.md '정량/정성 분리') ───────────────────────
def test_news_labels_schema_has_no_score_field() -> None:
    """LLM 출력 계약에 점수가 없어야 실수로 점수 경로에 다시 연결되지 않는다."""
    assert set(agents_mod._NewsLabels.model_fields) == {"labels", "key_events"}
    assert set(agents_mod._RelevanceLabel.model_fields) == {"idx", "relevant"}
    assert set(agents_mod._Reason.model_fields) == {"reasoning"}


def test_news_impact_score_is_deterministic_regardless_of_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM이 라벨을 어떻게 주든 news_impact_score는 동일해야 한다."""
    news = [
        {"news_id": "n1", "title": "삼성전자 흑자 확대", "summary": "실적 개선",
         "url": "", "press": "", "date": "2022-06-15"},
        {"news_id": "n2", "title": "삼성전자 신제품 출시", "summary": "호평",
         "url": "", "press": "", "date": "2022-06-15"},
    ]
    state = {"raw_news": news, "company_name": "삼성전자", "ticker": "005930"}

    monkeypatch.setattr(agents_mod, "structured", lambda p, s: None)
    a = agents_mod.news_agent(dict(state))["news_result"]

    labels = agents_mod._NewsLabels(
        labels=[agents_mod._RelevanceLabel(idx=0, relevant=True),
                agents_mod._RelevanceLabel(idx=1, relevant=True)],
        key_events=["LLM이 뽑은 이벤트"],
    )
    monkeypatch.setattr(agents_mod, "structured", lambda p, s: labels)
    b = agents_mod.news_agent(dict(state))["news_result"]

    assert a["news_impact_score"] == b["news_impact_score"]
    assert a["news_sentiment"] == b["news_sentiment"]
    assert a["key_events"] != b["key_events"]  # 이벤트 텍스트만 달라진다


def test_llm_text_cannot_change_any_score(monkeypatch: pytest.MonkeyPatch) -> None:
    """AGENTS.md 계약 테스트: LLM 텍스트가 어떤 숫자도 바꾸지 못한다."""
    news = [{"news_id": "n1", "title": "삼성전자 흑자 확대", "summary": "",
             "url": "", "press": "", "date": "2022-06-15"}]
    _patch_collectors(monkeypatch, news, _fin())

    calls = {"n": 0}

    def fake_structured(prompt, schema):
        calls["n"] += 1
        if schema is agents_mod._Reason:
            return agents_mod._Reason(reasoning=f"호출 {calls['n']}번째 근거 문장")
        return agents_mod._NewsLabels(
            labels=[agents_mod._RelevanceLabel(idx=0, relevant=True)],
            key_events=[f"이벤트 {calls['n']}"],
        )

    monkeypatch.setattr(agents_mod, "structured", fake_structured)
    a = graph_mod.run_pipeline("005930", "2022-06-15", "삼성전자")
    b = graph_mod.run_pipeline("005930", "2022-06-15", "삼성전자")

    numeric = [
        "news_sentiment", "news_impact_score", "news_sentiment_std", "news_staleness",
        "financial_health_score", "valuation_score", "composite_score",
        "value_investment_signal", "confidence", "article_count",
    ]
    for k in numeric:
        assert a[k] == b[k], f"{k}가 LLM 텍스트에 따라 달라짐 — 결정론 위반"
    assert a["reasoning"] != b["reasoning"]  # 설명 텍스트만 달라진다


def test_run_pipeline_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    news = [{"news_id": "n1", "title": "삼성전자 흑자 확대", "summary": "",
             "url": "", "press": "", "date": "2022-06-15"}]
    _patch_collectors(monkeypatch, news, _fin())
    a = graph_mod.run_pipeline("005930", "2022-06-15", "삼성전자")
    b = graph_mod.run_pipeline("005930", "2022-06-15", "삼성전자")
    assert a == b  # 결정론(같은 입력 → 같은 출력)


# ── 그래프 구조 ────────────────────────────────────────────────────
def test_graph_has_news_financial_validation_agents() -> None:
    nodes = set(graph_mod.build_graph().get_graph().nodes)
    assert {"news_agent", "financial_agent", "validation_agent", "synthesis_agent"} <= nodes
    assert "social_agent" not in nodes


def test_pipeline_state_has_no_social_keys() -> None:
    keys = set(graph_mod.PipelineState.__annotations__)
    assert not any("social" in k for k in keys)


def test_schema_has_no_social_analysis_or_fields() -> None:
    assert not hasattr(schema_mod, "SocialAnalysis")
    fields = set(schema_mod.ValueSignal.model_fields)
    assert not any("social" in f for f in fields)
    assert "sentiment_divergence" not in fields


# ── 출력 계약 ──────────────────────────────────────────────────────
_EXPECTED_FIELDS = {
    "ticker", "date", "company_name",
    "news_sentiment", "news_impact_score", "news_sentiment_std", "news_staleness",
    "key_events", "article_count", "article_count_raw",
    "financial_health_score", "valuation_score", "financial_metrics",
    "financial_fiscal_year",
    "composite_score", "value_investment_signal", "confidence", "reasoning",
    "news_source", "financial_source", "validation",
}


def test_value_signal_field_contract() -> None:
    assert set(schema_mod.ValueSignal.model_fields) == _EXPECTED_FIELDS
    # 제거된 필드가 되살아나지 않도록
    for gone in ("data_quality", "sentiment_backend", "llm_used"):
        assert gone not in schema_mod.ValueSignal.model_fields


def test_row_is_self_auditing(monkeypatch: pytest.MonkeyPatch) -> None:
    """행 하나만 보고 composite·signal을 재계산할 수 있어야 한다(화이트박스)."""
    news = [{"news_id": "n1", "title": "삼성전자 흑자 확대", "summary": "",
             "url": "", "press": "", "date": "2022-06-15"}]
    _patch_collectors(monkeypatch, news, _fin())
    out = graph_mod.run_pipeline("005930", "2022-06-15", "삼성전자")

    composite = (
        out["valuation_score"] * 0.6
        + out["financial_health_score"] * 0.4
        + out["news_sentiment"] * (out["news_impact_score"] / 10.0) * 2.0
    )
    composite = max(0.0, min(10.0, composite))
    assert out["composite_score"] == pytest.approx(composite, abs=1e-3)
    assert out["value_investment_signal"] == agents_mod._to_signal(composite)


def test_run_pipeline_news_and_financial_only(monkeypatch: pytest.MonkeyPatch) -> None:
    news = [
        {"news_id": "n1", "title": "삼성전자 사상 최대 실적 흑자",
         "summary": "매출 급등, 수주 확대", "url": "", "press": "매일경제",
         "date": "2022-06-15"},
        {"news_id": "n2", "title": "삼성전자 메모리 반등 기대", "summary": "업황 개선",
         "url": "", "press": "한국경제", "date": "2022-06-15"},
    ]
    _patch_collectors(monkeypatch, news, _fin())
    out = graph_mod.run_pipeline("005930", "2022-06-15", "삼성전자")

    assert not any("social" in k for k in out)
    assert "data_quality" not in out

    assert out["ticker"] == "005930"
    assert out["company_name"] == "삼성전자"
    assert out["value_investment_signal"] in {
        "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"
    }
    assert 0.0 <= out["confidence"] <= 1.0
    assert 0.0 <= out["composite_score"] <= 10.0
    assert out["article_count"] == 2
    assert out["news_source"] == "bigkinds"
    assert out["financial_source"] == "dart"
    assert out["financial_fiscal_year"] == 2021


# ── 관련성 필터 ────────────────────────────────────────────────────
def test_relevance_filter_excludes_unrelated_articles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """무관 기사가 감성에 들어가면 부호가 뒤집힌다 (실측 재현)."""
    news = [
        {"news_id": "n1", "title": "삼성전자 52주 신저가 5만전자 위기",
         "summary": "주가 급락 지속", "url": "", "press": "", "date": "2022-06-15"},
        {"news_id": "n2", "title": "구미대-희망디딤돌 경북센터 상호교류 업무협약 체결",
         "summary": "협약 성과 기대", "url": "", "press": "", "date": "2022-06-15"},
    ]
    labels = agents_mod._NewsLabels(
        labels=[agents_mod._RelevanceLabel(idx=0, relevant=True),
                agents_mod._RelevanceLabel(idx=1, relevant=False)],
        key_events=[],
    )
    monkeypatch.setattr(agents_mod, "structured", lambda p, s: labels)
    out = agents_mod.news_agent(
        {"raw_news": news, "company_name": "삼성전자", "ticker": "005930"}
    )["news_result"]

    assert out["article_count"] == 1       # 무관 기사 제외
    assert out["article_count_raw"] == 2   # 결측 지시자: 원래 몇 건이었는지
    assert out["relevance_backend"] == "llm"


def test_relevance_filter_falls_back_to_rule_without_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    news = [
        {"news_id": "n1", "title": "삼성전자 흑자", "summary": "", "url": "",
         "press": "", "date": "2022-06-15"},
        {"news_id": "n2", "title": "두산 반도체 투자", "summary": "", "url": "",
         "press": "", "date": "2022-06-15"},
    ]
    monkeypatch.setattr(agents_mod, "structured", lambda p, s: None)
    out = agents_mod.news_agent(
        {"raw_news": news, "company_name": "삼성전자", "ticker": "005930"}
    )["news_result"]
    assert out["article_count"] == 1
    assert out["relevance_backend"] == "rule"


def test_relevance_filter_never_drops_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    """필터가 전부 걸러내면 신뢰하지 않고 전량 사용 (조용한 무데이터 방지)."""
    news = [{"news_id": "n1", "title": "기사", "summary": "", "url": "", "press": "",
             "date": "2022-06-15"}]
    labels = agents_mod._NewsLabels(
        labels=[agents_mod._RelevanceLabel(idx=0, relevant=False)], key_events=[]
    )
    monkeypatch.setattr(agents_mod, "structured", lambda p, s: labels)
    out = agents_mod.news_agent(
        {"raw_news": news, "company_name": "삼성전자", "ticker": "005930"}
    )["news_result"]
    assert out["article_count"] == 1
    assert "empty-fallback" in out["relevance_backend"]


def test_key_events_carry_source_news_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    """HITL '근거·출처 항상 표시' + 환각 탐지."""
    news = [{"news_id": "n1", "title": "삼성전자 ASML 협력 논의", "summary": "반도체 장비",
             "url": "", "press": "", "date": "2022-06-15"}]
    labels = agents_mod._NewsLabels(
        labels=[agents_mod._RelevanceLabel(idx=0, relevant=True)],
        key_events=["삼성전자 ASML 반도체 장비 협력", "완전히 무관한 날조 이벤트 xyzzy"],
    )
    monkeypatch.setattr(agents_mod, "structured", lambda p, s: labels)
    out = agents_mod.news_agent(
        {"raw_news": news, "company_name": "삼성전자", "ticker": "005930"}
    )["news_result"]

    events = {e["event"]: e["news_ids"] for e in out["key_events"]}
    assert events["삼성전자 ASML 반도체 장비 협력"] == ["n1"]   # 출처 연결됨
    assert events["완전히 무관한 날조 이벤트 xyzzy"] == []      # 출처 없음 → 환각 의심


# ── validation_agent (규칙 기반) ───────────────────────────────────
def _validate(news_result: dict, fin_result: dict, raw_fin: dict, **over) -> dict:
    state = {
        "date": "2022-06-15", "ticker": "005930",
        "raw_news": [{"date": "2022-06-15"}],
        "news_result": news_result, "financial_result": fin_result,
        "raw_financials": raw_fin,
    }
    state.update(over)
    return agents_mod.validation_agent(state)["validation"]


_OK_NEWS = {"article_count": 2, "article_count_raw": 2, "key_events": []}


def test_validation_passes_on_consistent_data() -> None:
    m = metrics_mod.compute_metrics(_fin())
    v = _validate(
        _OK_NEWS,
        {"metrics": m, "fiscal_year": 2021},
        _fin(),
    )
    assert v["ok"], v["errors"]


def test_validation_catches_accounting_identity_violation() -> None:
    """자산 != 부채 + 자본 → 연결/별도 재무제표 혼입 탐지."""
    bad = _fin(total_equity=1.0e14)  # 자산 400 != 부채 100 + 자본 100
    v = _validate(_OK_NEWS, {"metrics": metrics_mod.compute_metrics(bad),
                             "fiscal_year": 2021}, bad)
    assert not v["ok"]
    assert any("회계 항등식" in e for e in v["errors"])


def test_validation_catches_lookahead_fiscal_year() -> None:
    """2022-06-15 피처에 FY2025 재무 → 룩어헤드."""
    v = _validate(_OK_NEWS,
                  {"metrics": metrics_mod.compute_metrics(_fin()), "fiscal_year": 2025},
                  _fin())
    assert not v["ok"]
    assert any("룩어헤드" in e for e in v["errors"])


def test_validation_catches_misaligned_news_date() -> None:
    v = _validate(_OK_NEWS,
                  {"metrics": metrics_mod.compute_metrics(_fin()), "fiscal_year": 2021},
                  _fin(),
                  raw_news=[{"date": "2022-06-14"}])
    assert not v["ok"]
    assert any("기준일" in e for e in v["errors"])


def test_validation_catches_zero_articles() -> None:
    """무데이터를 '중립'으로 통과시키지 않는다."""
    v = _validate({"article_count": 0, "article_count_raw": 0, "key_events": []},
                  {"metrics": metrics_mod.compute_metrics(_fin()), "fiscal_year": 2021},
                  _fin())
    assert not v["ok"]
    assert any("무데이터" in e for e in v["errors"])


def test_validation_catches_implausible_metric() -> None:
    """_band는 조용히 saturate하므로 범위 검사가 유일한 방어선."""
    bad = _fin(shares_outstanding=1.0)  # 단위 오류 → PER 폭발
    v = _validate(_OK_NEWS, {"metrics": metrics_mod.compute_metrics(bad),
                             "fiscal_year": 2021}, bad)
    assert not v["ok"]
    assert any("상식 범위" in e or "PER 불일치" in e for e in v["errors"])


def test_validation_warns_when_cap_drops_relevant_articles() -> None:
    """상한에 걸린 기사는 임의 선택으로 버려진다 → 조용히 넘어가면 안 된다."""
    v = _validate({"article_count": 30, "article_count_raw": 73,
                   "article_count_dropped": 7, "key_events": []},
                  {"metrics": metrics_mod.compute_metrics(_fin()), "fiscal_year": 2021},
                  _fin())
    assert any("상한" in w and "임의로 버려짐" in w for w in v["warnings"])


def test_relevance_cap_does_not_bind_on_real_scale(monkeypatch: pytest.MonkeyPatch) -> None:
    """상한은 병리적인 날 방어용 — 실제 규모(최악의 날 182건)에선 걸리면 안 된다."""
    news = [
        {"news_id": f"n{i}", "title": f"삼성전자 기사 {i}", "summary": "본문",
         "url": "", "press": "", "date": "2022-06-15"}
        for i in range(182)
    ]
    monkeypatch.setattr(agents_mod, "structured", lambda p, s: None)
    out = agents_mod.news_agent(
        {"raw_news": news, "company_name": "삼성전자", "ticker": "005930"}
    )["news_result"]
    assert out["article_count"] == 182
    assert out["article_count_dropped"] == 0


def test_validation_warns_on_ungrounded_event() -> None:
    v = _validate({"article_count": 2, "article_count_raw": 2,
                   "key_events": [{"event": "출처 없는 이벤트", "news_ids": []}]},
                  {"metrics": metrics_mod.compute_metrics(_fin()), "fiscal_year": 2021},
                  _fin())
    assert any("출처 기사를 찾지 못한" in w for w in v["warnings"])


def test_validation_result_reaches_output(monkeypatch: pytest.MonkeyPatch) -> None:
    news = [{"news_id": "n1", "title": "삼성전자 흑자", "summary": "", "url": "",
             "press": "", "date": "2022-06-15"}]
    _patch_collectors(monkeypatch, news, _fin())
    out = graph_mod.run_pipeline("005930", "2022-06-15", "삼성전자")
    assert "validation" in out
    assert out["validation"]["ok"], out["validation"]["errors"]


# ── metrics: 적자 vs 결측 ──────────────────────────────────────────
def test_valuation_missing_data_is_not_treated_as_loss() -> None:
    """per 결측이 곧 적자는 아니다 — 데이터가 없을 뿐일 수 있다.

    과거엔 `elif per is None: parts.append(3.0)` 이라 주가·발행주식수 누락만으로도
    적자 페널티를 먹고 valuation 3.0 → 종합 3.8 → 가짜 SELL이 나왔다.
    """
    # 주가·발행주식수 결측 → per/pbr 모두 None, roe도 None → 판단 근거 없음
    missing = metrics_mod.compute_metrics({"revenue": 1.0e14})
    assert missing["per"] is None and missing["roe"] is None
    assert metrics_mod.valuation_score(missing) == 5.0  # 3.0(적자 취급) 아님

    # 진짜 적자(roe<=0)는 여전히 3.0 페널티를 받는다.
    # valuation_score는 가용 항목의 '평균'이라, 페널티만 확인하려면 pbr도 결측이어야 한다.
    loss = metrics_mod.compute_metrics({"net_income": -1.0e13, "total_equity": 1.0e14})
    assert loss["roe"] is not None and loss["roe"] <= 0
    assert loss["per"] is None and loss["pbr"] is None
    assert metrics_mod.valuation_score(loss) == 3.0


# ── staleness (Tetlock 2011) ───────────────────────────────────────
def test_staleness_identical_article_is_fully_stale() -> None:
    text = ["삼성전자 반도체 실적 개선 전망 메모리 가격 반등"]
    assert staleness_mod.staleness_score(text, text) == 1.0


def test_staleness_new_article_is_fresh() -> None:
    cur = ["삼성전자 신규 파운드리 수주 계약 체결"]
    prev = ["기아 전기차 판매량 증가 유럽 시장"]
    assert staleness_mod.staleness_score(cur, prev) == 0.0


def test_staleness_no_prior_is_zero() -> None:
    assert staleness_mod.staleness_score(["삼성전자 실적"], []) == 0.0


def test_staleness_is_deterministic() -> None:
    cur = ["삼성전자 반도체 실적 개선", "메모리 가격 반등 기대"]
    prev = ["삼성전자 반도체 업황 전망", "낸드 가격 하락"]
    a = staleness_mod.staleness_score(cur, prev)
    b = staleness_mod.staleness_score(cur, prev)
    assert a == b
    assert 0.0 < a < 1.0  # 부분 중복
