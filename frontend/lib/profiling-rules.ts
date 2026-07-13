// SSOT는 backend/profiling/입니다. 규칙 변경 시 Python 상수 테이블과 동기화합니다.

import type {
  ActionIntent,
  ProfileType,
  ProfilingOutput,
  RiskFlag,
} from "./types";

export const PROFILE_TYPE_THRESHOLD = 60;

export const RISK_ANSWER_MAP = {
  Q1_A: { riskScore: 15, panicSellTendency: 0.85 },
  Q1_B: { riskScore: 35, panicSellTendency: 0.65 },
  Q1_C: { riskScore: 75, panicSellTendency: 0.2 },
} as const;

export const HORIZON_ANSWER_MAP = {
  Q2_A: {
    horizonScore: 80,
    timeHorizonMonths: 12,
    liquidityNeedRatio: 0.7,
    modelHorizon: "H5",
  },
  Q2_B: {
    horizonScore: 50,
    timeHorizonMonths: 48,
    liquidityNeedRatio: 0.25,
    modelHorizon: "H10",
  },
  Q2_C: {
    horizonScore: 20,
    timeHorizonMonths: 120,
    liquidityNeedRatio: 0.1,
    modelHorizon: "H20",
  },
} as const;

export const FOMO_ANSWER_MAP = {
  Q3_A: { fomoScore: 72, herdingScore: 0.38 },
  Q3_B: { fomoScore: 40, herdingScore: 0.3 },
  Q3_C: { fomoScore: 15, herdingScore: 0.2 },
} as const;

export const INFORMATION_SOURCE_BASE = { selfConfidence: 0.3 } as const;
export const INFORMATION_SOURCE_MAP = {
  Q4_A: { herdingDelta: 0.2, selfConfidenceDelta: 0 },
  Q4_B: { herdingDelta: 0.15, selfConfidenceDelta: 0 },
  Q4_C: { herdingDelta: 0, selfConfidenceDelta: 0.2 },
  Q4_D: { herdingDelta: 0, selfConfidenceDelta: 0.4 },
} as const;

export const EXPERIENCE_ANSWER_MAP = {
  Q5_A: 0.3,
  Q5_B: 1,
  Q5_C: 3.5,
  Q5_D: 7,
} as const;

export const AVOIDED_ASSET_LABELS: Record<RiskFlag, string> = {
  spac: "SPAC",
  managed_stock: "관리종목",
  low_liquidity: "저유동성 종목",
  penny_stock: "동전주",
  high_volatility: "고변동성 종목",
  preferred_stock: "우선주",
};

export const HORIZON_MODEL_RULES = [
  { minimum: 67, modelHorizon: "H5", style: "aggressive" },
  { minimum: 34, modelHorizon: "H10", style: "neutral" },
  { minimum: 0, modelHorizon: "H20", style: "conservative" },
] as const;

const CONFIDENCE_PER_FIELD = {
  risk_tolerance: 0.92,
  time_horizon_months: 0.95,
  liquidity_need_ratio: 0.88,
  fomo_index: 0.78,
  panic_sell_tendency: 0.7,
  herding_score: 0.85,
  self_confidence: 0.6,
  overheating_caution: 0.55,
};

const FREE_TEXT_SIGNAL_RULES = [
  {
    field: "fomo_index",
    keywords: ["남들 다 버는데", "뒤처지는", "놓칠까"],
    value: 0.8,
  },
  {
    field: "panic_sell_tendency",
    keywords: ["마이너스", "손실", "잠을 못"],
    value: 0.75,
  },
] as const;

export interface SurveyAnswers {
  user_id: string;
  session_id: string;
  timestamp: string;
  Q1: keyof typeof RISK_ANSWER_MAP;
  Q2: keyof typeof HORIZON_ANSWER_MAP;
  Q3: keyof typeof FOMO_ANSWER_MAP;
  Q4: (keyof typeof INFORMATION_SOURCE_MAP)[];
  Q5: keyof typeof EXPERIENCE_ANSWER_MAP;
  Q6: RiskFlag[];
  Q7?: string;
  preferred_sectors?: string[];
  portfolio?: ProfilingOutput["portfolio"];
  investment_amount_krw?: number;
  action_intent?: ActionIntent;
  target_ticker?: string;
  market_regime_hint?: string;
  benchmark_index?: string;
}

export function profileTypeForRiskScore(riskScore: number): ProfileType {
  assertScore(riskScore, "riskScore");
  return riskScore >= PROFILE_TYPE_THRESHOLD ? "aggressive" : "stable";
}

export function horizonCodeForScore(horizonScore: number) {
  assertScore(horizonScore, "horizonScore");
  const rule = HORIZON_MODEL_RULES.find(({ minimum }) => horizonScore >= minimum);
  if (!rule) throw new Error("horizon rules must cover 0-100");
  return rule.modelHorizon;
}

export function horizonScoreForMonths(months: number) {
  const match = Object.values(HORIZON_ANSWER_MAP).find(
    ({ timeHorizonMonths }) => timeHorizonMonths === months,
  );
  if (!match) throw new Error(`지원하지 않는 투자 기간입니다: ${months}`);
  return match.horizonScore;
}

export function convertSurveyAnswers(answers: SurveyAnswers): ProfilingOutput {
  const risk = requireChoice(RISK_ANSWER_MAP, answers.Q1, "Q1");
  const horizon = requireChoice(HORIZON_ANSWER_MAP, answers.Q2, "Q2");
  const fomo = requireChoice(FOMO_ANSWER_MAP, answers.Q3, "Q3");
  const experience = requireChoice(EXPERIENCE_ANSWER_MAP, answers.Q5, "Q5");
  if (!answers.Q4.length) throw new Error("Q4는 한 개 이상 선택해야 합니다.");
  assertChoices(INFORMATION_SOURCE_MAP, answers.Q4, "Q4");
  assertChoices(AVOIDED_ASSET_LABELS, answers.Q6, "Q6");
  if (horizonCodeForScore(horizon.horizonScore) !== horizon.modelHorizon) {
    throw new Error("Q2 시간지평 규칙이 일치하지 않습니다.");
  }

  const informationScores = answers.Q4.reduce<{
    herding: number;
    confidence: number;
  }>(
    (scores, choice) => ({
      herding:
        scores.herding + INFORMATION_SOURCE_MAP[choice].herdingDelta,
      confidence:
        scores.confidence +
        INFORMATION_SOURCE_MAP[choice].selfConfidenceDelta,
    }),
    {
      herding: fomo.herdingScore,
      confidence: INFORMATION_SOURCE_BASE.selfConfidence,
    },
  );
  const rawText = answers.Q7?.trim() ?? "";
  const extractedSignals: Record<string, number> = {};
  for (const rule of FREE_TEXT_SIGNAL_RULES) {
    if (rule.keywords.some((keyword) => rawText.includes(keyword))) {
      extractedSignals[rule.field] = rule.value;
    }
  }

  return {
    user_id: requireText(answers.user_id, "user_id"),
    session_id: requireText(answers.session_id, "session_id"),
    timestamp: requireText(answers.timestamp, "timestamp"),
    investor_profile: {
      risk_tolerance: risk.riskScore / 100,
      time_horizon_months: horizon.timeHorizonMonths,
      liquidity_need_ratio: horizon.liquidityNeedRatio,
      target_return_annual: 0.08,
      investment_experience_years: experience,
      profile_type: profileTypeForRiskScore(risk.riskScore),
    },
    psychological_state: {
      fomo_index: fomo.fomoScore / 100,
      panic_sell_tendency: risk.panicSellTendency,
      herding_score: clamp(informationScores.herding),
      self_confidence: clamp(informationScores.confidence),
      current_market_anxiety: 0.5,
      overheating_caution: 0.61,
    },
    constraints: {
      avoided_assets: [...new Set(answers.Q6)],
      preferred_sectors: [...(answers.preferred_sectors ?? [])],
    },
    portfolio: answers.portfolio ?? { holdings: [], watchlist: [] },
    free_text_signal: {
      raw_text: rawText,
      extracted_signals: extractedSignals,
      conflict_with_survey: false,
    },
    confidence_per_field: { ...CONFIDENCE_PER_FIELD },
    context: {
      investment_amount_krw: answers.investment_amount_krw ?? 0,
      action_intent: answers.action_intent ?? "buy_consideration",
      ...(answers.target_ticker ? { target_ticker: answers.target_ticker } : {}),
      ...(answers.market_regime_hint
        ? { market_regime_hint: answers.market_regime_hint }
        : {}),
      ...(answers.benchmark_index
        ? { benchmark_index: answers.benchmark_index }
        : {}),
    },
    meta: {
      schema_version: "1.0.0",
      source: "profiling_block",
      confidence: 0.81,
    },
  };
}

function requireChoice<T extends object, K extends keyof T>(
  mapping: T,
  choice: K,
  question: string,
): T[K] {
  if (!(choice in mapping)) throw new Error(`${question} 응답이 올바르지 않습니다.`);
  return mapping[choice];
}

function assertChoices<T extends object>(
  mapping: T,
  choices: PropertyKey[],
  question: string,
) {
  if (choices.some((choice) => !(choice in mapping))) {
    throw new Error(`${question} 응답에 지원하지 않는 항목이 있습니다.`);
  }
}

function requireText(value: string, field: string) {
  const normalized = value.trim();
  if (!normalized) throw new Error(`${field} 값이 필요합니다.`);
  return normalized;
}

function assertScore(value: number, field: string) {
  if (value < 0 || value > 100) throw new Error(`${field}는 0~100이어야 합니다.`);
}

function clamp(value: number) {
  const clamped = Math.min(1, Math.max(0, value));
  return Math.round(clamped * 1_000_000) / 1_000_000;
}
