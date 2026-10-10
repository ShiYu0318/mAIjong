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
    sessionStorage.setItem(`maijong.ticket.${roomId}`, JSON.stringify({ seat: j.seat, token: j.ws_token }));
  } catch {
    /* ignore */
  }
}

export function loadTicket(roomId: string): { seat: number; token: string } | null {
  try {
    const raw = sessionStorage.getItem(`maijong.ticket.${roomId}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
