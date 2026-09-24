// 종목 상세 인사이트 어댑터. 인터페이스 뒤에 실데이터 스냅샷과 픽스처 구현을 둔다.
// 시세·수급·재무·감성은 데모 4종목, 모델 기여도 픽스처는 삼성전자·현대차를 지원한다.

import type { NudgeMarket } from "../profiling/nudges";
import type { DataProvenance, PortfolioHolding, RiskGrade, StockDetail } from "../types";
import {
  CONTRIBUTION_FIXTURE,
  VOLATILITY_PERCENTILE_FIXTURE,
  businessDaysEndingAt,
} from "./fixtures.ts";
import HYUNDAI_SENTIMENT from "./sentiment-005380.json" with { type: "json" };
import KAKAO_SENTIMENT from "./sentiment-035720.json" with { type: "json" };
import CELLTRION_SENTIMENT from "./sentiment-068270.json" with { type: "json" };
import { SAMSUNG_SENTIMENT } from "./sentiment-fixture.ts";
import {
  FINANCIAL_SNAPSHOT,
  FINANCIAL_SOURCE,
  PRICE_PROVENANCE,
  SNAPSHOT_AS_OF,
  STOCK_SNAPSHOT,
  SUPPLY_PROVENANCE,
  SUPPLY_SNAPSHOT,
} from "./demo-snapshot.ts";

// 순매수 수량(주). + 순매수, - 순매도. 날짜 오름차순. 기타법인은 원천(네이버 금융)에 없어 뺐다.
export interface SupplyDemandDay {
  date: string;
  retail: number;
  foreign: number;
  institution: number; // 기관합계
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
  track?: NewsTrack["track"];
  provider?: NewsTrack["source"];
  backend?: string;
  status?: NewsTrackStatus;
  asOf?: string;
  coverage?: NewsTrackCoverage;
}
export type SentimentProvider = (code: string) => Promise<SentimentData | null>;

export type NewsTrackStatus = "ok" | "partial" | "insufficient_data";

export interface NewsTrackCoverage {
  fetched_count: number;
  relevant_count: number;
  publisher_count: number;
  newest_published_at: string | null;
  lag_minutes: number | null;
  provider_total_results?: number | null;
  provider_returned_count?: number | null;
  provider_pages?: number | null;
  provider_truncated?: boolean;
}

export interface NewsTrackPoint {
  date: string;
  status: "ok" | "insufficient_data";
  sentiment_mean: number | null;
  sentiment_std: number | null;
  article_count: number;
  publisher_count: number;
}

export interface NewsTrackArticle {
  news_id: string;
  ticker: string;
  title: string;
  press: string;
  url: string;
  date: string;
  published_at: string;
  event_id: string;
  sentiment_score: number;
}

export interface NewsTrack {
  schema_version: "1.0";
  track: "historical" | "live";
  scope: { ticker: string; company_name: string };
  source: "bigkinds" | "newsapi_ai";
  as_of: string;
  backend: string;
  status: NewsTrackStatus;
  coverage: NewsTrackCoverage;
  timeline: NewsTrackPoint[];
  articles: NewsTrackArticle[];
}

export function sentimentFromTrack(track: NewsTrack): SentimentData {
  return {
    days: track.timeline.flatMap((point) =>
      point.sentiment_mean === null
        ? []
        : [{ date: point.date, score: point.sentiment_mean, articleCount: point.article_count }],
    ),
    headlines: track.articles.slice(0, 3).map(({ date, title, press }) => ({ date, title, press })),
    source: "real",
    track: track.track,
    provider: track.source,
    backend: track.backend,
    status: track.status,
    asOf: track.as_of,
    coverage: track.coverage,
  };
}

export type ContributionCategory = "technical" | "financial" | "sentiment" | "supply";
export interface ContributionSignalInput {
  signal: string;
  label: string;
  category: ContributionCategory;
  weight: number;
  direction?: 1 | -1; // 신호를 미는 쪽. +1 오르는 쪽(기본), -1 내리는 쪽
  description: string;
}
export interface ContributionSignal extends Omit<ContributionSignalInput, "weight" | "direction"> {
  share: number; // 0~100, 종목 안에서 합 100
  direction: 1 | -1;
}
export type ContributionProvider = (code: string) => Promise<ContributionSignal[] | null>;

export interface FinancialMetric {
  key: string;
  label: string;
  value: number | null; // null = 확인 불가(검증 탈락·계산 불가). note에 이유
  unit: "배" | "%";
  basis: string; // 계산 근거(식과 원자료 값)
  note: string | null;
}
export interface FinancialSnapshot {
  period: string;
  metrics: FinancialMetric[];
}

const FINANCIAL_LABEL: Record<string, string> = {
  per: "PER",
  pbr: "PBR",
  roe: "ROE",
  operating_margin: "영업이익률",
  debt_ratio: "부채비율",
  revenue_growth: "매출 증가율(전년 대비)",
};
export type FinancialProvider = (code: string) => Promise<FinancialSnapshot | null>;

export const supplyDemandProvider: SupplyDemandProvider = async (code) =>
  SUPPLY_SNAPSHOT[code] ?? null;

const SENTIMENT_BY_CODE: Record<string, SentimentData> = {
  "005930": { ...SAMSUNG_SENTIMENT, source: "real" },
  "005380": sentimentFromTrack(HYUNDAI_SENTIMENT as NewsTrack),
  "035720": sentimentFromTrack(KAKAO_SENTIMENT as NewsTrack),
  "068270": sentimentFromTrack(CELLTRION_SENTIMENT as NewsTrack),
};
export const sentimentProvider: SentimentProvider = async (code) =>
  SENTIMENT_BY_CODE[code] ?? null;

export const contributionProvider: ContributionProvider = async (code) => {
  const inputs = CONTRIBUTION_FIXTURE[code];
  if (!inputs) return null;
  const total = inputs.reduce((sum, { weight }) => sum + Math.abs(weight), 0);
  return inputs
    .map(({ weight, direction = 1, ...signal }) => ({
      ...signal,
      direction,
      share: (Math.abs(weight) / total) * 100,
    }))
    .sort((left, right) => right.share - left.share);
};

export const financialProvider: FinancialProvider = async (code) => {
  const row = FINANCIAL_SNAPSHOT[code];
  if (!row) return null;
  return {
    period: `${row.fiscalYear} 사업연도 · ${row.statement}재무제표 · 사업보고서 ${row.filedAt} 공시(접수번호 ${row.receiptNo}) · 주식수 ${row.sharesBasis} · 주가 ${SNAPSHOT_AS_OF} 종가`,
    metrics: row.metrics.map((metric) => ({ ...metric, label: FINANCIAL_LABEL[metric.key] ?? metric.key })),
  };
};

export type HoldingWeight = Pick<PortfolioHolding, "code" | "quantity" | "avgBuyPrice">;

// 가격·거래량으로 본 분위기 한 줄(psychology_market_v1). 구간 말 + 풀이.
export interface PsychologyLine {
  word: string;
  explain: string;
  axis: number; // psych_greed_fear_axis -1(움츠러듦)~+1(들뜸). 숫자는 계산 근거에만
  provenance: DataProvenance;
}

export interface StockInsights {
  psychology: PsychologyLine | null;
  supply: SupplyDemandDay[] | null;
  sentiment: SentimentData | null;
  contributions: ContributionSignal[] | null;
  financial: FinancialSnapshot | null;
  provenance: Record<"supply" | "sentiment" | "contributions" | "financial", DataProvenance>;
}

const FIXTURE: DataProvenance = { kind: "fixture", source: "픽스처" };

export async function loadStockInsights(code: string): Promise<StockInsights> {
  const [supply, sentiment, contributions, financial] = await Promise.all([
    supplyDemandProvider(code),
    sentimentProvider(code),
    contributionProvider(code),
    financialProvider(code),
  ]);
  const psychology = STOCK_SNAPSHOT[code]?.psychology;
  return {
    psychology: psychology
      ? {
          word: psychology.word,
          explain: "최근 20일 오름세와 석 달 평균 거래 가격 대비 위치로 본 분위기예요",
          axis: psychology.axis,
          provenance: PRICE_PROVENANCE,
        }
      : null,
    supply,
    sentiment,
    contributions,
    financial,
    provenance: {
      supply: supply ? SUPPLY_PROVENANCE : FIXTURE,
      sentiment:
        sentiment?.source === "real"
          ? {
              kind: "real",
              source:
                sentiment.provider && sentiment.backend
                  ? `${sentiment.provider === "bigkinds" ? "BigKinds" : "NewsAPI.ai"} · ${sentiment.backend === "kr-finbert" ? "KR-FinBERT" : sentiment.backend}`
                  : "BigKinds · KR-FinBERT",
              asOf: sentiment.asOf?.slice(0, 10) ?? sentiment.days.at(-1)?.date,
            }
          : FIXTURE,
      contributions: FIXTURE,
      financial: financial ? { kind: "real", source: FINANCIAL_SOURCE, asOf: SNAPSHOT_AS_OF } : FIXTURE,
    },
  };
}

// 여러 입력에서 파생된 수치(넛지 등)는 입력이 모두 실데이터일 때만 실데이터다.
export function combinedProvenance(...inputs: DataProvenance[]): DataProvenance {
  return inputs.every(({ kind }) => kind === "real") ? inputs[0] : FIXTURE;
}

export interface Period {
  start: string; // YYYY-MM-DD
  end: string;
}

// mock 시세는 날짜 없이 기준일까지의 종가 배열이다. 기준일에서 거래일을 거꾸로 세어 기간을 만든다.
export function pricePeriod(detail: StockDetail): Period | null {
  const count = detail.priceHistory?.length ?? 0;
  if (count < 2) return null;
  if (detail.priceDates?.length === count) {
    return { start: detail.priceDates[0], end: detail.priceDates[count - 1] };
  }
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
