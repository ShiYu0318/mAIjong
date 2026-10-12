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
    } else if (await page.getByText("點一張牌選取").isVisible().catch(() => false)) {
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
    } else if (await page.getByText("點一張牌選取").isVisible().catch(() => false)) {
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
