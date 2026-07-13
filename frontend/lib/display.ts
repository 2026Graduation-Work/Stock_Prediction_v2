// 스키마 enum 값 → 화면 표기(라벨·색) 매핑. 점수 산출이 아닌 순수 표시 계층.
// 표현 제한 원칙: 확률 단정 대신 "과거 유사 신호 구간 상위 N%"류 표현만 사용한다.

import type {
  HorizonAgreement,
  HorizonDirection,
  InvestmentHorizon,
  MarketCondition,
  ReasonSource,
  RiskFlag,
  RiskGrade,
  SignalLight,
} from "./types";

export interface SignalMeta {
  label: string;
  dot: string; // 신호등 점 색
  text: string; // 강조 텍스트 색
  bandFrom: string; // 수익률 밴드 그라데이션 시작
  bandTo: string;
  heatBg: string; // 히트맵 타일 배경
  heatBorder: string;
}

export const SIGNAL_META: Record<SignalLight, SignalMeta> = {
  strong_positive: {
    label: "강한 긍정",
    dot: "#1e7d4f",
    text: "#1e7d4f",
    bandFrom: "#9cc7ab",
    bandTo: "#1e7d4f",
    heatBg: "#e6f1ea",
    heatBorder: "#c9e0d2",
  },
  positive: {
    label: "긍정",
    dot: "#58a15e",
    text: "#2f7a52",
    bandFrom: "#c9dbd0",
    bandTo: "#58a15e",
    heatBg: "#eef6f1",
    heatBorder: "#d4e8dc",
  },
  neutral: {
    label: "중립",
    dot: "#d9a514",
    text: "#9a7409",
    bandFrom: "#e8d9a8",
    bandTo: "#d9a514",
    heatBg: "#fbf5e2",
    heatBorder: "#ede0b7",
  },
  negative: {
    label: "부정",
    dot: "#dd7b2e",
    text: "#b45814",
    bandFrom: "#f2d4b8",
    bandTo: "#dd7b2e",
    heatBg: "#fdf1e6",
    heatBorder: "#f2ddc4",
  },
  strong_negative: {
    label: "강한 부정",
    dot: "#cd4b45",
    text: "#b03a34",
    bandFrom: "#efc4c1",
    bandTo: "#cd4b45",
    heatBg: "#fbe9e8",
    heatBorder: "#f1d2d0",
  },
};

// 신호등 5점 표시 순서 (왼쪽 = 강한 긍정)
export const SIGNAL_ORDER: SignalLight[] = [
  "strong_positive",
  "positive",
  "neutral",
  "negative",
  "strong_negative",
];

export const RISK_GRADE_META: Record<RiskGrade, { label: string; bg: string; text: string }> = {
  5: { label: "매우 안전", bg: "#e3f0e9", text: "#1e7d4f" },
  4: { label: "안전", bg: "#e9f4ee", text: "#2f7a52" },
  3: { label: "보통", bg: "#fbf5e2", text: "#9a7409" },
  2: { label: "위험", bg: "#fbe9e8", text: "#b03a34" },
  1: { label: "매우 위험", bg: "#f8dcda", text: "#8f2721" },
};

// risk_flags == profiling avoided_assets 태그 체계 (schema enum과 1:1)
export const RISK_FLAG_LABEL: Record<RiskFlag, string> = {
  spac: "SPAC",
  managed_stock: "관리종목",
  low_liquidity: "저유동성",
  penny_stock: "저가주",
  high_volatility: "고변동성",
  preferred_stock: "우선주",
};

export const HORIZON_META: Record<HorizonDirection, { arrow: string; bg: string; text: string }> = {
  up: { arrow: "↑", bg: "#e9f4ee", text: "#2f7a52" },
  flat: { arrow: "→", bg: "#eef1f5", text: "#667085" },
  down: { arrow: "↓", bg: "#fdf1e6", text: "#b45814" },
};

export const AGREEMENT_LABEL: Record<HorizonAgreement, string> = {
  aligned: "전 구간 방향 일치",
  mixed: "대체로 일치",
  conflict: "구간별 신호 엇갈림",
};

export const MARKET_CONDITION_META: Record<
  MarketCondition,
  { label: string; color: string; bg: string; comment: string }
> = {
  stable: {
    label: "안정",
    color: "#1e7d4f",
    bg: "#e3f0e9",
    comment: "시장이 평소 범위 안에서 움직이고 있습니다",
  },
  caution: {
    label: "주의",
    color: "#9a7409",
    bg: "#fbf5e2",
    comment: "변동성이 평소보다 높은 구간입니다",
  },
  high_volatility: {
    label: "경계",
    color: "#b45814",
    bg: "#fdf1e6",
    comment: "단기 변동성이 크게 확대된 구간입니다. 신규 진입은 신중히 판단하세요",
  },
};

// 예측 근거 출처 칩: 출처 계열(차트/뉴스/재무)별로 색을 고정해 섞이지 않게 한다
export const REASON_SOURCE_META: Record<ReasonSource, { bg: string; text: string }> = {
  chart: { bg: "#e8eefb", text: "#2f5fd0" },
  news: { bg: "#eee8fb", text: "#6b4fc9" },
  financial: { bg: "#e2f1ec", text: "#14735a" },
};

export const INVESTMENT_HORIZON_LABEL: Record<InvestmentHorizon, string> = {
  short: "단기",
  mid: "중기",
  long: "장기",
};
