"use client";

import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";
import { useT } from "@/lib/i18n";
import { useGame } from "@/store/gameStore";

/** While a player is disconnected the table waits for them; say so, with the time until an
 * AI takes their seat, so the pause doesn't look like a frozen game. */
export function AwayNotice({ names }: { names: string[] }) {
  const away = useGame((s) => s.away);
  const t = useT();
  const [now, setNow] = useState(() => Date.now());
  const seats = Object.keys(away).map(Number);
  useEffect(() => {
    if (!seats.length) return;
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, [seats.length]);
  if (!seats.length) return null;
  return (
    <div role="status" className="pointer-events-none absolute top-3 left-1/2 z-20 flex -translate-x-1/2 flex-col gap-1">
      {seats.map((seat) => {
        const left = Math.max(0, Math.ceil((away[seat] - now) / 1000));
        return (
          <p key={seat} className="flex items-center gap-2 rounded-full bg-black/75 px-4 py-1.5 text-sm font-bold whitespace-nowrap text-ivory shadow-lg">
            <WifiOff size={16} strokeWidth={2.6} className="text-zhong" aria-hidden="true" />
            {left > 0
              ? t("{name} 斷線了，{n} 秒後由 AI 代打", { name: names[seat] ?? "", n: left })
              : t("{name} 斷線了，AI 正在接手", { name: names[seat] ?? "" })}
          </p>
        );
      })}
    </div>
  );
}
