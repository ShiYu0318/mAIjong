"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { Avatar } from "@/components/Game/Avatar";
import { TABLE_CLOTHS } from "@/lib/cosmetics";
import { splitLevel, useT } from "@/lib/i18n";
import type { GameView } from "@/lib/protocol";
import { sfx } from "@/lib/sfx";
import { type TableLayout, relSeat, seatCorner, seatStamp, tableLayout } from "@/lib/tableLayout";
import { windName } from "@/lib/tiles";
import { useAccount } from "@/store/accountStore";
import { useGame } from "@/store/gameStore";

/** Tracks the size of the table area so the DOM layers line up with the Pixi canvas.
 * Returns a callback ref: the table element only appears once the game starts. */
export function useTableLayout(): [(el: HTMLElement | null) => void, TableLayout | null] {
  const [el, setEl] = useState<HTMLElement | null>(null);
  const [g, setG] = useState<TableLayout | null>(null);
  useEffect(() => {
    if (!el) return;
    const update = () => setG(tableLayout(el.clientWidth, el.clientHeight));
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [el]);
  return [setEl, g];
}

/** Felt cloth with a wooden rim, drawn under the canvas. */
export function TableFelt({ g }: { g: TableLayout }) {
  const cloth = useAccount((s) => s.profile?.equipped.table) ?? "emerald";
  const [a, b] = TABLE_CLOTHS[cloth] ?? TABLE_CLOTHS.emerald;
  const pad = 14;
  return (
    <div data-table-felt aria-hidden="true" className="pointer-events-none absolute rounded-[28px]"
      style={{
        left: g.cx - g.L / 2 - pad, top: g.cy - g.L / 2 - pad, width: g.L + pad * 2, height: g.L + pad * 2,
        background: "linear-gradient(145deg, #8a5a32, #5a3517 55%, #3d230e)",
        boxShadow: "0 30px 60px rgb(5 6 25 / 0.6), inset 0 2px 0 rgb(255 255 255 / 0.25)",
      }}>
      <div className="absolute rounded-[18px]"
        style={{
          inset: pad, background: `radial-gradient(circle at 50% 45%, ${a} 0%, ${b} 85%)`,
          boxShadow: "inset 0 0 50px rgb(0 0 0 / 0.45), inset 0 0 0 2px rgb(0 0 0 / 0.25)",
        }}>
        <div className="absolute inset-0 rounded-[18px] opacity-[0.08]"
          style={{ backgroundImage: "repeating-linear-gradient(45deg, #fff 0 1px, transparent 1px 7px)" }} />
      </div>
    </div>
  );
}

const STAMP_TEXT: Record<string, { text: string; colors: [string, string] }> = {
  PON: { text: "碰", colors: ["#7dffb5", "#16a874"] },
  CHI: { text: "吃", colors: ["#9fd0ff", "#2f63e8"] },
  KONG: { text: "槓", colors: ["#ffd98a", "#ff7a3d"] },
  TING: { text: "聽", colors: ["#ffb3d1", "#e83f88"] },
  FLOWER: { text: "補花", colors: ["#ffe8a3", "#d99a1b"] },
  FLOWER_ROB: { text: "搶花", colors: ["#ffe8a3", "#d99a1b"] },
};

function Stamp({ text, colors }: { text: string; colors: [string, string] }) {
  return (
    <span className="call-plaque animate-stamp font-tile"
      style={{ borderColor: colors[1] }}>
      {text}
    </span>
  );
}

function Abs({ x, y, children, className = "" }: { x: number; y: number; children: ReactNode; className?: string }) {
  return (
    <div className={`absolute -translate-x-1/2 -translate-y-1/2 ${className}`} style={{ left: x, top: y }}>
      {children}
    </div>
  );
}

type Clock = { left: number; frac: number; mine: boolean };

/** Seconds left for every acting seat: the server deadline for us, and for everyone else
 * the room's time limit counted from the moment their turn started. */
function useTurnClock(view: GameView, timeLimit: number | null): Record<number, Clock> {
  const deadline = useGame((s) => s.deadline);
  const me = view.you ?? -1;
  const [now, setNow] = useState(() => Date.now() / 1000);
  const starts = useRef(new Map<number, number>());
  const total = useRef<{ deadline: number; total: number } | null>(null);
  const actingKey = view.phase === "ENDED" ? "" : view.acting.join(",");
  useEffect(() => {
    const t0 = Date.now() / 1000;
    const acting = new Set(actingKey ? actingKey.split(",").map(Number) : []);
    for (const seat of [...starts.current.keys()]) if (!acting.has(seat)) starts.current.delete(seat);
    for (const seat of acting) if (!starts.current.has(seat)) starts.current.set(seat, t0);
    setNow(t0);
  }, [actingKey]);
  const ticking = actingKey !== "" && (deadline !== null || timeLimit !== null);
  useEffect(() => {
    if (!ticking) return;
    const id = setInterval(() => setNow(Date.now() / 1000), 250);
    return () => clearInterval(id);
  }, [ticking]);
  const out: Record<number, Clock> = {};
  if (deadline !== null && view.acting.includes(me)) {
    if (total.current?.deadline !== deadline) {
      total.current = { deadline, total: Math.max(1, deadline - Date.now() / 1000) };
    }
    const left = Math.max(0, deadline - now);
    out[me] = { left: Math.ceil(left), frac: Math.min(1, left / total.current.total), mine: true };
  }
  if (timeLimit) {
    for (const [seat, t0] of starts.current) {
      if (seat === me) continue;
      const left = Math.max(0, timeLimit - (now - t0));
      out[seat] = { left: Math.ceil(left), frac: left / timeLimit, mine: false };
    }
  }
  return out;
}

const ringColor = (c: Clock | undefined) => (c && c.left <= 5 ? "#ff4d6a" : "#38d0ff");

/** Seat panels, the centre compass and call stamps, drawn over the canvas. */
export function TableHud({ g, view, names, timeLimit = null }: {
  g: TableLayout; view: GameView; names: string[]; timeLimit?: number | null;
}) {
  const t = useT();
  const effects = useGame((s) => s.effects);
  const clocks = useTurnClock(view, timeLimit);
  const me = view.you ?? 0;
  return (
    <div className="pointer-events-none absolute inset-0">
      {view.players.map((p) => {
        const rel = relSeat(p.seat, me);
        const pos = seatCorner(rel, g);
        const acting = view.acting.includes(p.seat) && view.phase !== "ENDED";
        const clock = acting ? clocks[p.seat] : undefined;
        const name = names[p.seat] ?? `#${p.seat + 1}`;
        return (
          <Abs key={p.seat} x={pos.x} y={pos.y}>
            <div data-seat-panel={rel} aria-label={name} className={`flex items-center gap-2 rounded-xl px-2 py-1.5 transition-colors duration-300 ${
              acting ? "bg-black/65 ring-1 ring-gold" : "bg-black/40"}`} style={{ width: g.compact ? 120 : 168, height: g.compact ? 32 : 60 }}>
              <Avatar name={name} size={g.compact ? 22 : 34} active={acting && !clock} progress={clock?.frac} ringColor={ringColor(clock)} />
              <div className="min-w-0 flex-1 leading-tight">
                <div className="flex items-center gap-1">
                  <span className="rounded-md bg-ivory/90 px-1 text-xs font-black text-ink">{windName(p.seat_wind)}</span>
                  {g.compact && <span className="min-w-0 truncate text-[10px] font-bold">{splitLevel(name).base}</span>}
                  {view.dealer === p.seat && <span className="rounded-md bg-zhong px-1 text-xs font-black">{t("莊")}</span>}
                  {p.declared_ting && <span className="rounded-md bg-pink px-1 text-xs font-black">{t("聽")}</span>}
                  {clock && !clock.mine && (
                    <span className={`tabular ml-auto text-xs font-black ${clock.left <= 5 ? "text-zhong" : "text-cyan"}`}>{clock.left}</span>
                  )}
                </div>
                <div className={`flex min-w-0 items-center gap-1 ${g.compact ? "hidden" : ""}`}>
                  {/* a bot's name is short and must stay whole; a long level tag gives way */}
                  <span className={`text-sm font-bold ${splitLevel(name).level ? "shrink-0" : "truncate"}`}>
                    {splitLevel(name).base}
                  </span>
                  {splitLevel(name).level && (
                    <span className="min-w-0 truncate rounded bg-white/15 px-1 text-[10px] font-bold text-ivory-dim">
                      {splitLevel(name).level}
                    </span>
                  )}
                </div>
                <div className={`tabular text-xs font-black ${p.score > 0 ? "text-jade" : p.score < 0 ? "text-zhong" : "text-mist"}`}>
                  {p.score > 0 ? `+${p.score}` : p.score}
                </div>
              </div>
            </div>
          </Abs>
        );
      })}
      <Compass g={g} view={view} clocks={clocks} />
      {effects.map((e) => {
        const rel = relSeat(e.seat, me);
        const pos = seatStamp(rel, g);
        const st = STAMP_TEXT[e.kind];
        return st ? (
          <Abs key={e.id} x={pos.x} y={pos.y} className={g.compact ? "scale-75" : ""}>
            <Stamp text={t(st.text)} colors={st.colors} />
          </Abs>
        ) : null;
      })}
    </div>
  );
}

function Compass({ g, view, clocks }: {
  g: TableLayout; view: GameView; clocks: Record<number, Clock>;
}) {
  const t = useT();
  const me = view.you ?? 0;
  const size = Math.max(48, g.L * 0.2); // larger would cover the first river rows
  // our own countdown wins; otherwise show whoever is on the clock
  const clock = clocks[me] ?? view.acting.map((s) => clocks[s]).find(Boolean);
  const left = clock?.left ?? null;
  const lastTick = useRef<number | null>(null);
  useEffect(() => {
    if (clock?.mine && left !== null && left <= 5 && left > 0 && lastTick.current !== left) sfx.tick();
    lastTick.current = left;
  }, [left, clock?.mine]);
  const sides = [
    { rel: 0, style: { bottom: 6, left: "50%", transform: "translateX(-50%)" } },
    { rel: 1, style: { right: 6, top: "50%", transform: "translateY(-50%) rotate(-90deg)" } },
    { rel: 2, style: { top: 6, left: "50%", transform: "translateX(-50%) rotate(180deg)" } },
    { rel: 3, style: { left: 6, top: "50%", transform: "translateY(-50%) rotate(90deg)" } },
  ];
  // ring stays inside the four wind letters on the compass edge
  const rr = size * (g.compact ? 0.22 : 0.27);
  const ring = 2 * Math.PI * rr;
  const small = Math.max(10, size * 0.085);
  return (
    <Abs x={g.cx} y={g.cy}>
      <div className="relative rounded-[22%] border border-white/15 shadow-[0_10px_30px_rgb(0_0_0/0.45)]"
        style={{ width: size, height: size, background: "radial-gradient(circle at 50% 35%, #2d3573, #141838)" }}>
        {sides.map(({ rel, style }) => {
          const seat = (me + rel) % 4;
          const p = view.players[seat];
          const on = view.acting.includes(seat) && view.phase !== "ENDED";
          return (
            <span key={rel} className={`absolute font-display leading-none font-black transition ${on ? "text-gold drop-shadow-[0_0_8px_rgb(255_204_61/0.9)]" : "text-ivory/45"} ${
              view.dealer === seat ? "rounded-md px-0.5 ring-2 ring-zhong/80" : ""}`}
              style={{ ...style, fontSize: size * (g.compact ? 0.13 : 0.17) }} title={view.dealer === seat ? t("莊") : undefined}>
              {windName(p.seat_wind)}
            </span>
          );
        })}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {left !== null && clock ? (
            <>
              <svg className="absolute -rotate-90" width={rr * 2 + 6} height={rr * 2 + 6} viewBox={`0 0 ${rr * 2 + 6} ${rr * 2 + 6}`} aria-hidden="true">
                <circle cx={rr + 3} cy={rr + 3} r={rr} fill="none" stroke="rgb(255 255 255 / 0.12)" strokeWidth={4} />
                <circle cx={rr + 3} cy={rr + 3} r={rr} fill="none" stroke={ringColor(clock)}
                  strokeWidth={4} strokeLinecap="round" strokeDasharray={`${ring * clock.frac} ${ring}`}
                  className="transition-[stroke-dasharray] duration-300 ease-linear" />
              </svg>
              <span className={`tabular font-display leading-none font-black ${left <= 5 ? "text-zhong" : "text-ivory"}`}
                style={{ fontSize: size * 0.21 }} aria-label={t("剩餘 {n} 秒", { n: left })}>{left}</span>
              <span className="tabular mt-0.5 text-mist" style={{ fontSize: Math.max(9, size * 0.075) }}>
                {t("餘 {n} 張", { n: view.drawable })}
              </span>
            </>
          ) : (
            <>
              <span className="font-display font-black text-ivory" style={{ fontSize: size * 0.2 }}>{view.drawable}</span>
              <span className="text-mist" style={{ fontSize: small }}>{t("剩餘張數")}</span>
            </>
          )}
        </div>
      </div>
    </Abs>
  );
}
