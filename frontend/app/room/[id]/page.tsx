"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ActionBar } from "@/components/HUD/ActionBar";
import { CoachNote } from "@/components/HUD/CoachNote";
import { HintPanel } from "@/components/HUD/HintPanel";
import { ResultOverlay } from "@/components/HUD/ResultOverlay";
import { SidePanel } from "@/components/HUD/SidePanel";
import { HandList, TableAnnouncer, useTableKeys } from "@/components/HUD/TableAccess";
import { TableFelt, TableHud, useTableLayout } from "@/components/Board/TableOverlay";
import { SoundToggle } from "@/components/Game/SoundToggle";
import { WaitingRoom } from "@/components/HUD/WaitingRoom";
import { ApiError, loadTicket, rooms, saveTicket } from "@/lib/api";
import { LocaleToggle } from "@/components/I18n/LocaleToggle";
import { translate, useT } from "@/lib/i18n";
import { windName } from "@/lib/tiles";
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
  const t = useT();
  const [tableRef, layout] = useTableLayout();
  useTableKeys();

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
        <h1 className="font-display text-4xl">{t("加入這一桌")}</h1>
        <form className="mt-6 flex gap-2" onSubmit={async (e) => {
          e.preventDefault();
          try {
            const j = await rooms.join(id, name || undefined);
            saveTicket(id, j);
            setTicket({ seat: j.seat, token: j.ws_token });
          } catch (err) {
            setJoinError(err instanceof ApiError ? err.message : t("無法加入"));
          }
        }}>
          <input value={name} onChange={(e) => setName(e.target.value.slice(0, 20))} placeholder={t("暱稱")}
            aria-label={t("暱稱")} className="flex-1 rounded-md border border-felt-line bg-felt-deep px-3 py-2" />
          <button className="rounded-md bg-ivory px-4 py-2 text-ink">{t("入座")}</button>
        </form>
        {joinError && <p role="alert" className="mt-3 text-zhong">{joinError}</p>}
        <Link href="/" className="mt-8 inline-block text-mist underline">{t("回大廳")}</Link>
      </main>
    );
  }

  const names = (room?.seats ?? []).map((s, i) => s?.name ?? `座位${i + 1}`);

  if (room?.status === "WAITING" || (!view && room)) {
    return room.status === "WAITING" ? <WaitingRoom room={room} seat={seat} /> : <Loading />;
  }
  if (!room) return <Loading text={t(STATUS_TEXT[status] ?? "載入中…")} />;

  return (
    <main className="flex h-dvh flex-col">
      <header className="flex items-center gap-3 border-b border-white/10 bg-black/25 px-3 py-2 text-sm whitespace-nowrap backdrop-blur sm:gap-4 sm:px-4">
        <Link href="/" className="font-display text-xl font-black text-gold">{t("麥醬")}</Link>
        <span className="text-mist"><span className="hidden sm:inline">{t("房間")} </span><span className="tabular text-ivory">{room.code}</span></span>
        {view && (
          <span className="text-mist">
            {t("{wind}風圈・第 {n} 手", { wind: windName(view.round_wind), n: (room.match?.hands_played ?? 0) + 1 })}
          </span>
        )}
        {STATUS_TEXT[status] && <span className="text-zhong">{t(STATUS_TEXT[status])}</span>}
        <div className="ml-auto flex items-center gap-3"><SoundToggle /><LocaleToggle /></div>
      </header>
      <div className="flex min-h-0 flex-1">
        <section ref={tableRef} className="relative min-w-0 flex-1 overflow-hidden">
          {layout && <TableFelt g={layout} />}
          <TableCanvas />
          {layout && view && <TableHud g={layout} view={view} names={names} />}
          <HandList />
          <TableAnnouncer />
          <div className="absolute right-4 left-4 z-10" style={{ bottom: (layout?.handH ?? 80) + 40 }}>
            <ActionBar />
          </div>
          {error && (
            <p role="alert" className="absolute top-3 left-1/2 z-10 -translate-x-1/2 rounded-md bg-zhong/90 px-3 py-1.5 text-sm">
              {error}
            </p>
          )}
          <HintPanel />
          <CoachNote />
          <ResultOverlay names={names} />
        </section>
        <div className="hidden w-72 shrink-0 p-3 lg:block">
          <SidePanel names={names} />
        </div>
      </div>
    </main>
  );
}

function Loading({ text = translate("載入中…") }: { text?: string }) {
  return <main className="flex h-dvh items-center justify-center text-mist">{text}</main>;
}
