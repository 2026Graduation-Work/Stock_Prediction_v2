"""출력/중간 데이터 스키마 (Pydantic v2).

피처 설계 원칙
- 다운스트림 모델이 (ticker, date)로 OHLCV와 조인할 수 있게 복합키 보장.
- 점수는 100% 결정론 공식으로 산출(설명가능성·재현성). LLM은 라벨·추출·설명만.
- 소셜(대중 심리) 소스는 제외되고 뉴스(전문가 매체) 감성만 피처로 노출한다.

## 행 스스로 감사 가능(self-auditing)

출력 행 안의 모든 숫자를 그 행만 보고 재계산할 수 있어야 한다 — 이게 화이트박스다:

    composite  = clip(valuation_score*0.6 + financial_health_score*0.4
                      + news_sentiment*(news_impact_score/10)*2, 0, 10)
    signal     = band(composite)
    confidence = clip(0.5 + 0.125*real_sources - 0.15*news_sentiment_std
                      + 0.2*|composite-5|/5, 0.2, 0.95)

news_impact_score를 노출하는 이유가 이것이다 — composite 공식의 1급 항이라
빼면 재계산이 불가능해진다. article_count는 결측 지시자다: news_sentiment=0.0은
'기사 없음'과 '중립 기사' 둘 다이며 std도 양쪽 0.0이라 구분할 방법이 이것뿐이다.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Signal = Literal["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]


class FinancialMetrics(BaseModel):
    """모델 입력용 '비중복' 핵심 재무 지표 (차원당 대표 1개).

    PER·PBR·PSR·PEG·EV/EBITDA(밸류에이션), ROE·ROA·마진(수익성),
    유동/당좌비율·이자보상배율(유동성) 등은 서로 강하게 상관(다중공선성)되어
    중복 지표를 제거하고 각 축의 대표값만 노출한다. 제거된 지표들의 정보는
    financial_health_score / valuation_score 두 종합점수에 이미 반영되어 있다.
    값이 없으면 None(결측).
    """

    per: float | None = None              # 밸류에이션 대표: 주가수익비율
    pbr: float | None = None              # 밸류에이션 보조: 주가순자산비율
    roe: float | None = None              # 수익성 대표: 자기자본이익률
    revenue_growth: float | None = None   # 성장성 대표: 매출 증가율(전년 대비)
    debt_ratio: float | None = None       # 안정성 대표: 부채총계/자본총계 (배)
    altman_z: float | None = None         # 부도 위험 종합: Altman Z-Score


class KeyEvent(BaseModel):
    """핵심 이벤트 + 출처 (HITL '근거·출처 항상 표시')."""

    event: str
    news_ids: list[str] = Field(default_factory=list)  # 근거 기사 식별자


class NewsAnalysis(BaseModel):
    news_sentiment: float = Field(0.0, ge=-1, le=1)   # -1 극부정 ~ +1 극긍정
    news_impact_score: int = Field(5, ge=1, le=10)    # 주가 영향력(부정이어도 클 수 있음)
    news_sentiment_std: float = Field(0.0, ge=0)      # 기사 간 의견 분산(불확실성)
    key_events: list[KeyEvent] = Field(default_factory=list)
    article_count: int = 0                            # 관련성 필터 통과 기사 수
    article_count_raw: int = 0                        # 필터 전 그날 전체 기사 수
    article_count_dropped: int = 0                    # 상한에 걸려 버려진 관련 기사 수
    staleness: float = Field(0.0, ge=0, le=1)         # 직전 기사와의 중복률(Tetlock)
    backend: str = "none"  # 감성 산출 백엔드(kr-finbert / lexicon)
    relevance_backend: str = "none"  # 관련성 필터 백엔드(llm / rule)
    reasoning: str = ""


class FinancialAnalysis(BaseModel):
    financial_health_score: float = Field(5.0, ge=0, le=10)  # 재무 건전성
    valuation_score: float = Field(5.0, ge=0, le=10)         # 저평가 정도
    metrics: FinancialMetrics = Field(default_factory=FinancialMetrics)
    fiscal_year: int | None = None  # 어느 사업연도 재무를 썼는지 (point-in-time 감사)
    source: str = "sample"  # dart / sample
    reasoning: str = ""


class ValidationResult(BaseModel):
    """규칙 기반 검증 결과 (LLM 아님 — 결정론).

    LLM 크리틱을 쓰지 않는 이유: 외부 피드백 없는 자기검증은 실증적으로
    성능을 떨어뜨린다(Huang et al., ICLR 2024 — CommonSenseQA 75.8→41.8).
    자기교정이 작동하는 경우는 도구·규칙·검증기 같은 '외부 피드백'뿐이다.
    """

    ok: bool = True
    errors: list[str] = Field(default_factory=list)    # 출력을 신뢰할 수 없음
    warnings: list[str] = Field(default_factory=list)  # 주의가 필요하나 치명적이진 않음


class ValueSignal(BaseModel):
    """최종 출력 — 다운스트림 모델용 가치투자 피처 한 줄(=하루치)."""

    # 식별자 (복합 기본키)
    ticker: str
    date: str
    company_name: str = ""

    # 뉴스
    news_sentiment: float = 0.0
    news_impact_score: int = 5
    news_sentiment_std: float = 0.0
    news_staleness: float = 0.0          # 0=새 정보, 1=직전 기사 재탕 (Tetlock 2011)
    key_events: list[KeyEvent] = Field(default_factory=list)
    article_count: int = 0               # 관련성 통과 기사 수 (결측 지시자)
    article_count_raw: int = 0           # 필터 전 전체 기사 수

    # 재무
    financial_health_score: float = 5.0
    valuation_score: float = 5.0
    financial_metrics: FinancialMetrics = Field(default_factory=FinancialMetrics)
    financial_fiscal_year: int | None = None  # point-in-time 감사용

    # 종합 판단
    composite_score: float = Field(5.0, ge=0, le=10)  # 시그널을 결정하는 실제 점수
    value_investment_signal: Signal = "HOLD"
    confidence: float = Field(0.5, ge=0, le=1)
    reasoning: str = ""

    # 출처 (HITL: 근거·출처 항상 표시)
    news_source: str = ""       # bigkinds / naver_api / naver / sample
    financial_source: str = ""  # dart / sample

    # 검증 (규칙 기반, 결정론)
    validation: ValidationResult = Field(default_factory=ValidationResult)
