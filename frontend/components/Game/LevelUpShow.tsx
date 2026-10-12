"use client";

import { useEffect, useMemo } from "react";
import { CoinIcon } from "@/components/Game/CoinCounter";
import { LevelBadge } from "@/components/Game/LevelBadge";
import { useT } from "@/lib/i18n";
import { useAccount } from "@/store/accountStore";

const SPARK = ["#fff3b0", "#ffcc3d", "#ff9f1c", "#38d0ff", "#ff5c9a"];

/** Full-screen "LEVEL UP" moment (DESIGN.md §8.1); closes itself or on click. */
export function LevelUpShow() {
  const levelUp = useAccount((s) => s.levelUp);
  const clear = useAccount((s) => s.clearLevelUp);
  const t = useT();
  useEffect(() => {
    if (!levelUp) return;
    const id = setTimeout(clear, 3200);
    return () => clearTimeout(id);
  }, [levelUp, clear]);
  const sparks = useMemo(() => Array.from({ length: 40 }, (_, i) => {
    const a = (i / 40) * Math.PI * 2;
    const d = 180 + (i % 5) * 45;
    return { dx: `${Math.cos(a) * d}px`, dy: `${Math.sin(a) * d}px`, color: SPARK[i % SPARK.length],
      size: 8 + (i % 4) * 4, delay: (i % 7) * 0.03 };
  }), []);
  if (!levelUp) return null;
  return (
    <button type="button" onClick={clear} aria-label={t("升級！等級 {n}", { n: levelUp.level })}
      className="fixed inset-0 z-[60] flex cursor-pointer items-center justify-center bg-felt-deep/75 backdrop-blur-sm">
      <span className="pointer-events-none absolute h-[60vmin] w-[60vmin] animate-[spin_9s_linear_infinite] rounded-full opacity-60"
        style={{ background: "repeating-conic-gradient(rgb(255 204 61 / 0.35) 0 10deg, transparent 10deg 30deg)",
          maskImage: "radial-gradient(circle, black 30%, transparent 70%)" }} aria-hidden="true" />
      <span className="pointer-events-none absolute top-1/2 left-1/2" aria-hidden="true">
        {sparks.map((p, i) => (
          <span key={i} className="absolute animate-burst rounded-full"
            style={{ width: p.size, height: p.size, background: p.color, animationDelay: `${p.delay}s`,
              ["--dx" as string]: p.dx, ["--dy" as string]: p.dy, ["--rot" as string]: "0deg" }} />
        ))}
      </span>
      <span className="relative flex flex-col items-center" role="status">
        <span className="animate-stamp font-display text-6xl font-black tracking-wide sm:text-8xl"
          style={{ background: "linear-gradient(180deg,#fff3b0,#ffcc3d 55%,#ff9f1c)", WebkitBackgroundClip: "text",
            backgroundClip: "text", color: "transparent", filter: "drop-shadow(0 6px 0 rgb(0 0 0 / 0.35))" }}>
          LEVEL UP
        </span>
        <span className="mt-4 animate-pop-in" style={{ animationDelay: "250ms" }}>
          <LevelBadge level={levelUp.level} xp={1} xpNext={1} size={112} />
        </span>
        <span className="mt-4 flex animate-rise items-center gap-2 rounded-full bg-black/40 px-5 py-2 text-2xl font-black text-gold"
          style={{ animationDelay: "450ms" }}>
          <CoinIcon size={28} />+{levelUp.coins}
        </span>
        <span className="mt-6 text-sm text-mist">{t("點一下繼續")}</span>
      </span>
    </button>
  );
}
