import assert from "node:assert/strict";
import { test } from "node:test";
import { holdingAlerts, portfolioHoldings, recommendedStocks } from "./mock-data.ts";
import { holdingAlertsOutside, passesHardConstraints } from "./recommendation-filter.ts";

// supabase/seed.sql 김민지 보유 4종목의 위험등급·플래그와 회피 설정(SPAC·관리종목)
const MINJI_HOLDINGS = [
  { code: "005930", name: "삼성전자", riskGrade: 4, riskFlags: [] },
  { code: "035720", name: "카카오", riskGrade: 3, riskFlags: [] },
  { code: "068270", name: "셀트리온", riskGrade: 2, riskFlags: ["high_volatility"] },
  { code: "005380", name: "현대차", riskGrade: 5, riskFlags: [] },
];
const MINJI_AVOIDED = new Set(["spac", "managed_stock"]);

test("김민지 기본 상태: 성향에서 파생된 위험등급 상한으로는 보유 4종목이 하나도 빠지지 않는다", () => {
  const constraints = { userMaxRiskTier: null, avoided: MINJI_AVOIDED };
  const kept = MINJI_HOLDINGS.filter(({ riskGrade, riskFlags }) =>
    passesHardConstraints(riskGrade, riskFlags, constraints),
  );
  assert.deepEqual(
    kept.map(({ name }) => name),
    ["삼성전자", "카카오", "셀트리온", "현대차"],
  );
});

test("김민지 기본 상태(mock): 보유 4종목이 추천 카드 또는 보유 알림 카드에 모두 보인다", () => {
  const shown = [...recommendedStocks, ...holdingAlertsOutside(holdingAlerts, recommendedStocks)];
  const shownCodes = shown.map(({ code }) => code);
  assert.equal(new Set(shownCodes).size, shownCodes.length, "같은 종목이 두 번 보이면 안 된다");
  for (const { code, name } of portfolioHoldings) {
    assert.ok(shownCodes.includes(code), `${name}(${code})이 대시보드에 없다`);
  }
});

test("하드 제약은 그대로 적용된다: 회피 항목과 사용자가 직접 정한 위험등급", () => {
  const spac = { riskGrade: 1, riskFlags: ["spac"] };
  assert.equal(
    passesHardConstraints(spac.riskGrade, spac.riskFlags, { userMaxRiskTier: null, avoided: MINJI_AVOIDED }),
    false,
  );
  const explicit = { userMaxRiskTier: 4, avoided: new Set<string>() };
  assert.deepEqual(
    MINJI_HOLDINGS.filter(({ riskGrade, riskFlags }) =>
      passesHardConstraints(riskGrade, riskFlags, explicit),
    ).map(({ name }) => name),
    ["삼성전자", "현대차"],
  );
});

test("추천에 이미 있는 보유 종목은 보유 알림에서 뺀다", () => {
  const alerts = [{ code: "005930" }, { code: "035720" }];
  assert.deepEqual(holdingAlertsOutside(alerts, [{ code: "005930" }]), [{ code: "035720" }]);
});
