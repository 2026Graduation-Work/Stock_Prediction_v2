import assert from "node:assert/strict";
import { test } from "node:test";
import { investorStyleAxes, portfolioHoldings, stockDetails } from "../mock-data.ts";
import { classifyBit } from "../profiling/bit.ts";
import { selectNudges } from "../profiling/nudges.ts";
import type { StyleAxes } from "../types.ts";
import {
  contributionProvider,
  financialProvider,
  loadStockInsights,
  sentimentProvider,
  supplyDemandProvider,
  toNudgeMarket,
} from "./index.ts";

const CODES = ["005930", "005380"];

for (const code of CODES) {
  test(`${code}: 4개 Provider가 값을 반환한다`, async () => {
    const supply = await supplyDemandProvider(code);
    assert.equal(supply?.length, 20);
    assert.equal(supply?.at(-1)?.date, "2025-10-02");
    assert.deepEqual(
      supply?.map(({ date }) => date),
      [...(supply ?? [])].map(({ date }) => date).sort(),
    );

    const sentiment = await sentimentProvider(code);
    assert.equal(sentiment?.days.length, 20);
    assert.equal(sentiment?.headlines.length, 3);
    assert.equal(sentiment?.source, code === "005930" ? "real" : "synthetic");
    assert.ok(sentiment?.days.every(({ score }) => score >= -1 && score <= 1));

    const contributions = await contributionProvider(code);
    const total = contributions?.reduce((sum, { share }) => sum + share, 0) ?? 0;
    assert.ok(Math.abs(total - 100) < 1e-9);
    assert.deepEqual(
      new Set(contributions?.map(({ category }) => category)),
      new Set(["technical", "financial", "sentiment", "supply"]),
    );
    assert.ok(contributions?.every(({ description }) => description.length > 0));

    const financial = await financialProvider(code);
    assert.ok((financial?.metrics.length ?? 0) > 0);
  });
}

test("대상 외 종목은 null", async () => {
  const insights = await loadStockInsights("068270");
  assert.deepEqual(insights, {
    supply: null,
    sentiment: null,
    contributions: null,
    financial: null,
  });
});

function minjiWith(overrides: Record<string, number>): StyleAxes {
  return {
    ...investorStyleAxes,
    axes: investorStyleAxes.axes.map((axis) =>
      axis.axis_id in overrides ? { ...axis, ratio: overrides[axis.axis_id] } : axis,
    ),
  };
}

async function samsungNudges(styleAxes: StyleAxes) {
  const detail = stockDetails["005930"];
  const market = toNudgeMarket(detail, await loadStockInsights("005930"), portfolioHoldings);
  assert.ok(market);
  return selectNudges(classifyBit(styleAxes), market).map(({ id }) => id);
}

test("김민지 + 삼성전자: 넛지가 1개 이상 발화한다", async () => {
  const fired = await samsungNudges(investorStyleAxes);
  assert.ok(fired.length >= 1);
  assert.deepEqual(fired, EXPECTED_MINJI_SAMSUNG);
});

test("김민지 + 삼성전자: information_reliance를 0.3으로 올리면 수급 넛지 N02가 새로 발화한다", async () => {
  assert.ok(!(await samsungNudges(investorStyleAxes)).includes("N02"));
  assert.ok((await samsungNudges(minjiWith({ information_reliance: 0.3 }))).includes("N02"));
});

// 시장 조건: 변동성 상위 8%(FIXTURE 0.92) × drawdown_reaction +0.30 → N04.
// N07은 감성 시계열 마지막 두 날 변화량이 p90 미만이라 발화하지 않는다(sentiment-fixture.ts가 바뀌면 재확인).
const EXPECTED_MINJI_SAMSUNG: string[] = ["N04"];
