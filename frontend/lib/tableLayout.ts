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
  /** phone-sized: mini seat badges in the table corners, hand shrinks to fit */
  compact: boolean;
  /** 2 on portrait phones: one row of 17 tiles would leave each about 20 px, too small to tap */
  handRows: 1 | 2;
  /** height of the whole hand area at the bottom (rows, gaps and margin) */
  handBlock: number;
}

export function tableLayout(W: number, H: number): TableLayout {
  const compact = W < 640;
  if (compact && H > W * 1.25) {
    // portrait phone: the hand in two rows of about nine (tiles near fingertip size), the
    // table pushed to the top so the space goes to the hand and the action buttons
    const handW = Math.min(52, (W - 16) / 9.6);
    const handH = (handW * TILE_H) / TILE_W;
    const handBlock = handH * 2 + 6 + 18;
    // ~100 px between table and hand for the action buttons; short phones shrink the table
    const L = Math.max(220, Math.min(W - 24, H - handBlock - 100));
    const sd = Math.max(20, L / 22);
    return { W, H, L, cx: W / 2, cy: 8 + L / 2, handW, handH, sd, sdH: (sd * TILE_H) / TILE_W,
      compact, handRows: 2, handBlock };
  }
  const handW = Math.min(62, Math.max(28, (W - 48) / 21));
  const handH = (handW * TILE_H) / TILE_W;
  const bottom = handH + 40;
  const L = Math.max(220, Math.min(W - 24, H - bottom - 12));
  const cx = W / 2;
  const cy = 8 + (H - bottom - 8) / 2;
  const sd = Math.max(20, L / 22);
  return { W, H, L, cx, cy, handW, handH, sd, sdH: (sd * TILE_H) / TILE_W, compact,
    handRows: 1, handBlock: handH + 18 };
}

/** Seat position relative to the viewer: 0 bottom (you), 1 right, 2 top, 3 left. */
export const relSeat = (seat: number, me: number) => (seat - me + 4) % 4;

/** Where each seat's panel sits. With room beside the table the panels go outside it
 * (you bottom-left, left player centre-left, top player top-left, right player
 * centre-right) so they never cover tiles and the bottom-right stays free for actions;
 * on narrow screens they fall back to the inner corners. */
export const PANEL_W = 168;

export function seatCorner(rel: number, g: TableLayout): { x: number; y: number } {
  const side = (g.W - g.L) / 2;
  if (side >= PANEL_W + 28) {
    const left = g.cx - g.L / 2 - 14 - PANEL_W / 2 - 10;
    const right = g.cx + g.L / 2 + 14 + PANEL_W / 2 + 10;
    return [
      { x: left, y: g.cy + g.L / 2 - 36 },
      { x: right, y: g.cy },
      { x: left, y: g.cy - g.L / 2 + 36 },
      { x: left, y: g.cy },
    ][rel];
  }
  const d = g.compact ? g.L / 2 - 28 : g.L * 0.4;
  return [
    { x: g.cx + d, y: g.cy + d },
    { x: g.cx + d, y: g.cy - d },
    { x: g.cx - d, y: g.cy - d },
    { x: g.cx - d, y: g.cy + d },
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
