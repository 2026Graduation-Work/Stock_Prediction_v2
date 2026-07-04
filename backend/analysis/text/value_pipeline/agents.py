"""멀티 에이전트 노드 (LangGraph에서 호출).

설계 원칙
- 수치 피처(감성·재무점수·시그널·신뢰도)는 결정론적으로 계산 → 재현성·설명가능성.
- LLM(Gemini, 있을 때만)은 보조: 핵심 이벤트 추출, 자연어 근거 생성.
- LLM 자기보고 신뢰도는 과신 경향이 있어(스펙 참고) confidence는 데이터 품질·
  시그널 마진·의견 분산으로 직접 산출한다.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from . import metrics
from .llm import structured
from .schema import (
    FinancialAnalysis,
    FinancialMetrics,
    NewsAnalysis,
    SocialAnalysis,
    ValueSignal,
)
from .sentiment import aggregate, score_texts


# ── LLM 보조 출력 스키마 ────────────────────────────────────────
class _NewsExtract(BaseModel):
    key_events: list[str] = Field(
        default_factory=list, description="그날의 핵심 이벤트 3~6개, 간결한 한국어 명사구"
    )
    impact_score: int = Field(
        5, ge=1, le=10, description="이 뉴스들이 주가에 줄 영향력(부정이어도 클 수 있음)"
    )


class _Reason(BaseModel):
    reasoning: str = Field("", description="가치투자 판단 근거 2~3문장, 한국어")


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ── News Agent ─────────────────────────────────────────────────
def news_agent(state: dict) -> dict:
    items = state.get("raw_news") or []
    texts = [f"{i.get('title', '')} {i.get('summary', '')}".strip() for i in items]
    scores, backend = score_texts(texts)
    mean, std = aggregate(scores)

    extract = None
    if texts:
        headlines = "\n".join(f"- {t}" for t in texts[:25])
        extract = structured(
            f"다음은 '{state.get('company_name') or state.get('ticker')}' "
            f"관련 최신 뉴스 헤드라인이다.\n"
            f"{headlines}\n\n핵심 이벤트와 주가 영향력 점수(1~10)를 산출하라.",
            _NewsExtract,
        )

    if extract is not None:
        key_events, impact = extract.key_events[:6], extract.impact_score
    else:  # 규칙 기반 폴백: 감성 절댓값이 큰 헤드라인을 핵심 이벤트로
        ranked = sorted(zip(texts, scores, strict=False), key=lambda x: abs(x[1]), reverse=True)
        key_events = [t for t, _ in ranked[:5] if t]
        impact = int(_clip(3 + min(4, len(texts) // 3) + round(abs(mean) * 3), 1, 10))

    result = NewsAnalysis(
        news_sentiment=mean,
        news_impact_score=impact,
        news_sentiment_std=std,
        key_events=key_events,
        article_count=len(texts),
        backend=backend,
        reasoning=f"기사 {len(texts)}건 분석(감성 {mean:+.2f}, 분산 {std:.2f}, 백엔드 {backend}).",
    )
    return {"news_result": result.model_dump()}


# ── Social Agent ───────────────────────────────────────────────
def social_agent(state: dict) -> dict:
    posts = state.get("raw_social") or []
    texts = [p.get("title", "") for p in posts]
    scores, backend = score_texts(texts)
    mean, _ = aggregate(scores)
    buzz = len(posts)

    result = SocialAnalysis(
        social_buzz=buzz,
        social_sentiment=mean,
        post_count=len(texts),
        backend=backend,
        reasoning=f"게시글 {buzz}건(대중 감성 {mean:+.2f}, 백엔드 {backend}).",
    )
    return {"social_result": result.model_dump()}


# ── Financial Agent ────────────────────────────────────────────
def financial_agent(state: dict) -> dict:
    f = state.get("raw_financials") or {}
    m = metrics.compute_metrics(f)
    health = metrics.health_score(m)
    valuation = metrics.valuation_score(m, f.get("sector_per"), f.get("sector_pbr"))

    def fmt(x, pct=False):
        if x is None:
            return "N/A"
        return f"{x * 100:.1f}%" if pct else f"{x:.2f}"

    reasoning = (
        f"PER {fmt(m['per'])}, PBR {fmt(m['pbr'])}, ROE {fmt(m['roe'], pct=True)}, "
        f"부채비율 {fmt(m['debt_ratio'])}배, 매출성장 {fmt(m['revenue_growth'], pct=True)} "
        f"→ 건전성 {health}/10, 밸류 {valuation}/10."
    )

    result = FinancialAnalysis(
        financial_health_score=health,
        valuation_score=valuation,
        metrics=FinancialMetrics(**m),
        source=state.get("financial_source", "sample"),
        reasoning=reasoning,
    )
    return {"financial_result": result.model_dump()}


# ── Synthesis Agent ────────────────────────────────────────────
_SIGNAL_BANDS = [(8.0, "STRONG_BUY"), (6.5, "BUY"), (4.5, "HOLD"), (3.0, "SELL")]


def _to_signal(composite: float) -> str:
    for thr, sig in _SIGNAL_BANDS:
        if composite >= thr:
            return sig
    return "STRONG_SELL"


def synthesis_agent(state: dict) -> dict:
    news = state.get("news_result") or {}
    social = state.get("social_result") or {}
    fin = state.get("financial_result") or {}

    valuation = fin.get("valuation_score", 5.0)
    health = fin.get("financial_health_score", 5.0)
    news_sent = news.get("news_sentiment", 0.0)
    impact = news.get("news_impact_score", 5)
    social_sent = social.get("social_sentiment", 0.0)
    divergence = round(news_sent - social_sent, 4)

    # 펀더멘털(가치투자 핵심) + 감성 보정
    fundamental = valuation * 0.6 + health * 0.4              # 0~10
    sentiment_adj = (news_sent * (impact / 10.0) * 0.7 + social_sent * 0.3) * 2.0  # ±2 내외
    composite = _clip(fundamental + sentiment_adj, 0.0, 10.0)
    signal = _to_signal(composite)

    # 신뢰도: 데이터 품질 + 시그널 마진 - 뉴스 의견분산 (LLM 자기보고 대신 직접 산출)
    real_sources = sum(
        1
        for s in (
            state.get("news_source"),
            state.get("social_source"),
            state.get("financial_source"),
        )
        if s and s != "sample"
    )
    quality = 0.45 + 0.1 * real_sources                       # 0.45~0.75
    margin = abs(composite - 5.0) / 5.0                        # 0~1 (확신 강도)
    disagreement = news.get("news_sentiment_std", 0.0)
    confidence = round(_clip(quality + 0.2 * margin - 0.15 * disagreement, 0.2, 0.95), 3)

    # 근거: LLM 있으면 생성, 없으면 템플릿
    reason_obj = structured(
        f"종목 {state.get('ticker')} 가치투자 분석 결과:\n"
        f"- 밸류에이션 {valuation}/10, 재무건전성 {health}/10\n"
        f"- 뉴스감성 {news_sent:+.2f}(영향력 {impact}/10), "
        f"소셜감성 {social_sent:+.2f}, 다이버전스 {divergence:+.2f}\n"
        f"- 종합점수 {composite:.2f}/10 → 시그널 {signal}\n"
        f"핵심이벤트: {', '.join(news.get('key_events', [])[:4])}\n"
        f"위 수치와 일관되게 가치투자 판단 근거를 2~3문장으로 써라.",
        _Reason,
    )
    if reason_obj is not None and reason_obj.reasoning:
        reasoning = reason_obj.reasoning
    else:
        div_note = (
            " 뉴스(전문가)와 소셜(대중) 심리가 괴리되어 해석에 주의가 필요하다."
            if abs(divergence) >= 0.4 else ""
        )
        reasoning = (
            f"밸류에이션 {valuation}/10·재무건전성 {health}/10에 뉴스감성 {news_sent:+.2f}"
            f"(영향력 {impact}/10)를 반영한 종합점수 {composite:.1f}/10으로 "
            f"'{signal}' 판단.{div_note}"
        )

    out = ValueSignal(
        ticker=state["ticker"],
        date=state["date"],
        company_name=state.get("company_name", ""),
        news_sentiment=news_sent,
        news_impact_score=impact,
        news_sentiment_std=news.get("news_sentiment_std", 0.0),
        key_events=news.get("key_events", []),
        social_buzz=social.get("social_buzz", 0),
        social_sentiment=social_sent,
        sentiment_divergence=divergence,
        financial_health_score=health,
        valuation_score=valuation,
        financial_metrics=FinancialMetrics(**fin.get("metrics", {})),
        value_investment_signal=signal,
        confidence=confidence,
        reasoning=reasoning,
        data_quality={
            "composite_score": round(composite, 3),
            "news_source": state.get("news_source"),
            "social_source": state.get("social_source"),
            "financial_source": state.get("financial_source"),
            "sentiment_backend": news.get("backend"),
            "llm_used": reason_obj is not None,
            "article_count": news.get("article_count", 0),
            "post_count": social.get("post_count", 0),
        },
    )
    return {"final": out.model_dump()}
