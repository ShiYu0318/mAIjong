"use client";

import { useEffect, useRef, useState } from "react";
import { useT } from "@/lib/i18n";
import { useGame } from "@/store/gameStore";

export function SidePanel({ names }: { names: string[] }) {
  const log = useGame((s) => s.log);
  const chat = useGame((s) => s.chat);
  const sendChat = useGame((s) => s.sendChat);
  const t = useT();
  const [tab, setTab] = useState<"log" | "chat">("log");
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [log, chat, tab]);

  return (
    <aside className="flex h-full flex-col rounded-xl border border-felt-line bg-felt-deep/80 text-sm">
      <div className="flex border-b border-felt-line" role="tablist">
        {(["log", "chat"] as const).map((tb) => (
          <button key={tb} role="tab" aria-selected={tab === tb} onClick={() => setTab(tb)}
            className={`flex-1 py-2 ${tab === tb ? "text-ivory" : "text-mist"}`}>
            {tb === "log" ? t("牌局紀錄") : `${t("聊天")}${chat.length ? ` (${chat.length})` : ""}`}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        {tab === "log"
          ? log.map((l, i) => <p key={i} className="py-0.5 text-mist">{l}</p>)
          : chat.map((c, i) => (
            <p key={i} className="py-0.5"><span className="text-mist">{names[c.seat]}：</span>{c.message}</p>
          ))}
        <div ref={endRef} />
      </div>
      {tab === "chat" && (
        <form className="flex gap-2 border-t border-felt-line p-2" onSubmit={(e) => {
          e.preventDefault();
          sendChat(text);
          setText("");
        }}>
          <input value={text} onChange={(e) => setText(e.target.value.slice(0, 200))} aria-label={t("聊天訊息")}
            className="min-w-0 flex-1 rounded-md border border-felt-line bg-felt px-2 py-1.5" placeholder={t("說點什麼")} />
          <button className="rounded-md border border-ivory/30 px-3">{t("送出")}</button>
        </form>
      )}
    </aside>
  );
}
