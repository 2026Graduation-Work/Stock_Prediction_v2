// 차트 전용 색 상수.
//
// 왜 토큰(var(--color-*))을 그대로 쓰지 않는가:
// recharts는 색을 SVG "표현 속성"(fill="...", stroke="...")으로 넘긴다.
// 속성 안의 var()는 Chrome·Firefox에서는 풀리지만 Safari 동작이 확실하지 않아
// 차트가 검게 나올 수 있다. 그래서 차트에 들어가는 값만 리터럴로 둔다.
//
// ⚠️ app/globals.css의 @theme 값과 1:1로 같아야 한다. 한쪽만 고치지 말 것.
// DOM 요소(className·style)에는 이 파일이 아니라 토큰을 쓴다.
//
// 범주색은 없다. 범주(투자자·지표·실험 런)는 색이 아니라 라벨과 위치로 구분한다.
export const CHART = {
  ink: "#1d1d1f",
  muted: "#6e6e73",
  ghost: "#86868b",
  line: "#d2d2d7",
  lineSoft: "#e8e8ed",
  track: "#e8e8ed",
  page: "#f5f5f7",
  edge: "#d2d2d7",

  // 차트의 "나" 표시(성향 레이더 등) — 성균 연두. 글자에는 쓰지 않는다.
  accent: "#8dc63f",

  // 주가 실선 — 신호가 아니라 "사실"이라 무채색으로 둔다.
  priceLine: "#424245",

  // 가격 방향 (국내 관례: 상승·긍정 적 / 하락·부정 청)
  up: "#b0342a",
  down: "#274b96",
  sigSp: "#b0342a",
  sigP: "#ad4436",
  sigN: "#6e6e73",
  sigNg: "#4666b5",
  sigNgTint: "#eff2fa",
  sigSn: "#274b96",
} as const;
