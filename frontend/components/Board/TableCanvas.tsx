"use client";

import { Application, Container, Graphics, Sprite, Texture } from "pixi.js";
import { useEffect, useRef } from "react";
import type { GameView, MeldView, PlayerView } from "@/lib/protocol";
import { sfx } from "@/lib/sfx";
import { type TableLayout, relSeat, tableLayout } from "@/lib/tableLayout";
import { TILE_H, TILE_W, ensureTileFont, tileBack, tileCanvas } from "@/lib/tilePainter";
import { useLocale } from "@/lib/i18n";
import { useAccount } from "@/store/accountStore";
import { useGame } from "@/store/gameStore";

const COLORS = {
  cyan: 0x38d0ff,
  gold: 0xffcc3d,
  shadow: 0x050619,
};

type Textures = Map<number | "back", Texture> & { back?: string };

function buildTextures(font: string): Textures {
  const map: Textures = new Map();
  for (let id = 0; id < 42; id++) map.set(id, Texture.from(tileCanvas(id, font, 3)));
  map.set("back", Texture.from(tileCanvas(null, font, 3)));
  map.back = tileBack();
  return map;
}

/** Reuses tile sprites across redraws instead of re-creating ~150 per state update
 * (SPEC P11-7). Sprites are reset to defaults when taken from the pool. */
export class SpritePool {
  private free: Sprite[] = [];
  private used: Sprite[] = [];
  created = 0;

  get(texture: Texture): Sprite {
    let s = this.free.pop();
    if (!s) {
      s = new Sprite();
      this.created += 1;
    }
    s.texture = texture;
    s.alpha = 1;
    s.rotation = 0;
    s.visible = true;
    s.tint = 0xffffff;
    s.eventMode = "passive";
    s.cursor = "default";
    s.removeAllListeners();
    this.used.push(s);
    return s;
  }

  /** Detach every sprite handed out since the last call and make it available again. */
  releaseAll() {
    for (const s of this.used) {
      s.removeFromParent();
      s.removeAllListeners();
    }
    this.free.push(...this.used);
    this.used = [];
  }

  destroy() {
    this.releaseAll();
    for (const s of this.free) s.destroy();
    this.free = [];
  }

  get size() {
    return this.free.length + this.used.length;
  }
}

const pools = new WeakMap<Application, SpritePool>();
let pool = new SpritePool(); // the pool of the app being rendered (render() is synchronous)

function poolFor(app: Application): SpritePool {
  let p = pools.get(app);
  if (!p) {
    p = new SpritePool();
    pools.set(app, p);
  }
  return p;
}

function tileSprite(tex: Textures, id: number | null, w: number): Sprite {
  const s = pool.get(tex.get(id === null ? "back" : id)!);
  s.width = w;
  s.height = (w * TILE_H) / TILE_W;
  return s;
}

/** Per-app memory of the last frame, to animate what changed (new discard, new draw). */
interface Memory {
  gameId: string | null;
  rivers: number[];
  handLen: number;
  generation: number;
}
const memories = new WeakMap<Application, Memory>();

/** Tween a sprite from an offset to its resting place; stops if the scene is redrawn. */
function tweenIn(app: Application, mem: Memory, s: Sprite, from: { dx: number; dy: number; scale?: number },
  ms: number) {
  const gen = mem.generation;
  const toX = s.x;
  const toY = s.y;
  const w = s.width;
  const h = s.height;
  const k0 = from.scale ?? 1;
  let t = 0;
  const step = (ticker: { deltaMS: number }) => {
    if (mem.generation !== gen || s.destroyed) {
      app.ticker.remove(step);
      return;
    }
    t = Math.min(1, t + ticker.deltaMS / ms);
    const e = 1 - (1 - t) ** 3;
    const k = k0 + (1 - k0) * e;
    s.width = w * k;
    s.height = h * k;
    s.x = toX + from.dx * (1 - e) - (w * k - w) / 2;
    s.y = toY + from.dy * (1 - e) - (h * k - h) / 2;
    s.alpha = Math.min(1, 0.3 + e);
    if (t >= 1) app.ticker.remove(step);
  };
  step({ deltaMS: 0 });
  app.ticker.add(step);
}

function outline(c: Container, s: Sprite, color: number, width = 2.5) {
  c.addChild(new Graphics().roundRect(s.x - 1.5, s.y - 1.5, s.width + 3, s.height + 3, 6)
    .stroke({ width, color, alpha: 0.95 }));
}

/** Draws melds left→right starting at x; returns the x after the last meld.
 * Concealed kongs show their two outer tiles face down (all four for opponents). */
function drawMelds(c: Container, tex: Textures, melds: MeldView[], x: number, y: number, w: number,
  highlight: number | null): number {
  for (const m of melds) {
    m.tiles.forEach((t, i) => {
      const faceDown = t === null || (m.type === "AN_KONG" && (i === 0 || i === 3));
      const s = tileSprite(tex, faceDown ? null : t, w);
      s.x = x;
      s.y = y;
      c.addChild(s);
      if (!faceDown && t === highlight) outline(c, s, COLORS.cyan);
      x += w - 1;
    });
    x += w * 0.35;
  }
  return x;
}

interface Scene {
  view: GameView;
  selected: number | null;
  discardable: Set<number>;
  onTile: (tile: number) => void;
}

function render(app: Application, tex: Textures, sc: Scene) {
  const stage = app.stage;
  pool = poolFor(app);
  pool.releaseAll(); // pooled tile sprites survive; containers and graphics are rebuilt
  stage.removeChildren().forEach((ch) => ch.destroy({ children: true }));
  let mem = memories.get(app);
  if (!mem || mem.gameId !== sc.view.game_id) {
    mem = { gameId: sc.view.game_id, rivers: sc.view.players.map((p) => p.discards.length),
      handLen: 0, generation: 0 };
    memories.set(app, mem);
  }
  mem.generation += 1;
  const g = tableLayout(app.screen.width, app.screen.height);
  const me = sc.view.you ?? 0;
  const last = sc.view.last_discard;

  for (const p of sc.view.players) {
    const rel = relSeat(p.seat, me);
    const area = new Container();
    area.x = g.cx;
    area.y = g.cy;
    area.rotation = (-rel * Math.PI) / 2;
    stage.addChild(area);
    drawRiver(app, mem, area, tex, p, g, !!last && last[0] === p.seat, sc.selected);
    if (rel !== 0) drawOpponent(area, tex, p, g, sc.selected);
  }
  mem.rivers = sc.view.players.map((p) => p.discards.length);
  drawMyHand(app, mem, stage, tex, sc.view.players[me], sc, g);
}

function drawRiver(app: Application, mem: Memory, area: Container, tex: Textures, p: PlayerView,
  g: TableLayout, lastIsMine: boolean, highlight: number | null) {
  const perRow = 6;
  const w = g.sd;
  const h = g.sdH;
  const startX = -((perRow * w) / 2);
  const startY = g.L * 0.13;
  const isNew = p.discards.length === (mem.rivers[p.seat] ?? 0) + 1;
  p.discards.forEach((t, i) => {
    const s = tileSprite(tex, t, w);
    s.x = startX + (i % perRow) * w;
    s.y = startY + Math.floor(i / perRow) * (h - 3);
    if (p.tsumogiri?.[i]) s.tint = 0xb4b8cf; // tsumogiri: drawn and discarded straight away
    area.addChild(s);
    const newest = i === p.discards.length - 1;
    if (newest && lastIsMine) {
      area.addChild(new Graphics().roundRect(s.x - 2, s.y - 2, w + 4, h + 4, 6)
        .stroke({ width: 3, color: COLORS.gold, alpha: 0.95 }));
    } else if (t === highlight) {
      outline(area, s, COLORS.cyan);
    }
    // fly in from the player's hand
    if (newest && isNew) tweenIn(app, mem, s, { dx: -s.x, dy: g.L * 0.42 - s.y, scale: 1.6 }, 230);
  });
}

function drawOpponent(area: Container, tex: Textures, p: PlayerView, g: TableLayout,
  highlight: number | null) {
  const w = g.sd * 0.98;
  const h = (w * TILE_H) / TILE_W;
  const y = g.L / 2 - h - 8;
  const meldCount = p.melds.reduce((n, m) => n + m.tiles.length, 0);
  const total = p.hand_count + meldCount + p.melds.length * 0.35;
  let x = -((total * (w - 1)) / 2);
  const handTiles = p.hand ?? Array(p.hand_count).fill(null);
  for (const t of handTiles) {
    const s = tileSprite(tex, t, w);
    s.x = x;
    s.y = y;
    area.addChild(s);
    x += w - 1;
  }
  x += w * 0.5;
  drawMelds(area, tex, p.melds, x, y, w, highlight);
  p.flowers.forEach((f, i) => {
    const s = tileSprite(tex, f, w * 0.72);
    s.x = -g.L / 2 + 12 + i * (w * 0.72 - 1);
    s.y = y - h * 0.85;
    area.addChild(s);
  });
}

function drawMyHand(app: Application, mem: Memory, stage: Container, tex: Textures, p: PlayerView,
  sc: Scene, g: TableLayout) {
  const hand = p.hand ?? [];
  const w = g.handW;
  const h = g.handH;
  const lastDraw = sc.view.last_draw;
  let tiles = hand;
  let drawn: number | null = null;
  if (lastDraw !== null && sc.view.turn === p.seat && sc.view.phase === "DISCARD") {
    const idx = hand.lastIndexOf(lastDraw);
    if (idx >= 0) {
      tiles = [...hand.slice(0, idx), ...hand.slice(idx + 1)];
      drawn = lastDraw;
    }
  }
  const justDrew = drawn !== null && hand.length === mem.handLen + 1;
  mem.handLen = hand.length;
  const meldTiles = p.melds.reduce((n, m) => n + m.tiles.length, 0);
  const totalW = (tiles.length + (drawn !== null ? 1.4 : 0)) * w + meldTiles * w * 0.72
    + p.melds.length * w * 0.3;
  let x = Math.max(12, (g.W - totalW) / 2);
  const y = g.H - h - 18;
  const selectedIdx = sc.selected === null ? -1 : tiles.indexOf(sc.selected);

  // soft shadow under the hand row
  stage.addChild(new Graphics().roundRect(x - 10, y + h - 6, totalW + 20, 16, 8)
    .fill({ color: COLORS.shadow, alpha: 0.35 }));

  const place = (t: number, i: number | "drawn") => {
    const s = tileSprite(tex, t, w);
    const isSel = i === "drawn" ? sc.selected === t && selectedIdx === -1 : i === selectedIdx;
    s.x = x;
    s.y = isSel ? y - h * 0.28 : y;
    const playable = sc.discardable.has(t);
    if (sc.discardable.size > 0 && !playable) s.tint = 0x9aa0bf;
    stage.addChild(s);
    if (isSel) {
      stage.addChild(new Graphics().roundRect(s.x - 2, s.y - 2, w + 4, h + 4, 8)
        .stroke({ width: 3, color: COLORS.cyan }));
    }
    if (playable) {
      s.eventMode = "static";
      s.cursor = "pointer";
      const restY = s.y;
      s.on("pointerover", () => {
        if (!isSel) s.y = restY - 6;
      });
      s.on("pointerout", () => {
        s.y = restY;
      });
      s.on("pointertap", () => {
        if (!isSel) sfx.select();
        sc.onTile(t);
      });
    }
    if (i === "drawn" && justDrew) tweenIn(app, mem, s, { dx: w * 1.2, dy: -h * 0.3 }, 200);
    x += w;
  };
  tiles.forEach((t, i) => place(t, i));
  if (drawn !== null) {
    x += w * 0.4;
    place(drawn, "drawn");
  }
  x += w * 0.5;
  drawMelds(stage, tex, p.melds, x, y + h * 0.28, w * 0.72, sc.selected);
}

/** A fixed view to render instead of the live game store (replays). */
export interface StaticTable {
  view: GameView;
  names: string[];
}

export function TableCanvas({ fixed }: { fixed?: StaticTable } = {}) {
  const host = useRef<HTMLDivElement>(null);
  const fixedRef = useRef<StaticTable | undefined>(fixed);
  fixedRef.current = fixed;
  const appRef = useRef<Application | null>(null);
  const texRef = useRef<Textures | null>(null);
  const fontRef = useRef<string>("serif");
  const view = useGame((s) => s.view);
  const selected = useGame((s) => s.selected);
  const legal = useGame((s) => s.legal);
  const locale = useLocale((s) => s.locale);
  const back = useAccount((s) => s.profile?.equipped.tile_back);

  useEffect(() => {
    let disposed = false;
    const app = new Application();
    (async () => {
      const font = await ensureTileFont();
      fontRef.current = font;
      await app.init({
        resizeTo: host.current!,
        backgroundAlpha: 0,
        antialias: true,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
      });
      if (disposed) {
        app.destroy(true);
        return;
      }
      host.current!.appendChild(app.canvas);
      texRef.current = buildTextures(font);
      appRef.current = app;
      app.renderer.on("resize", () => redraw());
      redraw();
    })();
    return () => {
      disposed = true;
      if (appRef.current) {
        poolFor(appRef.current).destroy();
        appRef.current.destroy(true, { children: true });
        appRef.current = null;
      }
    };
  }, []);

  const redraw = () => {
    const app = appRef.current;
    let tex = texRef.current;
    if (app && tex && tex.back !== tileBack()) {
      tex = texRef.current = buildTextures(fontRef.current); // a new tile back was equipped
    }
    const st = useGame.getState();
    const f = fixedRef.current;
    if (app && tex && f) {
      render(app, tex, { view: f.view, selected: null, discardable: new Set(), onTile: () => undefined });
      return;
    }
    if (!app || !tex || !st.view) return;
    const discardable = new Set<number>(
      st.legal.filter((a) => a.action_type === "DISCARD" || a.action_type === "TING")
        .map((a) => a.tile as number),
    );
    render(app, tex, {
      view: st.view,
      selected: st.selected,
      discardable,
      onTile: (tile) => {
        const cur = useGame.getState();
        if (cur.selected === tile) {
          const ting = cur.legal.find((a) => a.action_type === "TING" && a.tile === tile);
          const plain = cur.legal.find((a) => a.action_type === "DISCARD" && a.tile === tile);
          // a second tap discards; declaring ready is an explicit button
          if (plain) cur.act(plain);
          else if (ting) cur.act(ting);
        } else {
          cur.select(tile);
        }
      },
    });
  };

  useEffect(() => {
    redraw();
  }, [view, selected, legal, fixed, locale, back]);

  return <div ref={host} className="absolute inset-0" aria-label="牌桌" role="img" />;
}
