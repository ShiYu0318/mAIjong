"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AccountBar } from "@/components/Account/AccountBar";
import { ApiError, type BoardRow, competition, saveTicket, type SeasonInfo } from "@/lib/api";
import { useAccount } from "@/store/accountStore";

const fmtDate = (s: string) => new Date(s).toLocaleDateString("zh-TW");

export default function LeaderboardPage() {
  const router = useRouter();
  const user = useAccount((s) => s.user);
  const [kind, setKind] = useState<"agent" | "human">("agent");
  const [season, setSeason] = useState("current");
  const [seasons, setSeasons] = useState<SeasonInfo[]>([]);
  const [rows, setRows] = useState<BoardRow[]>([]);
  const [current, setCurrent] = useState<SeasonInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    competition.seasons().then(setSeasons).catch(() => undefined);
  }, []);
  useEffect(() => {
    competition.leaderboard(season, kind).then((d) => {
      setRows(d.rows);
      setCurrent(d.season);
    }).catch(() => setError("無法載入排行榜。"));
  }, [season, kind]);

  return (
    <main className="mx-auto max-w-5xl px-5 py-8">
      <div className="flex items-center justify-between">
        <Link href="/" className="text-mist hover:text-ivory">← 大廳</Link>
        <AccountBar />
      </div>
      <h1 className="mt-4 font-display text-5xl">排行榜</h1>
      {current && (
        <p className="mt-2 text-mist">
          {current.status === "ACTIVE" ? "本賽季" : "已結束賽季"}：{fmtDate(current.starts_at)} – {fmtDate(current.ends_at)}
        </p>
      )}
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <div role="tablist" className="flex gap-1">
          {(["agent", "human"] as const).map((k) => (
            <button key={k} role="tab" aria-selected={kind === k} onClick={() => setKind(k)}
              className={`rounded-md px-3 py-1.5 ${kind === k ? "bg-ivory text-ink" : "border border-felt-line text-mist"}`}>
              {k === "agent" ? "AI 代理程式" : "真人玩家"}
            </button>
          ))}
        </div>
        <select aria-label="賽季" value={season} onChange={(e) => setSeason(e.target.value)}
          className="rounded-md border border-felt-line bg-felt-deep px-2 py-1.5">
          {seasons.map((s) => (
            <option key={s.id} value={s.status === "ACTIVE" ? "current" : String(s.id)}>
              {s.status === "ACTIVE" ? "本賽季" : `第 ${s.id} 季（${fmtDate(s.starts_at)}）`}
            </option>
          ))}
        </select>
        {kind === "human" && (
          <button disabled={!user || busy} title={user ? "" : "請先登入"}
            onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                const j = await competition.joinHumanArena();
                saveTicket(j.room.room_id, j);
                router.push(`/room/${j.room.room_id}`);
              } catch (e) {
                setError(e instanceof ApiError ? e.message : "無法加入競技場");
                setBusy(false);
              }
            }}
            className="ml-auto rounded-lg bg-zhong px-4 py-2 text-ivory disabled:opacity-50">
            {user ? (busy ? "配對中…" : "挑戰 AI 競技場") : "登入後可挑戰 AI 競技場"}
          </button>
        )}
      </div>
      {error && <p role="alert" className="mt-4 text-zhong">{error}</p>}
      <div className="mt-6 overflow-x-auto">
        <table className="w-full min-w-[640px] text-left">
          <thead className="text-sm text-mist">
            <tr className="border-b border-felt-line">
              <th className="py-2 font-normal">名次</th><th className="font-normal">名稱</th>
              <th className="font-normal">作者</th><th className="font-normal">rating</th>
              <th className="font-normal">場數</th><th className="font-normal">第一名率</th>
              <th className="font-normal">平均名次</th>
            </tr>
          </thead>
          <tbody className="tabular">
            {rows.length === 0 && <tr><td colSpan={7} className="py-6 text-mist">這一季還沒有紀錄。</td></tr>}
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-felt-line/50">
                <td className="py-2">{r.rank}</td>
                <td>{kind === "agent" ? <Link href={`/agents/${r.id}`} className="underline">{r.name}{r.version && r.version > 1 ? ` v${r.version}` : ""}</Link> : r.name}</td>
                <td className="text-mist">{r.author}</td>
                <td>{r.elo.toFixed(0)}</td>
                <td>{r.games}</td>
                <td>{(r.first_rate * 100).toFixed(1)}%</td>
                <td>{r.avg_place ? r.avg_place.toFixed(2) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
