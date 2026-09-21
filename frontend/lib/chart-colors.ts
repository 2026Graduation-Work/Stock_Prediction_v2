// 차트 전용 색 상수.
//
// 왜 토큰(var(--color-*))을 그대로 쓰지 않는가:
// recharts는 색을 SVG "표현 속성"(fill="...", stroke="...")으로 넘긴다.
// 속성 안의 var()는 Chrome·Firefox에서는 풀리지만 Safari 동작이 확실하지 않아
// 차트가 검게 나올 수 있다. 그래서 차트에 들어가는 값만 리터럴로 둔다.
//
// ⚠️ app/globals.css의 @theme 값과 1:1로 같아야 한다. 한쪽만 고치지 말 것.
// DOM 요소(className·style)에는 이 파일이 아니라 토큰을 쓴다.
export const CHART = {
  ink: "#1b2434",
  muted: "#667085",
  faint: "#8b95a5",
  line: "#e6e9ee",
  lineSoft: "#f0f2f5",
  track: "#eef0f4",
  page: "#f6f7f9",
  edge: "#d8dde5",

  brand: "#2f5fd0",
  brandSoft: "#eef2fc",

  // 계열(범주형) — 순서 없는 항목 구분용
  cat1: "#3a62c4",
  cat1Tint: "#eef2fc",
  cat2: "#1a7a63",
  cat2Tint: "#e9f4f1",
  cat3: "#6b58bd",
  cat3Tint: "#efedf9",
  cat4: "#a9762c",
  cat4Tint: "#f8f2e9",
  cat5: "#7d8899",

  // 신호 5단계
  sigSp: "#0f6b46",
  sigNg: "#a85c26",
  sigNgTint: "#faf3ec",
  sigSn: "#a63f39",
} as const;
