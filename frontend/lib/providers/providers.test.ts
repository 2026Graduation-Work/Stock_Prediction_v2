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
  const { supply, sentiment, contributions, financial } = await loadStockInsights("068270");
  assert.deepEqual(
    { supply, sentiment, contributions, financial },
    { supply: null, sentiment: null, contributions: null, financial: null },
  );
});

for (const code of CODES) {
  test(`${code}: 수급 네 주체(개인·외국인·기관합계·기타법인) 순매수 합은 매일 0`, async () => {
    const supply = (await supplyDemandProvider(code)) ?? [];
    assert.ok(supply.length > 0);
    for (const day of supply) {
      assert.equal(day.retail + day.foreign + day.institution + day.otherCorp, 0, day.date);
    }
  });
}

test("출처: 실데이터는 삼성전자 감성뿐이고 나머지는 픽스처", async () => {
  const samsung = await loadStockInsights("005930");
  assert.deepEqual(samsung.provenance.sentiment, {
    kind: "real",
    source: "BigKinds · KR-FinBERT",
    asOf: samsung.sentiment?.days.at(-1)?.date,
  });
  for (const key of ["supply", "contributions", "financial"] as const) {
    assert.equal(samsung.provenance[key].kind, "fixture", key);
  }
  const hyundai = await loadStockInsights("005380");
  assert.equal(hyundai.provenance.sentiment.kind, "fixture");
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

test("김민지 + 삼성전자: information_reliance를 0.3으로 올리면 수급 넛지 N02가 새로 발화하고 다른 축의 N07이 함께 보인다", async () => {
  assert.ok(!(await samsungNudges(investorStyleAxes)).includes("N02"));
  // N03도 시장 조건이 참이지만 N02와 같은 information_reliance 축이라 빠진다
  assert.deepEqual(await samsungNudges(minjiWith({ information_reliance: 0.3 })), ["N02", "N07"]);
});

// urgency +0.44 × 감성 창 마지막 날 |Δ| >= p90(실제 날짜 구간) → N07.
// N04(변동성 백분위 0.48)·N05(3개월 고점 대비 0%)는 시장 조건이 거짓이라 발화하지 않는다.
// sentiment-fixture.ts가 다시 생성되면 재확인한다.
const EXPECTED_MINJI_SAMSUNG: string[] = ["N07"];
