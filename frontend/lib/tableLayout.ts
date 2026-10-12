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
}

export function tableLayout(W: number, H: number): TableLayout {
  const handW = Math.min(62, Math.max(28, (W - 48) / 21));
  const handH = (handW * TILE_H) / TILE_W;
  const bottom = handH + 40;
  const L = Math.max(220, Math.min(W - 24, H - bottom - 12));
  const cx = W / 2;
  const cy = 8 + (H - bottom - 8) / 2;
  const sd = Math.max(20, L / 22);
  return { W, H, L, cx, cy, handW, handH, sd, sdH: (sd * TILE_H) / TILE_W };
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
  const d = g.L * 0.4;
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
