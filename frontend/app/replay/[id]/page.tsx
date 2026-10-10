"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { type Annotation, API_URL, authToken, games, type GameSummary, type ReplayFrame } from "@/lib/api";
import { actionLabel, describeAction } from "@/lib/actions";
import { WINDS } from "@/lib/tiles";

const TableCanvas = dynamic(() => import("@/components/Board/TableCanvas").then((m) => m.TableCanvas), { ssr: false });

export default function ReplayPage() {
  const { id } = useParams<{ id: string }>();
  const [frames, setFrames] = useState<ReplayFrame[] | null>(null);
  const [game, setGame] = useState<GameSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [seat, setSeat] = useState(0);
  const [showAll, setShowAll] = useState(true);
  const [notes, setNotes] = useState<Annotation[]>([]);
  const [draft, setDraft] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    games.frames(id).then((d) => {
      setFrames(d.frames);
      setGame(d.game);
    }).catch(() => setError("找不到這段錄影。"));
    games.annotations(id).then(setNotes).catch(() => undefined);
  }, [id]);

  const last = frames ? frames.length - 1 : 0;
  const step = useCallback((d: number) => setI((x) => Math.max(0, Math.min(last, x + d))), [last]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === "INPUT") return;
      if (e.key === "ArrowRight") step(1);
      if (e.key === "ArrowLeft") step(-1);
      if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step]);

  useEffect(() => {
    if (!playing) return;
    if (i >= last) { setPlaying(false); return; }
    const t = setTimeout(() => step(1), 700);
    return () => clearTimeout(t);
  }, [playing, i, last, step]);

  const names = useMemo(() => (game?.seats ?? []).map((s, k) => s?.name ?? `座位${k + 1}`), [game]);
  const frame = frames?.[i];
  const fixed = useMemo(() => {
    if (!frame) return undefined;
    const view = {
      ...frame.view,
      you: seat,
      players: frame.view.players.map((p) => (showAll || p.seat === seat ? p : { ...p, hand: null })),
    };
    return { view, names };
  }, [frame, seat, showAll, names]);

  if (error) return <main className="p-10">{error} <Link href="/" className="underline">回大廳</Link></main>;
  if (!frames || !frame || !fixed) return <main className="flex h-dvh items-center justify-center text-mist">載入錄影…</main>;

  const decision = frame.decision;
  const ranked = decision
    ? Object.entries(decision.scores).map(([a, v]) => [Number(a), v] as const).sort((a, b) => b[1] - a[1]).slice(0, 5)
    : [];
  const here = notes.filter((n) => n.seq === i);

  return (
    <main className="flex h-dvh flex-col">
      <header className="flex flex-wrap items-center gap-4 border-b border-felt-line px-4 py-2 text-sm">
        <Link href="/" className="font-display text-xl">麥醬</Link>
        <span className="text-mist">錄影・{WINDS[game?.round_wind ?? 0]}風圈第 {(game?.hand_index ?? 0) + 1} 手</span>
        <label className="flex items-center gap-2 text-mist">
          視角
          <select value={seat} onChange={(e) => setSeat(Number(e.target.value))}
            className="rounded border border-felt-line bg-felt-deep px-2 py-1 text-ivory">
            {names.map((n, k) => <option key={k} value={k}>{n}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2 text-mist">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
          顯示所有手牌
        </label>
        <div className="ml-auto flex gap-2">
          <button onClick={async () => {
            const { url } = await games.replayUrl(id);
            window.location.href = url.startsWith("http") ? url : `${API_URL}${url}`;
          }} className="rounded border border-ivory/30 px-3 py-1 hover:bg-ivory/10">下載錄影檔</button>
          <button onClick={() => navigator.clipboard?.writeText(window.location.href).then(() => setCopied(true))}
            className="rounded border border-ivory/30 px-3 py-1 hover:bg-ivory/10">{copied ? "已複製" : "分享連結"}</button>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        <section className="relative min-w-0 flex-1">
          <TableCanvas fixed={fixed} />
        </section>
        <aside className="hidden w-80 shrink-0 flex-col gap-4 overflow-y-auto border-l border-felt-line p-4 text-sm lg:flex">
          <div>
            <p className="text-mist">第 {i} / {last} 步</p>
            <p className="mt-1 text-lg">
              {frame.actor === null ? "開局" : `${names[frame.actor]} ${describeAction(frame.action!)}`}
            </p>
          </div>
          {decision && (
            <div>
              <h2 className="font-display text-xl">AI 的判斷{decision.timeout ? "（逾時代打）" : ""}</h2>
              <ol className="mt-2 space-y-1">
                {ranked.map(([a, v]) => (
                  <li key={a} className={`flex justify-between ${a === decision.chosen ? "text-ivory" : "text-mist"}`}>
                    <span>{actionLabel(a)}{a === decision.chosen ? "（選擇）" : ""}</span>
                    <span className="tabular">{v.toFixed(2)}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
          {i === last && game?.result && (
            <div>
              <h2 className="font-display text-xl">結果</h2>
              <p className="mt-1">
                {game.result.kind === "DRAW" ? "流局" : `${names[game.result.winner!]} ${game.result.self_draw ? "自摸" : "胡牌"}`}
              </p>
              <p className="text-mist">{(game.result.tai_breakdown ?? []).map((t) => `${t.name} ${t.tai}`).join("、")}</p>
            </div>
          )}
          <div>
            <h2 className="font-display text-xl">這一步的筆記</h2>
            {here.length === 0 && <p className="mt-1 text-mist">還沒有筆記。</p>}
            {here.map((n) => <p key={n.id} className="mt-1"><span className="text-mist">{n.user}：</span>{n.note}</p>)}
            {authToken() ? (
              <form className="mt-2 flex gap-2" onSubmit={async (e) => {
                e.preventDefault();
                if (!draft.trim()) return;
                const n = await games.annotate(id, i, draft.trim());
                setNotes([...notes, n]);
                setDraft("");
              }}>
                <input value={draft} onChange={(e) => setDraft(e.target.value.slice(0, 500))} aria-label="新增筆記"
                  className="min-w-0 flex-1 rounded border border-felt-line bg-felt-deep px-2 py-1" placeholder="寫下想法" />
                <button className="rounded border border-ivory/30 px-2">新增</button>
              </form>
            ) : <p className="mt-1 text-xs text-mist">登入後可以新增筆記。</p>}
          </div>
        </aside>
      </div>
      <footer className="flex items-center gap-3 border-t border-felt-line px-4 py-3">
        <button onClick={() => step(-1)} aria-label="上一步" className="rounded border border-ivory/30 px-3 py-1">‹</button>
        <button onClick={() => setPlaying(!playing)} className="w-16 rounded bg-ivory px-3 py-1 text-ink">
          {playing ? "暫停" : "播放"}
        </button>
        <button onClick={() => step(1)} aria-label="下一步" className="rounded border border-ivory/30 px-3 py-1">›</button>
        <input type="range" min={0} max={last} value={i} onChange={(e) => setI(Number(e.target.value))}
          aria-label="時間軸" className="flex-1 accent-ivory" />
        <span className="tabular w-20 text-right text-mist">{i}/{last}</span>
      </footer>
    </main>
  );
}
