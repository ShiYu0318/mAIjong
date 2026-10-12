"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { Avatar } from "@/components/Game/Avatar";
import { TABLE_CLOTHS } from "@/lib/cosmetics";
import { useT } from "@/lib/i18n";
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
    <div aria-hidden="true" className="pointer-events-none absolute rounded-[28px]"
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
    <span className="block animate-stamp font-display text-6xl font-black"
      style={{
        background: `linear-gradient(180deg, ${colors[0]}, ${colors[1]})`, WebkitBackgroundClip: "text",
        backgroundClip: "text", color: "transparent", WebkitTextStroke: "2px rgb(255 255 255 / 0.9)",
        filter: "drop-shadow(0 6px 0 rgb(0 0 0 / 0.35)) drop-shadow(0 0 18px rgb(255 255 255 / 0.35))",
      }}>
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

/** Seat panels, the centre compass and call stamps, drawn over the canvas. */
export function TableHud({ g, view, names }: { g: TableLayout; view: GameView; names: string[] }) {
  const t = useT();
  const effects = useGame((s) => s.effects);
  const me = view.you ?? 0;
  return (
    <div className="pointer-events-none absolute inset-0">
      {view.players.map((p) => {
        const rel = relSeat(p.seat, me);
        const pos = seatCorner(rel, g);
        const acting = view.acting.includes(p.seat) && view.phase !== "ENDED";
        const name = names[p.seat] ?? `#${p.seat + 1}`;
        if (g.compact) {
          return (
            <Abs key={p.seat} x={pos.x} y={pos.y}>
              <div className={`flex flex-col items-center rounded-xl px-1 py-0.5 ${acting ? "bg-black/60 ring-2 ring-gold" : "bg-black/40"}`}
                aria-label={name}>
                <span className="relative">
                  <Avatar name={name} size={22} active={acting} />
                  <span className="absolute -top-1 -right-2 rounded bg-ivory px-0.5 text-[10px] leading-tight font-black text-ink">
                    {windName(p.seat_wind)}
                  </span>
                </span>
                <span className={`tabular text-[10px] font-black ${p.score > 0 ? "text-jade" : p.score < 0 ? "text-zhong" : "text-mist"}`}>
                  {p.score > 0 ? `+${p.score}` : p.score}
                </span>
                {(view.dealer === p.seat || p.declared_ting) && (
                  <span className="flex gap-0.5 text-[9px] font-black">
                    {view.dealer === p.seat && <span className="rounded bg-zhong px-0.5">{t("莊")}</span>}
                    {p.declared_ting && <span className="rounded bg-pink px-0.5">{t("聽")}</span>}
                  </span>
                )}
              </div>
            </Abs>
          );
        }
        return (
          <Abs key={p.seat} x={pos.x} y={pos.y}>
            <div className={`flex w-[168px] items-center gap-2 rounded-2xl px-2 py-1.5 transition-all duration-300 ${
              acting ? "scale-105 bg-black/55 ring-2 ring-gold shadow-[0_0_24px_rgb(255_204_61/0.45)]" : "bg-black/35"}`}>
              <Avatar name={name} size={34} active={acting} />
              <div className="min-w-0 flex-1 leading-tight">
                <div className="flex items-center gap-1">
                  <span className="rounded-md bg-ivory/90 px-1 text-xs font-black text-ink">{windName(p.seat_wind)}</span>
                  {view.dealer === p.seat && <span className="rounded-md bg-zhong px-1 text-xs font-black">{t("莊")}</span>}
                  {p.declared_ting && <span className="rounded-md bg-pink px-1 text-xs font-black">{t("聽")}</span>}
                </div>
                <div className="truncate text-sm font-bold">{name}</div>
                <div className={`tabular text-xs font-black ${p.score > 0 ? "text-jade" : p.score < 0 ? "text-zhong" : "text-mist"}`}>
                  {p.score > 0 ? `+${p.score}` : p.score}
                </div>
              </div>
            </div>
          </Abs>
        );
      })}
      <Compass g={g} view={view} />
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

function Compass({ g, view }: { g: TableLayout; view: GameView }) {
  const t = useT();
  const deadline = useGame((s) => s.deadline);
  const me = view.you ?? 0;
  const size = Math.max(96, g.L * 0.2);
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (deadline === null) return;
    const id = setInterval(() => setNow(Date.now() / 1000), 250);
    return () => clearInterval(id);
  }, [deadline]);
  const left = deadline === null ? null : Math.max(0, Math.ceil(deadline - now));
  const lastTick = useRef<number | null>(null);
  useEffect(() => {
    if (left !== null && left <= 5 && left > 0 && lastTick.current !== left) sfx.tick();
    lastTick.current = left;
  }, [left]);
  const sides = [
    { rel: 0, style: { bottom: 6, left: "50%", transform: "translateX(-50%)" } },
    { rel: 1, style: { right: 6, top: "50%", transform: "translateY(-50%) rotate(-90deg)" } },
    { rel: 2, style: { top: 6, left: "50%", transform: "translateX(-50%) rotate(180deg)" } },
    { rel: 3, style: { left: 6, top: "50%", transform: "translateY(-50%) rotate(90deg)" } },
  ];
  const ring = 2 * Math.PI * (size * 0.3);
  return (
    <Abs x={g.cx} y={g.cy}>
      <div className="relative rounded-[22%] border border-white/15 shadow-[0_10px_30px_rgb(0_0_0/0.45)]"
        style={{ width: size, height: size, background: "radial-gradient(circle at 50% 35%, #2d3573, #141838)" }}>
        {sides.map(({ rel, style }) => {
          const seat = (me + rel) % 4;
          const p = view.players[seat];
          const on = view.acting.includes(seat) && view.phase !== "ENDED";
          return (
            <span key={rel} className={`absolute font-display font-black transition ${on ? "text-gold drop-shadow-[0_0_8px_rgb(255_204_61/0.9)]" : "text-ivory/45"}`}
              style={{ ...style, fontSize: size * 0.17 }}>
              {windName(p.seat_wind)}
            </span>
          );
        })}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {left !== null ? (
            <>
              <svg className="absolute -rotate-90" width={size * 0.66} height={size * 0.66} viewBox={`0 0 ${size * 0.66} ${size * 0.66}`} aria-hidden="true">
                <circle cx={size * 0.33} cy={size * 0.33} r={size * 0.3} fill="none" stroke="rgb(255 255 255 / 0.12)" strokeWidth={4} />
                <circle cx={size * 0.33} cy={size * 0.33} r={size * 0.3} fill="none" stroke={left <= 5 ? "#ff4d6a" : "#38d0ff"}
                  strokeWidth={4} strokeLinecap="round"
                  strokeDasharray={`${ring * Math.min(1, left / 30)} ${ring}`} />
              </svg>
              <span className={`tabular font-display font-black ${left <= 5 ? "text-zhong" : "text-ivory"}`}
                style={{ fontSize: size * 0.26 }} aria-label={t("剩餘 {n} 秒", { n: left })}>{left}</span>
            </>
          ) : (
            <>
              <span className="font-display font-black text-ivory" style={{ fontSize: size * 0.2 }}>{view.drawable}</span>
              <span className="text-mist" style={{ fontSize: Math.max(10, size * 0.09) }}>{t("剩餘張數")}</span>
            </>
          )}
        </div>
      </div>
    </Abs>
  );
}
