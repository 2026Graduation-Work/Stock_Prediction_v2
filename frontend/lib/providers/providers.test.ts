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
    assert.equal(supply?.at(-1)?.date, "2025-12-30"); // 데모 기준일
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
  const { supply, sentiment, contributions, financial } = await loadStockInsights("000660");
  assert.deepEqual(
    { supply, sentiment, contributions, financial },
    { supply: null, sentiment: null, contributions: null, financial: null },
  );
});

test("수급: 데모 4종목은 실데이터 20영업일(기준일까지, 12-25 휴장 제외) 정수 수량", async () => {
  for (const code of ["005930", "005380", "035720", "068270"]) {
    const supply = (await supplyDemandProvider(code)) ?? [];
    assert.equal(supply.length, 20, code);
    assert.equal(supply[0].date, "2025-12-02", code);
    assert.equal(supply.at(-1)?.date, "2025-12-30", code);
    assert.ok(!supply.some(({ date }) => date === "2025-12-25"), code);
    for (const day of supply) {
      for (const value of [day.retail, day.foreign, day.institution]) assert.ok(Number.isInteger(value), `${code} ${day.date}`);
    }
    const { provenance } = await loadStockInsights(code);
    assert.deepEqual(provenance.supply, { kind: "real", source: "네이버 금융 투자자별 매매동향", asOf: "2025-12-30" });
  }
});

test("출처: 감성은 삼성전자만 실데이터, 모델 근거·재무는 픽스처", async () => {
  const samsung = await loadStockInsights("005930");
  assert.deepEqual(samsung.provenance.sentiment, {
    kind: "real",
    source: "BigKinds · KR-FinBERT",
    asOf: samsung.sentiment?.days.at(-1)?.date,
  });
  for (const key of ["contributions", "financial"] as const) {
    assert.equal(samsung.provenance[key].kind, "fixture", key);
  }
  const hyundai = await loadStockInsights("005380");
  assert.equal(hyundai.provenance.sentiment.kind, "fixture");
});

test("가격 흐름 분위기: 데모 4종목은 실데이터 스냅샷에서 구간 말을 갖는다", async () => {
  for (const code of ["005930", "005380", "035720", "068270"]) {
    const { psychology } = await loadStockInsights(code);
    assert.ok(psychology, code);
    assert.equal(psychology.provenance.kind, "real");
    assert.equal(psychology.provenance.asOf, "2025-12-30");
    assert.ok(psychology.axis >= -1 && psychology.axis <= 1);
    assert.ok(["많이 들뜸", "조금 들뜸", "차분함", "조금 움츠러듦", "많이 움츠러듦"].includes(psychology.word));
  }
  assert.equal((await loadStockInsights("000660")).psychology, null);
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
  // N03(최근 5일 중 기관 순매수 4일 이상)은 실데이터에서 3일이라 시장 조건이 거짓이다
  assert.deepEqual(await samsungNudges(minjiWith({ information_reliance: 0.3 })), ["N02", "N07"]);
});

// urgency +0.44 × 감성 창 마지막 날 |Δ| >= p90(실제 날짜 구간) → N07.
// N04(변동성 백분위 0.48)·N05(3개월 고점 대비, 실데이터 시세)는 시장 조건이 거짓이라 발화하지 않는다.
// sentiment-fixture.ts가 다시 생성되면 재확인한다.
const EXPECTED_MINJI_SAMSUNG: string[] = ["N07"];
