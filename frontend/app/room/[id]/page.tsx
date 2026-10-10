"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ActionBar } from "@/components/HUD/ActionBar";
import { ResultOverlay } from "@/components/HUD/ResultOverlay";
import { SidePanel } from "@/components/HUD/SidePanel";
import { TurnTimer } from "@/components/HUD/TurnTimer";
import { WaitingRoom } from "@/components/HUD/WaitingRoom";
import { ApiError, loadTicket, rooms, saveTicket } from "@/lib/api";
import { WINDS } from "@/lib/tiles";
import { GameSocket } from "@/lib/ws";
import { useGame } from "@/store/gameStore";

const TableCanvas = dynamic(() => import("@/components/Board/TableCanvas").then((m) => m.TableCanvas), {
  ssr: false,
});

const STATUS_TEXT: Record<string, string> = {
  connecting: "連線中…",
  reconnecting: "連線中斷，重新連線中…",
  closed: "已離線",
};

export default function RoomPage() {
  const { id } = useParams<{ id: string }>();
  const [ticket, setTicket] = useState<{ seat: number; token: string } | null | undefined>(undefined);
  const [name, setName] = useState("");
  const [joinError, setJoinError] = useState<string | null>(null);
  const status = useGame((s) => s.status);
  const room = useGame((s) => s.room);
  const view = useGame((s) => s.view);
  const seat = useGame((s) => s.seat);
  const error = useGame((s) => s.error);

  useEffect(() => {
    setTicket(loadTicket(id));
  }, [id]);

  useEffect(() => {
    if (!ticket) return;
    useGame.getState().reset();
    const sock = new GameSocket(id, ticket.token);
    sock.connect();
    return () => sock.close();
  }, [id, ticket]);

  if (ticket === undefined) return null;

  if (ticket === null) {
    return (
      <main className="mx-auto max-w-md px-5 py-20">
        <h1 className="font-display text-4xl">加入這一桌</h1>
        <form className="mt-6 flex gap-2" onSubmit={async (e) => {
          e.preventDefault();
          try {
            const j = await rooms.join(id, name || undefined);
            saveTicket(id, j);
            setTicket({ seat: j.seat, token: j.ws_token });
          } catch (err) {
            setJoinError(err instanceof ApiError ? err.message : "無法加入");
          }
        }}>
          <input value={name} onChange={(e) => setName(e.target.value.slice(0, 20))} placeholder="暱稱"
            aria-label="暱稱" className="flex-1 rounded-md border border-felt-line bg-felt-deep px-3 py-2" />
          <button className="rounded-md bg-ivory px-4 py-2 text-ink">入座</button>
        </form>
        {joinError && <p role="alert" className="mt-3 text-zhong">{joinError}</p>}
        <Link href="/" className="mt-8 inline-block text-mist underline">回大廳</Link>
      </main>
    );
  }

  const names = (room?.seats ?? []).map((s, i) => s?.name ?? `座位${i + 1}`);

  if (room?.status === "WAITING" || (!view && room)) {
    return room.status === "WAITING" ? <WaitingRoom room={room} seat={seat} /> : <Loading />;
  }
  if (!room) return <Loading text={STATUS_TEXT[status] ?? "載入中…"} />;

  return (
    <main className="flex h-dvh flex-col">
      <header className="flex items-center gap-4 border-b border-felt-line px-4 py-2 text-sm">
        <Link href="/" className="font-display text-xl">麥醬</Link>
        <span className="text-mist">房間 <span className="tabular text-ivory">{room.code}</span></span>
        {view && (
          <span className="text-mist">
            {WINDS[view.round_wind]}風圈・第 {(room.match?.hands_played ?? 0) + 1} 手
          </span>
        )}
        {STATUS_TEXT[status] && <span className="text-zhong">{STATUS_TEXT[status]}</span>}
        <div className="ml-auto"><TurnTimer /></div>
      </header>
      <div className="flex min-h-0 flex-1">
        <section className="relative min-w-0 flex-1">
          <TableCanvas />
          <div className="absolute right-4 bottom-[118px] left-4 z-10">
            <ActionBar />
          </div>
          {error && (
            <p role="alert" className="absolute top-3 left-1/2 z-10 -translate-x-1/2 rounded-md bg-zhong/90 px-3 py-1.5 text-sm">
              {error}
            </p>
          )}
          <ResultOverlay names={names} />
        </section>
        <div className="hidden w-72 shrink-0 p-3 lg:block">
          <SidePanel names={names} />
        </div>
      </div>
    </main>
  );
}

function Loading({ text = "載入中…" }: { text?: string }) {
  return <main className="flex h-dvh items-center justify-center text-mist">{text}</main>;
}
