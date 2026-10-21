"use client";

import { TableFelt, TableHud, useTableLayout } from "@/components/Board/TableOverlay";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { type Annotation, ApiError, apiUrl, authToken, games, type GameSummary, type ReplayFrame } from "@/lib/api";
import { actionLabel, describeAction } from "@/lib/actions";
import { localName, taiName, useT } from "@/lib/i18n";
import { windName } from "@/lib/tiles";

const TableCanvas = dynamic(() => import("@/components/Board/TableCanvas").then((m) => m.TableCanvas), { ssr: false });

export default function ReplayPage() {
  const { id } = useParams<{ id: string }>();
  const t = useT();
  const [tableRef, layout] = useTableLayout();
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
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    games.frames(id).then((d) => {
      setFrames(d.frames);
      setGame(d.game);
      return games.annotations(id).then(setNotes).catch(() => undefined);  // only for real games
    }).catch(() => setError("找不到這段錄影。"));  // translated when shown
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
    const timer = setTimeout(() => step(1), 700);
    return () => clearTimeout(timer);
  }, [playing, i, last, step]);

  const names = useMemo(() => (game?.seats ?? []).map((s, k) => (s ? localName(s.name) : t("座位 {n}", { n: k + 1 }))),
    [game, t]);
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

  if (error) return <main className="p-10">{t(error)} <Link href="/" className="underline">{t("回大廳")}</Link></main>;
  if (!frames || !frame || !fixed) {
    return <main className="flex h-dvh items-center justify-center text-mist">{t("載入錄影…")}</main>;
  }

  const decision = frame.decision;
  const ranked = decision
    ? Object.entries(decision.scores).map(([a, v]) => [Number(a), v] as const).sort((a, b) => b[1] - a[1]).slice(0, 5)
    : [];
  const here = notes.filter((n) => n.seq === i);

  return (
    <main className="flex h-dvh flex-col">
      <header className="flex flex-wrap items-center gap-4 border-b border-felt-line px-4 py-2 text-sm">
        <Link href="/" className="font-display text-xl">{t("麥醬")}</Link>
        <span className="text-mist">
          {t("錄影・{wind}風圈第 {n} 手", { wind: windName(game?.round_wind ?? 0), n: (game?.hand_index ?? 0) + 1 })}
        </span>
        <label className="flex items-center gap-2 text-mist">
          {t("視角")}
          <select value={seat} onChange={(e) => setSeat(Number(e.target.value))}
            className="rounded border border-felt-line bg-felt-deep px-2 py-1 text-ivory">
            {names.map((n, k) => <option key={k} value={k}>{n}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2 text-mist">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
          {t("顯示所有手牌")}
        </label>
        <div className="ml-auto flex gap-2">
          <button onClick={async () => {
            setActionError(null);
            try {
              const { url } = await games.replayUrl(id);
              window.location.href = url.startsWith("http") ? url : `${apiUrl()}${url}`;
            } catch {
              setActionError(t("無法下載錄影檔。"));
            }
          }} className="rounded border border-ivory/30 px-3 py-1 hover:bg-ivory/10">{t("下載錄影檔")}</button>
          <button onClick={() => navigator.clipboard?.writeText(window.location.href).then(() => setCopied(true))
            .catch(() => setActionError(t("無法複製連結。")))}
            className="rounded border border-ivory/30 px-3 py-1 hover:bg-ivory/10">{copied ? t("已複製") : t("分享連結")}</button>
        </div>
        {actionError && <p role="alert" className="w-full text-zhong">{actionError}</p>}
      </header>
      <div className="flex min-h-0 flex-1">
        <section ref={tableRef} className="relative min-w-0 flex-1 overflow-hidden">
          {layout && <TableFelt g={layout} />}
          <TableCanvas fixed={fixed} />
          {layout && <TableHud g={layout} view={fixed.view} names={fixed.names} />}
        </section>
        <aside className="hidden w-80 shrink-0 flex-col gap-4 overflow-y-auto border-l border-felt-line p-4 text-sm lg:flex">
          <div>
            <p className="text-mist">{t("第 {i} / {last} 步", { i, last })}</p>
            <p className="mt-1 text-lg">
              {frame.actor === null ? t("開局") : `${names[frame.actor]} ${describeAction(frame.action!)}`}
            </p>
          </div>
          {decision && (
            <div>
              <h2 className="font-display text-xl">{t("AI 的判斷")}{decision.timeout ? t("（逾時代打）") : ""}</h2>
              <ol className="mt-2 space-y-1">
                {ranked.map(([a, v]) => (
                  <li key={a} className={`flex justify-between ${a === decision.chosen ? "text-ivory" : "text-mist"}`}>
                    <span>{actionLabel(a)}{a === decision.chosen ? t("（選擇）") : ""}</span>
                    <span className="tabular">{v.toFixed(2)}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
          {i === last && game?.result && (
            <div>
              <h2 className="font-display text-xl">{t("結果")}</h2>
              <p className="mt-1">
                {game.result.kind === "DRAW" ? t("流局")
                  : t(game.result.self_draw ? "{who} 自摸" : "{who} 胡牌", { who: names[game.result.winner!] })}
              </p>
              <p className="text-mist">
                {(game.result.tai_breakdown ?? []).map((x) => `${taiName(x.id, x.name)} ${x.tai}`).join(t("、"))}
              </p>
            </div>
          )}
          <div>
            <h2 className="font-display text-xl">{t("這一步的筆記")}</h2>
            {here.length === 0 && <p className="mt-1 text-mist">{t("還沒有筆記。")}</p>}
            {here.map((n) => <p key={n.id} className="mt-1"><span className="text-mist">{t("{user}：", { user: localName(n.user) })}</span>{n.note}</p>)}
            {authToken() ? (
              <form className="mt-2 flex gap-2" onSubmit={async (e) => {
                e.preventDefault();
                if (!draft.trim()) return;
                setActionError(null);
                try {
                  const n = await games.annotate(id, i, draft.trim());
                  setNotes([...notes, n]);
                  setDraft("");
                } catch (err) {
                  setActionError(err instanceof ApiError ? err.message : t("無法新增筆記。"));
                }
              }}>
                <input value={draft} onChange={(e) => setDraft(e.target.value.slice(0, 500))} aria-label={t("新增筆記")}
                  className="min-w-0 flex-1 rounded border border-felt-line bg-felt-deep px-2 py-1" placeholder={t("寫下想法")} />
                <button className="rounded border border-ivory/30 px-2">{t("新增")}</button>
              </form>
            ) : <p className="mt-1 text-xs text-mist">{t("登入後可以新增筆記。")}</p>}
          </div>
        </aside>
      </div>
      <footer className="flex items-center gap-3 border-t border-felt-line px-4 py-3">
        <button onClick={() => step(-1)} aria-label={t("上一步")} className="rounded border border-ivory/30 px-3 py-1">‹</button>
        <button onClick={() => setPlaying(!playing)} className="w-16 rounded bg-ivory px-3 py-1 text-ink">
          {playing ? t("暫停") : t("播放")}
        </button>
        <button onClick={() => step(1)} aria-label={t("下一步")} className="rounded border border-ivory/30 px-3 py-1">›</button>
        <input type="range" min={0} max={last} value={i} onChange={(e) => setI(Number(e.target.value))}
          aria-label={t("時間軸")} className="flex-1 accent-ivory" />
        <span className="tabular w-20 text-right text-mist">{i}/{last}</span>
      </footer>
    </main>
  );
}
