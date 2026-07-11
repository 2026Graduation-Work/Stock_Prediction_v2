// 데모용 목데이터. 추후 Supabase 조회로 교체하되 형태는 schema/ 계약을 따른다.
// (수치는 디자인 프로토타입 "Main Dashboard" 기준)

import type {
  InvestorProfileSummary,
  MarketStatus,
  PortfolioHolding,
  RecommendedStock,
} from "./types";

export const marketStatus: MarketStatus = {
  date: "2026-07-07",
  condition: "caution",
  volatilityScore: 61,
  volumeScore: 48,
};

export const investorProfile: InvestorProfileSummary = {
  displayName: "김민지",
  avatarLabel: "민",
  profileTypeLabel: "안정추구형",
  personaLabel: "신중한 장기 투자자",
  riskTolerance: 35,
  sentimentSensitivity: 62,
  horizon: "long",
  surveyedAt: "2026.03",
};

export const recommendedStocks: RecommendedStock[] = [
  {
    code: "005930",
    name: "삼성전자",
    market: "KOSPI",
    riskGrade: 4,
    signalLight: "positive",
    rankPercentile: 0.82,
    returnBand: { low: -0.8, high: 4.2, ciLevel: 0.68 },
    hitRate: 0.61,
    similarCaseCount: 128,
    horizonAgreement: { h5: "up", h10: "up", h20: "up", agreement: "aligned" },
    riskFlags: [],
  },
  {
    code: "005380",
    name: "현대차",
    market: "KOSPI",
    riskGrade: 5,
    signalLight: "strong_positive",
    rankPercentile: 0.95,
    returnBand: { low: 0.6, high: 7.2, ciLevel: 0.68 },
    hitRate: 0.66,
    similarCaseCount: 52,
    horizonAgreement: { h5: "up", h10: "up", h20: "up", agreement: "aligned" },
    riskFlags: [],
  },
  {
    code: "068270",
    name: "셀트리온",
    market: "KOSDAQ",
    riskGrade: 2,
    signalLight: "neutral",
    rankPercentile: 0.59,
    returnBand: { low: -2.0, high: 7.4, ciLevel: 0.68 },
    hitRate: 0.57,
    similarCaseCount: 34,
    horizonAgreement: { h5: "up", h10: "up", h20: "flat", agreement: "mixed" },
    riskFlags: ["high_volatility"],
    caution:
      "안정추구형 성향보다 변동성이 큰 종목입니다. 담더라도 비중을 낮게 가져가는 것을 권장합니다.",
  },
];

// 회피 설정(avoided_assets)으로 추천에서 제외된 종목 안내
export const avoidanceNotice = {
  excludedCount: 1,
  avoidedLabels: ["SPAC", "관리종목"],
};

export const portfolioHoldings: PortfolioHolding[] = [
  { code: "005930", name: "삼성전자", signalLight: "positive" },
  { code: "035720", name: "카카오", signalLight: "negative" },
  { code: "068270", name: "셀트리온", signalLight: "neutral" },
  { code: "005380", name: "현대차", signalLight: "strong_positive" },
];
