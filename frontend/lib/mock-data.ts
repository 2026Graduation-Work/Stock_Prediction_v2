// 데모용 목데이터. 추후 Supabase 조회로 교체하되 형태는 schema/ 계약을 따른다.
// (수치는 디자인 프로토타입 "Main Dashboard"/"Stock Detail" 기준.
//  데이터 기준일과 예측 생성일은 하나의 날짜로 통일한다. 팀 리뷰 결정)

import type {
  InvestorProfileSummary,
  MarketStatus,
  PortfolioHolding,
  RecommendedStock,
  StockDetail,
} from "./types";

export const marketStatus: MarketStatus = {
  date: "2025-10-02",
  source: "mock",
  condition: "caution",
  volatilityScore: 61,
  volumeScore: 48,
  indexQuotes: [
    {
      symbol: "KOSPI",
      label: "KOSPI",
      value: 3549.21,
      change: 93.38,
      changePercent: 2.7,
    },
    {
      symbol: "KOSDAQ",
      label: "KOSDAQ",
      value: 854.25,
      change: 8.91,
      changePercent: 1.05,
    },
    {
      symbol: "KOSPI200",
      label: "KOSPI 200",
      value: 493.41,
      change: 14.04,
      changePercent: 2.93,
    },
    {
      symbol: "USD/KRW",
      label: "원/달러",
      value: 1401.82,
      change: -1.33,
      changePercent: -0.09,
    },
  ],
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

const kia: RecommendedStock = {
  code: "000270",
  name: "기아",
  market: "KOSPI",
  riskGrade: 5,
  signalLight: "positive",
  rankPercentile: 0.85,
  returnBand: { low: -0.5, high: 5.5, ciLevel: 0.68 },
  hitRate: 0.64,
  similarCaseCount: 97,
  horizonAgreement: { h5: "up", h10: "up", h20: "up", agreement: "aligned" },
  riskFlags: [],
};

const skHynix: RecommendedStock = {
  code: "000660",
  name: "SK하이닉스",
  market: "KOSPI",
  riskGrade: 4,
  signalLight: "strong_positive",
  rankPercentile: 0.97,
  returnBand: { low: 2.5, high: 13.0, ciLevel: 0.68 },
  hitRate: 0.69,
  similarCaseCount: 41,
  horizonAgreement: { h5: "up", h10: "up", h20: "up", agreement: "aligned" },
  riskFlags: [],
};

const celltrion: RecommendedStock = {
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
    "위험 2등급 종목으로, 안정추구형 성향의 허용 범위(4·5등급) 밖에 있습니다.",
};

// 추천 리스트: max_risk_tier 규칙(안정추구형 = 위험 4·5등급)을 만족하는 종목만.
// 등급 미달 보유 종목(셀트리온)은 추천이 아닌 "보유 종목 알림"으로 분리 노출.
export const recommendedStocks: RecommendedStock[] = [kia, skHynix];

// 보유 중이라 신호를 알려주지만 추천은 아닌 종목 (성향 대비 위험등급 미달)
export const holdingAlerts: RecommendedStock[] = [celltrion];

// 회피 설정(avoided_assets)으로 추천에서 제외된 종목 안내.
// 화이트박스 원칙: 어떤 종목이 왜 빠졌는지 펼쳐서 확인 가능해야 한다.
export const avoidanceNotice = {
  avoidedLabels: ["SPAC", "관리종목"],
  excludedStocks: [{ name: "미래에셋비전스팩3호", code: "418250", reason: "SPAC" }],
};

export const portfolioHoldings: PortfolioHolding[] = [
  {
    code: "005930",
    name: "삼성전자",
    signalLight: "positive",
    quantity: 15,
    avgBuyPrice: 71_200,
  },
  {
    code: "035720",
    name: "카카오",
    signalLight: "negative",
    quantity: 8,
    avgBuyPrice: 48_500,
  },
  {
    code: "068270",
    name: "셀트리온",
    signalLight: "neutral",
    quantity: 3,
    avgBuyPrice: 182_000,
  },
  {
    code: "005380",
    name: "현대차",
    signalLight: "strong_positive",
    quantity: 5,
    avgBuyPrice: 235_000,
  },
];

// 결정론적 60거래일 종가 시리즈(같은 입력 → 같은 출력).
// 웨이포인트 선형 보간에 사인 파동을 얹고, 양 끝은 웨이포인트 값과 정확히 일치시킨다.
function priceSeries(waypoints: number[], wiggle: number, tick: number, days = 60): number[] {
  const spans = waypoints.length - 1;
  return Array.from({ length: days }, (_, i) => {
    const t = (i / (days - 1)) * spans;
    const k = Math.min(Math.floor(t), spans - 1);
    const base = waypoints[k] + (waypoints[k + 1] - waypoints[k]) * (t - k);
    const wave = Math.sin(i * 1.9 + waypoints[0]) + 0.6 * Math.sin(i * 0.7);
    const damp = Math.sin((Math.PI * i) / (days - 1));
    return Math.round((base + wave * wiggle * damp) / tick) * tick;
  });
}

// 종목 상세. 진입 동선: 대시보드 카드 "근거 보기" → /stocks/[code]
export const stockDetails: Record<string, StockDetail> = {
  [celltrion.code]: {
    ...celltrion,
    currentPrice: 190_800,
    changePercent: 1.2,
    asOf: "2025-10-02",
    priceHistory: priceSeries(
      [176_200, 183_400, 178_900, 187_300, 183_900, 192_300, 187_400, 190_800],
      1_400,
      100,
    ),
    realizedReturns: [
      { from: -6, to: -4, count: 2 },
      { from: -4, to: -2, count: 3 },
      { from: -2, to: 0, count: 6 },
      { from: 0, to: 2, count: 7 },
      { from: 2, to: 4, count: 6 },
      { from: 4, to: 6, count: 4 },
      { from: 6, to: 8, count: 3 },
      { from: 8, to: 10, count: 2 },
      { from: 10, to: 12, count: 1 },
    ],
    reasons: [
      {
        title: "최근 20거래일 거래량이 평소의 2.8배",
        detail: "기여도 상 · 매집 또는 이슈성 거래 가능성 모두 포함",
        source: "chart",
        sourceLabel: "차트 지표 (거래량)",
      },
      {
        title: "60일 모멘텀이 전체 종목 상위 15%",
        detail: "기여도 중 · 중기 추세는 우상향 유지",
        source: "chart",
        sourceLabel: "차트 지표 (모멘텀)",
      },
      {
        title: "최근 2주 뉴스 감성은 중립~약긍정",
        detail: "기여도 중 · 바이오시밀러 수주 기사 대비 부정 기사 적음",
        source: "news",
        sourceLabel: "뉴스 감성 분석",
      },
    ],
    aiAdvice:
      "현재 셀트리온은 중립(노랑) 신호로, 방향성이 뚜렷하지 않은 구간입니다. 과거 유사한 신호 34건에서 실현 수익률은 -2.0%에서 +7.4% 사이에 넓게 분포했고, 이 구간의 적중률은 57%로 확신이 높은 편은 아닙니다. 김민지님은 위험 감수 성향(35)이 낮고 심리 민감도(62)가 높은 편이어서, 변동성이 큰 이 종목의 급등락은 심리적 부담이 될 수 있습니다.",
  },
  [kia.code]: {
    ...kia,
    currentPrice: 104_200,
    changePercent: 3.58,
    asOf: "2025-10-02",
    priceHistory: priceSeries(
      [105_100, 103_000, 107_200, 104_900, 101_700, 102_800, 100_200, 104_200],
      800,
      100,
    ),
    realizedReturns: [
      { from: -2, to: -1, count: 3 },
      { from: -1, to: 0, count: 6 },
      { from: 0, to: 1, count: 10 },
      { from: 1, to: 2, count: 16 },
      { from: 2, to: 3, count: 20 },
      { from: 3, to: 4, count: 18 },
      { from: 4, to: 5, count: 13 },
      { from: 5, to: 6, count: 8 },
      { from: 6, to: 7, count: 3 },
    ],
    reasons: [
      {
        title: "20일 이동평균이 60일 이동평균을 상향 돌파",
        detail: "기여도 상 · 교차 이후 6거래일째 추세 유지",
        source: "chart",
        sourceLabel: "차트 지표 (추세)",
      },
      {
        title: "북미 관세 리스크 완화 기대감에 수출주 반등",
        detail: "기여도 중 · 관세 협상 관련 기사 이후 감성 개선",
        source: "news",
        sourceLabel: "뉴스 감성 분석",
      },
      {
        title: "3분기 실적 컨센서스 상향, xEV 판매 확대 전망",
        detail: "기여도 중 · 전기차 물량 증가 반영한 추정치 상향",
        source: "financial",
        sourceLabel: "재무 지표 (실적)",
      },
    ],
    aiAdvice:
      "기아는 긍정(연두) 신호로, 단기(H5)·중기(H10)·장기(H20) 방향이 모두 위를 가리키고 있습니다. 과거 유사 신호 97건에서 실현 수익률은 -0.5%에서 +5.5% 사이에 분포했고, 이 구간의 적중률은 64%였습니다. 위험 5등급(매우 안전) 종목으로 김민지님의 안정추구형 성향(위험 감수 35) 허용 범위 안에 있고, 분포 폭이 넓지 않은 편이라 심리 민감도(62)가 높은 김민지님에게 급등락 부담이 덜한 유형입니다.",
  },
  [skHynix.code]: {
    ...skHynix,
    currentPrice: 395_500,
    changePercent: 9.86,
    asOf: "2025-10-02",
    priceHistory: priceSeries(
      [255_500, 261_500, 260_500, 277_000, 331_000, 361_000, 336_500, 395_500],
      3_500,
      500,
    ),
    realizedReturns: [
      { from: 1, to: 3, count: 3 },
      { from: 3, to: 5, count: 6 },
      { from: 5, to: 7, count: 8 },
      { from: 7, to: 9, count: 9 },
      { from: 9, to: 11, count: 7 },
      { from: 11, to: 13, count: 5 },
      { from: 13, to: 15, count: 3 },
    ],
    reasons: [
      {
        title: "최근 20거래일 거래량이 평소의 3.0배",
        detail: "기여도 상 · 급등과 같은 방향의 거래 급증",
        source: "chart",
        sourceLabel: "차트 지표 (거래량)",
      },
      {
        title: "HBM4 공급 계약 기대감에 뉴스 감성 긍정 비율 급등",
        detail: "기여도 상 · AI 반도체 수요 확대 기사 중심",
        source: "news",
        sourceLabel: "뉴스 감성 분석",
      },
      {
        title: "메모리 반도체 가격 상승 전망에 실적 추정치 상향",
        detail: "기여도 중 · 4분기 영업이익 컨센서스 상향 반영",
        source: "financial",
        sourceLabel: "재무 지표 (실적)",
      },
    ],
    aiAdvice:
      "SK하이닉스는 강한 긍정(초록) 신호로, 오늘 신호 강도 상위 3%에 해당합니다. 과거 유사 신호 41건의 실현 수익률은 +2.5%에서 +13.0%로 분포 하단이 0% 위에 있었고, 이 구간의 적중률은 69%였습니다. 다만 유사 사례 수가 41건으로 많지 않아, 분포 폭의 통계적 확신은 사례가 더 많은 신호보다 낮습니다. 위험 4등급(안전)으로 김민지님의 안정추구형 성향(위험 감수 35) 허용 범위 안에 있지만, 변동성이 큰 구간이라 심리 민감도(62)가 높은 김민지님에게는 급등락 부담이 있을 수 있습니다.",
  },
};
