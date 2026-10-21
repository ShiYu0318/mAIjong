import { translate } from "./i18n";
import type { RoomInfo } from "./protocol";

/** Backend base URL. Without NEXT_PUBLIC_API_URL the page talks to port 8000 on whatever host
 * served it, so opening the dev server by LAN address (or from a phone) still works. */
export function apiUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined") return `${window.location.protocol}//${window.location.hostname}:8000`;
  return "http://localhost:8000";
}

export function wsUrl(): string {
  return process.env.NEXT_PUBLIC_WS_URL ?? apiUrl().replace(/^http/, "ws");
}

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

/** Server error details a player can run into, worded for the interface. */
const SERVER_ERRORS: Record<string, string> = {
  "game already started": "牌局已經開始，無法加入。",
  "already started": "牌局已經開始了。",
  "seat taken": "這個座位已經有人了。",
  "room full": "這桌已經坐滿了。",
  "room not found": "找不到這個房間。",
  "only the host can start": "只有開桌的人可以開始。",
  "not enough coins": "金幣不足。",
  "already owned": "已經擁有這個物品。",
  "not owned": "還沒有這個物品。",
  "no such item": "沒有這個物品。",
  "bonus already claimed today": "今天的獎勵已經領過了。",
  "already claimed": "已經領取過了。",
  "mission not complete": "任務還沒完成。",
  "no such mission today": "今天沒有這個任務。",
  "already a registered account": "這已經是正式帳號了。",
  "username or email already taken": "這個名稱或信箱已經註冊過。",
  "wrong email or password": "信箱或密碼不正確。",
  "not authenticated": "請先登入。",
  "invalid token": "登入已過期，請重新整理頁面。",
  "note is empty": "筆記不能是空的。",
  "game not found": "找不到這場牌局。",
  "agent not found": "找不到這個代理程式。",
  "not your agent": "這不是你的代理程式。",
  "not enough eligible agents": "目前沒有足夠的代理程式可以比賽。",
  "not a zip file": "上傳的檔案不是 zip。",
  "submission needs agent.py and manifest.json": "提交包需要 agent.py 和 manifest.json。",
  "manifest.json is not valid JSON": "manifest.json 不是正確的 JSON。",
  "manifest needs agent_class and name": "manifest.json 需要 agent_class 與 name 欄位。",
  "submission larger than 200 MB": "提交包超過 200 MB。",
  "try again": "請再試一次。",
};

export class ApiError extends Error {
  /** `detail` is the server's own text; `message` is it in the interface language. */
  constructor(public status: number, public detail: string) {
    super(translate(SERVER_ERRORS[detail] ?? detail));
  }
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  const token = authToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init.json !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`${apiUrl()}/api/v1${path}`, {
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
  progress: () =>
    api<{ lesson_id: string; status: string; quiz_score: number | null }[]>("/tutor/progress"),
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

export interface LabRun {
  name: string;
  kind: string;
  updated_at: number;
  points: number;
  last_step: number | null;
  eval_win_rate: number | null;
}

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
  training: (id: string, since?: number) =>
    api<LabJob & { series: MetricPoint[] }>(`/lab/training/${id}${since !== undefined ? `?since=${since}` : ""}`),
  runs: () => api<LabRun[]>("/lab/runs"),
  run: (name: string, since?: number) =>
    api<{ name: string; config: Record<string, unknown>; series: MetricPoint[] }>(
      `/lab/runs/${encodeURIComponent(name)}${since !== undefined ? `?since=${since}` : ""}`),
  stop: (id: string) => api<LabJob>(`/lab/training/${id}/stop`, { method: "POST" }),
  resume: (id: string) => api<LabJob>(`/lab/training/${id}/resume`, { method: "POST" }),
  replays: (q: Record<string, string>) =>
    api<{ id: string; seats: GameSummary["seats"]; result: import("./protocol").HandResult; created_at: string }[]>(
      `/lab/replays?${new URLSearchParams(q).toString()}`),
};

export interface UserInfo {
  id: string;
  username: string;
  email: string;
  elo_human: number;
  games_played: number;
  is_guest?: boolean;
}

export const account = {
  register: (username: string, email: string, password: string) =>
    api<{ token: string; user: UserInfo }>("/auth/register", { method: "POST", json: { username, email, password } }),
  login: (email: string, password: string) =>
    api<{ token: string; user: UserInfo }>("/auth/login", { method: "POST", json: { email, password } }),
  me: () => api<UserInfo>("/auth/me"),
  guest: () => api<{ token: string; user: UserInfo }>("/auth/guest", { method: "POST" }),
  upgrade: (username: string, email: string, password: string) =>
    api<{ token: string; user: UserInfo }>("/auth/upgrade", { method: "POST", json: { username, email, password } }),
};

export interface Mission {
  id: string;
  name: string;
  progress: number;
  target: number;
  reward: number;
  claimed: boolean;
}

export interface Achievement {
  id: string;
  name: string;
  description: string;
  reward: number;
  unlocked: boolean;
}

export type CosmeticSlot = "tile_back" | "table" | "win_effect";

export interface Profile {
  user: UserInfo;
  level: number;
  xp: number;
  xp_next: number;
  coins: number;
  rank: { id: string; name: string; next: string | null; next_at: number | null; progress: number };
  bonus: { available: boolean; amount: number; streak: number };
  missions: Mission[];
  achievements: Achievement[];
  equipped: Record<CosmeticSlot, string>;
  owned: string[];
  stats: Record<string, number>;
}

export interface ShopItem {
  id: string;
  name: string;
  price: number;
  owned: boolean;
  equipped: boolean;
}

export const profileApi = {
  me: () => api<Profile>("/profile/me"),
  claimBonus: () => api<{ amount: number; coins: number; streak: number }>("/profile/bonus", { method: "POST" }),
  claimMission: (id: string) => api<{ reward: number; coins: number }>(`/profile/missions/${id}/claim`, { method: "POST" }),
  shop: () => api<{ coins: number; items: Record<CosmeticSlot, ShopItem[]> }>("/shop"),
  buy: (slot: CosmeticSlot, item: string) =>
    api<{ coins: number; items: Record<CosmeticSlot, ShopItem[]> }>("/shop/buy", { method: "POST", json: { slot, item } }),
  equip: (slot: CosmeticSlot, item: string) =>
    api<{ equipped: Record<CosmeticSlot, string> }>("/profile/equip", { method: "POST", json: { slot, item } }),
};

export interface AgentInfo {
  id: string;
  name: string;
  version: number;
  elo: number;
  games_played: number;
  status: string;
  owner: string | null;
  owner_id: string | null;
  description: string;
  validation: { passed: boolean; errors: string[]; decisions?: number; max_decision_s?: number } | null;
  created_at: string;
  elo_history?: { elo: number; placement: number; at: string }[];
}

export interface BoardRow {
  rank: number;
  id: string;
  name: string;
  version?: number;
  author: string;
  elo: number;
  games: number;
  first_rate: number;
  avg_place: number | null;
}

export interface SeasonInfo {
  id: number;
  starts_at: string;
  ends_at: string;
  status: string;
}

export const agentsApi = {
  list: (all = false) => api<AgentInfo[]>(`/agents?limit=100${all ? "&status_=ALL" : ""}`),
  get: (id: string) => api<AgentInfo>(`/agents/${id}`),
  submit: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return api<AgentInfo>("/agents/submit", { method: "POST", body });
  },
  remove: (id: string) => fetch(`${apiUrl()}/api/v1/agents/${id}`, {
    method: "DELETE", headers: { Authorization: `Bearer ${authToken()}` },
  }),
};

export const competition = {
  leaderboard: (season: string, kind: "agent" | "human") =>
    api<{ season: SeasonInfo; rows: BoardRow[] }>(`/leaderboard?season=${season}&kind=${kind}`),
  seasons: () => api<SeasonInfo[]>("/seasons"),
  challenge: (agent_id: string, opponent_id: string, n_games: number) =>
    api<{ id: string; status: string }>("/challenges", { method: "POST", json: { agent_id, opponent_id, n_games } }),
  getChallenge: (id: string) =>
    api<{ id: string; status: string; result: { total_score?: Record<string, number>; first_places?: Record<string, number>; winner?: string; error?: string } }>(`/challenges/${id}`),
  joinHumanArena: () => api<JoinResult>("/arena/human/join", { method: "POST" }),
  aiVsHumans: (level = 5) => api<AiVsHumans>(`/stats/ai-vs-humans?level=${level}`),
};

/** How a bot level fares against people at the same table (SPEC 05.7 D). */
export interface AiVsHumans {
  level: number;
  hands: number;
  bot_win_rate: number | null;
  human_win_rate: number | null;
  target_bot_win_rate: number;
}

export interface SpeedState {
  token: string;
  hand: number[];
  drawn: number | null;
  drawable: number;
  done: boolean;
  tenpai: boolean;
  score: number | null;
  shanten: number;
}

export interface DefenseState {
  token: string;
  seat: number;
  hand: number[];
  drawn: number | null;
  discards: number[][];
  melds: { type: string; tiles: (number | null)[] }[][];
  declared: number[];
  survived: number;
  turns: number;
  done: boolean;
  dealt_in: boolean;
  success: boolean;
  waits?: Record<string, number[]>;
}

export interface Scenario {
  id: string;
  title: string;
  category: string;
  seat: number;
  description: string;
}

export const practice = {
  speedStart: () => api<SpeedState>("/practice/speed/start", { method: "POST" }),
  speedDiscard: (token: string, tile: number) =>
    api<SpeedState>("/practice/speed/discard", { method: "POST", json: { token, tile } }),
  defenseStart: () => api<DefenseState>("/practice/defense/start", { method: "POST" }),
  defenseDiscard: (token: string, tile: number) =>
    api<DefenseState>("/practice/defense/discard", { method: "POST", json: { token, tile } }),
  scenarios: () => api<Scenario[]>("/practice/scenarios"),
  playScenario: (id: string) =>
    api<JoinResult>(`/practice/scenarios/${id}/play`, { method: "POST" }),
};
