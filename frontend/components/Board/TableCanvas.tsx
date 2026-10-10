"use client";

import { Application, Container, Graphics, Sprite, Text, Texture } from "pixi.js";
import { useEffect, useRef } from "react";
import type { GameView, MeldView, PlayerView } from "@/lib/protocol";
import { TILE_H, TILE_W, ensureTileFont, tileCanvas } from "@/lib/tilePainter";
import { WINDS } from "@/lib/tiles";
import { useGame } from "@/store/gameStore";

const COLORS = {
  felt: 0x12302b,
  feltDeep: 0x0c221e,
  line: 0x24493f,
  ivory: 0xf4efe1,
  mist: 0xa9bdb4,
  zhong: 0xb3192c,
  jade: 0x1f6f57,
};

type Textures = Map<number | "back", Texture>;

function buildTextures(font: string): Textures {
  const map: Textures = new Map();
  for (let id = 0; id < 42; id++) map.set(id, Texture.from(tileCanvas(id, font, 3)));
  map.set("back", Texture.from(tileCanvas(null, font, 3)));
  return map;
}

function tileSprite(tex: Textures, id: number | null, w: number): Sprite {
  const s = new Sprite(tex.get(id === null ? "back" : id)!);
  s.width = w;
  s.height = (w * TILE_H) / TILE_W;
  return s;
}

/** Draws melds left→right starting at x; returns the x after the last meld.
 * Concealed kongs show their two outer tiles face down (all four for opponents). */
function drawMelds(c: Container, tex: Textures, melds: MeldView[], x: number, y: number,
  w: number): number {
  for (const m of melds) {
    m.tiles.forEach((t, i) => {
      const faceDown = t === null || (m.type === "AN_KONG" && (i === 0 || i === 3));
      const s = tileSprite(tex, faceDown ? null : t, w);
      s.x = x;
      s.y = y;
      c.addChild(s);
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
  names: string[];
}

function render(app: Application, tex: Textures, sc: Scene) {
  const stage = app.stage;
  stage.removeChildren().forEach((ch) => ch.destroy({ children: true }));
  const W = app.screen.width;
  const H = app.screen.height;
  const me = sc.view.you ?? 0;
  const handW = Math.min(52, (W - 40) / 23);
  const handH = (handW * TILE_H) / TILE_W;
  const tableH = H - handH - 40;
  const L = Math.min(W, tableH);
  const cx = W / 2;
  const cy = tableH / 2 + 10;
  const sd = Math.max(20, L / 24); // discard tile width
  const sdH = (sd * TILE_H) / TILE_W;

  // table outline
  const table = new Graphics()
    .roundRect(cx - L / 2, cy - L / 2, L, L, 18)
    .fill({ color: COLORS.feltDeep })
    .stroke({ width: 1, color: COLORS.line });
  stage.addChild(table);

  const players = sc.view.players;
  const last = sc.view.last_discard;
  drawCenter(stage, sc.view, cx, cy, L);

  for (const p of players) {
    const rel = (p.seat - me + 4) % 4;
    const area = new Container();
    area.x = cx;
    area.y = cy;
    area.rotation = (-rel * Math.PI) / 2;
    stage.addChild(area);
    drawRiver(area, tex, p, sd, sdH, L, last && last[0] === p.seat ? true : false);
    if (rel !== 0) drawOpponent(area, tex, p, sd * 0.95, L);
    drawSeatLabel(area, p, sc, L, rel);
  }

  drawMyHand(stage, tex, players[me], sc, W, H, handW, handH);
}

function drawRiver(area: Container, tex: Textures, p: PlayerView, w: number, h: number,
  L: number, lastIsMine: boolean) {
  const perRow = 6;
  const startX = -((perRow * w) / 2);
  const startY = L * 0.15;
  p.discards.forEach((t, i) => {
    const s = tileSprite(tex, t, w);
    s.x = startX + (i % perRow) * w;
    s.y = startY + Math.floor(i / perRow) * (h - 2);
    area.addChild(s);
    if (lastIsMine && i === p.discards.length - 1) {
      const mark = new Graphics().roundRect(s.x - 1, s.y - 1, w + 2, h + 2, 4)
        .stroke({ width: 2, color: COLORS.zhong });
      area.addChild(mark);
    }
  });
}

function drawOpponent(area: Container, tex: Textures, p: PlayerView, w: number, L: number) {
  const h = (w * TILE_H) / TILE_W;
  const y = L / 2 - h - 10;
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
  drawMelds(area, tex, p.melds, x, y, w);
  // flowers on the left of the hand
  p.flowers.forEach((f, i) => {
    const s = tileSprite(tex, f, w * 0.7);
    s.x = -L / 2 + 14 + i * (w * 0.7 - 1);
    s.y = y - h * 0.8;
    area.addChild(s);
  });
}

function drawSeatLabel(area: Container, p: PlayerView, sc: Scene, L: number, rel: number) {
  const acting = sc.view.acting.includes(p.seat);
  const dealer = sc.view.dealer === p.seat;
  const name = sc.names[p.seat] ?? "";
  const tags = [dealer ? "莊" : "", p.declared_ting ? "聽" : ""].filter(Boolean).join("・");
  const t = new Text({
    text: `${acting ? "▶ " : ""}${WINDS[p.seat_wind]}　${name}\n${p.score}${tags ? "　" + tags : ""}`,
    style: {
      fontFamily: "PingFang TC, Noto Sans TC, sans-serif",
      fontSize: 13,
      fill: acting ? COLORS.ivory : COLORS.mist,
      fontWeight: acting ? "700" : "400",
      align: "center",
      lineHeight: 18,
    },
  });
  // each seat's label sits in the corner to its right, always upright
  t.anchor.set(0.5);
  t.x = L * 0.3;
  t.y = L * 0.3;
  t.rotation = (rel * Math.PI) / 2;
  area.addChild(t);
}

function drawCenter(stage: Container, view: GameView, cx: number, cy: number, L: number) {
  const size = L * 0.15;
  const g = new Graphics().roundRect(cx - size / 2, cy - size / 2, size, size, 10)
    .fill({ color: COLORS.felt }).stroke({ width: 1, color: COLORS.line });
  stage.addChild(g);
  const wind = new Text({
    text: `${WINDS[view.round_wind]}風圈`,
    style: { fontFamily: "var(--font-wenkai), Kaiti TC, serif", fontSize: Math.max(16, size * 0.2), fill: COLORS.ivory },
  });
  wind.anchor.set(0.5);
  wind.x = cx;
  wind.y = cy - size * 0.18;
  const info = new Text({
    text: `剩 ${view.drawable} 張\n連莊 ${view.dealer_streak}`,
    style: { fontFamily: "PingFang TC, sans-serif", fontSize: Math.max(11, size * 0.1), fill: COLORS.mist, align: "center" },
  });
  info.anchor.set(0.5);
  info.x = cx;
  info.y = cy + size * 0.2;
  stage.addChild(wind, info);
}

function drawMyHand(stage: Container, tex: Textures, p: PlayerView, sc: Scene, W: number,
  H: number, w: number, h: number) {
  const hand = p.hand ?? [];
  const lastDraw = sc.view.last_draw;
  // keep the freshly drawn tile apart on the right
  let tiles = hand;
  let drawn: number | null = null;
  if (lastDraw !== null && sc.view.turn === p.seat && sc.view.phase === "DISCARD") {
    const idx = hand.lastIndexOf(lastDraw);
    if (idx >= 0) {
      tiles = [...hand.slice(0, idx), ...hand.slice(idx + 1)];
      drawn = lastDraw;
    }
  }
  const meldTiles = p.melds.reduce((n, m) => n + m.tiles.length, 0);
  const totalW = (tiles.length + (drawn !== null ? 1.4 : 0)) * w + meldTiles * w * 0.75 + p.melds.length * w * 0.3;
  let x = Math.max(12, (W - totalW) / 2);
  const y = H - h - 14;
  const selectedIdx = sc.selected === null ? -1 : tiles.indexOf(sc.selected);

  const place = (t: number, i: number | "drawn") => {
    const s = tileSprite(tex, t, w);
    const isSel = i === "drawn" ? sc.selected === t && selectedIdx === -1 : i === selectedIdx;
    s.x = x;
    s.y = isSel ? y - 14 : y;
    const playable = sc.discardable.has(t);
    s.alpha = sc.discardable.size === 0 || playable ? 1 : 0.55;
    if (playable) {
      s.eventMode = "static";
      s.cursor = "pointer";
      s.on("pointertap", () => sc.onTile(t));
    }
    stage.addChild(s);
    x += w;
  };
  tiles.forEach((t, i) => place(t, i));
  if (drawn !== null) {
    x += w * 0.4;
    place(drawn, "drawn");
  }
  x += w * 0.5;
  drawMelds(stage, tex, p.melds, x, y + h * 0.25, w * 0.75);
  // flowers above the hand, left aligned
  p.flowers.forEach((f, i) => {
    const s = tileSprite(tex, f, w * 0.6);
    s.x = 14 + i * (w * 0.6);
    s.y = y - h * 0.75;
    stage.addChild(s);
  });
}

export function TableCanvas() {
  const host = useRef<HTMLDivElement>(null);
  const appRef = useRef<Application | null>(null);
  const texRef = useRef<Textures | null>(null);
  const view = useGame((s) => s.view);
  const selected = useGame((s) => s.selected);
  const legal = useGame((s) => s.legal);
  const room = useGame((s) => s.room);

  useEffect(() => {
    let disposed = false;
    const app = new Application();
    (async () => {
      const font = await ensureTileFont();
      await app.init({
        resizeTo: host.current!,
        background: COLORS.felt,
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
        appRef.current.destroy(true, { children: true });
        appRef.current = null;
      }
    };
  }, []);

  const redraw = () => {
    const app = appRef.current;
    const tex = texRef.current;
    const st = useGame.getState();
    if (!app || !tex || !st.view) return;
    const discardable = new Set<number>(
      st.legal.filter((a) => a.action_type === "DISCARD" || a.action_type === "TING")
        .map((a) => a.tile as number),
    );
    render(app, tex, {
      view: st.view,
      selected: st.selected,
      discardable,
      names: (st.room?.seats ?? []).map((s, i) => s?.name ?? `玩家${i + 1}`),
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
  }, [view, selected, legal, room]);

  return <div ref={host} className="absolute inset-0" aria-label="牌桌" role="img" />;
}
