"use client";

import Link from "next/link";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Avatar } from "@/components/Game/Avatar";
import { CoinIcon } from "@/components/Game/CoinCounter";
import { GameButton } from "@/components/Game/GameButton";
import { ProgressBar } from "@/components/Game/ProgressBar";
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

/** A number that counts from `from` to `to`. */
function Roll({ to, from = 0, ms = 700, signed = false }: { to: number; from?: number; ms?: number; signed?: boolean }) {
  const [v, setV] = useState(from);
  useEffect(() => {
    const t0 = performance.now();
    let raf = 0;
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / ms);
      setV(Math.round(from + (to - from) * (1 - (1 - k) ** 3)));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [to, from, ms]);
  return <>{signed && v > 0 ? `+${v}` : v}</>;
}

/** The winning hand, face down first, then turned over tile by tile. */
function RevealHand({ hand, winTile, melds }: {
  hand: number[]; winTile: number | null; melds: { tiles: (number | null)[] }[];
}) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (shown >= hand.length) return;
    const id = setTimeout(() => setShown((n) => n + 1), shown === 0 ? 120 : 55);
    return () => clearTimeout(id);
  }, [shown, hand.length]);
  const winIdx = winTile === null ? -1 : hand.lastIndexOf(winTile);
  return (
    <div className="mt-5 flex justify-center gap-[2px] overflow-x-auto pb-1">
      {hand.map((tile, i) => (
        <span key={i} className={i < shown ? "animate-flip-in" : ""}>
          <TileImage id={i < shown ? tile : null} width={30}
            className={i === winIdx && shown >= hand.length
              ? "rounded-md shadow-[0_0_14px_rgb(255_204_61/0.95)] ring-4 ring-gold" : ""} />
        </span>
      ))}
      {melds.map((m, i) => (
        <span key={i} className="ml-2 flex gap-[1px]">
          {m.tiles.map((tile, j) => <TileImage key={j} id={tile} width={26} />)}
        </span>
      ))}
    </div>
  );
}

type Flight = { key: string; x: number; y: number; dy: number; delay: number };

/** Payments table; coins fly from every payer's row to the winner's. */
function Payments({ payments, taiByPayer, winner, names, mySeat }: {
  payments: number[]; taiByPayer?: Record<string, number>; winner: number; names: string[]; mySeat: number | null;
}) {
  const t = useT();
  const rows = useRef<(HTMLTableRowElement | null)[]>([]);
  const box = useRef<HTMLDivElement>(null);
  const [flights, setFlights] = useState<Flight[]>([]);
  useLayoutEffect(() => {
    const root = box.current?.getBoundingClientRect();
    const target = rows.current[winner]?.getBoundingClientRect();
    if (!root || !target) return;
    const out: Flight[] = [];
    payments.forEach((p, seat) => {
      const from = rows.current[seat]?.getBoundingClientRect();
      if (p >= 0 || !from) return;
      for (let k = 0; k < 3; k++) {
        out.push({ key: `${seat}-${k}`, x: from.right - root.left - 80, y: from.top - root.top + from.height / 2 - 10,
          dy: target.top - from.top, delay: k * 0.12 + seat * 0.05 });
      }
    });
    setFlights(out);
    if (out.length) sfx.coin();
  }, [payments, winner]);
  return (
    <div ref={box} className="relative mt-5 animate-rise">
      <table className="w-full text-left">
        <tbody>
          {payments.map((p, seat) => (
            <tr key={seat} ref={(el) => { rows.current[seat] = el; }}
              className={`border-b border-white/10 ${seat === mySeat ? "font-black" : ""} ${seat === winner ? "bg-gold/10" : ""}`}>
              <td className="flex items-center gap-2 py-1.5"><Avatar name={names[seat] ?? ""} size={22} />{names[seat]}</td>
              <td className="tabular py-1.5 text-mist">
                {taiByPayer?.[String(seat)] !== undefined ? t("付 {n} 台", { n: taiByPayer[String(seat)] }) : ""}
              </td>
              <td className={`tabular py-1.5 pr-1 text-right text-lg font-black ${p > 0 ? "text-jade" : p < 0 ? "text-zhong" : "text-mist"}`}>
                <Roll to={p} ms={900} signed />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="pointer-events-none absolute inset-0" aria-hidden="true">
        {flights.map((f) => (
          <span key={f.key} className="absolute animate-coin-fly"
            style={{ left: f.x, top: f.y, animationDelay: `${f.delay}s`,
              ["--dx" as string]: "0px", ["--dy" as string]: `${f.dy}px` }}>
            <CoinIcon size={20} />
          </span>
        ))}
      </div>
    </div>
  );
}

/** Experience bar growing from before the hand, plus today's missions. */
function Rewards() {
  const t = useT();
  const xp = useAccount((s) => s.lastXp);
  const before = useAccount((s) => s.xpBefore);
  const profile = useAccount((s) => s.profile);
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    setGrown(false);
    const id = setTimeout(() => setGrown(true), 150);
    return () => clearTimeout(id);
  }, [before, profile?.xp]);
  if (!profile || xp <= 0) return null;
  const levelled = before !== null && before.level < profile.level;
  // grow from the old value; when the hand crossed a level, fill the old bar to the end
  const value = !grown ? (before?.xp ?? profile.xp) : levelled ? (before?.xp_next ?? 1) : profile.xp;
  const max = !grown || levelled ? (before?.xp_next ?? profile.xp_next) : profile.xp_next;
  return (
    <div className="mt-5 grid animate-rise gap-3 rounded-2xl bg-black/20 p-4 sm:grid-cols-2">
      <div>
        <p className="flex items-baseline justify-between text-sm">
          <span className="font-black text-gold">Lv.{levelled && before ? before.level : profile.level}</span>
          <span className="font-black text-cyan">+{xp} XP</span>
        </p>
        <ProgressBar value={value} max={max} className="mt-1.5" label={t("經驗值")}
          color="linear-gradient(90deg,#38d0ff,#7a5cff)" />
      </div>
      <ul className="space-y-1.5" aria-label={t("今日任務")}>
        {profile.missions.map((m) => (
          <li key={m.id} className="text-xs">
            <span className="flex justify-between">
              <span className={m.progress >= m.target ? "font-black text-jade" : "text-mist"}>
                {m.progress >= m.target ? "✓ " : ""}{t(m.name)}
              </span>
              <span className="tabular text-mist">{Math.min(m.progress, m.target)}/{m.target}</span>
            </span>
            <ProgressBar value={m.progress} max={m.target} className="mt-0.5 !h-1.5"
              color="linear-gradient(90deg,#43e0a3,#16a874)" label={t(m.name)} />
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Shrinking bar until the next hand deals. */
function NextHandBar() {
  const t = useT();
  const at = useGame((s) => s.nextHandAt);
  const [now, setNow] = useState(() => Date.now());
  const [go, setGo] = useState(false);
  const [total, setTotal] = useState(0);
  useEffect(() => {
    if (at === null) return;
    setTotal(Math.max(1, at - Date.now()));
    setGo(false);
    const raf = requestAnimationFrame(() => requestAnimationFrame(() => setGo(true)));
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => { cancelAnimationFrame(raf); clearInterval(id); };
  }, [at]);
  if (at === null) return <span>{t("下一手即將開始。")}</span>;
  const left = Math.max(0, Math.ceil((at - now) / 1000));
  return (
    <span className="flex min-w-40 flex-1 flex-col gap-1">
      <span>{t("下一手 {n} 秒後開始", { n: left })}</span>
      <span className="block h-1.5 overflow-hidden rounded-full bg-black/30" aria-hidden="true">
        <span className="block h-full rounded-full bg-gradient-to-r from-gold to-amber"
          style={{ width: go ? "0%" : "100%", transition: go ? `width ${total}ms linear` : "none" }} />
      </span>
    </span>
  );
}

const MEDALS = ["🥇", "🥈", "🥉", "🎖️"];
// two grey swells for the exhaustive-draw band; animate-wave slides it one period (240px)
const WAVE = "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='80' viewBox='0 0 240 80'%3E%3Cpath d='M0 40 Q30 10 60 40 T120 40 T180 40 T240 40' fill='none' stroke='%23a3a9d6' stroke-width='10' stroke-linecap='round'/%3E%3Cpath d='M0 62 Q30 36 60 62 T120 62 T180 62 T240 62' fill='none' stroke='%23a3a9d6' stroke-opacity='0.5' stroke-width='6'/%3E%3C/svg%3E\")";

export function ResultOverlay({ names }: { names: string[] }) {
  const win = useGame((s) => s.win);
  const drawn = useGame((s) => s.drawn);
  const drawInfo = useGame((s) => s.drawInfo);
  const gameEnd = useGame((s) => s.gameEnd);
  const dismiss = useGame((s) => s.dismissResult);
  const gameId = useGame((s) => s.view?.game_id);
  const mySeat = useGame((s) => s.seat);
  const effect = useAccount((s) => s.profile?.equipped.win_effect) ?? "gold";
  const t = useT();
  const [stage, setStage] = useState(0);
  const [shownTai, setShownTai] = useState(0);

  const items = useMemo(() => win?.tai_breakdown ?? [], [win]);
  const total = items.reduce((n, it) => n + it.tai, 0) + (win?.dealer_tai ?? 0);
  const iWon = win !== null && win.winner === mySeat;

  // staged reveal: stamp → hand turns over → tai lines one by one → payments and rewards
  useEffect(() => {
    setStage(0);
    setShownTai(0);
    if (!win && !drawn) return;
    if (win) (iWon ? sfx.win : sfx.lose)();
    else sfx.lose();
    const reveal = win ? 200 + (win.hand?.length ?? 0) * 55 : 0;
    const timers = [setTimeout(() => setStage(1), 650), setTimeout(() => setStage(2), 650 + reveal)];
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
  const huge = total >= 10;
  const runningTai = items.slice(0, shownTai).reduce((n, it) => n + it.tai, 0)
    + (stage >= 3 ? win?.dealer_tai ?? 0 : 0);

  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center overflow-y-auto bg-felt-deep/80 p-4 backdrop-blur-sm"
      role="dialog" aria-modal="true" aria-label={t("本手結果")}>
      {win && huge && <div className="pointer-events-none fixed inset-0 z-30 animate-flash bg-white" aria-hidden="true" />}
      <div className={`panel relative m-auto w-full max-w-2xl animate-pop-in overflow-hidden p-6 sm:p-8 ${
        big && win ? "shadow-[0_0_60px_rgb(255_204_61/0.45)]" : ""}`}>
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
            {stage >= 1 && <RevealHand hand={win.hand ?? []} winTile={win.win_tile ?? null} melds={win.melds} />}
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
              <Payments payments={win.payments} taiByPayer={win.tai_by_payer} winner={win.winner} names={names} mySeat={mySeat} />
            )}
          </>
        )}
        {drawn && !win && (
          <div className="relative text-center">
            <div className="pointer-events-none absolute inset-x-[-2rem] top-4 h-20 animate-wave opacity-35"
              style={{ backgroundImage: WAVE, backgroundRepeat: "repeat-x" }} aria-hidden="true" />
            <h2 className="relative inline-block animate-stamp font-display text-6xl font-black text-mist">{t("海底流局")}</h2>
            <p className="relative mt-2 text-mist">{t("沒有人胡牌，莊家連莊。")}</p>
            {drawInfo && (
              <ul className="relative mt-5 grid grid-cols-2 gap-2 text-left sm:grid-cols-4">
                {drawInfo.tenpai.map((ready, seat) => (
                  <li key={seat} className={`flex animate-rise items-center gap-2 rounded-xl px-2 py-1.5 ${
                    ready ? "bg-jade/15 ring-1 ring-jade/50" : "bg-black/25"}`} style={{ animationDelay: `${seat * 80}ms` }}>
                    <Avatar name={names[seat] ?? ""} size={22} />
                    <span className="min-w-0 leading-tight">
                      <span className="block truncate text-sm font-bold">{names[seat]}</span>
                      <span className={`text-xs font-black ${ready ? "text-jade" : "text-mist"}`}>
                        {ready ? t("聽牌") : t("未聽")}{drawInfo.declared[seat] ? ` · ${t("已宣告")}` : ""}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {(stage >= 3 || (drawn && !win)) && <Rewards />}
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
              <Link href="/" className="btn-game btn-primary px-8 py-3 text-lg">{t("回大廳")}</Link>
            </div>
          </div>
        ) : (
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-sm text-mist">
            <NextHandBar />
            {gameId && (
              <a href={`/replay/${gameId}`} target="_blank" rel="noreferrer" className="text-cyan underline">
                {t("看這手錄影")}
              </a>
            )}
            <GameButton variant="ghost" size="sm" onClick={dismiss}>{t("看牌桌")}</GameButton>
          </div>
        )}
      </div>
      {win && <Burst effect={effect} big={big} />}
    </div>
  );
}
