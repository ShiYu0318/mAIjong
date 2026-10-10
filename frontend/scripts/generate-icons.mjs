// Render the app icon (a jade-backed tile with 麥) to PNGs with headless Chromium.
// node scripts/generate-icons.mjs
import { chromium } from "@playwright/test";

const html = (size, pad) => `<!doctype html><html><head>
<link href="https://fonts.googleapis.com/css2?family=LXGW+WenKai+TC:wght@700&display=block" rel="stylesheet">
<style>html,body{margin:0;background:#12302b}</style></head><body>
<canvas id="c" width="${size}" height="${size}"></canvas>
<script>
document.fonts.load('700 10px "LXGW WenKai TC"', '麥').then(() => {
  const c = document.getElementById('c'), x = c.getContext('2d'), s = ${size}, p = s * ${pad};
  x.fillStyle = '#12302b'; x.fillRect(0, 0, s, s);
  const w = s - 2 * p, h = s - 2 * p, r = s * 0.12;
  const rr = (X, Y, W, H) => { x.beginPath(); x.moveTo(X + r, Y); x.arcTo(X + W, Y, X + W, Y + H, r);
    x.arcTo(X + W, Y + H, X, Y + H, r); x.arcTo(X, Y + H, X, Y, r); x.arcTo(X, Y, X + W, Y, r); x.closePath(); };
  rr(p, p + s * 0.05, w, h - s * 0.05); x.fillStyle = '#1f6f57'; x.fill();
  rr(p, p, w, h - s * 0.08); x.fillStyle = '#f4efe1'; x.fill();
  x.fillStyle = '#b3192c'; x.font = '700 ' + (s * 0.5) + 'px "LXGW WenKai TC"';
  x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText('麥', s / 2, s / 2 - s * 0.03);
  document.title = 'done';
});
</script></body></html>`;

const browser = await chromium.launch();
for (const [size, name, pad] of [[512, "icon-512.png", 0.1], [192, "icon-192.png", 0.1],
  [180, "apple-touch-icon.png", 0.08], [512, "icon-maskable-512.png", 0.2]]) {
  const page = await browser.newPage({ viewport: { width: size, height: size } });
  await page.setContent(html(size, pad));
  await page.waitForFunction(() => document.title === "done", null, { timeout: 30000 });
  await page.locator("#c").screenshot({ path: `public/icons/${name}` });
  await page.close();
}
await browser.close();
console.log("icons written to public/icons");
