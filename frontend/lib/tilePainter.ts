/**
 * Procedural tile artwork drawn with Canvas 2D so the page's calligraphic web font
 * applies to the printed characters. The same canvases back PixiJS textures and
 * DOM <img> previews.
 */
import { DRAGONS, FLOWERS, NUMERALS, WINDS } from "./tiles";

export const TILE_W = 60;
export const TILE_H = 80;
const DEPTH = 6; // jade back visible below the ivory face

const C = {
  face: "#f4efe1",
  faceEdge: "#cfc6ac",
  back: "#1f6f57",
  backEdge: "#164f3e",
  ink: "#1a1a17",
  red: "#b3192c",
  green: "#1f6f57",
  blue: "#1e4f8c",
};

type Pt = [number, number];

// dot / stick layouts on a 0-1 grid inside the face
const LAYOUT: Record<number, Pt[]> = {
  1: [[0.5, 0.5]],
  2: [[0.5, 0.27], [0.5, 0.73]],
  3: [[0.25, 0.22], [0.5, 0.5], [0.75, 0.78]],
  4: [[0.3, 0.28], [0.7, 0.28], [0.3, 0.72], [0.7, 0.72]],
  5: [[0.27, 0.24], [0.73, 0.24], [0.5, 0.5], [0.27, 0.76], [0.73, 0.76]],
  6: [[0.3, 0.2], [0.7, 0.2], [0.3, 0.5], [0.7, 0.5], [0.3, 0.8], [0.7, 0.8]],
  7: [[0.22, 0.16], [0.5, 0.26], [0.78, 0.36], [0.3, 0.6], [0.7, 0.6], [0.3, 0.84], [0.7, 0.84]],
  8: [[0.3, 0.14], [0.7, 0.14], [0.3, 0.38], [0.7, 0.38], [0.3, 0.62], [0.7, 0.62],
      [0.3, 0.86], [0.7, 0.86]],
  9: [[0.2, 0.18], [0.5, 0.18], [0.8, 0.18], [0.2, 0.5], [0.5, 0.5], [0.8, 0.5],
      [0.2, 0.82], [0.5, 0.82], [0.8, 0.82]],
};

const FACE = { x: 4, y: 4, w: TILE_W - 8, h: TILE_H - DEPTH - 8 };

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number,
  r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function body(ctx: CanvasRenderingContext2D, faceUp: boolean) {
  // jade back peeking out underneath
  roundRect(ctx, 1, DEPTH, TILE_W - 2, TILE_H - DEPTH - 1, 7);
  ctx.fillStyle = C.back;
  ctx.fill();
  ctx.strokeStyle = C.backEdge;
  ctx.lineWidth = 1.5;
  ctx.stroke();
  roundRect(ctx, 1, 1, TILE_W - 2, TILE_H - DEPTH - 1, 7);
  ctx.fillStyle = faceUp ? C.face : C.back;
  ctx.fill();
  ctx.strokeStyle = faceUp ? C.faceEdge : C.backEdge;
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

function pos([u, v]: Pt): Pt {
  return [FACE.x + u * FACE.w, FACE.y + v * FACE.h];
}

function circles(ctx: CanvasRenderingContext2D, n: number) {
  const pts = LAYOUT[n];
  const r = n === 1 ? 17 : n <= 4 ? 9 : n <= 6 ? 7.5 : 6.2;
  pts.forEach((p, i) => {
    const [x, y] = pos(p);
    const color = n === 1 ? C.blue : [C.blue, C.green, C.red][i % 3];
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = C.face;
    ctx.fill();
    ctx.lineWidth = Math.max(1.6, r * 0.32);
    ctx.strokeStyle = color;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(x, y, r * 0.38, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  });
}

function sticks(ctx: CanvasRenderingContext2D, n: number, font: string) {
  if (n === 1) {
    // 一條 is traditionally a bird; a bold single bamboo with a red tip reads clearly
    const [x, y] = pos([0.5, 0.5]);
    stick(ctx, x, y, 9, 46, C.green);
    ctx.fillStyle = C.red;
    ctx.beginPath();
    ctx.arc(x, y - 25, 4.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.font = `700 11px ${font}`;
    ctx.textAlign = "center";
    ctx.fillText("一", x + 15, y - 18);
    return;
  }
  const h = n <= 3 ? 26 : n <= 6 ? 17 : 13;
  LAYOUT[n].forEach((p, i) => {
    const [x, y] = pos(p);
    const color = n >= 5 && i === Math.floor(LAYOUT[n].length / 2) && n % 2 === 1
      ? C.red : C.green;
    stick(ctx, x, y, 5.5, h, color);
  });
}

function stick(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number,
  color: string) {
  roundRect(ctx, x - w / 2, y - h / 2, w, h, w / 2);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.strokeStyle = C.face;
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(x - w / 2, y);
  ctx.lineTo(x + w / 2, y);
  ctx.stroke();
}

function text(ctx: CanvasRenderingContext2D, s: string, x: number, y: number, size: number,
  color: string, font: string, weight = 700) {
  ctx.font = `${weight} ${size}px ${font}`;
  ctx.fillStyle = color;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(s, x, y);
}

/** Paint tile `id` (or a face-down tile when id is null) at the canvas origin. */
export function paintTile(ctx: CanvasRenderingContext2D, id: number | null, font: string) {
  body(ctx, id !== null);
  if (id === null) return;
  const cx = FACE.x + FACE.w / 2;
  if (id < 9) {
    text(ctx, NUMERALS[id], cx, FACE.y + FACE.h * 0.3, 23, C.ink, font);
    text(ctx, "萬", cx, FACE.y + FACE.h * 0.72, 25, C.red, font);
  } else if (id < 18) {
    sticks(ctx, id - 8, font);
  } else if (id < 27) {
    circles(ctx, id - 17);
  } else if (id < 31) {
    text(ctx, WINDS[id - 27], cx, FACE.y + FACE.h / 2, 36, C.ink, font);
  } else if (id === 31) {
    text(ctx, DRAGONS[0], cx, FACE.y + FACE.h / 2, 38, C.red, font);
  } else if (id === 32) {
    text(ctx, DRAGONS[1], cx, FACE.y + FACE.h / 2, 36, C.green, font);
  } else if (id === 33) {
    roundRect(ctx, FACE.x + 7, FACE.y + 8, FACE.w - 14, FACE.h - 16, 3);
    ctx.strokeStyle = C.blue;
    ctx.lineWidth = 3;
    ctx.stroke();
  } else {
    const k = id - 34;
    const color = k < 4 ? C.green : C.red;
    text(ctx, FLOWERS[k], cx, FACE.y + FACE.h * 0.55, 30, color, font);
    text(ctx, String((k % 4) + 1), FACE.x + 8, FACE.y + 9, 11, C.blue, font);
  }
}

const cache = new Map<string, HTMLCanvasElement>();

/** Cached, high-DPI canvas for a tile. */
export function tileCanvas(id: number | null, font: string, scale = 2): HTMLCanvasElement {
  const key = `${id}:${scale}:${font}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const c = document.createElement("canvas");
  c.width = TILE_W * scale;
  c.height = TILE_H * scale;
  const ctx = c.getContext("2d")!;
  ctx.scale(scale, scale);
  paintTile(ctx, id, font);
  cache.set(key, c);
  return c;
}

const urlCache = new Map<string, string>();

export function tileDataUrl(id: number | null, font: string): string {
  const key = `${id}:${font}`;
  let url = urlCache.get(key);
  if (!url) {
    url = tileCanvas(id, font).toDataURL("image/png");
    urlCache.set(key, url);
  }
  return url;
}

/** Resolve the loaded calligraphic font family (falls back to system Kai faces). */
export function tileFontFamily(): string {
  if (typeof window === "undefined") return "serif";
  const v = getComputedStyle(document.documentElement).getPropertyValue("--font-wenkai").trim();
  return `${v ? v + ", " : ""}"Kaiti TC", "BiauKai", serif`;
}

const TILE_CHARS = "一二三四五六七八九萬條筒東南西北中發白春夏秋冬梅蘭菊竹1234";
let fontPromise: Promise<string> | null = null;

/** Load the calligraphic glyphs used on tiles before painting (CJK subsets load lazily). */
export function ensureTileFont(): Promise<string> {
  if (!fontPromise) {
    const family = tileFontFamily();
    const first = family.split(",")[0].trim();
    fontPromise = Promise.all([
      document.fonts.load(`700 30px ${first}`, TILE_CHARS),
      document.fonts.load(`400 30px ${first}`, TILE_CHARS),
    ]).then(() => family, () => family);
  }
  return fontPromise;
}
