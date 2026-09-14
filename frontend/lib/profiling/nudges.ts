// 편향 넛지 12종. 순수 함수, 외부 의존성 없음.
// 문구는 기획 확정본이다. 한 글자도 바꾸지 않는다.
// 형식 규칙: 사실 + 사실 병렬. 인과 주장·추종 유도·매수/매도 권유 금지.

import type { RiskGrade, StyleAxisId } from "../types";
import type { BitResult } from "./bit";

export type NudgeId =
  | "N01" | "N02" | "N03" | "N04" | "N05" | "N06"
  | "N07" | "N08" | "N09" | "N10" | "N11" | "N12";

// 넛지가 어떤 성향에서 나왔는지. bit_type은 축이 아니라 BIT 유형 조건.
export type NudgeSource = StyleAxisId | "bit_type";

// 종목·시장 사실. 수급·감성·시세 어댑터 결과에서 계산해 넣는다.
export interface NudgeMarket {
  retailNetBuyStreakDays: number; // 최근일부터 센 개인 연속 순매수 일수
  retailNetLatest: number; // 최근일 개인 순매수(+)/순매도(-)
  foreignNetLatest: number; // 최근일 외국인 순매수(+)/순매도(-)
  institutionNetBuyDaysOf5: number; // 최근 5거래일 중 기관 순매수 일수
  volatilityPercentile: number; // 0~1, 시장 내 변동성 백분위. 1 = 가장 큼
  drawdownFrom3mHigh: number; // 3개월 고점 대비. -0.15 = -15%
  return3d: number; // 최근 3거래일 누적. 0.10 = +10%
  sentimentChange: number; // 뉴스 감성 점수(-1~1)의 전일 대비 변화량
  isTopHolding: boolean; // 보유 종목 중 비중 1위
  riskGrade: RiskGrade; // 1 매우 위험 ~ 5 매우 안전
}

export interface FiredNudge {
  id: NudgeId;
  text: string;
  sources: NudgeSource[];
}

export const MAX_VISIBLE_NUDGES = 2;
// 앞에 있을수록 먼저 노출. 여기 없는 id는 id 순으로 뒤에 붙는다.
const PRIORITY: readonly NudgeId[] = ["N02", "N05", "N11", "N04", "N01"];

const AXIS_THRESHOLD = 0.3;
const STREAK_DAYS = 5;
const INSTITUTION_BUY_DAYS = 4;
const VOLATILITY_TOP_10 = 0.9;
const DRAWDOWN_LIMIT = -0.15;
const RALLY_3D = 0.1;
// ponytail: 감성 "급변" 임계는 임의값. 감성 실데이터 분포를 보고 회의에서 정한다.
const SENTIMENT_SHIFT = 0.5;

type Traits = (bit: BitResult) => NudgeSource[];

const above =
  (axis: StyleAxisId): Traits =>
  (bit) =>
    bit.ratios[axis] > AXIS_THRESHOLD ? [axis] : [];
const below =
  (axis: StyleAxisId): Traits =>
  (bit) =>
    bit.ratios[axis] < -AXIS_THRESHOLD ? [axis] : [];
// information_reliance: -1=본인 판단, +1=시장·타인 추종. 또는 BIT 추종형.
const herding: Traits = (bit) => [
  ...above("information_reliance")(bit),
  ...(bit.type === "FOLLOWER" ? (["bit_type"] as const) : []),
];
const always = () => true;

interface NudgeRule {
  id: NudgeId;
  traits: Traits;
  market: (m: NudgeMarket) => boolean;
  text: string;
}

export const NUDGES: readonly NudgeRule[] = [
  {
    id: "N01",
    traits: herding, // information_reliance > 0.3 || FOLLOWER
    market: (m) => m.retailNetBuyStreakDays >= STREAK_DAYS,
    text: "개인 투자자 순매수가 5일 연속입니다. 당신은 시장 분위기와 타인의 판단을 근거로 삼는 편이라고 답했습니다. 지금 판단이 그 흐름과 같은지 확인해 보세요.",
  },
  {
    id: "N02",
    traits: herding, // information_reliance > 0.3 || FOLLOWER
    market: (m) => m.retailNetLatest > 0 && m.foreignNetLatest < 0,
    text: "개인은 순매수, 외국인은 순매도 중입니다. 두 집단의 판단이 갈리고 있습니다. 어느 쪽 근거를 보고 계신지 짚어 보세요.",
  },
  {
    id: "N03",
    traits: herding, // information_reliance > 0.3 || FOLLOWER
    market: (m) => m.institutionNetBuyDaysOf5 >= INSTITUTION_BUY_DAYS,
    text: "기관 순매수가 최근 5일 중 4일입니다. 다만 기관의 매매 이유는 공개되지 않습니다. 당신이 보고 있는 근거는 무엇인지 짚어 보세요.",
  },
  {
    id: "N04",
    // drawdown_reaction: -1=하락 시 유지, +1=하락 시 이탈
    traits: above("drawdown_reaction"),
    market: (m) => m.volatilityPercentile >= VOLATILITY_TOP_10,
    text: "이 종목의 최근 변동성은 시장 상위 10%입니다. 당신은 하락 구간에서 계획보다 일찍 정리하는 편이라고 답했습니다.",
  },
  {
    id: "N05",
    // drawdown_reaction: -1=하락 시 유지, +1=하락 시 이탈
    traits: above("drawdown_reaction"),
    market: (m) => m.drawdownFrom3mHigh <= DRAWDOWN_LIMIT,
    text: "현재가가 3개월 고점보다 크게 아래에 있습니다. 진입할 때 보았던 근거가 지금도 유효한지 확인해 보세요.",
  },
  {
    id: "N06",
    // urgency: -1=여유, +1=조급함
    traits: above("urgency"),
    market: (m) => m.return3d >= RALLY_3D,
    text: "최근 3거래일 동안 큰 폭으로 올랐습니다. 당신은 결정을 빠르게 내리는 편이라고 답했습니다.",
  },
  {
    id: "N07",
    // urgency: -1=여유, +1=조급함
    traits: above("urgency"),
    market: (m) => Math.abs(m.sentimentChange) >= SENTIMENT_SHIFT,
    text: "오늘 이 종목 관련 뉴스 감성이 어제와 크게 달라졌습니다. 기사 여러 건이 같은 사안을 다루고 있을 수 있습니다.",
  },
  {
    id: "N08",
    // concentration: -1=폭넓은 분산, +1=소수 집중
    traits: above("concentration"),
    market: (m) => m.isTopHolding,
    text: "보유 종목 중 이 종목의 비중이 가장 큽니다. 당신은 소수 종목에 집중하는 편이라고 답했습니다.",
  },
  {
    id: "N09",
    // turnover: -1=장기 보유, +1=단기 매매
    traits: above("turnover"),
    market: always,
    text: "당신은 보유 기간이 짧은 편이라고 답했습니다. 이 종목에 대해 정해 둔 보유 기간이 있다면 지금 다시 확인해 보세요.",
  },
  {
    id: "N10",
    // rule_adherence: -1=사전 규칙 준수, +1=상황별 재량.
    // 이름과 반대로 +가 "규칙을 덜 지킨다"는 뜻이다. "지키기 어려운 편"은 + 쪽이다.
    traits: above("rule_adherence"),
    market: always,
    text: "당신은 사전에 정한 매매 기준을 지키기 어려운 편이라고 답했습니다. 손절선과 목표가를 정해 두셨다면 지금 확인해 보세요.",
  },
  {
    id: "N11",
    // loss_tolerance: -1=원금 보전, +1=수익 기회. risk_grade: 1=매우 위험 ~ 5=매우 안전
    traits: below("loss_tolerance"),
    market: (m) => m.riskGrade <= 2,
    text: "이 종목의 위험 등급은 상위권입니다. 당신은 원금 손실 가능성에 민감한 편이라고 답했습니다.",
  },
  {
    id: "N12",
    // BIT 스펙트럼 수동 쪽 두 유형
    traits: (bit) =>
      bit.type === "PRESERVER" || bit.type === "FOLLOWER" ? ["bit_type"] : [],
    market: always,
    text: "이 화면의 지표 중 처음 보시는 것이 있을 수 있습니다. 각 지표 옆 물음표를 누르면 왜 보는지 설명이 나옵니다.",
  },
];

function rank(id: NudgeId) {
  const index = PRIORITY.indexOf(id);
  return index === -1 ? PRIORITY.length : index;
}

export function selectNudges(bit: BitResult, market: NudgeMarket): FiredNudge[] {
  return NUDGES.flatMap((rule) => {
    const sources = rule.traits(bit);
    return sources.length > 0 && rule.market(market)
      ? [{ id: rule.id, text: rule.text, sources }]
      : [];
  })
    .sort((left, right) => rank(left.id) - rank(right.id) || left.id.localeCompare(right.id))
    .slice(0, MAX_VISIBLE_NUDGES);
}
