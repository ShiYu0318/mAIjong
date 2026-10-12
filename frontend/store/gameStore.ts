import { create } from "zustand";
import type { Action, GameView, RoomInfo, ServerMessage, WinPayload } from "@/lib/protocol";
import { translate } from "@/lib/i18n";
import { sfx } from "@/lib/sfx";
import { type ProgressEvent, useAccount } from "@/store/accountStore";
import { tileName } from "@/lib/tiles";

export interface ChatLine {
  seat: number;
  message: string;
  at: number;
}

export interface HintCandidate {
  tile: number;
  name: string;
  shanten_after: number;
  uke_ire: number[];
  uke_count: number;
  danger: number;
  can_declare: boolean;
  waits: number[];
  best_tai: number | null;
}

export interface Hint {
  candidates: HintCandidate[];
  explanation: string;
  remaining: number | null;
}

export interface CoachNoteData {
  seat: number;
  tile: number;
  text: string;
  candidates: HintCandidate[];
}

/** A call / event shown as a stamp on the table (chi, pon, kong, ready, flower, win). */
export interface TableEffect {
  id: number;
  kind: string;
  seat: number;
  tile: number | null;
}

/** For each discard that leaves the hand ready: [wait tile, copies not yet seen]. */
export type Waits = Record<string, [number, number][]>;

export interface GameEnd {
  final_scores: number[];
  ranks: number[];
}

type Status = "idle" | "connecting" | "open" | "reconnecting" | "closed";

interface GameState {
  status: Status;
  room: RoomInfo | null;
  seat: number | null;
  view: GameView | null;
  legal: Action[];
  deadline: number | null;
  waits: Waits;
  effects: TableEffect[];
  selected: number | null;
  log: string[];
  chat: ChatLine[];
  win: WinPayload | null;
  drawn: boolean;
  /** ROUND_DRAW details: who was ready and who had declared */
  drawInfo: { tenpai: boolean[]; declared: boolean[] } | null;
  /** epoch ms when the next hand starts (NEXT_HAND_IN), for the result countdown */
  nextHandAt: number | null;
  gameEnd: GameEnd | null;
  hint: Hint | null;
  coach: CoachNoteData | null;
  error: string | null;
  sender: ((msg: object) => void) | null;
  setStatus: (s: Status) => void;
  setSender: (fn: ((msg: object) => void) | null) => void;
  handle: (msg: ServerMessage) => void;
  act: (a: Action) => void;
  select: (tile: number | null) => void;
  sendChat: (text: string) => void;
  requestHint: () => void;
  closeHint: () => void;
  dismissResult: () => void;
  reset: () => void;
}

const SEATS = ["甲", "乙", "丙", "丁"];

function eventLine(ev: Record<string, unknown>, names: string[]): string | null {
  const p = ev.player as number | null;
  const who = p === null || p === undefined ? "" : names[p] ?? SEATS[p];
  const t = ev.tile as number | null;
  const tile = t === null || t === undefined ? "" : tileName(t);
  switch (ev.type) {
    case "DISCARD": return translate("{who} 打出 {tile}", { who, tile });
    case "TING": return translate("{who} 打出 {tile} 並宣告聽牌", { who, tile });
    case "PON": return translate("{who} 碰 {tile}", { who, tile });
    case "CHI": return translate("{who} 吃 {tile}", { who, tile });
    case "KONG": return ev.kind === "AN_KONG" ? translate("{who} 暗槓", { who }) : translate("{who} 槓 {tile}", { who, tile });
    case "FLOWER": return translate("{who} 補花 {tile}", { who, tile });
    case "FLOWER_ROB": return translate("{who} 搶花 {tile}", { who, tile });
    default: return null;
  }
}

let effectSeq = 0;
const STAMPED = new Set(["PON", "CHI", "KONG", "TING", "FLOWER", "FLOWER_ROB"]);

/** Sounds for every event; stamps for calls (removed again after the animation). */
function effectFor(ev: Record<string, unknown>, get: () => GameState,
  set: (s: Partial<GameState>) => void) {
  const kind = String(ev.type);
  const seat = ev.player as number | null;
  if (kind === "DISCARD") sfx.discard();
  else if (kind === "DRAW" && seat === get().seat) sfx.draw();
  else if (kind === "TING") { sfx.discard(); sfx.ting(); }
  else if (kind === "PON" || kind === "CHI" || kind === "KONG") sfx.call();
  if (seat === null || seat === undefined || !STAMPED.has(kind)) return;
  const id = ++effectSeq;
  set({ effects: [...get().effects.slice(-4), { id, kind, seat, tile: (ev.tile as number | null) ?? null }] });
  setTimeout(() => set({ effects: get().effects.filter((e) => e.id !== id) }), 1400);
}

const initial = {
  status: "idle" as Status,
  room: null,
  seat: null,
  view: null,
  legal: [],
  deadline: null,
  waits: {},
  effects: [],
  selected: null,
  log: [],
  chat: [],
  win: null,
  drawn: false,
  drawInfo: null,
  nextHandAt: null,
  gameEnd: null,
  hint: null,
  coach: null,
  error: null,
  sender: null,
};

export const useGame = create<GameState>((set, get) => ({
  ...initial,
  setStatus: (status) => set({ status }),
  setSender: (sender) => set({ sender }),
  reset: () => set({ ...initial }),
  select: (selected) => set({ selected }),
  dismissResult: () => set({ win: null, drawn: false, drawInfo: null }),
  act: (a) => {
    get().sender?.({ type: "ACTION", payload: a });
    set({ legal: [], deadline: null, waits: {}, selected: null, hint: null });
  },
  requestHint: () => {
    set({ error: null });
    get().sender?.({ type: "HINT_REQUEST" });
  },
  closeHint: () => set({ hint: null }),
  sendChat: (message) => {
    const text = message.trim();
    if (text) get().sender?.({ type: "CHAT", payload: { message: text } });
  },
  handle: (msg) => {
    const p = msg.payload ?? {};
    const names = (get().room?.seats ?? []).map((s, i) => s?.name ?? SEATS[i]);
    switch (msg.type) {
      case "JOINED":
        set({ seat: p.seat as number, room: p.room as RoomInfo, error: null });
        break;
      case "ROOM_STATE":
        set({ room: p as unknown as RoomInfo });
        break;
      case "GAME_START":
      case "NEXT_ROUND": {
        const room = get().room;
        useAccount.getState().resetHandRewards();
        set({
          win: null, drawn: false, drawInfo: null, nextHandAt: null, log: [], gameEnd: null,
          room: room ? { ...room, status: "IN_GAME" } : room,
        });
        break;
      }
      case "DEAL":
        set({ selected: null });
        break;
      case "STATE_UPDATE": {
        const view = p as unknown as GameView;
        const room = get().room;
        if (room && room.status === "WAITING") set({ room: { ...room, status: "IN_GAME" } });
        const mine = get().seat;
        const stillActing = mine !== null && view.acting.includes(mine);
        set({ view, ...(stillActing ? {} : { legal: [], deadline: null }) });
        break;
      }
      case "ACTION_REQUEST":
        if (p.player === get().seat) {
          set({ legal: p.legal_actions as Action[], deadline: (p.deadline as number | null) ?? null,
            waits: (p.waits as Waits | undefined) ?? {} });
        }
        break;
      case "PLAYER_ACTION": {
        const ev = p.event as Record<string, unknown>;
        const line = eventLine(ev, names);
        if (line) set({ log: [...get().log.slice(-60), line] });
        effectFor(ev, get, set);
        break;
      }
      case "WIN_DECLARED":
        set({ win: p as unknown as WinPayload, legal: [], deadline: null, waits: {} });
        break;
      case "ROUND_DRAW":
        set({ drawn: true, legal: [], deadline: null,
          drawInfo: Array.isArray(p.tenpai)
            ? { tenpai: p.tenpai as boolean[], declared: (p.declared as boolean[] | undefined) ?? [] } : null });
        break;
      case "NEXT_HAND_IN":
        set({ nextHandAt: Date.now() + Number(p.seconds ?? 0) * 1000 });
        break;
      case "GAME_END":
        set({ gameEnd: p as unknown as GameEnd });
        break;
      case "CHAT":
        set({ chat: [...get().chat.slice(-100), { seat: p.seat as number, message: p.message as string, at: Date.now() }] });
        break;
      case "SEAT_BOT_FILL":
      case "PLAYER_DISCONNECTED":
      case "PLAYER_RECONNECTED":
        get().sender?.({ type: "READY" });
        break;
      case "TUTOR_NOTE":
        set({ coach: p as unknown as CoachNoteData });
        break;
      case "PROGRESS":
        useAccount.getState().applyProgress((p.events ?? []) as ProgressEvent[]);
        break;
      case "HINT_RESULT":
        set({ hint: p as unknown as Hint });
        break;
      case "ERROR":
        set({ error: `${p.message ?? p.code}` });
        setTimeout(() => {
          if (get().error === `${p.message ?? p.code}`) set({ error: null });
        }, 4000);
        break;
    }
  },
}));
