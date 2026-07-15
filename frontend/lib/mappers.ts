import { AVOIDED_ASSET_LABELS } from "./profiling-rules";
import type {
  HorizonAgreement,
  HorizonDirection,
  InvestorProfileSummary,
  MarketCondition,
  MarketStatus,
  PortfolioHolding,
  RecommendedStock,
  RiskFlag,
  RiskGrade,
  SignalLight,
} from "./types";

export interface UserRow {
  id: string;
  display_name: string;
  avatar_label: string;
}

export interface IpsProfileRow {
  user_id: string;
  surveyed_at: string;
  profile_type: "stable" | "aggressive";
  max_risk_tier: number;
  risk_score: number;
  fomo_score: number;
  horizon_score: number;
}

export interface AvoidedAssetRow {
  asset_type: string;
}

export interface StockRow {
  code: string;
  name: string;
  market: "KOSPI" | "KOSDAQ";
  risk_grade: number;
  risk_flags: string[];
}

export interface PredictionRow {
  stock_code: string;
  prediction_date: string;
  signal_light: string;
  rank_percentile: number;
  return_low: number;
  return_high: number;
  return_ci_level: number | null;
  bucket_hit_rate: number;
  similar_case_count: number | null;
  horizon_h5: string | null;
  horizon_h10: string | null;
  horizon_h20: string | null;
  horizon_agreement: string | null;
  caution: string | null;
  display_order: number;
}

export interface PortfolioHoldingRow {
  stock_code: string;
  display_order: number;
}

export interface MarketStatusRow {
  status_date: string;
  condition: string;
  volatility_score: number;
  volume_score: number;
}

export interface ExcludedStock {
  name: string;
  code: string;
  reason: string;
}

const RISK_FLAGS: RiskFlag[] = [
  "spac",
  "managed_stock",
  "low_liquidity",
  "penny_stock",
  "high_volatility",
  "preferred_stock",
];

const SIGNAL_LIGHTS: SignalLight[] = [
  "strong_positive",
  "positive",
  "neutral",
  "negative",
  "strong_negative",
];

const HORIZON_DIRECTIONS: HorizonDirection[] = ["up", "flat", "down"];
const HORIZON_AGREEMENTS: HorizonAgreement[] = ["aligned", "mixed", "conflict"];
const MARKET_CONDITIONS: MarketCondition[] = ["stable", "caution", "high_volatility"];

export function mapMarketStatus(row: MarketStatusRow): MarketStatus {
  return {
    date: row.status_date,
    condition: includes(MARKET_CONDITIONS, row.condition) ? row.condition : "caution",
    volatilityScore: row.volatility_score,
    volumeScore: row.volume_score,
  };
}

export function mapRecommendedStock(
  prediction: PredictionRow,
  stock: StockRow,
): RecommendedStock {
  return {
    code: stock.code,
    name: stock.name,
    market: stock.market,
    riskGrade: toRiskGrade(stock.risk_grade),
    signalLight: includes(SIGNAL_LIGHTS, prediction.signal_light)
      ? prediction.signal_light
      : "neutral",
    rankPercentile: prediction.rank_percentile,
    returnBand: {
      low: prediction.return_low,
      high: prediction.return_high,
      ciLevel: prediction.return_ci_level ?? 0.68,
    },
    hitRate: prediction.bucket_hit_rate,
    similarCaseCount: prediction.similar_case_count ?? 0,
    horizonAgreement: {
      h5: toHorizonDirection(prediction.horizon_h5),
      h10: toHorizonDirection(prediction.horizon_h10),
      h20: toHorizonDirection(prediction.horizon_h20),
      agreement: includes(HORIZON_AGREEMENTS, prediction.horizon_agreement)
        ? prediction.horizon_agreement
        : "mixed",
    },
    riskFlags: toRiskFlags(stock.risk_flags),
    ...(prediction.caution ? { caution: prediction.caution } : {}),
  };
}

export function mapProfileSummary(
  user: UserRow,
  profile: IpsProfileRow,
): InvestorProfileSummary {
  const horizon =
    profile.horizon_score >= 67
      ? "short"
      : profile.horizon_score >= 34
        ? "mid"
        : "long";
  const stable = profile.profile_type === "stable";
  const personaLabel = stable
    ? horizon === "long"
      ? "신중한 장기 투자자"
      : "신중한 중장기 투자자"
    : "적극적인 기회 탐색형 투자자";

  return {
    displayName: user.display_name,
    avatarLabel: user.avatar_label,
    profileTypeLabel: stable ? "안정추구형" : "수익추구형",
    personaLabel,
    riskTolerance: profile.risk_score,
    sentimentSensitivity: profile.fomo_score,
    horizon,
    surveyedAt: profile.surveyed_at.slice(0, 7).replace("-", "."),
  };
}

export function mapPortfolioHolding(
  holding: PortfolioHoldingRow,
  stock: StockRow,
  prediction?: PredictionRow,
): PortfolioHolding {
  return {
    code: holding.stock_code,
    name: stock.name,
    signalLight:
      prediction && includes(SIGNAL_LIGHTS, prediction.signal_light)
        ? prediction.signal_light
        : "neutral",
  };
}

export function mapAvoidedAssetLabels(rows: AvoidedAssetRow[]): string[] {
  const selected = new Set(rows.map(({ asset_type }) => asset_type));
  return RISK_FLAGS.filter((flag) => selected.has(flag)).map(
    (flag) => AVOIDED_ASSET_LABELS[flag],
  );
}

export function mapExcludedStocks(
  stocks: StockRow[],
  avoidedRows: AvoidedAssetRow[],
): ExcludedStock[] {
  const avoided = new Set(
    avoidedRows
      .map(({ asset_type }) => asset_type)
      .filter((flag): flag is RiskFlag => includes(RISK_FLAGS, flag)),
  );

  return stocks.flatMap((stock) => {
    const reason = RISK_FLAGS.find(
      (flag) => avoided.has(flag) && stock.risk_flags.includes(flag),
    );
    return reason
      ? [{ name: stock.name, code: stock.code, reason: AVOIDED_ASSET_LABELS[reason] }]
      : [];
  });
}

export function toRiskFlags(values: string[]): RiskFlag[] {
  return values.filter((value): value is RiskFlag => includes(RISK_FLAGS, value));
}

function toRiskGrade(value: number): RiskGrade {
  if (![1, 2, 3, 4, 5].includes(value)) {
    throw new Error(`지원하지 않는 위험 등급입니다: ${value}`);
  }
  return value as RiskGrade;
}

function toHorizonDirection(value: string | null): HorizonDirection {
  return includes(HORIZON_DIRECTIONS, value) ? value : "flat";
}

function includes<T extends string>(values: readonly T[], value: unknown): value is T {
  return typeof value === "string" && values.includes(value as T);
}
