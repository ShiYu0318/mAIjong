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

test("a double tap on the daily bonus claims it once", async ({ page }) => {
  const codes: number[] = [];
  page.on("response", (r) => { if (r.url().includes("/profile/bonus")) codes.push(r.status()); });
  await page.goto("/");
  await page.getByRole("button", { name: /領取 \d+/ }).dblclick();
  await expect(page.getByRole("button", { name: "已領取" })).toBeVisible();
  expect(codes).toEqual([200]);
});

test("joining a table that already started explains why, in the interface language", async ({ page, browser }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "開桌" }).click();
  await page.waitForURL(/\/room\//);
  const code = (await page.locator(".tabular.text-gold").first().innerText()).trim();
  await page.getByRole("button", { name: "開始", exact: true }).click();
  await expect(page.getByRole("tab", { name: "牌局紀錄" })).toBeVisible({ timeout: 30_000 });

  const late = await (await browser.newContext()).newPage();
  await late.goto("/");
  await late.getByLabel("六碼房間碼").fill(code);
  await late.getByRole("button", { name: "加入", exact: true }).click();
  await expect(late.getByText("牌局已經開始，無法加入。")).toBeVisible();
});

test("every page reads in English once switched", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("maijong.locale", "en"));
  const pages = ["/", "/agents", "/lab", "/offline", "/practice", "/tutor", "/tutor/analyze", "/tutor/quiz",
    "/tutor/lesson/calls", "/tutor/lesson/nope", "/leaderboard", "/profile", "/shop", "/no-such-page"];
  for (const path of pages) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    // runs of two or more Chinese characters; the language toggle says 中文 and the footer
    // carries the author's own name
    const chinese = (await page.locator("body").innerText()).match(/[\u4e00-\u9fff]{2,}/g) ?? [];
    expect(chinese.filter((w) => w !== "中文" && w !== "黃士育"), path).toEqual([]);
  }
});

const API = "http://localhost:8010/api/v1";

test("missing pages say what is missing and lead back", async ({ page }) => {
  const annotationCalls: string[] = [];
  page.on("request", (r) => { if (r.url().includes("/annotations")) annotationCalls.push(r.url()); });
  const cases: [string, string][] = [
    ["/no-such-page", "找不到這個頁面"],
    ["/agents/does-not-exist", "找不到這個代理程式。"],
    ["/replay/does-not-exist", "找不到這段錄影。"],
    ["/tutor/lesson/does-not-exist", "找不到這堂課。"],
    ["/room/does-not-exist", "找不到這個房間。"],
  ];
  for (const [path, text] of cases) {
    await page.goto(path);
    await expect(page.getByText(text), path).toBeVisible();
  }
  await page.goto("/no-such-page");
  await page.getByRole("link", { name: "回大廳" }).click();
  await expect(page.getByRole("heading", { name: "快速配對" })).toBeVisible();
  expect(annotationCalls).toEqual([]);  // notes are only fetched for replays that exist
});

test("an invite link seats a friend while waiting and explains once the game started", async ({ page, browser }) => {
  await page.goto("/");
  await page.getByLabel("座位 2").selectOption("open");
  await page.getByRole("button", { name: "開桌" }).click();
  await page.waitForURL(/\/room\//);
  const invite = page.url();
  const code = (await page.locator(".tabular.text-gold").first().innerText()).trim();

  const friend = await (await browser.newContext()).newPage();
  await friend.goto(invite);
  await expect(friend.getByText(code)).toBeVisible();
  await friend.getByRole("button", { name: "入座" }).click();
  await expect(friend.getByRole("heading", { name: "等待開局" })).toBeVisible();

  await page.getByRole("button", { name: "開始", exact: true }).click();
  await expect(page.getByRole("tab", { name: "牌局紀錄" })).toBeVisible({ timeout: 30_000 });
  const late = await (await browser.newContext()).newPage();
  await late.goto(invite);
  await expect(late.getByRole("heading", { name: "牌局已經開始了。" })).toBeVisible();
});

test("an invite to a table with no open seat says it is full", async ({ page, browser }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "開桌" }).click();  // every other seat is an AI by default
  await page.waitForURL(/\/room\//);
  const friend = await (await browser.newContext()).newPage();
  await friend.goto(page.url());
  await expect(friend.getByRole("heading", { name: "這桌已經坐滿了。" })).toBeVisible();
});

test("no sound starts before the first tap", async ({ page }) => {
  const warnings: string[] = [];
  page.on("console", (m) => { if (/AudioContext/.test(m.text())) warnings.push(m.text()); });
  await page.goto("/dev/result");  // the result show plays sounds on its own
  await page.waitForTimeout(3000);
  expect(warnings).toEqual([]);
});

test("lesson progress follows the account to another device", async ({ page, request }) => {
  const id = Date.now() % 1_000_000;
  const reg = await (await request.post(`${API}/auth/register`, {
    data: { username: `prog${id}`, email: `prog${id}@example.com`, password: "secret123" },
  })).json();
  await request.put(`${API}/tutor/progress/tiles`, {
    headers: { Authorization: `Bearer ${reg.token}` }, data: { status: "COMPLETED", quiz_score: 1 },
  });
  // a fresh browser that only knows the account, not the local lesson record
  await page.addInitScript((token) => localStorage.setItem("maijong.token", token), reg.token);
  await page.goto("/tutor");
  await expect(page.getByText("1 / 8")).toBeVisible();
});

test("decision quiz tiles are named for screen readers", async ({ page }) => {
  await page.goto("/tutor/quiz");
  const first = page.getByRole("button", { name: /^打出 / }).first();
  await expect(first).toBeVisible({ timeout: 15_000 });
  expect(await first.getAttribute("aria-label")).not.toMatch(/^打出 \d+$/);
});

test("the header keeps the hand number while its result shows", async ({ page }) => {
  test.setTimeout(240_000);
  await page.goto("/");
  await page.getByRole("button", { name: "開桌" }).click();
  await page.waitForURL(/\/room\//);
  await page.getByRole("button", { name: "開始", exact: true }).click();
  const header = page.locator("header").first();
  await expect(header).toContainText("第 1 手", { timeout: 30_000 });
  // the round is named once, in the header, not over the discards
  await expect(page.getByText(/東風圈・第 1 手/)).toHaveCount(1);
  const result = page.getByRole("dialog", { name: "本手結果" });
  while (!(await result.isVisible())) {
    const pass = page.getByRole("button", { name: "過", exact: true });
    if (await pass.isVisible()) await pass.click().catch(() => {});
    else if (await page.getByRole("button", { name: "提示", exact: true }).isVisible()) {
      await page.keyboard.press("ArrowRight");
      await page.keyboard.press("Enter");
    }
    await page.waitForTimeout(150);
  }
  await page.waitForTimeout(800);  // the room update with the new count arrives after the result
  await expect(header).toContainText("第 1 手");
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

  test("the leaderboard podium fits in English", async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("maijong.locale", "en"));
    await page.goto("/leaderboard");
    const podium = page.getByRole("region", { name: "Top three" }).or(page.locator("section[aria-label='Top three']"));
    await expect(podium.first()).toBeVisible();
    const box = await podium.first().evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth }));
    expect(box.scroll).toBeLessThanOrEqual(box.client + 1);
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
