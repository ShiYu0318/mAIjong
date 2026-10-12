"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Avatar } from "@/components/Game/Avatar";
import { GameButton } from "@/components/Game/GameButton";
import { TileImage } from "@/components/Hand/TileImage";
import { WIN_EFFECTS } from "@/lib/cosmetics";
import { taiName, useT } from "@/lib/i18n";
import { sfx } from "@/lib/sfx";
import { useAccount } from "@/store/accountStore";
import { useGame } from "@/store/gameStore";

/** Confetti-like burst in the colours of the equipped win effect. */
function Burst({ effect, big }: { effect: string; big: boolean }) {
  const fx = WIN_EFFECTS[effect] ?? WIN_EFFECTS.gold;
  const parts = useMemo(() => Array.from({ length: big ? 56 : 32 }, (_, i) => {
    const angle = (i / (big ? 56 : 32)) * Math.PI * 2 + Math.random() * 0.4;
    const dist = (big ? 260 : 180) + Math.random() * 120;
    return {
      dx: `${Math.cos(angle) * dist}px`, dy: `${Math.sin(angle) * dist}px`, rot: `${Math.random() * 720 - 360}deg`,
      color: fx.colors[i % fx.colors.length], size: 9 + Math.random() * 12, delay: Math.random() * 0.15,
      round: i % 3 === 0,
    };
  }), [fx, big]);
  return (
    <div className="pointer-events-none absolute top-[28%] left-1/2 z-10" aria-hidden="true">
      {parts.map((p, i) => (
        <span key={i} className="absolute animate-burst"
          style={{ width: p.size, height: p.size * (p.round ? 1 : 0.5), background: p.color,
            borderRadius: p.round ? "50%" : 2, animationDelay: `${p.delay}s`,
            ["--dx" as string]: p.dx, ["--dy" as string]: p.dy, ["--rot" as string]: p.rot }} />
      ))}
      <span className="absolute -translate-x-1/2 -translate-y-1/2 animate-burst text-8xl"
        style={{ ["--dx" as string]: "0px", ["--dy" as string]: "-40px", ["--rot" as string]: "0deg" }}>{fx.icon}</span>
    </div>
  );
}

const MEDALS = ["🥇", "🥈", "🥉", "🎖️"];

export function ResultOverlay({ names }: { names: string[] }) {
  const win = useGame((s) => s.win);
  const drawn = useGame((s) => s.drawn);
  const gameEnd = useGame((s) => s.gameEnd);
  const dismiss = useGame((s) => s.dismissResult);
  const gameId = useGame((s) => s.view?.game_id);
  const mySeat = useGame((s) => s.seat);
  const xp = useAccount((s) => s.lastXp);
  const effect = useAccount((s) => s.profile?.equipped.win_effect) ?? "gold";
  const t = useT();
  const [stage, setStage] = useState(0);
  const [shownTai, setShownTai] = useState(0);

  const items = useMemo(() => win?.tai_breakdown ?? [], [win]);
  const total = items.reduce((n, it) => n + it.tai, 0) + (win?.dealer_tai ?? 0);
  const iWon = win !== null && win.winner === mySeat;

  // staged reveal: stamp → hand → tai lines one by one → payments
  useEffect(() => {
    setStage(0);
    setShownTai(0);
    if (!win && !drawn) return;
    if (win) (iWon ? sfx.win : sfx.lose)();
    else sfx.lose();
    const timers = [setTimeout(() => setStage(1), 650), setTimeout(() => setStage(2), 1100)];
    return () => timers.forEach(clearTimeout);
  }, [win, drawn, iWon]);
  useEffect(() => {
    if (stage < 2 || !win) return;
    if (shownTai >= items.length) {
      const id = setTimeout(() => setStage(3), 250);
      return () => clearTimeout(id);
    }
    const id = setTimeout(() => {
      sfx.tick();
      setShownTai((n) => n + 1);
    }, 160);
    return () => clearTimeout(id);
  }, [stage, shownTai, items.length, win]);

  if (!win && !drawn && !gameEnd) return null;
  const big = total >= 5;
  const runningTai = items.slice(0, shownTai).reduce((n, it) => n + it.tai, 0)
    + (stage >= 3 ? win?.dealer_tai ?? 0 : 0);

  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-felt-deep/80 p-4 backdrop-blur-sm" role="dialog"
      aria-modal="true" aria-label={t("本手結果")}>
      <div className="panel relative w-full max-w-2xl animate-pop-in overflow-hidden p-6 sm:p-8">
        {win && (
          <>
            <div className="text-center">
              <h2 className="inline-block animate-stamp font-display text-6xl font-black"
                style={{ background: iWon ? "linear-gradient(180deg,#fff3b0,#ffcc3d 55%,#ff9f1c)" : "linear-gradient(180deg,#ffd0dc,#ff4d6a)",
                  WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent",
                  filter: "drop-shadow(0 5px 0 rgb(0 0 0 / 0.35))" }}>
                {win.flower_win ? t("花牌胡") : win.self_draw ? t("自摸！") : t("胡！")}
              </h2>
              <p className="mt-2 flex items-center justify-center gap-2 text-lg font-bold">
                <Avatar name={names[win.winner] ?? ""} size={28} />
                {t(win.flower_win ? "{who} 花牌胡" : win.self_draw ? "{who} 自摸" : "{who} 胡牌", { who: names[win.winner] })}
              </p>
              {win.loser !== null && win.loser !== undefined && !win.self_draw && (
                <p className="mt-1 text-mist">{t("{who} 放槍", { who: names[win.loser] })}</p>
              )}
            </div>
            {stage >= 1 && (
              <div className="mt-5 flex justify-center gap-[2px] overflow-x-auto pb-1">
                {(win.hand ?? []).map((tile, i) => (
                  <span key={i} className="animate-rise" style={{ animationDelay: `${i * 35}ms` }}>
                    <TileImage id={tile} width={30}
                      className={tile === win.win_tile && i === (win.hand ?? []).lastIndexOf(tile)
                        ? "rounded-md ring-4 ring-gold" : ""} />
                  </span>
                ))}
                {win.melds.map((m, i) => (
                  <span key={i} className="ml-2 flex gap-[1px]">
                    {m.tiles.map((tile, j) => <TileImage key={j} id={tile} width={26} />)}
                  </span>
                ))}
              </div>
            )}
            {stage >= 2 && (
              <div className="mt-5 grid gap-4 sm:grid-cols-[1fr_auto]">
                <ul className="grid grid-cols-2 gap-x-4 gap-y-1">
                  {items.slice(0, shownTai).map((it, i) => (
                    <li key={i} className="flex animate-pop-in justify-between rounded-lg bg-black/20 px-3 py-1">
                      <span>{taiName(it.id, it.name)}</span>
                      <span className="tabular font-black text-gold">{t("{n} 台", { n: it.tai })}</span>
                    </li>
                  ))}
                  {stage >= 3 && !!win.dealer_tai && (
                    <li className="flex animate-pop-in justify-between rounded-lg bg-black/20 px-3 py-1 text-mist">
                      <span>{t("莊家與連莊")}</span><span className="tabular">{t("{n} 台", { n: win.dealer_tai })}</span>
                    </li>
                  )}
                </ul>
                <div className="flex flex-col items-center justify-center rounded-2xl bg-gradient-to-b from-gold/25 to-amber/10 px-6 py-3">
                  <span className="text-sm text-mist">{t("總台數")}</span>
                  <span className={`tabular font-display text-5xl font-black text-gold ${big && stage >= 3 ? "animate-pulse-glow rounded-full" : ""}`}>
                    {runningTai}
                  </span>
                </div>
              </div>
            )}
            {stage >= 3 && (
              <table className="mt-5 w-full animate-rise text-left">
                <tbody>
                  {win.payments.map((p, seat) => (
                    <tr key={seat} className={`border-b border-white/10 ${seat === mySeat ? "font-black" : ""}`}>
                      <td className="flex items-center gap-2 py-1.5"><Avatar name={names[seat] ?? ""} size={22} />{names[seat]}</td>
                      <td className="tabular py-1.5 text-mist">
                        {win.tai_by_payer?.[String(seat)] !== undefined ? t("付 {n} 台", { n: win.tai_by_payer[String(seat)] }) : ""}
                      </td>
                      <td className={`tabular py-1.5 text-right text-lg font-black ${p > 0 ? "text-jade" : p < 0 ? "text-zhong" : "text-mist"}`}>
                        {p > 0 ? `+${p}` : p}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
        {drawn && !win && (
          <div className="text-center">
            <h2 className="inline-block animate-stamp font-display text-6xl font-black text-mist">{t("海底流局")}</h2>
            <p className="mt-2 text-mist">{t("沒有人胡牌，莊家連莊。")}</p>
          </div>
        )}
        {xp > 0 && (stage >= 3 || (drawn && !win)) && (
          <p className="mt-4 animate-pop-in text-center font-black text-cyan">+{xp} XP</p>
        )}
        {gameEnd ? (
          <div className="mt-6">
            <h3 className="text-center font-display text-3xl font-black">{t("最終名次")}</h3>
            <ol className="mt-4 space-y-2">
              {[0, 1, 2, 3].sort((a, b) => gameEnd.ranks[a] - gameEnd.ranks[b]).map((seat, i) => (
                <li key={seat} className={`flex animate-rise items-center justify-between rounded-2xl px-4 py-2 ${
                  seat === mySeat ? "bg-gold/20 ring-1 ring-gold/60" : "bg-black/20"}`} style={{ animationDelay: `${i * 90}ms` }}>
                  <span className="flex items-center gap-3">
                    <span className="text-2xl" aria-hidden="true">{MEDALS[gameEnd.ranks[seat] - 1]}</span>
                    {t("第 {n} 名　{who}", { n: gameEnd.ranks[seat], who: names[seat] })}
                  </span>
                  <span className="tabular font-black">{gameEnd.final_scores[seat]}</span>
                </li>
              ))}
            </ol>
            <div className="mt-6 text-center">
              <Link href="/" className="btn-game px-8 py-3 text-lg"
                style={{ background: "linear-gradient(180deg,#ffb547,#ff7a3d)", ["--btn-lip" as string]: "#b8481c" }}>
                {t("回大廳")}
              </Link>
            </div>
          </div>
        ) : (
          <div className="mt-6 flex items-center justify-between gap-3 text-sm text-mist">
            <span>
              {t("下一手即將開始。")}
              {gameId && (
                <a href={`/replay/${gameId}`} target="_blank" rel="noreferrer" className="ml-3 text-cyan underline">
                  {t("看這手錄影")}
                </a>
              )}
            </span>
            <GameButton variant="ghost" size="sm" onClick={dismiss}>{t("看牌桌")}</GameButton>
          </div>
        )}
      </div>
      {win && <Burst effect={effect} big={big} />}
    </div>
  );
}
