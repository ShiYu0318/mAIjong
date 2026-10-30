"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ActionBar, ReadyWaits } from "@/components/HUD/ActionBar";
import { AwayNotice } from "@/components/HUD/AwayNotice";
import { CoachNote } from "@/components/HUD/CoachNote";
import { ScenarioBanner, ScenarioFeedback } from "@/components/HUD/ScenarioPanel";
import { HintPanel } from "@/components/HUD/HintPanel";
import { ResultOverlay } from "@/components/HUD/ResultOverlay";
import { SidePanel } from "@/components/HUD/SidePanel";
import { HandList, TableAnnouncer, useTableKeys } from "@/components/HUD/TableAccess";
import { TableFelt, TableHud, useTableLayout } from "@/components/Board/TableOverlay";
import { SoundToggle } from "@/components/Game/SoundToggle";
import { GameButton } from "@/components/Game/GameButton";
import { WaitingRoom } from "@/components/HUD/WaitingRoom";
import { ApiError, loadTicket, rooms, saveTicket } from "@/lib/api";
import { MissingState } from "@/components/Game/MissingState";
import type { RoomInfo } from "@/lib/protocol";
import { LocaleToggle } from "@/components/I18n/LocaleToggle";
import { localName, translate, useT } from "@/lib/i18n";
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
  /** the table an invite link points at, looked up before offering a seat */
  const [invite, setInvite] = useState<RoomInfo | "missing" | null>(null);
  const status = useGame((s) => s.status);
  const room = useGame((s) => s.room);
  const view = useGame((s) => s.view);
  // the server counts a hand as played the moment it ends; keep its number while its result shows
  const handOver = useGame((s) => s.win !== null || s.drawn);
  const played = room?.match?.hands_played ?? 0;
  const [handNo, setHandNo] = useState<number | null>(null);
  useEffect(() => {
    if (!handOver) setHandNo(played + 1);
  }, [handOver, played]);
  const seat = useGame((s) => s.seat);
  const error = useGame((s) => s.error);
  const t = useT();
  const [tableRef, layout] = useTableLayout();
  useTableKeys();

  useEffect(() => {
    setTicket(loadTicket(id));
  }, [id]);

  useEffect(() => {
    if (ticket !== null) return;
    rooms.get(id).then(setInvite).catch(() => setInvite("missing"));
  }, [id, ticket]);

  useEffect(() => {
    if (!ticket) return;
    useGame.getState().reset();
    const sock = new GameSocket(id, ticket.token);
    sock.connect();
    return () => sock.close();
  }, [id, ticket]);

  if (ticket === undefined) return null;

  if (ticket === null) {
    if (invite === null) return null;
    if (invite === "missing") {
      return <MissingState title={t("找不到這個房間。")} message={t("這一桌可能已經結束，或連結打錯了。")} linkLabel={t("回大廳")} />;
    }
    if (invite.status !== "WAITING") {
      return <MissingState title={t("牌局已經開始了。")} message={t("這一桌已經開打，無法再入座。")} linkLabel={t("回大廳")} />;
    }
    if (!invite.seats.some((x) => x === null)) {
      return <MissingState title={t("這桌已經坐滿了。")} message={t("請朋友開一桌留空位給你，或回大廳快速配對。")} linkLabel={t("回大廳")} />;
    }
    return (
      <main className="mx-auto max-w-md px-5 py-16">
        <section className="panel animate-pop-in p-6 sm:p-8">
          <h1 className="font-display text-4xl font-black">{t("加入這一桌")}</h1>
          <p className="mt-2 text-mist">
            {t("房間碼")}{" "}
            <span className="tabular font-display text-xl font-black tracking-[0.18em] text-gold">{invite.code}</span>
          </p>
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
              aria-label={t("暱稱")} className="min-w-0 flex-1 rounded-xl border border-white/10 bg-felt-deep px-3 py-2" />
            <GameButton type="submit" className="shrink-0">{t("入座")}</GameButton>
          </form>
          {joinError && <p role="alert" className="mt-3 font-bold text-zhong">{joinError}</p>}
        </section>
        <Link href="/" className="mt-6 inline-block text-mist underline">{t("回大廳")}</Link>
      </main>
    );
  }

  const names = (room?.seats ?? []).map((s, i) => (s ? localName(s.name) : t("座位 {n}", { n: i + 1 })));

  if (room?.status === "WAITING" || (!view && room)) {
    return room.status === "WAITING" ? <WaitingRoom room={room} seat={seat} /> : <Loading />;
  }
  if (!room) return <Loading text={t(STATUS_TEXT[status] ?? "載入中…")} />;

  return (
    <main className="flex h-dvh flex-col">
      <div role="dialog" aria-label={t("請橫向遊玩")} className="table-rotate fixed inset-0 z-50 flex-col items-center justify-center gap-5 bg-[#10162e] px-8 text-center">
        <span aria-hidden="true" className="text-6xl">↻</span>
        <h1 className="font-display text-3xl font-black">{t("請橫向遊玩")}</h1>
        <p className="max-w-xs text-mist">{t("將手機轉成橫向，完整查看四家牌面與手牌。")}</p>
        <Link href="/" className="mt-4 text-gold underline">{t("回大廳")}</Link>
      </div>
      <header className="flex items-center gap-3 border-b border-white/10 bg-black/25 px-3 py-2 text-sm whitespace-nowrap backdrop-blur sm:gap-4 sm:px-4">
        <Link href="/" className="font-display text-xl font-black text-gold">{t("麥醬")}</Link>
        <span className="text-mist"><span className="hidden sm:inline">{t("房間")} </span><span className="tabular text-ivory">{room.code}</span></span>
        {view && (
          <span className="text-mist">
            {t("{wind}風圈・第 {n} 手", { wind: windName(view.round_wind), n: handNo ?? played })}
            {view.dealer_streak > 0 && <span className="ml-1 text-gold">{t("連 {n}", { n: view.dealer_streak })}</span>}
          </span>
        )}
        {STATUS_TEXT[status] && <span className="text-zhong">{t(STATUS_TEXT[status])}</span>}
        <div className="ml-auto flex items-center gap-3"><SoundToggle /><LocaleToggle /></div>
      </header>
      <div className="flex min-h-0 flex-1">
        <section ref={tableRef} className="relative min-w-0 flex-1 overflow-hidden">
          {layout && <TableFelt g={layout} />}
          <TableCanvas />
          {layout && view && (
            <TableHud g={layout} view={view} names={names} timeLimit={room.config.time_limit} />
          )}
          <HandList />
          <TableAnnouncer />
          <div className="absolute right-4 left-4 z-10 flex items-end justify-between gap-3"
            style={{ bottom: (layout?.handBlock ?? 98) + 22 }}>
            <ReadyWaits />
            <div className="table-actions ml-auto"><ActionBar /></div>
          </div>
          {error && (
            <p role="alert" className="absolute top-3 left-1/2 z-10 -translate-x-1/2 rounded-md bg-zhong/90 px-3 py-1.5 text-sm">
              {error}
            </p>
          )}
          <HintPanel />
          <CoachNote />
          <AwayNotice names={names} />
          {room.scenario && <ScenarioBanner info={room.scenario} />}
          {room.scenario && <ScenarioFeedback info={room.scenario} />}
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
