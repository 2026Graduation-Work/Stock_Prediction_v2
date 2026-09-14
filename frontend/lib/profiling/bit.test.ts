// node --test "lib/**/*.test.ts" (Node 24 타입 스트리핑, 추가 의존성 없음)
import assert from "node:assert/strict";
import { test } from "node:test";
import type { StyleAxes, StyleAxisId } from "../types.ts";
import { investorStyleAxes } from "../mock-data.ts";
import { BIAS_PROFILE_AXES, CARD_ORDER, classifyBit, type BitType } from "./bit.ts";
import { NUDGES, selectNudges, type NudgeMarket } from "./nudges.ts";

const AXIS_IDS: StyleAxisId[] = [
  "market_participation",
  "loss_tolerance",
  "turnover",
  "concentration",
  "rule_adherence",
  "information_reliance",
  "urgency",
  "drawdown_reaction",
];

function axes(ratios: Partial<Record<StyleAxisId, number>>, confidence = 0.9): StyleAxes {
  return {
    assessment_mode: "quick",
    axes: AXIS_IDS.map((axis_id) => ({
      axis_id,
      ratio: ratios[axis_id] ?? 0,
      confidence,
      answered_count: 3,
      question_count: 3,
    })),
  };
}

// 분류 3축을 같은 값으로 두면 composite도 그 값이다.
const spectrum = (value: number) =>
  axes({ turnover: value, loss_tolerance: value, concentration: value });

const CALM: NudgeMarket = {
  retailNetBuyStreakDays: 0,
  retailNetLatest: 0,
  foreignNetLatest: 0,
  institutionNetBuyDaysOf5: 0,
  volatilityPercentile: 0.5,
  drawdownFrom3mHigh: -0.02,
  return3d: 0,
  sentimentChange: 0,
  isTopHolding: false,
  riskGrade: 3,
};

const ids = (bit: StyleAxes, market: Partial<NudgeMarket> = {}) =>
  selectNudges(classifyBit(bit), { ...CALM, ...market }).map(({ id }) => id);

const TYPE_CASES: [number, BitType, "emotional" | "cognitive"][] = [
  [-0.8, "PRESERVER", "emotional"],
  [-0.3, "FOLLOWER", "cognitive"],
  [0.2, "INDEPENDENT", "cognitive"],
  [0.8, "ACCUMULATOR", "emotional"],
];

for (const [composite, type, biasMode] of TYPE_CASES) {
  test(`${type}: composite ${composite} → ${biasMode}, 유형별 카드 순서`, () => {
    const result = classifyBit(spectrum(composite));
    assert.equal(result.type, type);
    assert.equal(result.biasMode, biasMode);
    assert.deepEqual(result.cardOrder, CARD_ORDER[type]);
    assert.equal(result.cardOrder[0], "nudge");
    assert.equal(new Set(result.cardOrder).size, 6);
  });
}

test("구간 경계값은 위 구간에 속한다", () => {
  assert.equal(classifyBit(spectrum(-0.51)).type, "PRESERVER");
  assert.equal(classifyBit(spectrum(-0.5)).type, "FOLLOWER");
  assert.equal(classifyBit(spectrum(0)).type, "INDEPENDENT");
  assert.equal(classifyBit(spectrum(0.5)).type, "ACCUMULATOR");
});

test("김민지: FOLLOWER, 신뢰도는 분류 3축 confidence 평균", () => {
  const result = classifyBit(investorStyleAxes);
  assert.equal(result.type, "FOLLOWER");
  assert.ok(Math.abs(result.composite - -0.3) < 1e-9);
  assert.ok(Math.abs(result.confidence - (0.95 + 0.92 + 0.81) / 3) < 1e-9);
  assert.equal(result.lowConfidence, false);
});

test("market_participation은 분류에 쓰지 않고 편향 프로필로 간다", () => {
  const low = classifyBit(axes({ market_participation: -1 }));
  const high = classifyBit(axes({ market_participation: 1 }));
  assert.equal(low.type, high.type);
  assert.equal(low.composite, high.composite);
  assert.deepEqual(
    high.biasProfile.map(({ axisId }) => axisId),
    BIAS_PROFILE_AXES,
  );
});

test("confidence 0.5 미만이면 유형과 함께 lowConfidence", () => {
  const result = classifyBit(axes({}, 0.4));
  assert.equal(result.type, "INDEPENDENT");
  assert.equal(result.lowConfidence, true);
});

test("넛지 12종, id 중복 없음, 권유 표현 없음", () => {
  assert.equal(new Set(NUDGES.map(({ id }) => id)).size, 12);
  for (const { id, text } of NUDGES) {
    assert.doesNotMatch(text, /사세요|파세요|매수하|매도하|권장|추천/, id);
  }
});

test("N04·N05는 drawdown_reaction +0.3 초과(하락 시 이탈)에서만", () => {
  const hot = { volatilityPercentile: 0.95, drawdownFrom3mHigh: -0.2 };
  assert.deepEqual(ids(axes({ drawdown_reaction: 0.5 }), hot), ["N05", "N04"]);
  assert.deepEqual(ids(axes({ drawdown_reaction: -0.5 }), hot), []);
});

test("N10은 rule_adherence +0.3 초과(상황별 재량)에서만", () => {
  assert.deepEqual(ids(axes({ rule_adherence: 0.5 })), ["N10"]);
  assert.deepEqual(ids(axes({ rule_adherence: -0.5 })), []);
});

test("N11은 위험 등급 2 이하(위험 쪽)에서만", () => {
  const averse = axes({ loss_tolerance: -0.5 });
  assert.ok(ids(averse, { riskGrade: 2 }).includes("N11"));
  assert.ok(!ids(averse, { riskGrade: 4 }).includes("N11"));
});

test("N01~N03은 FOLLOWER면 information_reliance가 낮아도 발화하고 출처에 bit_type", () => {
  const fired = selectNudges(classifyBit(investorStyleAxes), {
    ...CALM,
    retailNetBuyStreakDays: 5,
  });
  const n01 = fired.find(({ id }) => id === "N01");
  assert.deepEqual(n01?.sources, ["bit_type"]);
});

test("N12는 PRESERVER·FOLLOWER에서만", () => {
  // spectrum(0.8)은 turnover 0.8이라 N09가 함께 발화하므로 N12 포함 여부만 본다.
  assert.ok(ids(spectrum(-0.8)).includes("N12"));
  assert.ok(ids(spectrum(-0.3)).includes("N12"));
  assert.ok(!ids(spectrum(0.2)).includes("N12"));
  assert.ok(!ids(spectrum(0.8)).includes("N12"));
});

test("최대 2개, 우선순위 N02 > N05 > N11 > N04 > N01 > id 순", () => {
  const everything = axes({
    information_reliance: 0.5,
    drawdown_reaction: 0.5,
    loss_tolerance: -0.5,
    urgency: 0.5,
    rule_adherence: 0.5,
  });
  const market: Partial<NudgeMarket> = {
    retailNetBuyStreakDays: 5,
    retailNetLatest: 1,
    foreignNetLatest: -1,
    institutionNetBuyDaysOf5: 4,
    volatilityPercentile: 0.95,
    drawdownFrom3mHigh: -0.2,
    return3d: 0.12,
    sentimentChange: 0.8,
    riskGrade: 2,
  };
  assert.deepEqual(ids(everything, market), ["N02", "N05"]);
  assert.deepEqual(ids(everything, { ...market, foreignNetLatest: 1 }), ["N05", "N11"]);
  assert.deepEqual(
    ids(everything, { ...market, foreignNetLatest: 1, drawdownFrom3mHigh: -0.05 }),
    ["N11", "N04"],
  );
  assert.deepEqual(
    ids(everything, { ...market, foreignNetLatest: 1, drawdownFrom3mHigh: -0.05, riskGrade: 3 }),
    ["N04", "N01"],
  );
  assert.deepEqual(
    ids(everything, {
      ...market,
      foreignNetLatest: 1,
      drawdownFrom3mHigh: -0.05,
      riskGrade: 3,
      volatilityPercentile: 0.5,
    }),
    ["N01", "N03"],
  );
});
