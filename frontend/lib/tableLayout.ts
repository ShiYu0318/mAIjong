/** Table geometry shared by the Pixi canvas and the DOM overlays (seat panels, compass). */
import { TILE_H, TILE_W } from "./tilePainter";

export interface TableLayout {
  W: number;
  H: number;
  /** side of the square playing area */
  L: number;
  cx: number;
  cy: number;
  handW: number;
  handH: number;
  /** discard (river) tile size */
  sd: number;
  sdH: number;
  /** Narrow or short screen: compact player panels. */
  compact: boolean;
  /** 2 on portrait phones: one row of 17 tiles would leave each about 20 px, too small to tap */
  handRows: 1 | 2;
  /** height of the whole hand area at the bottom (rows, gaps and margin) */
  handBlock: number;
}

export function tableLayout(W: number, H: number): TableLayout {
  const compact = W < 640 || H < 560;
  if (compact && H > W * 1.25) {
    // portrait phone: the hand in two rows of about nine (tiles near fingertip size), the
    // table pushed to the top so the space goes to the hand and the action buttons
    const handW = Math.min(52, (W - 16) / 9.6);
    const handH = (handW * TILE_H) / TILE_W;
    const handBlock = handH * 2 + 6 + 18;
    // ~100 px between table and hand for the action buttons; short phones shrink the table
    const L = Math.max(220, Math.min(W - 24, H - handBlock - 100));
    const sd = Math.max(8, L / 22);
    return { W, H, L, cx: W / 2, cy: 8 + L / 2, handW, handH, sd, sdH: (sd * TILE_H) / TILE_W,
      compact, handRows: 2, handBlock };
  }
  const handW = Math.min(62, Math.max(28, (W - 48) / 21));
  const handH = (handW * TILE_H) / TILE_W;
  const handBlock = handH + 18;
  const top = compact ? 48 : 84;
  const bottom = handBlock + (compact ? 52 : 88);
  const L = Math.max(120, Math.min(W - (compact ? 280 : 400), H - top - bottom));
  const cx = W / 2;
  const cy = top + L / 2;
  const sd = Math.max(8, L / 22);
  return { W, H, L, cx, cy, handW, handH, sd, sdH: (sd * TILE_H) / TILE_W, compact,
    handRows: 1, handBlock };
}

/** Seat position relative to the viewer: 0 bottom (you), 1 right, 2 top, 3 left. */
export const relSeat = (seat: number, me: number) => (seat - me + 4) % 4;

/** Player panels stay outside the wooden rim, centered on each edge. */
export const PANEL_W = 168;

export function seatCorner(rel: number, g: TableLayout): { x: number; y: number } {
  const halfHeight = g.compact ? 16 : 30;
  const halfWidth = g.compact ? 60 : 84;
  const gap = 20;
  return [
    { x: g.cx, y: g.cy + g.L / 2 + gap + halfHeight },
    { x: g.cx + g.L / 2 + gap + halfWidth, y: g.cy },
    { x: g.cx, y: g.cy - g.L / 2 - gap - halfHeight },
    { x: g.cx - g.L / 2 - gap - halfWidth, y: g.cy },
  ][rel];
}

/** Where a seat's call stamp appears (in front of that player's river). */
export function seatStamp(rel: number, g: TableLayout): { x: number; y: number } {
  const d = g.L * 0.22;
  return [
    { x: g.cx, y: g.cy + d },
    { x: g.cx + d, y: g.cy },
    { x: g.cx, y: g.cy - d },
    { x: g.cx - d, y: g.cy },
  ][rel];
}
