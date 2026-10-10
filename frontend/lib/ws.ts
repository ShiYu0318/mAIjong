import { useGame } from "@/store/gameStore";
import type { ServerMessage } from "./protocol";
import { WS_URL } from "./api";

/** WebSocket with automatic reconnection and keep-alive pings. */
export class GameSocket {
  private ws: WebSocket | null = null;
  private closed = false;
  private retries = 0;
  private ping: ReturnType<typeof setInterval> | null = null;

  constructor(private roomId: string, private token: string | null) {}

  connect() {
    const store = useGame.getState();
    store.setStatus(this.retries ? "reconnecting" : "connecting");
    const q = this.token ? `?token=${encodeURIComponent(this.token)}` : "";
    const ws = new WebSocket(`${WS_URL}/ws/game/${this.roomId}${q}`);
    this.ws = ws;
    ws.onopen = () => {
      this.retries = 0;
      useGame.getState().setStatus("open");
      useGame.getState().setSender((m) => this.send(m));
      this.ping = setInterval(() => this.send({ type: "PING" }), 30_000);
    };
    ws.onmessage = (e) => {
      try {
        useGame.getState().handle(JSON.parse(e.data) as ServerMessage);
      } catch {
        /* ignore malformed frame */
      }
    };
    ws.onclose = (e) => {
      if (this.ping) clearInterval(this.ping);
      useGame.getState().setSender(null);
      if (this.closed || e.code >= 4400) {
        useGame.getState().setStatus("closed");
        return;
      }
      this.retries += 1;
      useGame.getState().setStatus("reconnecting");
      setTimeout(() => this.connect(), Math.min(10_000, 500 * 2 ** this.retries));
    };
  }

  send(msg: object) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
  }

  close() {
    this.closed = true;
    if (this.ping) clearInterval(this.ping);
    this.ws?.close();
  }
}
