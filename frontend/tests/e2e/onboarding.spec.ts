import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const SESSION_KEY = "signallab.demo-session.v1";
const PROFILE_KEY = "signallab.ips-profile.v1";

// 문항 정의(정본)를 읽어, 모든 축을 +2(축의 positive 쪽 끝)로 답하게 만든다.
// 김민지 mock(추종형)과 다른 "적극 축적형"이 나와야 대시보드·상세가 설문 결과를 쓰는지 가려진다.
const BANK = JSON.parse(
  readFileSync(path.resolve(process.cwd(), "lib/profiling/style-questions.json"), "utf8"),
) as {
  likert: { options: { value: number; label: string }[] };
  questions: { id: string; text: string; direction: number; quick: boolean }[];
};
const LIKERT_LABEL = new Map(BANK.likert.options.map(({ value, label }) => [value, label]));
const ANSWER_LABEL = new Map(
  BANK.questions
    .filter(({ quick }) => quick)
    .map(({ text, direction }) => [text, LIKERT_LABEL.get(3 + 2 * direction)!]),
);

async function answerVisibleQuestions(page: Page): Promise<number> {
  const groups = page.locator("fieldset");
  const count = await groups.count();
  for (let index = 0; index < count; index += 1) {
    const group = groups.nth(index);
    const text = (await group.locator("legend").innerText()).trim();
    const label = ANSWER_LABEL.get(text);
    if (!label) throw new Error(`문항 정의에 없는 문항: ${text}`);
    await group.getByLabel(label, { exact: true }).check();
  }
  return count;
}

test("new user: 8축 설문 -> 결과 확인 -> 대시보드 -> 종목 상세까지 같은 8축 -> logout", async ({
  page,
}) => {
  const browserErrors = collectBrowserErrors(page);

  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "시그널랩 로그인" })).toBeVisible();
  // 계정 로그인과 데모 계정이 항상 함께 보인다(환경변수가 없으면 계정 쪽은 안내만)
  await expect(page.getByRole("heading", { name: "이메일로 시작" })).toBeVisible();
  await expect(page.getByText("데모 계정 · 예시 데이터")).toHaveCount(0);

  await page.getByRole("button", { name: "데모 계정으로 둘러보기" }).click();
  await expect(page).toHaveURL(/\/survey$/);
  await expect(page.getByText("데모 계정 · 예시 데이터")).toBeVisible();
  await expect(page.getByText("성향 문항 1/8", { exact: false })).toBeVisible();
  await assertNoHorizontalOverflow(page, 390, 844);
  await page.setViewportSize({ width: 1024, height: 900 });

  // 빠른 진단 24문항: 한 화면 1~2문항, 축 단위 진행 표시
  let answered = 0;
  for (let axis = 1; axis <= 8; axis += 1) {
    await expect(page.getByText(`성향 문항 ${axis}/8`, { exact: false })).toBeVisible();
    answered += await answerVisibleQuestions(page);
    await page.getByRole("button", { name: "다음" }).click();
    answered += await answerVisibleQuestions(page);
    // 축을 다 답하면 응답 방향 한 줄이 보인다
    await expect(page.getByRole("status")).toContainText("쪽이에요");

    if (axis === 2) {
      // 뒤로가기: 답이 남아 있어야 한다
      await page.getByRole("button", { name: "이전" }).click();
      await expect(page.locator("fieldset input:checked")).toHaveCount(2);
      await page.getByRole("button", { name: "다음" }).click();
    }
    if (axis === 4) {
      // 중간 저장: 새로고침해도 같은 화면에서 이어진다
      await page.reload();
      await expect(page.getByText("저장해 둔 응답을 불러왔어요", { exact: false })).toBeVisible();
      await expect(page.getByText("성향 문항 4/8", { exact: false })).toBeVisible();
      await expect(page.locator("fieldset input:checked")).toHaveCount(1);
    }
    await page.getByRole("button", { name: "다음" }).click();
  }
  expect(answered).toBe(24);

  await expect(page.getByText("마무리 1/3", { exact: false })).toBeVisible();
  await page.getByLabel("6개월~2년").check();
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByLabel("SPAC", { exact: false }).check();
  await page.getByRole("button", { name: "다음" }).click();
  await expect(page.getByText("마무리 3/3", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "결과 확인" }).click();

  // 결과 확인: 저장 전 확인 단계
  await expect(page.getByRole("heading", { name: "적극 축적형" })).toBeVisible();
  await expect(page.getByText("이 결과가 나와 맞나요?")).toBeVisible();
  await expectStoredOnboardingData(page, { session: true, profile: false });
  await page.getByRole("button", { name: "네, 이대로 저장" }).click();
  await expect(page.getByText("프로필 저장 완료")).toBeVisible();
  await expectStoredOnboardingData(page, { session: true, profile: true });
  const storedTypes = await page.evaluate((key) => {
    const profile = JSON.parse(localStorage.getItem(key) ?? "{}");
    return profile.style_axes.axes.map((axis: { ratio: number }) => axis.ratio);
  }, PROFILE_KEY);
  expect(storedTypes).toEqual(Array(8).fill(1));

  await page.getByRole("button", { name: "대시보드로 이동" }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByText("오늘의 추천 종목", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("데모 계정 · 예시 데이터")).toBeVisible();
  await expect(page.getByText("적극 축적형", { exact: true })).toBeVisible();
  await expect(page.getByText("추종형", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("적극 축적형", { exact: true })).toBeVisible();
  await assertNoHorizontalOverflow(page, 390, 844);

  await page.setViewportSize({ width: 1024, height: 900 });
  await page.getByRole("link", { name: /자세히 보기/ }).first().click();
  await expect(page).toHaveURL(/\/stocks\/(005930|005380|068270)$/);
  await expect(page.getByText(/과거 유사 신호 .*실현 수익률 분포/).first()).toBeVisible();
  await expect(page.locator('[data-bit-type="ACCUMULATOR"]')).toBeVisible();
  await expect(page.getByText("데모 계정 · 예시 데이터")).toBeVisible();

  // 다른 성향으로 보기: 이 화면만 바뀌고 저장된 결과는 그대로
  await page.getByRole("button", { name: "자산 보존형" }).click();
  await expect(page.locator('[data-bit-type="PRESERVER"]')).toBeVisible();
  await expect(page.getByText("시선으로 보는 중", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "내 성향" }).click();
  await expect(page.locator('[data-bit-type="ACCUMULATOR"]')).toBeVisible();

  await page.getByRole("link", { name: "모델 성적표" }).click();
  await expect(page).toHaveURL(/\/performance$/);
  await expect(page.getByRole("heading", { name: "4런 전체 구간 비교" })).toBeVisible();

  await page.getByRole("button", { name: /로그아웃|나가기/ }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expectStoredOnboardingData(page, { session: false, profile: false });
  expect(browserErrors).toEqual([]);
});

function collectBrowserErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
  return errors;
}

async function assertNoHorizontalOverflow(
  page: Page,
  width: number,
  height: number,
): Promise<void> {
  await page.setViewportSize({ width, height });
  await page.waitForFunction(
    () =>
      document.documentElement.scrollWidth <=
      document.documentElement.clientWidth,
    undefined,
    { timeout: 2_000 },
  );
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
}

async function expectStoredOnboardingData(
  page: Page,
  present: { session: boolean; profile: boolean },
): Promise<void> {
  const stored = await page.evaluate(
    ({ sessionKey, profileKey }) => ({
      session: localStorage.getItem(sessionKey),
      profile: localStorage.getItem(profileKey),
    }),
    { sessionKey: SESSION_KEY, profileKey: PROFILE_KEY },
  );
  expect(Boolean(stored.session)).toBe(present.session);
  expect(Boolean(stored.profile)).toBe(present.profile);
}
