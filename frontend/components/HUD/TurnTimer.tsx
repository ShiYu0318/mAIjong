"use client";

import { useEffect, useState } from "react";
import { useGame } from "@/store/gameStore";

export function TurnTimer() {
  const deadline = useGame((s) => s.deadline);
  const send = useGame((s) => s.sender);
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (deadline === null) return;
    const id = setInterval(() => setNow(Date.now() / 1000), 250);
    return () => clearInterval(id);
  }, [deadline]);
  if (deadline === null) return null;
  const left = Math.max(0, Math.ceil(deadline - now));
  return (
    <div className="flex items-center gap-3">
      <span className={`tabular font-display text-3xl ${left <= 5 ? "text-zhong" : "text-ivory"}`}
        aria-live="polite" aria-label={`剩餘 ${left} 秒`}>
        {left}
      </span>
      <button onClick={() => send?.({ type: "EXTEND_TIME" })}
        className="rounded-md border border-ivory/30 px-2 py-1 text-xs text-mist hover:bg-ivory/10">
        延長 15 秒
      </button>
    </div>
  );
}
