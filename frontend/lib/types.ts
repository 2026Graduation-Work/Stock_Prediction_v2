// schema/ v1.0에서 파생된 프론트 타입입니다. 스키마 변경 시 반드시 동기화합니다.
// chart_output.schema.json: signal_light·rank_percentile·return_band·confidence·horizon_agreement·risk_flags

export type SignalLight =
  | "strong_positive"
  | "positive"
  | "neutral"
  | "negative"
  | "strong_negative";

export type HorizonDirection = "up" | "flat" | "down";

export type HorizonAgreement = "aligned" | "mixed" | "conflict";

export type RiskFlag =
  | "spac"
  | "managed_stock"
  | "low_liquidity"
  | "penny_stock"
  | "high_volatility"
  | "preferred_stock";

export type RiskGrade = 1 | 2 | 3 | 4 | 5; // 5 = 매우 안전, 1 = 매우 위험

export interface ReturnBand {
  low: number; // 밴드 하한(%). -1.2 = -1.2%
  high: number; // 밴드 상한(%)
  ciLevel: number; // 신뢰구간 수준 (예: 0.68)
}

export interface HorizonAgreementSet {
  h5: HorizonDirection;
  h10: HorizonDirection;
  h20: HorizonDirection;
  agreement: HorizonAgreement;
}

export interface RecommendedStock {
  code: string;
  name: string;
  market: "KOSPI" | "KOSDAQ";
  riskGrade: RiskGrade;
  signalLight: SignalLight;
  rankPercentile: number; // 0~1, 1이 당일 신호 강도 최상위
  returnBand: ReturnBand;
  hitRate: number; // 0~1, 과거 유사 신호 구간 적중률 (confidence.bucket_hit_rate)
  similarCaseCount: number;
  horizonAgreement: HorizonAgreementSet;
  riskFlags: RiskFlag[];
  caution?: string; // 성향 대비 주의 문구. 있을 때만 카드 하단에 표시
}

// 예측 근거 출처 구분 (chart=차트 지표, news=뉴스 감성, financial=재무 지표)
export type ReasonSource = "chart" | "news" | "financial";

export interface PredictionReason {
  title: string; // 예: 최근 20거래일 거래량이 평소의 2.8배
  detail: string; // 기여도 수준 + 보조 설명
  source: ReasonSource;
  sourceLabel: string; // 칩 표기. 예: 차트 지표 (거래량)
}

// 과거 유사 신호 구간의 실현 수익률 분포 히스토그램 빈. [from, to) 단위 %
export interface ReturnBin {
  from: number;
  to: number;
  count: number;
}

export interface StockDetail extends RecommendedStock {
  currentPrice: number; // 원
  changePercent: number; // 전일 대비 %. +1.2 = +1.2%
  asOf: string; // 데이터·예측 기준일 (ISO). 두 날짜는 항상 동일하게 유지
  priceHistory: number[]; // 최근 60거래일 종가(원). 마지막 원소 = currentPrice
  realizedReturns: ReturnBin[]; // similarCaseCount건의 H10 실현 수익률 분포
  reasons: PredictionReason[]; // 기여도 순 Top 3
  aiAdvice: string; // LLM 생성 설명(수치 번역만, 행동 제안 없음)
}

export type MarketCondition = "stable" | "caution" | "high_volatility";

export interface MarketStatus {
  date: string; // ISO date (YYYY-MM-DD)
  condition: MarketCondition;
  volatilityScore: number; // 0~100
  volumeScore: number; // 0~100
}

export type InvestmentHorizon = "short" | "mid" | "long";

export interface InvestorProfileSummary {
  displayName: string;
  avatarLabel: string;
  profileTypeLabel: string; // 예: 안정추구형 (profiling profile_type의 화면 표기)
  personaLabel: string; // 예: 신중한 장기 투자자
  riskTolerance: number; // 0~100
  sentimentSensitivity: number; // 0~100
  horizon: InvestmentHorizon;
  surveyedAt: string; // 예: 2026.03
}

export interface PortfolioHolding {
  code: string;
  name: string;
  signalLight: SignalLight;
}

export type ProfileType = "stable" | "aggressive";
export type ActionIntent =
  | "buy_consideration"
  | "sell_consideration"
  | "hold_consideration";

export interface ProfilingHolding {
  ticker: string;
  name: string;
  quantity: number;
  avg_buy_price: number;
}

export interface ProfilingOutput {
  user_id: string;
  session_id: string;
  timestamp: string;
  investor_profile: {
    risk_tolerance: number;
    time_horizon_months: number;
    liquidity_need_ratio: number;
    target_return_annual: number;
    investment_experience_years: number;
    profile_type: ProfileType;
  };
  psychological_state: {
    fomo_index: number;
    panic_sell_tendency: number;
    herding_score: number;
    self_confidence: number;
    current_market_anxiety: number;
    overheating_caution: number;
  };
  constraints: {
    avoided_assets: RiskFlag[];
    preferred_sectors: string[];
  };
  portfolio: {
    holdings: ProfilingHolding[];
    watchlist: string[];
  };
  free_text_signal: {
    raw_text: string;
    extracted_signals: Record<string, number>;
    conflict_with_survey: boolean;
  };
  confidence_per_field: Record<string, number>;
  context: {
    target_ticker?: string;
    investment_amount_krw: number;
    action_intent: ActionIntent;
    market_regime_hint?: string;
    benchmark_index?: string;
  };
  meta: {
    schema_version: "1.0.0";
    source: "profiling_block";
    confidence: number;
  };
}
