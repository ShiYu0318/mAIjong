import type { RoomInfo } from "./protocol";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? API_URL.replace(/^http/, "ws");

const TOKEN_KEY = "maijong.token";

export function authToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: stay logged out */
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  const token = authToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init.json !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers,
    body: init.json !== undefined ? JSON.stringify(init.json) : init.body,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export interface JoinResult {
  seat: number;
  ws_token: string;
  room: RoomInfo;
}

export interface RoomConfigInput {
  time_limit: number | null;
  rounds: number;
  base_points: number;
  tai_points: number;
  bot_levels: (number | null)[];
  tutor: boolean;
}

export const rooms = {
  create: (type: string, config: Partial<RoomConfigInput>) =>
    api<{ room_id: string; code: string; room: RoomInfo }>("/rooms", { method: "POST", json: { type, config } }),
  get: (code: string) => api<RoomInfo>(`/rooms/${encodeURIComponent(code)}`),
  join: (roomId: string, name?: string, seat?: number) =>
    api<JoinResult>(`/rooms/${roomId}/join`, { method: "POST", json: { name, seat } }),
  start: (roomId: string) => api<RoomInfo>(`/rooms/${roomId}/start`, { method: "POST" }),
  quick: (name?: string) => api<JoinResult>("/rooms/quick/join", { method: "POST", json: { name } }),
};

/** Seat tickets are kept per room so a refresh reconnects to the same seat. */
export function saveTicket(roomId: string, j: JoinResult) {
  try {
    localStorage.setItem(`maijong.ticket.${roomId}`, JSON.stringify({ seat: j.seat, token: j.ws_token }));
  } catch {
    /* ignore */
  }
}

export function loadTicket(roomId: string): { seat: number; token: string } | null {
  try {
    const raw = localStorage.getItem(`maijong.ticket.${roomId}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export interface MeldInput {
  type: "CHI" | "PON" | "AN_KONG";
  tiles: number[];
}

export interface DiscardRow {
  tile: number;
  name: string;
  shanten_after: number;
  uke_ire: number[];
  uke_count: number;
  waits?: number[];
  best_tai?: number | null;
  danger?: number;
}

export interface Analysis {
  tiles: number;
  melds: number;
  shanten: number;
  discards?: DiscardRow[];
  uke_ire?: number[];
  uke_count?: number;
  waits?: { tile: number; name: string; tai: number | null }[];
}

export interface QuizPosition {
  seat: number;
  hand: number[];
  last_draw: number | null;
  melds: { type: string; tiles: number[] }[];
  flowers: number[];
  discards: number[][];
  declared: boolean[];
  seat_wind: number;
  round_wind: number;
  drawable: number;
}

export interface QuizAnswer {
  verdict: "best" | "good" | "worse";
  rank: number;
  best: DiscardRow;
  chosen: DiscardRow;
  candidates: DiscardRow[];
  explanation: string;
}

export const tutor = {
  analyze: (hand: number[], melds: MeldInput[], flowers: number[] = []) =>
    api<Analysis>("/tutor/analyze", { method: "POST", json: { hand, melds, flowers } }),
  quiz: (difficulty: number) =>
    api<{ quiz_token: string; position: QuizPosition }>(`/tutor/quiz?difficulty=${difficulty}`),
  answer: (quiz_token: string, tile: number) =>
    api<QuizAnswer>("/tutor/quiz/answer", { method: "POST", json: { quiz_token, tile } }),
  setProgress: (lessonId: string, status: "STARTED" | "COMPLETED", quiz_score?: number) =>
    api(`/tutor/progress/${lessonId}`, { method: "PUT", json: { status, quiz_score } }),
};

/** Start a guided game against beginner AI with coach notes, returning the room id. */
export async function startGuidedGame(name?: string): Promise<string> {
  const r = await rooms.create("PRIVATE", {
    bot_levels: [null, 1, 1, 1], time_limit: null, rounds: 1, tutor: true,
  });
  const j = await rooms.join(r.room_id, name, 0);
  saveTicket(r.room_id, j);
  await rooms.start(r.room_id);
  return r.room_id;
}

export interface ReplayFrame {
  index: number;
  actor: number | null;
  action: { action_type: string; tile: number | null } | null;
  events: Record<string, unknown>[];
  view: import("./protocol").GameView;
  decision: { agent: string; timeout: boolean; scores: Record<string, number>; chosen: number } | null;
}

export interface GameSummary {
  id: string;
  room_id: string | null;
  round_wind: number;
  hand_index: number;
  dealer_streak: number;
  seats: ({ seat: number; name: string; is_bot: boolean; user_id: string | null } | null)[];
  result: import("./protocol").HandResult;
  is_public: boolean;
  created_at: string;
}

export interface Annotation {
  id: number;
  seq: number;
  note: string;
  user: string;
}

export const games = {
  frames: (id: string) => api<{ meta: Record<string, unknown>; frames: ReplayFrame[]; game: GameSummary }>(`/games/${id}/frames`),
  replayUrl: (id: string) => api<{ url: string }>(`/games/${id}/replay`),
  annotations: (id: string) => api<Annotation[]>(`/games/${id}/annotations`),
  annotate: (id: string, seq: number, note: string) =>
    api<Annotation>(`/games/${id}/annotations`, { method: "POST", json: { seq, note } }),
  mine: (userId: string) => api<GameSummary[]>(`/users/${userId}/games`),
};

export interface AgentStats {
  agent: string;
  win_rate: number;
  self_draw_rate: number;
  deal_in_rate: number;
  avg_score: number;
  avg_tai_on_win: number;
  win_share?: number;
  p_value?: number;
}

export interface LabJob {
  id: string;
  kind: string;
  status: "QUEUED" | "RUNNING" | "DONE" | "FAILED" | "STOPPED";
  config: Record<string, unknown>;
  metrics: {
    progress?: number;
    done?: number;
    error?: string;
    summary?: { hands: number; draw_rate: number; seats: (AgentStats & { hands: number })[] };
    agents?: AgentStats[];
  };
  created_at: string;
  finished_at: string | null;
}

export type MetricPoint = { step: number; time: number } & Record<string, number>;

export const lab = {
  agents: () => api<string[]>("/lab/agents"),
  jobs: () => api<LabJob[]>("/lab/jobs"),
  job: (id: string) => api<LabJob>(`/lab/jobs/${id}`),
  simulate: (seats: string[], n_games: number, seed: number) =>
    api<{ job_id: string }>("/lab/simulate", { method: "POST", json: { seats, n_games, seed } }),
  compare: (agents: string[], n_games: number) =>
    api<{ job_id: string }>("/lab/compare", { method: "POST", json: { agents, n_games } }),
  train: (kind: string, config: Record<string, unknown>) =>
    api<{ job_id: string }>("/lab/training", { method: "POST", json: { kind, config } }),
  training: (id: string) => api<LabJob & { series: MetricPoint[] }>(`/lab/training/${id}`),
  stop: (id: string) => api<LabJob>(`/lab/training/${id}/stop`, { method: "POST" }),
  resume: (id: string) => api<LabJob>(`/lab/training/${id}/resume`, { method: "POST" }),
  replays: (q: Record<string, string>) =>
    api<{ id: string; seats: GameSummary["seats"]; result: import("./protocol").HandResult; created_at: string }[]>(
      `/lab/replays?${new URLSearchParams(q).toString()}`),
};
