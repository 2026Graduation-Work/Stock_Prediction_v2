"""출력/중간 데이터 스키마 (Pydantic v2).

피처 설계 원칙
- 다운스트림 모델이 (ticker, date)로 OHLCV와 조인할 수 있게 복합키 보장.
- 점수는 가능한 한 결정론적 공식으로 산출(설명가능성·재현성) + LLM은 보조.
- 뉴스/소셜을 분리해 '전문가 시각 vs 대중 심리' 다이버전스를 피처로 노출.
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


class NewsAnalysis(BaseModel):
    news_sentiment: float = Field(0.0, ge=-1, le=1)   # -1 극부정 ~ +1 극긍정
    news_impact_score: int = Field(5, ge=1, le=10)    # 주가 영향력(부정이어도 클 수 있음)
    news_sentiment_std: float = Field(0.0, ge=0)      # 기사 간 의견 분산(불확실성)
    key_events: list[str] = Field(default_factory=list)
    article_count: int = 0
    backend: str = "none"  # 감성 산출 백엔드(kr-finbert / lexicon)
    reasoning: str = ""


class SocialAnalysis(BaseModel):
    social_buzz: int = 0                              # 언급량(관심도 지표)
    social_sentiment: float = Field(0.0, ge=-1, le=1)
    post_count: int = 0
    backend: str = "none"
    reasoning: str = ""


class FinancialAnalysis(BaseModel):
    financial_health_score: float = Field(5.0, ge=0, le=10)  # 재무 건전성
    valuation_score: float = Field(5.0, ge=0, le=10)         # 저평가 정도
    metrics: FinancialMetrics = Field(default_factory=FinancialMetrics)
    source: str = "sample"  # dart / sample
    reasoning: str = ""


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
    key_events: list[str] = Field(default_factory=list)

    # 소셜
    social_buzz: int = 0
    social_sentiment: float = 0.0
    sentiment_divergence: float = 0.0  # news_sentiment - social_sentiment

    # 재무
    financial_health_score: float = 5.0
    valuation_score: float = 5.0
    financial_metrics: FinancialMetrics = Field(default_factory=FinancialMetrics)

    # 종합 판단
    value_investment_signal: Signal = "HOLD"
    confidence: float = Field(0.5, ge=0, le=1)
    reasoning: str = ""

    # 메타 (데이터 출처/완전성 → 신뢰도 보정 및 디버깅용)
    data_quality: dict = Field(default_factory=dict)
