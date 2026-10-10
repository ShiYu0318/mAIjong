/** Wire types mirroring backend/ws/view.py and backend/ws/hub.py. */

export type ActionType =
  | "DISCARD" | "KONG" | "PON" | "CHI_LOW" | "CHI_MID" | "CHI_HIGH" | "HU" | "PASS" | "TING";

export interface Action {
  action_type: ActionType;
  tile: number | null;
}

export interface MeldView {
  type: "CHI" | "PON" | "MING_KONG" | "ADD_KONG" | "AN_KONG";
  tiles: (number | null)[];
  called: number | null;
  from_player: number | null;
}

export interface PlayerView {
  seat: number;
  seat_wind: number;
  hand: number[] | null;
  hand_count: number;
  melds: MeldView[];
  flowers: number[];
  discards: number[];
  score: number;
  declared_ting: boolean;
}

export interface TaiItem {
  id: string;
  name: string;
  tai: number;
}

export interface HandResult {
  kind: "HU" | "DRAW";
  winner?: number;
  loser?: number | null;
  self_draw?: boolean;
  win_tile?: number | null;
  hand?: number[];
  flower_win?: string | null;
  tai_breakdown?: TaiItem[];
  dealer_tai?: number;
  tai_by_payer?: Record<string, number>;
  payments: number[];
  reason?: string;
}

export interface GameView {
  game_id: string;
  phase: "DISCARD" | "RESPONSE" | "ROB_KONG" | "ENDED";
  turn: number;
  dealer: number;
  dealer_streak: number;
  round_wind: number;
  drawable: number;
  last_discard: [number, number] | null;
  last_draw: number | null;
  acting: number[];
  players: PlayerView[];
  you: number | null;
  result: HandResult | null;
}

export interface SeatInfo {
  seat: number;
  name: string;
  is_bot: boolean;
  bot_level: number | null;
  connected: boolean;
  taken_over: boolean;
  user_id: string | null;
}

export interface RoomInfo {
  room_id: string;
  code: string;
  type: string;
  status: "WAITING" | "IN_GAME" | "ROUND_END" | "GAME_END";
  host_id: string | null;
  seats: (SeatInfo | null)[];
  config: {
    time_limit: number | null;
    rounds: number;
    base_points: number;
    tai_points: number;
    tai_cap: number | null;
    bot_levels: (number | null)[];
  };
  match: {
    dealer: number;
    dealer_streak: number;
    round_wind: number;
    hands_played: number;
    scores: number[];
    finished: boolean;
  } | null;
}

export interface ServerMessage {
  type: string;
  payload: Record<string, unknown>;
}

export interface WinPayload extends HandResult {
  winner: number;
  melds: MeldView[];
  flowers: number[];
}
