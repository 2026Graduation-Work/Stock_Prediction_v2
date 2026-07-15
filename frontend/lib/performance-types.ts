export type ComparisonProfile = "stable" | "aggressive";
export type ComparisonVariant = "A" | "B";
export type ComparisonFeatureSet = "baseline" | "treatment";
export type ComparisonSample = "all" | "volatile_top_20pct";

export interface ComparisonMetricRow {
  profile: ComparisonProfile;
  variant: ComparisonVariant;
  feature_set: ComparisonFeatureSet;
  sample: ComparisonSample;
  feature_count: number;
  sample_rows: number;
  sample_dates: number;
  positive_rate: number;
  auc: number | null;
  hit_rate: number;
  calibration_brier: number;
  calibration_ece: number;
  sharpe: number;
  mdd: number;
  cumulative_return: number;
  trade_count: number;
}

export interface ComparisonDeltaRow {
  profile: ComparisonProfile;
  sample: ComparisonSample;
  delta_B_minus_A_auc: number | null;
  delta_B_minus_A_hit_rate: number;
  delta_B_minus_A_calibration_brier: number;
  delta_B_minus_A_calibration_ece: number;
  delta_B_minus_A_sharpe: number;
  delta_B_minus_A_mdd: number;
  delta_B_minus_A_cumulative_return: number;
  delta_B_minus_A_trade_count: number;
}

export interface ComparisonResults {
  four_run_metrics: ComparisonMetricRow[];
  volatile_subsample_metrics: ComparisonMetricRow[];
  comparison_deltas: ComparisonDeltaRow[];
}
