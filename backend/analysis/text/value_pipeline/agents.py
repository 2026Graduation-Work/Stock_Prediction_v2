"""멀티 에이전트 노드 (LangGraph에서 호출).

    ingest → {news_agent ∥ financial_agent} → validation_agent → synthesis_agent

설계 원칙 (AGENTS.md '정량/정성 분리')
- 수치 피처(감성·재무점수·영향력·시그널·신뢰도)는 결정론적으로 계산 → 재현성·설명가능성.
- LLM은 '라벨·분류·추출·설명'만: 뉴스 관련성 판정, 핵심 이벤트 추출, 자연어 근거.
  LLM 출력은 llm.structured가 content-hash로 동결하므로 재실행 시 결정론이 유지된다.
- validation_agent는 규칙 기반이다. LLM 크리틱은 쓰지 않는다 —
  자기검증은 실증적으로 성능을 떨어뜨리고(ICLR 2024), 판사 LLM은 저perplexity
  텍스트를 선호해 매끄러운 보도자료를 진짜 새 정보보다 높게 친다.

## 왜 관련성 필터가 LLM의 자리인가 (실측)

2022-06-15 삼성전자(52주 신저가일) 30건 기준:
    전체 30건 감성      = +0.0429  (긍정 — 틀림)
    무관 8건 제외 22건  = -0.1230  (부정 — 맞음)
'구미대-희망디딤돌 업무협약'(+1.000), '두산 반도체 투자'(+0.985), '미래에셋 ELW
상장'(+0.976) 같은 기사가 FinBERT에서 만점 긍정을 받는다. 판정은 다 맞다.
삼성전자 기사가 아닐 뿐이다. 관련성이 감성 부호를 뒤집는다.

반면 본문 200자 중간 절단(82.4%)은 FinBERT 감성에 영향이 없다(raw vs trim r=0.9995).
그래서 LLM을 요약이 아니라 관련성 필터에 쓴다.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from . import metrics, staleness
from .config import SETTINGS
from .llm import structured
from .schema import (
    FinancialAnalysis,
    FinancialMetrics,
    KeyEvent,
    NewsAnalysis,
    ValidationResult,
    ValueSignal,
)
from .sentiment import aggregate, score_texts


# ── LLM 보조 출력 스키마 ────────────────────────────────────────
# 주의: 이 스키마에 '점수' 필드를 추가하지 말 것. LLM 출력 계약에 점수가 없어야
# 실수로 점수 경로에 다시 연결되지 않는다(관례가 아니라 구조로 강제).
class _RelevanceLabel(BaseModel):
    idx: int = Field(description="기사 번호")
    relevant: bool = Field(description="이 기사가 해당 기업의 사업·실적·주가에 관한 것인가")


class _NewsLabels(BaseModel):
    labels: list[_RelevanceLabel] = Field(
        default_factory=list, description="기사 번호별 관련성 판정. 모든 번호에 대해 하나씩."
    )
    key_events: list[str] = Field(
        default_factory=list, description="관련 기사에서 뽑은 그날의 핵심 이벤트 3~6개, 간결한 한국어 명사구"
    )


class _Reason(BaseModel):
    reasoning: str = Field("", description="가치투자 판단 근거 2~3문장, 한국어")


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _text_of(item: dict) -> str:
    return f"{item.get('title', '')} {item.get('summary', '')}".strip()


# ── News Agent ─────────────────────────────────────────────────
def _label_relevance(items: list[dict], company: str) -> tuple[_NewsLabels | None, str]:
    """LLM 배치 1콜로 기사별 관련성 + 핵심 이벤트. 실패 시 (None, 'rule')."""
    if not items:
        return None, "none"
    listing = "\n".join(f"[{i}] {_text_of(it)[:150]}" for i, it in enumerate(items))
    out = structured(
        f"다음은 '{company}' 키워드로 수집한 하루치 뉴스다. 키워드 검색이라 "
        f"해당 기업과 무관한 기사가 섞여 있다.\n\n{listing}\n\n"
        f"각 기사가 '{company}'의 사업·실적·주가·경영에 관한 것인지 판정하라.\n"
        f"- 관련 없음(relevant=false)의 예: 다른 기업이 주인공인 기사, 지수·시황 "
        f"일반론, 주식 리딩방 광고, 연예·스포츠, '{company}'가 단순 언급만 된 기사\n"
        f"- 관련 있음(relevant=true)의 예: 실적·수주·신제품·소송·규제·인사·투자 등 "
        f"'{company}' 자체의 사업 관련 기사, '{company}' 주가에 대한 기사\n"
        f"모든 기사 번호에 대해 판정을 하나씩 내고, 관련 있는 기사에서만 "
        f"핵심 이벤트를 3~6개의 간결한 한국어 명사구로 추출하라.",
        _NewsLabels,
    )
    if out is None:
        return None, "rule"
    return out, "llm"


def _rule_relevance(items: list[dict], company: str) -> list[int]:
    """LLM 없을 때 폴백: 제목에 회사명이 있는 기사만. 결정론."""
    key = (company or "").replace(" ", "")
    if not key:
        return list(range(len(items)))
    return [
        i for i, it in enumerate(items)
        if key in str(it.get("title", "")).replace(" ", "")
    ]


def news_agent(state: dict) -> dict:
    items = state.get("raw_news") or []
    company = state.get("company_name") or state.get("ticker") or ""
    raw_count = len(items)

    labels, rel_backend = _label_relevance(items, company)
    if labels is not None:
        keep = {lb.idx for lb in labels.labels if lb.relevant and 0 <= lb.idx < raw_count}
        llm_events = labels.key_events[:6]
    else:
        keep = set(_rule_relevance(items, company))
        llm_events = []
    # 관련 기사가 하나도 없으면 필터를 신뢰하지 않고 전량 사용(전부 거르는 사고 방지)
    if not keep and items:
        keep = set(range(raw_count))
        rel_backend = f"{rel_backend}-empty-fallback"

    relevant_all = [items[i] for i in sorted(keep)]
    relevant = relevant_all[: SETTINGS.max_daily_articles]
    dropped = len(relevant_all) - len(relevant)
    texts = [_text_of(it) for it in relevant]
    scores, backend = score_texts(texts)
    mean, std = aggregate(scores)

    # 영향력 점수는 LLM 유무와 무관하게 항상 결정론 규칙으로 산출한다.
    # (AGENTS.md: 점수 산출은 100% 결정론, LLM은 설명 텍스트 생성에만)
    impact = int(_clip(3 + min(4, len(texts) // 3) + round(abs(mean) * 3), 1, 10))

    # 핵심 이벤트: LLM 문구를 실제 기사에 그라운딩해 출처 news_id를 붙인다.
    if llm_events:
        key_events = [_ground_event(e, relevant) for e in llm_events]
    else:  # 규칙 기반 폴백: 감성 절댓값이 큰 헤드라인을 핵심 이벤트로
        ranked = sorted(
            zip(relevant, scores, strict=False), key=lambda x: abs(x[1]), reverse=True
        )
        key_events = [
            KeyEvent(event=str(it.get("title", "")), news_ids=[str(it.get("news_id", ""))])
            for it, _ in ranked[:5]
            if it.get("title")
        ]

    prior = state.get("prior_news") or []
    stale = staleness.staleness_score(texts, [_text_of(p) for p in prior])

    result = NewsAnalysis(
        news_sentiment=mean,
        news_impact_score=impact,
        news_sentiment_std=std,
        key_events=key_events,
        article_count=len(texts),
        article_count_raw=raw_count,
        article_count_dropped=dropped,
        staleness=stale,
        backend=backend,
        relevance_backend=rel_backend,
        reasoning=(
            f"수집 {raw_count}건 중 관련 {len(texts)}건 분석"
            f"(감성 {mean:+.2f}, 분산 {std:.2f}, 신선도 {1 - stale:.2f}, 백엔드 {backend})."
        ),
    )
    return {"news_result": result.model_dump()}


def _ground_event(event: str, items: list[dict]) -> KeyEvent:
    """LLM이 쓴 이벤트 문구를 실제 기사에 연결해 출처 news_id를 붙인다.

    토큰 겹침으로 가장 유사한 기사를 찾는다. 하나도 안 겹치면 news_ids=[] →
    validation_agent가 '출처 없는 이벤트'로 잡아낸다(환각 탐지).
    """
    ev_tokens = staleness.tokenize(event)
    if not ev_tokens:
        return KeyEvent(event=event, news_ids=[])
    scored = []
    for it in items:
        overlap = len(ev_tokens & staleness.tokenize(_text_of(it)))
        if overlap:
            scored.append((overlap, str(it.get("news_id", ""))))
    scored.sort(reverse=True)
    return KeyEvent(event=event, news_ids=[nid for _, nid in scored[:2] if nid])


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
        fiscal_year=f.get("fiscal_year"),
        source=state.get("financial_source", "sample"),
        reasoning=reasoning,
    )
    return {"financial_result": result.model_dump()}


# ── Validation Agent (규칙 기반, 결정론) ────────────────────────
_PLAUSIBLE = {  # 지표별 상식 범위 — 벗어나면 단위/매핑 오류 의심
    # 하한이 중요하다: 발행주식수가 과소하면 EPS가 폭증해 PER이 0에 수렴한다.
    # 단위 오류는 지표를 크게 만드는 만큼 작게도 만든다.
    "per": (0.1, 500.0),
    "pbr": (0.005, 100.0),
    "roe": (-1.0, 2.0),
    "debt_ratio": (0.0, 50.0),
    "altman_z": (-5.0, 30.0),
    "revenue_growth": (-1.0, 10.0),
}

# 한국 상장사 시가총액 상식 범위 (원). 발행주식수·주가 단위 오류를 잡는다.
_MKTCAP_RANGE = (1e9, 1e16)


def validation_agent(state: dict) -> dict:
    """앞 단계 두 에이전트의 산출물이 실제로 정합적인지 규칙으로 검증한다.

    _DART_MAP은 best-effort 매핑이고 DART는 회사마다 계정 구조가 달라, 매핑이
    조용히 실패해도 지표는 '그럴듯한 float'로 남는다. 항등식 검사만이 그걸 잡는다.
    """
    errors: list[str] = []
    warns: list[str] = []

    news = state.get("news_result") or {}
    fin = state.get("financial_result") or {}
    f = state.get("raw_financials") or {}
    m = fin.get("metrics") or {}

    # 1) 회계 항등식: 자산총계 = 부채총계 + 자본총계
    ta, tl, eq = f.get("total_assets"), f.get("total_liabilities"), f.get("total_equity")
    if ta and tl and eq:
        gap = abs(ta - (tl + eq)) / ta
        if gap > 0.005:
            errors.append(
                f"회계 항등식 위배: 자산({ta:,.0f}) != 부채+자본({tl + eq:,.0f}), "
                f"괴리 {gap:.2%} → 연결/별도 재무제표 혼입 의심"
            )
    else:
        warns.append("재무상태표 3항목(자산/부채/자본) 중 결측 있음 → 항등식 검증 불가")

    # 2) 시가총액 상식 범위.
    # per×eps≈price 같은 검사는 동어반복이다 — compute_metrics가 per=price/eps로
    # 계산하므로 항상 참이다. 대신 독립 입력(주가·발행주식수)의 곱이 상식적인지 본다.
    price, sh = f.get("price"), f.get("shares_outstanding")
    if price and sh:
        mktcap = price * sh
        lo, hi = _MKTCAP_RANGE
        if not (lo <= mktcap <= hi):
            errors.append(
                f"시가총액 {mktcap:,.0f}원이 상식 범위 밖 "
                f"(주가 {price:,.0f} × 주식수 {sh:,.0f}) → 단위 오류 의심"
            )
    if m.get("per") is None and (sh is None or price is None):
        warns.append("발행주식수 또는 주가 결측 → per/pbr/altman_z 계산 불가")

    # 3) 지표 상식 범위 (_band는 조용히 saturate하므로 여기서 잡아야 한다)
    for k, (lo, hi) in _PLAUSIBLE.items():
        v = m.get(k)
        if v is not None and not (lo <= v <= hi):
            errors.append(f"{k}={v:.4g} 이 상식 범위 [{lo}, {hi}] 밖 → 단위 오류 의심")

    # 4) 파생 항목 정합성
    for a, b, label in [
        ("current_assets", "total_assets", "유동자산 ≤ 자산총계"),
        ("current_liabilities", "total_liabilities", "유동부채 ≤ 부채총계"),
        ("retained_earnings", "total_equity", "이익잉여금 ≤ 자본총계"),
    ]:
        x, y = f.get(a), f.get(b)
        if x is not None and y is not None and x > y * 1.005:
            errors.append(f"{label} 위배: {a}={x:,.0f} > {b}={y:,.0f}")

    # 5) 뉴스 날짜 정렬 (point-in-time)
    date = state.get("date")
    bad = [
        str(it.get("date"))
        for it in (state.get("raw_news") or [])
        if str(it.get("date", "")) != date
    ]
    if bad:
        errors.append(f"기준일({date})이 아닌 기사 {len(bad)}건 혼입: {sorted(set(bad))[:3]}")

    # 6) point-in-time 재무: 기준일보다 미래 회계연도를 쓰면 룩어헤드
    fy = fin.get("fiscal_year")
    if fy is not None and date:
        expected = int(date[:4]) - 1 if date[5:10] >= "04-01" else int(date[:4]) - 2
        if fy > expected:
            errors.append(
                f"룩어헤드: FY{fy} 재무를 {date} 피처에 사용 (기대 FY{expected}) "
                f"→ 미래 정보 유출"
            )

    # 7) 결측 vs 0 구분
    if news.get("article_count", 0) == 0:
        errors.append("관련 기사 0건 → news_sentiment=0.0은 '중립'이 아니라 '무데이터'")
    if all(m.get(k) is None for k in _PLAUSIBLE):
        errors.append("재무 지표가 전부 결측 → 점수가 기본값으로 채워짐")

    # 8) 이벤트 그라운딩: 출처 기사가 없는 이벤트 = 환각 의심
    ungrounded = [e.get("event") for e in (news.get("key_events") or []) if not e.get("news_ids")]
    if ungrounded:
        warns.append(f"출처 기사를 찾지 못한 이벤트 {len(ungrounded)}건: {ungrounded[:2]}")

    # 9) 관련성 필터가 너무 많이 걸러냈는지
    raw, kept = news.get("article_count_raw", 0), news.get("article_count", 0)
    if raw and kept / raw < 0.1:
        warns.append(f"관련성 필터가 {raw}건 중 {kept}건만 남김({kept / raw:.0%}) → 과대 필터 의심")

    # 10) 상한에 걸려 관련 기사가 버려졌는지 (조용한 유실 금지).
    # 어느 기사를 버릴지가 임의 선택이라, 관련성 필터로 없앤 노이즈가 되살아난다.
    dropped = news.get("article_count_dropped", 0)
    if dropped:
        warns.append(
            f"관련 기사 {dropped}건이 상한({SETTINGS.max_daily_articles})에 걸려 "
            f"임의로 버려짐 → max_daily_articles 상향 검토"
        )

    result = ValidationResult(ok=not errors, errors=errors, warnings=warns)
    return {"validation": result.model_dump()}


# ── Synthesis Agent ────────────────────────────────────────────
_SIGNAL_BANDS = [(8.0, "STRONG_BUY"), (6.5, "BUY"), (4.5, "HOLD"), (3.0, "SELL")]


def _to_signal(composite: float) -> str:
    for thr, sig in _SIGNAL_BANDS:
        if composite >= thr:
            return sig
    return "STRONG_SELL"


def synthesis_agent(state: dict) -> dict:
    news = state.get("news_result") or {}
    fin = state.get("financial_result") or {}
    valid = state.get("validation") or {}

    valuation = fin.get("valuation_score", 5.0)
    health = fin.get("financial_health_score", 5.0)
    news_sent = news.get("news_sentiment", 0.0)
    impact = news.get("news_impact_score", 5)

    # 펀더멘털(가치투자 핵심) + 뉴스 감성 보정.
    # 소셜(대중) 심리 소스가 제거되어 감성 축은 뉴스(전문가 매체) 단일 소스로 산출한다.
    fundamental = valuation * 0.6 + health * 0.4              # 0~10
    sentiment_adj = news_sent * (impact / 10.0) * 2.0         # ±2 내외
    composite = _clip(fundamental + sentiment_adj, 0.0, 10.0)
    signal = _to_signal(composite)

    # 신뢰도: 데이터 품질 + 시그널 마진 - 뉴스 의견분산 (LLM 자기보고 대신 직접 산출).
    # 실데이터 소스는 뉴스·재무 2개뿐이라 base/계수를 2소스 기준으로 재조정한다.
    real_sources = sum(
        1
        for s in (state.get("news_source"), state.get("financial_source"))
        if s and s != "sample"
    )
    quality = 0.5 + 0.125 * real_sources                      # 0.5~0.75 (2소스)
    margin = abs(composite - 5.0) / 5.0                        # 0~1 (확신 강도)
    disagreement = news.get("news_sentiment_std", 0.0)
    confidence = round(_clip(quality + 0.2 * margin - 0.15 * disagreement, 0.2, 0.95), 3)

    # 근거: LLM 있으면 생성, 없으면 템플릿
    events = [e.get("event", "") for e in (news.get("key_events") or [])][:4]
    reason_obj = structured(
        f"종목 {state.get('ticker')} 가치투자 분석 결과:\n"
        f"- 밸류에이션 {valuation}/10, 재무건전성 {health}/10\n"
        f"- 뉴스감성 {news_sent:+.2f}(영향력 {impact}/10)\n"
        f"- 종합점수 {composite:.2f}/10 → 시그널 {signal}\n"
        f"핵심이벤트: {', '.join(events)}\n"
        f"위 수치와 일관되게 가치투자 판단 근거를 2~3문장으로 써라.",
        _Reason,
    )
    if reason_obj is not None and reason_obj.reasoning:
        reasoning = reason_obj.reasoning
    else:
        reasoning = (
            f"밸류에이션 {valuation}/10·재무건전성 {health}/10에 뉴스감성 {news_sent:+.2f}"
            f"(영향력 {impact}/10)를 반영한 종합점수 {composite:.1f}/10으로 "
            f"'{signal}' 판단."
        )

    out = ValueSignal(
        ticker=state["ticker"],
        date=state["date"],
        company_name=state.get("company_name", ""),
        news_sentiment=news_sent,
        news_impact_score=impact,
        news_sentiment_std=news.get("news_sentiment_std", 0.0),
        news_staleness=news.get("staleness", 0.0),
        key_events=[KeyEvent(**e) for e in (news.get("key_events") or [])],
        article_count=news.get("article_count", 0),
        article_count_raw=news.get("article_count_raw", 0),
        financial_health_score=health,
        valuation_score=valuation,
        financial_metrics=FinancialMetrics(**fin.get("metrics", {})),
        financial_fiscal_year=fin.get("fiscal_year"),
        composite_score=round(composite, 3),
        value_investment_signal=signal,
        confidence=confidence,
        reasoning=reasoning,
        news_source=state.get("news_source", ""),
        financial_source=state.get("financial_source", ""),
        validation=ValidationResult(**valid) if valid else ValidationResult(),
    )
    return {"final": out.model_dump()}
