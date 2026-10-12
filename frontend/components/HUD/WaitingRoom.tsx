"use client";

import { useState } from "react";
import { rooms } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { RoomInfo } from "@/lib/protocol";

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
      setError(e instanceof Error ? e.message : t("無法開始"));
      setBusy(false);
    }
  };
  const link = typeof window !== "undefined" ? window.location.href : "";
  return (
    <div className="mx-auto max-w-xl px-5 py-16">
      <h1 className="font-display text-5xl">{t("等待開局")}</h1>
      <p className="mt-3 text-mist">{t("把房間碼給朋友，或直接開始，空位會由 AI 補上。")}</p>
      <div className="mt-8 flex items-center gap-4">
        <span className="tabular font-display text-5xl tracking-[0.15em]">{room.code}</span>
        <button onClick={() => {
          navigator.clipboard?.writeText(link).then(() => setCopied(true));
        }} className="rounded-md border border-ivory/30 px-3 py-1.5 text-sm hover:bg-ivory/10">
          {copied ? t("已複製連結") : t("複製邀請連結")}
        </button>
      </div>
      <ul className="mt-8 divide-y divide-felt-line border-y border-felt-line">
        {room.seats.map((s, i) => (
          <li key={i} className="flex justify-between py-3">
            <span>{t("座位 {n}", { n: i + 1 })}{seat === i ? t("（你）") : ""}</span>
            <span className="text-mist">
              {s === null ? t("空位") : s.is_bot ? t("AI {level}", { level: t(LEVEL[s.bot_level ?? 3]) }) : s.name}
            </span>
          </li>
        ))}
      </ul>
      {error && <p role="alert" className="mt-4 text-zhong">{error}</p>}
      <button onClick={start} disabled={busy}
        className="mt-8 rounded-lg bg-ivory px-6 py-3 font-display text-2xl text-ink hover:bg-white disabled:opacity-60">
        {busy ? t("開局中…") : t("開始")}
      </button>
    </div>
  );
}
