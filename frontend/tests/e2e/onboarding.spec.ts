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
  questions: { id: string; text: string; direction: number; short: boolean }[];
};
const LIKERT_LABEL = new Map(BANK.likert.options.map(({ value, label }) => [value, label]));
const ANSWER_LABEL = new Map(
  BANK.questions
    .filter(({ short }) => short)
    .map(({ text, direction }) => [text, LIKERT_LABEL.get(3 + 2 * direction)!]),
);

// 한 화면 한 문항: 고르면 바로 다음 문항으로 넘어간다.
async function answerCurrentQuestion(page: Page): Promise<void> {
  const group = page.locator("fieldset");
  const text = (await group.locator("legend").innerText()).trim();
  const label = ANSWER_LABEL.get(text);
  if (!label) throw new Error(`문항 정의에 없는 문항: ${text}`);
  await group.getByLabel(label, { exact: true }).check();
}

async function startDemo(page: Page): Promise<void> {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByRole("button", { name: "데모로 둘러보기" }).click();
  await expect(page).toHaveURL(/\/survey$/);
  // 처음 온 사람: 환영 1장 + 상단 진행 표시
  await expect(page.getByRole("heading", { name: "시그널랩은 이렇게 도와줘요" })).toBeVisible();
  await expect(page.getByRole("list", { name: "시작 단계" })).toContainText("1 성향2 보유 종목3 시작");
}

test("new user: 환영 -> 16문항 -> 결과 -> 보유 종목 1개 -> 대시보드 맵 -> 상세 -> logout", async ({ page }) => {
  const browserErrors = collectBrowserErrors(page);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "시그널랩 로그인" })).toBeVisible();
  // 계정 로그인과 데모 계정이 항상 함께 보인다(환경변수가 없으면 계정 쪽은 안내만)
  await expect(page.getByText(/이메일로 시작|계정 기능이 아직 연결되지 않았어요/).first()).toBeVisible();
  await expect(page.getByText("데모 계정 · 예시 데이터")).toHaveCount(0);

  await startDemo(page);
  await expect(page.getByText("데모 계정 · 예시 데이터")).toBeVisible();
  await assertNoHorizontalOverflow(page, 390, 844);
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.getByRole("button", { name: "시작하기" }).click();

  // 짧은 진단 16문항: 한 화면 한 문항, 고르면 바로 다음
  for (let number = 1; number <= 16; number += 1) {
    await expect(page.getByText(`질문 ${number}/16`)).toBeVisible();
    await answerCurrentQuestion(page);
    if (number === 3) {
      // 되돌리기: 이전 문항의 답이 남아 있어야 한다
      await expect(page.getByText("질문 4/16")).toBeVisible();
      await page.getByRole("button", { name: "이전" }).click();
      await expect(page.getByText("질문 3/16")).toBeVisible();
      await expect(page.locator("fieldset input:checked")).toHaveCount(1);
      // 이미 고른 답을 다시 눌러도 다음으로 넘어간다
      await page.locator("fieldset input:checked").click();
    }
    if (number === 8) {
      // 중간 저장: 새로고침해도 같은 문항에서 이어진다
      await expect(page.getByText("질문 9/16")).toBeVisible();
      await page.reload();
      await expect(page.getByText("저장해 둔 응답을 불러왔어요", { exact: false })).toBeVisible();
      await expect(page.getByText("질문 9/16")).toBeVisible();
    }
  }

  await expect(page.getByText("마무리 1/3")).toBeVisible();
  await page.getByLabel("6개월~2년").check();
  await expect(page.getByText("마무리 2/3")).toBeVisible();
  await page.getByLabel("SPAC", { exact: false }).check();
  await page.getByRole("button", { name: "다음" }).click();
  await expect(page.getByText("마무리 3/3")).toBeVisible();
  await page.getByRole("button", { name: "결과 확인" }).click();

  // 결과 확인: 저장 전 확인 단계 + 24문항으로 더 정확하게 진단하는 길
  await expect(page.getByRole("heading", { name: "적극 축적형" })).toBeVisible();
  await expect(page.getByText("이 결과가 나와 맞나요?")).toBeVisible();
  await expect(page.getByRole("button", { name: "더 정확하게 진단하기(24문항)" })).toBeVisible();
  await expectStoredOnboardingData(page, { session: true, profile: false });
  await page.getByRole("button", { name: "네, 이대로 저장" }).click();
  await expect(page.getByText("프로필 저장 완료")).toBeVisible();
  await expectStoredOnboardingData(page, { session: true, profile: true });
  const storedTypes = await page.evaluate((key) => {
    const profile = JSON.parse(localStorage.getItem(key) ?? "{}");
    return profile.style_axes.axes.map((axis: { ratio: number; question_count: number }) => [
      axis.ratio,
      axis.question_count,
    ]);
  }, PROFILE_KEY);
  expect(storedTypes).toEqual(Array(8).fill([1, 2]));

  // 보유 종목: 데모 예시를 비우고 1종목만 넣는다(평균 매입가는 비워 둠 → 현재가 기준)
  await page.getByRole("button", { name: "다음: 보유 종목" }).click();
  await expect(page.getByRole("heading", { name: "지금 가진 주식이 있나요?" })).toBeVisible();
  await expect(page.getByText("예시로 넣어 뒀어요, 바꿔도 돼요.")).toBeVisible();
  for (const name of ["삼성전자", "카카오", "셀트리온", "현대차"]) {
    await page.getByRole("button", { name: `${name} 빼기` }).click();
  }
  await page.getByLabel("종목 검색").fill("삼성전자");
  await page.getByLabel("수량(주)").fill("10");
  await page.getByRole("button", { name: "종목 넣기" }).click();
  await expect(page.getByText("평균 매입가 모름(현재가 기준)")).toBeVisible();
  await page.getByRole("button", { name: "저장하고 시작" }).click();

  // 대시보드: 두 결과(성향 + 보유 종목)를 합쳐 보여 준다
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("보유 1종목 모두 부정 신호는 없어요.");
  await expect(page.getByRole("list", { name: "보유 종목별 오늘 모델 신호" }).getByRole("listitem")).toHaveCount(1);
  await expect(page.getByText("평균 매입가를 비운 종목은 현재가 기준")).toBeVisible();
  await expect(page.getByRole("heading", { name: "오늘 신호가 강한 종목" })).toBeVisible();
  await expect(page.getByText("데모 계정 · 예시 데이터")).toBeVisible();
  await expect(page.getByText("적극 축적형", { exact: true })).toBeVisible();
  await expect(page.getByText("추종형", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("적극 축적형", { exact: true })).toBeVisible();
  await assertNoHorizontalOverflow(page, 390, 844);

  // 계정 메뉴에 다시 진단·보유 종목 편집이 묶여 있다
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.getByText("계정", { exact: true }).click();
  await expect(page.getByRole("link", { name: "내 성향 다시 진단" })).toBeVisible();
  await expect(page.getByRole("link", { name: "보유 종목 편집" })).toBeVisible();
  await page.getByText("계정", { exact: true }).click();

  await page.locator("[data-stock-row]").first().click();
  await expect(page).toHaveURL(/\/stocks\/(005930|005380|068270)$/);
  await expect(page.getByText(/과거 비슷한 경우, 2주 뒤 수익률은 10번 중 \d번 이 범위였어요/)).toBeVisible();
  await expect(page.locator('[data-bit-type="ACCUMULATOR"]')).toBeVisible();
  // 판단 근거 탭 순서 = 유형의 카드 순서(연구 문항 ②). 적극 축적형: 모델이 본 이유가 첫 탭
  await expect(page.getByRole("tablist", { name: "판단 근거" })).toHaveAttribute(
    "data-card-order",
    "nudge,contribution,sentiment,supply,risk,financial",
  );
  await expect(page.getByRole("tab", { selected: true })).toHaveText("모델이 본 이유");
  await expect(page.getByText("데모 계정 · 예시 데이터")).toBeVisible();

  // 다른 유형이라면?: 이 화면만 바뀌고 저장된 결과는 그대로
  await page.getByText("다른 유형이라면?").click();
  await page.getByRole("button", { name: "자산 보존형" }).click();
  await expect(page.locator('[data-bit-type="PRESERVER"]')).toBeVisible();
  await expect(page.getByText("시선으로 보는 중", { exact: false })).toBeVisible();
  await expect(page.getByRole("tab", { selected: true })).toHaveText("시장 분위기");
  await page.getByRole("button", { name: "내 성향" }).click();
  await expect(page.locator('[data-bit-type="ACCUMULATOR"]')).toBeVisible();

  await page.getByRole("link", { name: "모델 성적표" }).click();
  await expect(page).toHaveURL(/\/performance$/);
  await expect(page.getByRole("heading", { name: /판별력\(AUC\)/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "심리 지표를 더하면 나아지나요?" })).toBeVisible();

  await page.getByRole("button", { name: /로그아웃|나가기/ }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expectStoredOnboardingData(page, { session: false, profile: false });
  expect(browserErrors).toEqual([]);
});

test("new user: 보유 종목 '아직 없어요' -> 대시보드 빈 상태", async ({ page }) => {
  const browserErrors = collectBrowserErrors(page);
  await startDemo(page);
  await page.getByRole("button", { name: "시작하기" }).click();
  await page.getByRole("button", { name: /데모 응답/ }).click();
  await page.getByRole("button", { name: "결과 확인" }).click();
  await page.getByRole("button", { name: "네, 이대로 저장" }).click();
  await page.getByRole("button", { name: "다음: 보유 종목" }).click();
  await page.getByRole("button", { name: "아직 없어요" }).click();

  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("오늘 모델 신호가 강한 종목은 2개예요.");
  await expect(page.getByText("관심 가는 종목을 검색해 보세요")).toBeVisible();
  // 돌아온 사용자는 온보딩을 건너뛴다
  await page.goto("/survey");
  await expect(page.getByRole("heading", { name: "시그널랩은 이렇게 도와줘요" })).toHaveCount(0);
  await expect(page.getByText("질문 1/16")).toBeVisible();
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
