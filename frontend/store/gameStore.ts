import { create } from "zustand";
import type { Action, GameView, RoomInfo, ServerMessage, WinPayload } from "@/lib/protocol";
import { tileName } from "@/lib/tiles";

export interface ChatLine {
  seat: number;
  message: string;
  at: number;
}

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
  selected: number | null;
  log: string[];
  chat: ChatLine[];
  win: WinPayload | null;
  drawn: boolean;
  gameEnd: GameEnd | null;
  error: string | null;
  sender: ((msg: object) => void) | null;
  setStatus: (s: Status) => void;
  setSender: (fn: ((msg: object) => void) | null) => void;
  handle: (msg: ServerMessage) => void;
  act: (a: Action) => void;
  select: (tile: number | null) => void;
  sendChat: (text: string) => void;
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
    case "DISCARD": return `${who} 打出 ${tile}`;
    case "TING": return `${who} 打出 ${tile} 並宣告聽牌`;
    case "PON": return `${who} 碰 ${tile}`;
    case "CHI": return `${who} 吃 ${tile}`;
    case "KONG": return ev.kind === "AN_KONG" ? `${who} 暗槓` : `${who} 槓 ${tile}`;
    case "FLOWER": return `${who} 補花 ${tile}`;
    case "FLOWER_ROB": return `${who} 搶花 ${tile}`;
    default: return null;
  }
}

const initial = {
  status: "idle" as Status,
  room: null,
  seat: null,
  view: null,
  legal: [],
  deadline: null,
  selected: null,
  log: [],
  chat: [],
  win: null,
  drawn: false,
  gameEnd: null,
  error: null,
  sender: null,
};

export const useGame = create<GameState>((set, get) => ({
  ...initial,
  setStatus: (status) => set({ status }),
  setSender: (sender) => set({ sender }),
  reset: () => set({ ...initial }),
  select: (selected) => set({ selected }),
  dismissResult: () => set({ win: null, drawn: false }),
  act: (a) => {
    get().sender?.({ type: "ACTION", payload: a });
    set({ legal: [], deadline: null, selected: null });
  },
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
        set({
          win: null, drawn: false, log: [], gameEnd: null,
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
          set({ legal: p.legal_actions as Action[], deadline: (p.deadline as number | null) ?? null });
        }
        break;
      case "PLAYER_ACTION": {
        const line = eventLine(p.event as Record<string, unknown>, names);
        if (line) set({ log: [...get().log.slice(-60), line] });
        break;
      }
      case "WIN_DECLARED":
        set({ win: p as unknown as WinPayload, legal: [], deadline: null });
        break;
      case "ROUND_DRAW":
        set({ drawn: true, legal: [], deadline: null });
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
      case "ERROR":
        set({ error: `${p.message ?? p.code}` });
        break;
    }
  },
}));
