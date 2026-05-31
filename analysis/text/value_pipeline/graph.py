"""LangGraph 오케스트레이터.

    START → ingest → ┌ news_agent ─────┐
                     ├ social_agent ───┼→ synthesis_agent → END
                     └ financial_agent ┘
ingest가 3개 소스를 수집하면, 3개 분석 에이전트가 병렬 실행되고,
synthesis_agent가 모두 끝난 뒤 종합 시그널 JSON을 만든다.
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from . import collectors
from .agents import financial_agent, news_agent, social_agent, synthesis_agent


class PipelineState(TypedDict, total=False):
    # 입력
    ticker: str
    date: str
    company_name: str
    # ingest 산출 원천 데이터
    raw_news: list
    news_source: str
    raw_social: list
    social_source: str
    raw_financials: dict
    financial_source: str
    # 에이전트 산출
    news_result: dict
    social_result: dict
    financial_result: dict
    final: dict


def ingest(state: PipelineState) -> dict:
    ticker = state["ticker"]
    date = state["date"]
    name = state.get("company_name") or ticker

    news, news_src = collectors.collect_news(ticker, name, date)
    social, social_src = collectors.collect_social(ticker, date)
    fin, fin_src = collectors.collect_financials(ticker, date)

    return {
        "company_name": state.get("company_name") or fin.get("company_name") or ticker,
        "raw_news": news,
        "news_source": news_src,
        "raw_social": social,
        "social_source": social_src,
        "raw_financials": fin,
        "financial_source": fin_src,
    }


def build_graph():
    g = StateGraph(PipelineState)
    g.add_node("ingest", ingest)
    g.add_node("news_agent", news_agent)
    g.add_node("social_agent", social_agent)
    g.add_node("financial_agent", financial_agent)
    g.add_node("synthesis_agent", synthesis_agent)

    g.add_edge(START, "ingest")
    for node in ("news_agent", "social_agent", "financial_agent"):
        g.add_edge("ingest", node)            # 병렬 fan-out
        g.add_edge(node, "synthesis_agent")   # fan-in (모두 완료 후 synthesis)
    g.add_edge("synthesis_agent", END)
    return g.compile()


APP = build_graph()


def run_pipeline(ticker: str, date: str, company_name: str = "") -> dict:
    """파이프라인 실행 → 최종 ValueSignal dict 반환."""
    state: PipelineState = {"ticker": ticker, "date": date, "company_name": company_name}
    result = APP.invoke(state)
    return result["final"]
