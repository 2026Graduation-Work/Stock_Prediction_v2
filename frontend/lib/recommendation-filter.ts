// 추천·보유 알림에서 종목을 거르는 규칙. 하드 제약(사용자가 직접 정한 값)만 종목을 제거한다
// (AGENTS.md "명시 규칙만 하드 제약"). 성향에서 자동 파생된 위험등급 상한은 소프트 틸트라
// 여기서 쓰지 않고 주의 문구로만 보여 준다.

export interface HardConstraints {
  // 사용자가 직접 설정한 위험등급 하한(이 등급보다 위험한 종목 제외). 설정한 적이 없으면 null.
  userMaxRiskTier: number | null;
  avoided: ReadonlySet<string>; // 회피 항목(avoided_assets)
}

export function passesHardConstraints(
  riskGrade: number,
  riskFlags: readonly string[],
  constraints: HardConstraints,
): boolean {
  if (constraints.userMaxRiskTier !== null && riskGrade < constraints.userMaxRiskTier) return false;
  return !riskFlags.some((flag) => constraints.avoided.has(flag));
}

// 보유 종목은 추천 카드나 보유 알림 중 한 곳에 보인다. 추천에 이미 있으면 알림에서 뺀다.
export function holdingAlertsOutside<T extends { code: string }>(
  alerts: readonly T[],
  recommended: readonly { code: string }[],
): T[] {
  const recommendedCodes = new Set(recommended.map(({ code }) => code));
  return alerts.filter(({ code }) => !recommendedCodes.has(code));
}
