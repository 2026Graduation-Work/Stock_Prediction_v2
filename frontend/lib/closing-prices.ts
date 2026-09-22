// 기준일 종가. 평균 매입가를 비워 둔 보유 종목의 비중("현재가 기준")을 셀 때 쓴다.
// 지금은 상세 화면 예시 시세(mock-data)의 마지막 종가다. 실데이터 스냅샷이 생기면 여기만 바꾼다.

import { stockDetails } from "./mock-data.ts";

export const CLOSING_PRICE: Record<string, number> = Object.fromEntries(
  Object.values(stockDetails).flatMap(({ code, currentPrice }) =>
    typeof currentPrice === "number" ? [[code, currentPrice]] : [],
  ),
);
