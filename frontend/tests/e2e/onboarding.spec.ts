import { expect, test, type Page } from "@playwright/test";

const SESSION_KEY = "signallab.demo-session.v1";
const PROFILE_KEY = "signallab.ips-profile.v1";

test("login -> survey -> dashboard -> detail -> performance -> logout", async ({
  page,
}) => {
  const browserErrors = collectBrowserErrors(page);

  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "시그널랩 로그인" })).toBeVisible();

  await page.getByRole("button", { name: "김민지 데모로 시작" }).click();
  await expect(page).toHaveURL(/\/survey$/);
  await expect(
    page.getByRole("heading", { name: /투자한 종목이 15% 하락/ }),
  ).toBeVisible();
  await assertNoHorizontalOverflow(page, 390, 844);

  await page.setViewportSize({ width: 1024, height: 768 });
  await page.getByRole("button", { name: "데모 응답 불러오기" }).click();
  for (let step = 0; step < 6; step += 1) {
    await page.getByRole("button", { name: "다음" }).click();
  }
  await page.getByRole("button", { name: "결과 확인" }).click();
  await expect(page.getByRole("heading", { name: "안정추구형" })).toBeVisible();

  await page.getByRole("button", { name: "대시보드로 이동" }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByText("오늘의 추천 종목", { exact: false }).first()).toBeVisible();
  await expectStoredOnboardingData(page, true);

  await page.reload();
  await expect(page).toHaveURL("/");
  await expect(page.getByText("오늘의 추천 종목", { exact: false }).first()).toBeVisible();
  await assertNoHorizontalOverflow(page, 390, 844);

  await page.setViewportSize({ width: 1024, height: 900 });
  await page.getByRole("link", { name: /근거 보기/ }).first().click();
  await expect(page).toHaveURL(/\/stocks\/(005930|005380|068270)$/);
  await expect(page.getByText(/과거 유사 신호 .*실현 수익률 분포/).first()).toBeVisible();
  await expect(page.getByText("주가 흐름", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "모델 성능" }).click();
  await expect(page).toHaveURL(/\/performance$/);
  await expect(
    page.getByRole("heading", { name: "심리 지수를 반영하면 예측이 나아지는가?" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "4런 전체 구간 비교" })).toBeVisible();

  await page.getByRole("button", { name: /로그아웃|나가기/ }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expectStoredOnboardingData(page, false);
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

async function expectStoredOnboardingData(page: Page, present: boolean): Promise<void> {
  const stored = await page.evaluate(
    ({ sessionKey, profileKey }) => ({
      session: localStorage.getItem(sessionKey),
      profile: localStorage.getItem(profileKey),
    }),
    { sessionKey: SESSION_KEY, profileKey: PROFILE_KEY },
  );
  expect(Boolean(stored.session)).toBe(present);
  expect(Boolean(stored.profile)).toBe(present);
}
