import type {
  ComparisonDeltaRow,
  ComparisonMetricRow,
  ComparisonProfile,
} from "./performance-types";

export type MetricKey =
  | "auc"
  | "hit_rate"
  | "calibration_brier"
  | "calibration_ece"
  | "sharpe"
  | "mdd"
  | "cumulative_return"
  | "trade_count";

export type DeltaMetricKey = Exclude<
  keyof ComparisonDeltaRow,
  "profile" | "sample"
>;

export type DeltaOutcome =
  | "improved"
  | "worsened"
  | "unchanged"
  | "neutral"
  | "unavailable";

export interface MetricDefinition {
  key: MetricKey;
  deltaKey: DeltaMetricKey;
  label: string;
  shortLabel: string;
  group: "ML" | "Trading";
  direction: "higher" | "lower" | "neutral";
  format: "decimal3" | "decimal2" | "percent" | "integer";
}

export const METRICS: MetricDefinition[] = [
  {
    key: "auc",
    deltaKey: "delta_B_minus_A_auc",
    label: "AUC",
    shortLabel: "AUC",
    group: "ML",
    direction: "higher",
    format: "decimal3",
  },
  {
    key: "hit_rate",
    deltaKey: "delta_B_minus_A_hit_rate",
    label: "적중률",
    shortLabel: "적중률",
    group: "ML",
    direction: "higher",
    format: "decimal3",
  },
  {
    key: "calibration_brier",
    deltaKey: "delta_B_minus_A_calibration_brier",
    label: "Brier",
    shortLabel: "Brier",
    group: "ML",
    direction: "lower",
    format: "decimal3",
  },
  {
    key: "calibration_ece",
    deltaKey: "delta_B_minus_A_calibration_ece",
    label: "ECE",
    shortLabel: "ECE",
    group: "ML",
    direction: "lower",
    format: "decimal3",
  },
  {
    key: "sharpe",
    deltaKey: "delta_B_minus_A_sharpe",
    label: "Sharpe",
    shortLabel: "Sharpe",
    group: "Trading",
    direction: "higher",
    format: "decimal2",
  },
  {
    key: "mdd",
    deltaKey: "delta_B_minus_A_mdd",
    label: "MDD",
    shortLabel: "MDD",
    group: "Trading",
    direction: "higher",
    format: "percent",
  },
  {
    key: "cumulative_return",
    deltaKey: "delta_B_minus_A_cumulative_return",
    label: "누적수익률",
    shortLabel: "누적수익",
    group: "Trading",
    direction: "higher",
    format: "percent",
  },
  {
    key: "trade_count",
    deltaKey: "delta_B_minus_A_trade_count",
    label: "거래 수",
    shortLabel: "거래 수",
    group: "Trading",
    direction: "neutral",
    format: "integer",
  },
];

export const ML_METRICS = METRICS.filter(({ group }) => group === "ML");
export const TRADING_METRICS = METRICS.filter(({ group }) => group === "Trading");

export const PROFILE_LABEL: Record<ComparisonProfile, string> = {
  stable: "안정형",
  aggressive: "공격형",
};

export function formatMetricValue(
  value: ComparisonMetricRow[MetricKey],
  metric: MetricDefinition,
): string {
  if (value === null || !Number.isFinite(value)) return "N/A";
  if (metric.format === "integer") return Math.round(value).toLocaleString("ko-KR");
  if (metric.format === "percent") return `${(value * 100).toFixed(1)}%`;
  if (metric.format === "decimal2") return value.toFixed(2);
  return value.toFixed(3);
}

export function formatDeltaValue(
  value: ComparisonDeltaRow[DeltaMetricKey],
  metric: MetricDefinition,
): string {
  if (value === null || !Number.isFinite(value)) return "N/A";
  const sign = value > 0 ? "+" : "";
  if (metric.format === "integer") return `${sign}${Math.round(value).toLocaleString("ko-KR")}`;
  if (metric.format === "percent") return `${sign}${(value * 100).toFixed(1)}%p`;
  if (metric.format === "decimal2") return `${sign}${value.toFixed(2)}`;
  return `${sign}${value.toFixed(3)}`;
}

export function deltaOutcome(
  value: ComparisonDeltaRow[DeltaMetricKey],
  metric: MetricDefinition,
): DeltaOutcome {
  if (value === null || !Number.isFinite(value)) return "unavailable";
  if (metric.direction === "neutral") return "neutral";
  if (Math.abs(value) < 1e-12) return "unchanged";
  const improved = metric.direction === "higher" ? value > 0 : value < 0;
  return improved ? "improved" : "worsened";
}
