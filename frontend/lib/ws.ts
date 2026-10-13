import { useGame } from "@/store/gameStore";
import type { ServerMessage } from "./protocol";
import { wsUrl } from "./api";

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
    // batch=1: the server packs each burst of messages into one BATCH frame (SPEC P11-7)
    const q = this.token ? `?token=${encodeURIComponent(this.token)}&batch=1` : "?batch=1";
    const ws = new WebSocket(`${wsUrl()}/ws/game/${this.roomId}${q}`);
    this.ws = ws;
    ws.onopen = () => {
      this.retries = 0;
      useGame.getState().setStatus("open");
      useGame.getState().setSender((m) => this.send(m));
      this.ping = setInterval(() => this.send({ type: "PING" }), 30_000);
    };
    ws.onmessage = (e) => {
      let frame: ServerMessage;
      try {
        frame = JSON.parse(e.data) as ServerMessage;
      } catch {
        return; // ignore malformed frame
      }
      const handle = useGame.getState().handle;
      for (const msg of unpackFrame(frame)) handle(msg);
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

/** A BATCH frame carries several server messages in order; anything else is one message. */
export function unpackFrame(frame: ServerMessage): ServerMessage[] {
  if (frame.type === "BATCH") {
    const messages = (frame.payload as { messages?: ServerMessage[] } | undefined)?.messages;
    return Array.isArray(messages) ? messages : [];
  }
  return [frame];
}
