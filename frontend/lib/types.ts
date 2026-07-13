// 대시보드 UI 타입. 값 체계는 schema/ v1.0 freeze 계약을 그대로 따른다.
// (chart_output.schema.json: signal_light·rank_percentile·return_band·confidence·horizon_agreement·risk_flags)

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
