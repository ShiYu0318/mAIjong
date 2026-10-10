"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { TileImage } from "@/components/Hand/TileImage";
import { type Analysis, ApiError, type MeldInput, tutor } from "@/lib/api";
import { isNumber, rankOf, tileName } from "@/lib/tiles";

type Mode = "hand" | "PON" | "CHI" | "AN_KONG";
const MODES: { v: Mode; label: string }[] = [
  { v: "hand", label: "加入手牌" },
  { v: "PON", label: "加一組碰" },
  { v: "CHI", label: "加一組吃（點順子最小張）" },
  { v: "AN_KONG", label: "加一組暗槓" },
];
const PICKER = Array.from({ length: 34 }, (_, i) => i);

function shantenText(sh: number) {
  return sh < 0 ? "已胡牌" : sh === 0 ? "聽牌" : `${sh} 向聽`;
}

export default function AnalyzePage() {
  const [hand, setHand] = useState<number[]>([]);
  const [melds, setMelds] = useState<MeldInput[]>([]);
  const [mode, setMode] = useState<Mode>("hand");
  const [result, setResult] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  const counts = new Map<number, number>();
  for (const t of [...hand, ...melds.flatMap((m) => m.tiles)]) counts.set(t, (counts.get(t) ?? 0) + 1);
  const left = (t: number) => 4 - (counts.get(t) ?? 0);
  const need = 3 * (5 - melds.length);

  const add = (t: number) => {
    setError(null);
    if (mode === "hand") {
      if (left(t) < 1 || hand.length >= need + 2) return;
      setHand([...hand, t].sort((a, b) => a - b));
    } else if (mode === "PON" && left(t) >= 3 && melds.length < 5) {
      setMelds([...melds, { type: "PON", tiles: [t, t, t] }]);
    } else if (mode === "AN_KONG" && left(t) >= 4 && melds.length < 5) {
      setMelds([...melds, { type: "AN_KONG", tiles: [t, t, t, t] }]);
    } else if (mode === "CHI" && isNumber(t) && rankOf(t) <= 7 && [t, t + 1, t + 2].every((x) => left(x) >= 1) && melds.length < 5) {
      setMelds([...melds, { type: "CHI", tiles: [t, t + 1, t + 2] }]);
    }
  };

  useEffect(() => {
    if (hand.length !== need + 1 && hand.length !== need + 2) {
      setResult(null);
      return;
    }
    let alive = true;
    tutor.analyze(hand, melds).then((r) => alive && setResult(r)).catch((e) => {
      if (alive) setError(e instanceof ApiError ? e.message : "連不上伺服器");
    });
    return () => {
      alive = false;
    };
  }, [hand, melds, need]);

  return (
    <main className="mx-auto max-w-5xl px-5 py-10">
      <Link href="/tutor" className="text-mist hover:text-ivory">← AI 教練</Link>
      <h1 className="mt-4 font-display text-5xl">手牌分析</h1>
      <p className="mt-3 text-mist">點下方的牌組出手牌。湊滿 {need + 1} 張看聽牌與進張；{need + 2} 張則分析每張牌該不該打。</p>

      <div className="mt-6 flex flex-wrap gap-2" role="radiogroup" aria-label="輸入模式">
        {MODES.map((m) => (
          <button key={m.v} role="radio" aria-checked={mode === m.v} onClick={() => setMode(m.v)}
            className={`rounded-md border px-3 py-1.5 text-sm ${mode === m.v ? "border-ivory bg-ivory/15" : "border-felt-line text-mist"}`}>
            {m.label}
          </button>
        ))}
      </div>
      <div className="mt-4 grid w-fit grid-cols-9 gap-1">
        {PICKER.map((t) => (
          <button key={t} onClick={() => add(t)} disabled={left(t) < 1} aria-label={`加入 ${tileName(t)}`}
            className="disabled:opacity-30">
            <TileImage id={t} width={36} />
          </button>
        ))}
      </div>

      <section className="mt-8">
        <div className="flex items-baseline gap-4">
          <h2 className="font-display text-2xl">你的牌（{hand.length} 張）</h2>
          <button onClick={() => { setHand([]); setMelds([]); }} className="text-sm text-mist underline">清空</button>
        </div>
        <div className="mt-3 flex min-h-14 flex-wrap items-end gap-[2px]">
          {hand.map((t, i) => (
            <button key={i} onClick={() => setHand(hand.filter((_, j) => j !== i))} aria-label={`移除 ${tileName(t)}`}>
              <TileImage id={t} width={40} />
            </button>
          ))}
          {melds.map((m, i) => (
            <button key={`m${i}`} onClick={() => setMelds(melds.filter((_, j) => j !== i))}
              className="ml-3 flex gap-[1px]" aria-label="移除這組副露">
              {m.tiles.map((t, j) => <TileImage key={j} id={m.type === "AN_KONG" && (j === 0 || j === 3) ? null : t} width={32} />)}
            </button>
          ))}
        </div>
      </section>

      {error && <p role="alert" className="mt-4 text-zhong">{error}</p>}
      {result && (
        <section className="mt-8 border-t border-felt-line pt-6">
          <p className="font-display text-3xl">{shantenText(result.shanten)}</p>
          {result.waits && (
            <ul className="mt-4 flex flex-wrap gap-4">
              {result.waits.map((w) => (
                <li key={w.tile} className="flex items-center gap-2">
                  <TileImage id={w.tile} width={34} /> <span className="tabular">{w.tai ?? 0} 台</span>
                </li>
              ))}
            </ul>
          )}
          {result.uke_ire && !result.waits && (
            <p className="mt-3 text-mist">有效進張 {result.uke_count} 張：{result.uke_ire.map(tileName).join("、")}</p>
          )}
          {result.discards && (
            <table className="mt-4 w-full text-left text-sm">
              <thead className="text-mist">
                <tr><th className="py-2">打出</th><th>之後</th><th>進張</th><th>聽牌時的台數</th></tr>
              </thead>
              <tbody>
                {result.discards.map((d, i) => (
                  <tr key={d.tile} className={`border-t border-felt-line ${i === 0 ? "bg-jade/15" : ""}`}>
                    <td className="py-1.5"><TileImage id={d.tile} width={28} /></td>
                    <td>{shantenText(d.shanten_after)}</td>
                    <td className="tabular">{d.uke_count} 張</td>
                    <td className="tabular">{d.best_tai ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </main>
  );
}
