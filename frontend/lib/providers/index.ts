// 종목 상세 인사이트 어댑터. 인터페이스 뒤에 픽스처 구현을 둔다.
// 대상 종목은 삼성전자(005930)·현대차(005380)이고, 그 외 종목은 null을 돌려준다.

import type { NudgeMarket } from "../profiling/nudges";
import type { PortfolioHolding, RiskGrade, StockDetail } from "../types";
import {
  CONTRIBUTION_FIXTURE,
  FINANCIAL_FIXTURE,
  HYUNDAI_SENTIMENT,
  SUPPLY_FIXTURE,
  VOLATILITY_PERCENTILE_FIXTURE,
  businessDaysEndingAt,
} from "./fixtures.ts";
import { SAMSUNG_SENTIMENT } from "./sentiment-fixture.ts";

// 억원. + 순매수, - 순매도. 날짜 오름차순.
export interface SupplyDemandDay {
  date: string;
  retail: number;
  foreign: number;
  institution: number;
}
export type SupplyDemandProvider = (code: string) => Promise<SupplyDemandDay[] | null>;

export interface SentimentDay {
  date: string;
  score: number; // -1(부정) ~ +1(긍정)
  articleCount: number;
}
export interface Headline {
  date: string;
  title: string;
  press: string;
}
// 생성 파일(sentiment-fixture.ts)이 쓰는 형태. 생성 스크립트와 맞춰야 한다.
export interface SentimentSeries {
  days: SentimentDay[]; // 날짜 오름차순
  headlines: Headline[]; // 대표 기사 3건
}
export interface SentimentData extends SentimentSeries {
  source: "real" | "synthetic"; // real = 실제 기사에서 집계
}
export type SentimentProvider = (code: string) => Promise<SentimentData | null>;

export type ContributionCategory = "technical" | "financial" | "sentiment" | "supply";
export interface ContributionSignalInput {
  signal: string;
  label: string;
  category: ContributionCategory;
  weight: number;
  description: string;
}
export interface ContributionSignal extends Omit<ContributionSignalInput, "weight"> {
  share: number; // 0~100, 종목 안에서 합 100
}
export type ContributionProvider = (code: string) => Promise<ContributionSignal[] | null>;

export interface FinancialMetric {
  key: string;
  label: string;
  value: number;
  unit: "배" | "%";
  description: string;
}
export interface FinancialSnapshot {
  period: string;
  metrics: FinancialMetric[];
}
export type FinancialProvider = (code: string) => Promise<FinancialSnapshot | null>;

// TODO: KRX 약관 검증이 끝나면 pykrx 구현체로 교체할 자리.
export const supplyDemandProvider: SupplyDemandProvider = async (code) =>
  SUPPLY_FIXTURE[code] ?? null;

const SENTIMENT_BY_CODE: Record<string, SentimentData> = {
  "005930": { ...SAMSUNG_SENTIMENT, source: "real" },
  "005380": { ...HYUNDAI_SENTIMENT, source: "synthetic" },
};
export const sentimentProvider: SentimentProvider = async (code) =>
  SENTIMENT_BY_CODE[code] ?? null;

export const contributionProvider: ContributionProvider = async (code) => {
  const inputs = CONTRIBUTION_FIXTURE[code];
  if (!inputs) return null;
  const total = inputs.reduce((sum, { weight }) => sum + Math.abs(weight), 0);
  return inputs
    .map(({ weight, ...signal }) => ({ ...signal, share: (Math.abs(weight) / total) * 100 }))
    .sort((left, right) => right.share - left.share);
};

export const financialProvider: FinancialProvider = async (code) =>
  FINANCIAL_FIXTURE[code] ?? null;

export type HoldingWeight = Pick<PortfolioHolding, "code" | "quantity" | "avgBuyPrice">;

export interface StockInsights {
  supply: SupplyDemandDay[] | null;
  sentiment: SentimentData | null;
  contributions: ContributionSignal[] | null;
  financial: FinancialSnapshot | null;
}

export async function loadStockInsights(code: string): Promise<StockInsights> {
  const [supply, sentiment, contributions, financial] = await Promise.all([
    supplyDemandProvider(code),
    sentimentProvider(code),
    contributionProvider(code),
    financialProvider(code),
  ]);
  return { supply, sentiment, contributions, financial };
}

export interface Period {
  start: string; // YYYY-MM-DD
  end: string;
}

// mock 시세는 날짜 없이 기준일까지의 종가 배열이다. 기준일에서 거래일을 거꾸로 세어 기간을 만든다.
export function pricePeriod(detail: StockDetail): Period | null {
  const count = detail.priceHistory?.length ?? 0;
  if (count < 2) return null;
  const dates = businessDaysEndingAt(detail.asOf, count);
  return { start: dates[0], end: dates[dates.length - 1] };
}

export function sentimentPeriod(sentiment: SentimentSeries): Period | null {
  const { days } = sentiment;
  return days.length ? { start: days[0].date, end: days[days.length - 1].date } : null;
}

export const periodsOverlap = (left: Period, right: Period) =>
  left.start <= right.end && right.start <= left.end;

export interface RiskSnapshot {
  volatilityAnnual: number; // 일간 로그수익률 표준편차 × √252
  volatilityPercentile: number; // 0~1, FIXTURE
  drawdownFrom3mHigh: number; // 60거래일(≈3개월) 최고가 대비
  return3d: number;
  riskGrade: RiskGrade; // 1 매우 위험 ~ 5 매우 안전
}

// priceHistory(최근 60거래일 종가)에서 계산한다. 변동성 백분위만 픽스처다.
export function riskSnapshot(detail: StockDetail): RiskSnapshot | null {
  const prices = detail.priceHistory ?? [];
  const volatilityPercentile = VOLATILITY_PERCENTILE_FIXTURE[detail.code];
  if (prices.length < 4 || volatilityPercentile === undefined) return null;

  const returns = prices.slice(1).map((price, index) => Math.log(price / prices[index]));
  const mean = returns.reduce((sum, value) => sum + value, 0) / returns.length;
  const variance =
    returns.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (returns.length - 1);
  const last = prices[prices.length - 1];
  return {
    volatilityAnnual: Math.sqrt(variance * 252),
    volatilityPercentile,
    drawdownFrom3mHigh: last / Math.max(...prices) - 1,
    return3d: last / prices[prices.length - 4] - 1,
    riskGrade: detail.riskGrade,
  };
}

// 넛지 판정 입력. 필요한 데이터가 하나라도 없으면 null이고, 그 종목은 넛지를 판정하지 않는다.
// 감성 변화(N07)는 감성 시계열의 마지막 두 날 기준이다. 시세 기준일과 맞추지 않는다.
export function toNudgeMarket(
  detail: StockDetail,
  insights: StockInsights,
  holdings: HoldingWeight[],
): NudgeMarket | null {
  const risk = riskSnapshot(detail);
  const { supply, sentiment } = insights;
  if (!risk || !supply?.length || !sentiment || sentiment.days.length < 2) return null;

  let retailStreak = 0;
  for (let index = supply.length - 1; index >= 0 && supply[index].retail > 0; index -= 1) {
    retailStreak += 1;
  }
  const latest = supply[supply.length - 1];
  const [previousDay, latestDay] = sentiment.days.slice(-2);
  // ponytail: 보유 비중은 매입금액(수량 × 평단) 기준. 보유 종목 현재가가 연결되면 평가금액 기준으로 바꾼다.
  const cost = ({ quantity, avgBuyPrice }: HoldingWeight) => quantity * avgBuyPrice;
  const topHolding = holdings.reduce<HoldingWeight | null>(
    (top, holding) => (!top || cost(holding) > cost(top) ? holding : top),
    null,
  );

  return {
    retailNetBuyStreakDays: retailStreak,
    retailNetLatest: latest.retail,
    foreignNetLatest: latest.foreign,
    institutionNetBuyDaysOf5: supply.slice(-5).filter(({ institution }) => institution > 0).length,
    volatilityPercentile: risk.volatilityPercentile,
    drawdownFrom3mHigh: risk.drawdownFrom3mHigh,
    return3d: risk.return3d,
    sentimentChange: latestDay.score - previousDay.score,
    isTopHolding: topHolding?.code === detail.code,
    riskGrade: detail.riskGrade,
  };
}
