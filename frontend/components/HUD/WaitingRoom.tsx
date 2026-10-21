"use client";

import { useState } from "react";
import { PlayerBar } from "@/components/Account/PlayerBar";
import { Avatar } from "@/components/Game/Avatar";
import { GameButton } from "@/components/Game/GameButton";
import { rooms } from "@/lib/api";
import { localName, useT } from "@/lib/i18n";
import type { RoomInfo } from "@/lib/protocol";
import { sfx } from "@/lib/sfx";

const LEVEL = ["", "初學", "入門", "普通", "進階", "高手"];

export function WaitingRoom({ room, seat }: { room: RoomInfo; seat: number | null }) {
  const t = useT();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      await rooms.start(room.room_id);
    } catch (e) {
      sfx.error();
      setError(e instanceof Error ? e.message : t("無法開始"));
      setBusy(false);
    }
  };
  const link = typeof window !== "undefined" ? window.location.href : "";
  return (
    <main className="mx-auto max-w-3xl px-4 pt-4 pb-12 sm:px-8">
      <header className="flex justify-end"><PlayerBar compact /></header>
      <section className="panel mt-8 animate-pop-in p-6 sm:p-8">
        <h1 className="font-display text-5xl font-black">{t("等待開局")}</h1>
        <p className="mt-2 text-mist">{t("把房間碼給朋友，或直接開始，空位會由 AI 補上。")}</p>
        <div className="mt-6 flex flex-wrap items-center gap-4">
          <span className="tabular rounded-2xl bg-black/30 px-5 py-2 font-display text-5xl font-black tracking-[0.18em] text-gold">
            {room.code}
          </span>
          <GameButton variant="ghost" size="sm" onClick={() => {
            navigator.clipboard?.writeText(link).then(() => setCopied(true));
          }}>
            {copied ? t("已複製連結") : t("複製邀請連結")}
          </GameButton>
        </div>
        <ul className="mt-6 grid gap-3 sm:grid-cols-2">
          {room.seats.map((s, i) => (
            <li key={i} className={`flex animate-rise items-center gap-3 rounded-2xl p-3 ${seat === i ? "bg-gold/15 ring-1 ring-gold/60" : "bg-black/20"}`}
              style={{ animationDelay: `${i * 70}ms` }}>
              {s ? <Avatar name={s.name} size={40} /> : (
                <span className="flex size-[48px] items-center justify-center rounded-full border-2 border-dashed border-white/25 text-mist">?</span>
              )}
              <span className="flex-1">
                <span className="block text-sm text-mist">{t("座位 {n}", { n: i + 1 })}{seat === i ? t("（你）") : ""}</span>
                <span className="block font-black">
                  {s === null ? t("空位") : s.is_bot ? t("AI {level}", { level: t(LEVEL[s.bot_level ?? 3]) }) : localName(s.name)}
                </span>
              </span>
            </li>
          ))}
        </ul>
        {error && <p role="alert" className="mt-4 animate-wiggle font-bold text-zhong">{error}</p>}
        <GameButton size="xl" className="mt-8 w-full" onClick={start} disabled={busy}>
          {busy ? t("開局中…") : t("開始")}
        </GameButton>
      </section>
    </main>
  );
}
