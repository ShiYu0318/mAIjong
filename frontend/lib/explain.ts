/**
 * English wording of the server's discard explanations (backend/hints/llm_provider.py),
 * built from the same candidate rows so the reasoning matches the Chinese text.
 */
import { tileNameEn } from "./tiles";

export interface Candidate {
  tile: number;
  shanten_after: number;
  uke_ire: number[];
  uke_count: number;
  waits?: number[];
  best_tai?: number | null;
  danger?: number;
}

function state(sh: number): string {
  if (sh < 0) return "a winning hand";
  if (sh === 0) return "ready";
  return `${sh} away from ready`;
}

function list(ids: number[], limit = 8): string {
  const names = ids.slice(0, limit).map(tileNameEn);
  return names.join(", ") + (ids.length > limit ? " and more" : "");
}

export function explainEn(cands: Candidate[], chosen?: Candidate | null): string {
  const best = cands[0];
  if (!best) return "";
  const parts = [`Discard ${tileNameEn(best.tile)}: afterwards you are ${state(best.shanten_after)}`];
  if (best.shanten_after === 0) {
    parts.push(`waiting on ${list(best.waits ?? [])} with ${best.uke_count} tiles left to win on`);
    if (best.best_tai != null) parts.push(`worth up to about ${best.best_tai} tai (before dealer tai)`);
  } else {
    parts.push(`${best.uke_ire.length} kinds of useful draws, ${best.uke_count} tiles (${list(best.uke_ire)})`);
  }
  if ((best.danger ?? 0) >= 0.5) parts.push("though this tile could deal in");
  let text = parts.join(", ") + ".";
  if (chosen && chosen.tile !== best.tile) {
    const name = tileNameEn(chosen.tile);
    if (chosen.shanten_after > best.shanten_after) {
      text += ` Your ${name} sets the hand back to ${state(chosen.shanten_after)}.`;
    } else if (chosen.uke_count < best.uke_count) {
      text += ` Your ${name} also leaves you ${state(chosen.shanten_after)}, but with only ${chosen.uke_count} useful tiles.`;
    } else if ((chosen.danger ?? 0) > (best.danger ?? 0) + 0.2) {
      text += ` Your ${name} draws as well but is more dangerous.`;
    } else {
      text += ` Your ${name} is close to the best choice too.`;
    }
  }
  return text;
}

/** The guided-game coach note for a discard by `who` (the player or a bot). */
export function coachNoteEn(cands: Candidate[], chosen: Candidate, who: string, human: boolean): string {
  if (human) {
    return cands[0]?.tile === chosen.tile ? `Good discard! ${explainEn(cands)}` : explainEn(cands, chosen);
  }
  const detail = chosen.shanten_after === 0
    ? `waiting on ${list(chosen.waits ?? [])}` : `${chosen.uke_count} useful tiles`;
  return `${who} discarded ${tileNameEn(chosen.tile)}: now ${state(chosen.shanten_after)}, ${detail}.`;
}
