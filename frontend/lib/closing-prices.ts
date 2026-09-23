// 기준일(2025-12-30) 종가. 평균 매입가를 비워 둔 보유 종목의 비중("현재가 기준")을 셀 때 쓴다.
// 원천: 실데이터 스냅샷(네이버 금융 수정주가). 스냅샷에 없는 종목은 비중 0으로 센다.

import { STOCK_SNAPSHOT } from "./providers/demo-snapshot.ts";

export const CLOSING_PRICE: Record<string, number> = Object.fromEntries(
  Object.entries(STOCK_SNAPSHOT).map(([code, { close }]) => [code, close]),
);
