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
