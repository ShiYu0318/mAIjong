import { expect, test } from "@playwright/test";

test("create a table with AI seats and play several turns", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "麥醬" })).toBeVisible();
  await page.getByRole("button", { name: "開桌" }).click();
  await page.waitForURL(/\/room\//);
  await expect(page.getByRole("heading", { name: "等待開局" })).toBeVisible();
  await page.getByRole("button", { name: "開始" }).click();

  const canvas = page.locator("canvas");
  await expect(canvas).toBeVisible({ timeout: 30_000 });
  const log = page.locator("aside p");

  // act whenever asked: pass on calls, otherwise discard the right-most tile
  for (let i = 0; i < 25 && (await log.count()) < 8; i++) {
    const pass = page.getByRole("button", { name: "過", exact: true });
    if (await pass.isVisible().catch(() => false)) {
      await pass.click();
    } else if (await page.getByRole("button", { name: "提示", exact: true }).isVisible().catch(() => false)) {
      const box = (await canvas.boundingBox())!;
      const x = box.x + box.width / 2;
      const y = box.y + box.height - 45;
      await page.mouse.click(x, y);
      await page.mouse.click(x, y);
    }
    await page.waitForTimeout(800);
  }
  expect(await log.count()).toBeGreaterThanOrEqual(8);
});

test("play with the keyboard only", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "開桌" }).click();
  await page.waitForURL(/\/room\//);
  await page.getByRole("button", { name: "開始" }).click();
  await expect(page.locator("canvas")).toBeVisible({ timeout: 30_000 });
  const handList = page.getByRole("region", { name: "你的手牌" });
  const log = page.locator("aside p");

  let discarded = false;
  for (let i = 0; i < 40 && !discarded; i++) {
    if (await page.getByRole("button", { name: "過", exact: true }).isVisible().catch(() => false)) {
      await page.keyboard.press("x");
    } else if (await page.getByRole("button", { name: "提示", exact: true }).isVisible().catch(() => false)) {
      // our discard turn (the help text is hidden when a kong or win is also possible)
      const before = await log.count();
      await page.keyboard.press("ArrowLeft");
      await expect(handList.locator("button[aria-pressed=true]")).toHaveCount(1);
      await page.keyboard.press("Enter");
      await expect.poll(() => log.count()).toBeGreaterThan(before);
      discarded = true;
    }
    await page.waitForTimeout(500);
  }
  expect(discarded).toBe(true);
  await expect(page.locator("[aria-live=polite]").first()).not.toBeEmpty();
});

test("switch the interface to English and keep the choice", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "切換語言" }).click();
  await expect(page.getByRole("heading", { name: "Quick match" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Open a table" })).toBeVisible();
  await page.getByRole("button", { name: "Open table" }).click();
  await page.waitForURL(/\/room\//);
  await expect(page.getByRole("heading", { name: "Waiting to start" })).toBeVisible();
  await page.getByRole("button", { name: "Start" }).click();
  await expect(page.getByRole("tab", { name: "Log" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Switch language" }).click();
  await expect(page.getByRole("tab", { name: "牌局紀錄" })).toBeVisible();
});

test("every page reads in English once switched", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("maijong.locale", "en"));
  const pages = ["/", "/agents", "/lab", "/offline", "/practice", "/tutor", "/tutor/analyze", "/tutor/quiz",
    "/tutor/lesson/calls", "/tutor/lesson/nope", "/leaderboard", "/profile", "/shop"];
  for (const path of pages) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    // runs of two or more Chinese characters; the language toggle itself says 中文
    const chinese = (await page.locator("body").innerText()).match(/[\u4e00-\u9fff]{2,}/g) ?? [];
    expect(chinese.filter((w) => w !== "中文"), path).toEqual([]);
  }
});

test.describe("phone screen", () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

  test("lobby and table fit without sideways scrolling", async ({ page }) => {
    const overflow = () => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "快速配對" })).toBeVisible();
    await page.waitForTimeout(1500);
    expect(await overflow()).toBeLessThanOrEqual(1);
    await page.getByRole("button", { name: "開桌" }).click();
    await page.waitForURL(/\/room\//);
    await page.getByRole("button", { name: "開始" }).click();
    await expect(page.locator("canvas")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("region", { name: "你的手牌" })).toBeAttached();
    expect(await overflow()).toBeLessThanOrEqual(1);
  });

  test("account, sound and language fold into the phone menu", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("button", { name: "切換語言" })).toBeHidden();
    await page.getByRole("button", { name: "選單" }).click();
    await expect(page.getByRole("button", { name: "切換語言" })).toBeVisible();
    await expect(page.getByRole("button", { name: "綁定帳號" })).toBeVisible();
  });
});

test("level-up moment plays and closes on a tap", async ({ page }) => {
  await page.goto("/dev/ui");
  await page.getByRole("button", { name: "升級演出" }).click();
  const show = page.getByRole("button", { name: "升級！等級 12" });
  await expect(show).toBeVisible();
  await expect(page.getByText("LEVEL UP")).toBeVisible();
  await show.click();
  await expect(show).toBeHidden();
});

test("result show counts down to the next hand and lists readiness on a draw", async ({ page }) => {
  await page.goto("/dev/result");
  await expect(page.getByRole("dialog", { name: "本手結果" })).toBeVisible();
  await expect(page.getByText(/下一手 \d+ 秒後開始/)).toBeVisible();
  await expect(page.getByText("總台數")).toBeVisible({ timeout: 10_000 });
  await page.goto("/dev/result?draw");
  await expect(page.getByText("海底流局")).toBeVisible();
  await expect(page.getByText("聽牌 · 已宣告")).toBeVisible();
  await expect(page.getByText("未聽").first()).toBeVisible();
});
