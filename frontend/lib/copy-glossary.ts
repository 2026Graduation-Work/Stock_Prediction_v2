// 쉬운 말 사전. 화면 문구는 여기서 가져다 쓰고, 개발 용어를 화면에 직접 쓰지 않는다.
// 금지어 검사는 copy-rules.ts. 개발 용어는 "계산 근거" 영역에서만 쓴다.

import type { HorizonAgreement, HorizonDirection, RiskGrade } from "./types";

export type HorizonKey = "h5" | "h10" | "h20";

// 모델의 예측 기간. 5·10·20거래일 ≈ 1·2·4주
export const HORIZON_LABEL: Record<HorizonKey, string> = {
  h5: "1주 뒤",
  h10: "2주 뒤",
  h20: "4주 뒤",
};

// 화면에서 쓰는 이름. 왼쪽은 코드·문서 용어
export const TERM = {
  contribution: "모델이 본 이유",
  supply: "누가 사고팔았나",
  sentiment: "뉴스 분위기",
  volatility: "가격 흔들림",
  nudge: "체크포인트",
  market: "시장 분위기",
  financial: "회사 체력",
  horizonAgreement: "기간마다 같은 방향인가요?",
} as const;

// 예상 수익률 밴드(신뢰구간) → 과거 비슷한 경우의 빈도 문장
export function bandSentence(horizon: HorizonKey, ciLevel: number): string {
  const times = Math.round(ciLevel * 10);
  return `과거 비슷한 경우, ${HORIZON_LABEL[horizon]} 수익률은 10번 중 ${times}번 이 범위였어요`;
}

// 신호 강도 순위(0~1, 1이 최상위) → "오늘 분석한 종목 중 상위 N%"
export function topPercentLabel(rankPercentile: number): string {
  return `오늘 분석한 종목 중 상위 ${Math.max(1, Math.round((1 - rankPercentile) * 100))}%`;
}

export const DIRECTION_WORD: Record<HorizonDirection, string> = {
  up: "오르는 쪽",
  flat: "뚜렷하지 않음",
  down: "내리는 쪽",
};

export const AGREEMENT_ANSWER: Record<HorizonAgreement, string> = {
  aligned: "네, 세 기간 모두 같은 방향이에요",
  mixed: "대체로 같지만 한 기간은 달라요",
  conflict: "아니요, 기간마다 엇갈려요",
};

// 재무 지표는 이름을 그대로 두고 괄호로 풀어 쓴다
export const FINANCIAL_TERM: Record<string, string> = {
  per: "PER(주가가 1년 이익의 몇 배인지)",
  pbr: "PBR(주가가 회사 순자산의 몇 배인지)",
  roe: "ROE(자기 돈으로 1년에 얼마를 벌었는지)",
  operating_margin: "영업이익률(매출 100원에서 남긴 영업이익)",
  debt_ratio: "부채비율(빚이 자기 돈의 몇 %인지)",
  revenue_growth: "매출 증가율(1년 전보다 매출이 늘어난 정도)",
};

export type RiskLevel = "낮음" | "보통" | "높음";

// 위험등급(5 = 매우 안전)은 숫자가 뒤집혀 헷갈린다. 화면에는 단어 + 5칸(찬 칸이 많을수록 위험)으로 쓴다.
export function riskLevel(grade: RiskGrade): { word: RiskLevel; filled: number } {
  return {
    word: grade >= 4 ? "낮음" : grade === 3 ? "보통" : "높음",
    filled: 6 - grade,
  };
}
