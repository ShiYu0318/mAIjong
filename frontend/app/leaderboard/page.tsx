"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Avatar } from "@/components/Game/Avatar";
import { GameButton } from "@/components/Game/GameButton";
import { PageShell, PillTabs } from "@/components/Game/PageShell";
import { Panel } from "@/components/Game/Panel";
import { RankBadge } from "@/components/Game/RankBadge";
import { type AiVsHumans, ApiError, type BoardRow, competition, saveTicket, type SeasonInfo } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { sfx } from "@/lib/sfx";
import { useAccount } from "@/store/accountStore";
import { GameIcon } from "@/components/Game/GameIcon";
import { Medal } from "@/components/Game/Medal";
import { Swords, Trophy } from "lucide-react";

const fmtDate = (s: string) => new Date(s).toLocaleDateString("zh-TW");
type Kind = "agent" | "human";
const PODIUM = [
  { order: "order-2", height: "h-36", tone: "from-[#ffe27a] to-[#d39a12]" },
  { order: "order-1", height: "h-28", tone: "from-[#e3e8f4] to-[#8a93ad]" },
  { order: "order-3", height: "h-24", tone: "from-[#f0a777] to-[#8a4f2a]" },
];

export default function LeaderboardPage() {
  const router = useRouter();
  const t = useT();
  const user = useAccount((s) => s.user);
  const [kind, setKind] = useState<Kind>("agent");
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
    }).catch(() => setError(t("無法載入排行榜。")));
  }, [season, kind, t]);

  const nameOf = (r: BoardRow) => kind === "agent"
    ? <Link href={`/agents/${r.id}`} className="hover:underline">{r.name}{r.version && r.version > 1 ? ` v${r.version}` : ""}</Link>
    : r.name;

  return (
    <PageShell icon={<GameIcon icon={Trophy} tone="gold" size={60} />} title={t("排行榜")}
      subtitle={current ? `${current.status === "ACTIVE" ? t("本賽季") : t("已結束賽季")}：${fmtDate(current.starts_at)} – ${fmtDate(current.ends_at)}` : undefined}
      actions={kind === "human" && (
        <GameButton variant="danger" size="lg" disabled={!user || busy} onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            const j = await competition.joinHumanArena();
            saveTicket(j.room.room_id, j);
            router.push(`/room/${j.room.room_id}`);
          } catch (e) {
            sfx.error();
            setError(e instanceof ApiError ? e.message : t("無法加入競技場"));
            setBusy(false);
          }
        }}>
          <Swords size={22} strokeWidth={2.6} aria-hidden="true" />{busy ? t("配對中…") : t("挑戰 AI 競技場")}
        </GameButton>
      )}>
      <div className="flex flex-wrap items-center gap-4">
        <PillTabs<Kind> value={kind} onChange={(v) => { sfx.tap(); setKind(v); }}
          tabs={[{ id: "agent", label: t("AI 代理程式") }, { id: "human", label: t("真人玩家") }]} />
        <select aria-label={t("賽季")} value={season} onChange={(e) => setSeason(e.target.value)}
          className="rounded-full border border-white/10 bg-black/25 px-4 py-2 font-bold">
          {seasons.map((s) => (
            <option key={s.id} value={s.status === "ACTIVE" ? "current" : String(s.id)}>
              {s.status === "ACTIVE" ? t("本賽季") : t("第 {n} 季（{date}）", { n: s.id, date: fmtDate(s.starts_at) })}
            </option>
          ))}
        </select>
      </div>
      {error && <p role="alert" className="mt-4 font-bold text-zhong">{error}</p>}

      {rows.length >= 1 && (
        <section className="mt-8 flex items-end justify-center gap-4" aria-label={t("前三名")}>
          {rows.slice(0, 3).map((r, i) => (
            <div key={r.id} className={`flex w-40 animate-rise flex-col items-center ${PODIUM[i].order}`}
              style={{ animationDelay: `${i * 120}ms` }}>
              <Medal place={i + 1} size={44} />
              <Avatar name={r.name} size={i === 0 ? 64 : 52} />
              <span className="mt-1 max-w-full truncate font-black">{nameOf(r)}</span>
              {kind === "human" && <RankBadge rating={r.elo} size={20} />}
              <div className={`mt-2 flex w-full ${PODIUM[i].height} items-start justify-center rounded-t-2xl bg-gradient-to-b pt-3 font-display text-2xl font-black text-ink shadow-inner ${PODIUM[i].tone}`}>
                {r.elo.toFixed(0)}
              </div>
            </div>
          ))}
        </section>
      )}

      {kind === "human" && <AiVsHumansCard />}

      <Panel className="mt-6 overflow-x-auto p-0">
        <table className="w-full min-w-[640px] text-left">
          <thead className="text-sm text-mist">
            <tr className="border-b border-white/10">
              <th className="px-4 py-3 font-bold">{t("名次")}</th><th className="font-bold">{t("名稱")}</th>
              <th className="font-bold">{t("作者")}</th><th className="font-bold">rating</th>
              <th className="font-bold">{t("場數")}</th><th className="font-bold">{t("第一名率")}</th>
              <th className="pr-4 font-bold">{t("平均名次")}</th>
            </tr>
          </thead>
          <tbody className="tabular">
            {rows.length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-mist">{t("這一季還沒有紀錄。")}</td></tr>}
            {rows.map((r) => (
              <tr key={r.id} className={`border-b border-white/5 ${user && kind === "human" && r.id === user.id ? "bg-gold/10" : "hover:bg-white/5"}`}>
                <td className="px-4 py-2.5 font-black">{r.rank}</td>
                <td>
                  <span className="flex items-center gap-2">
                    <Avatar name={r.name} size={26} />
                    {nameOf(r)}
                    {kind === "human" && <RankBadge rating={r.elo} size={18} showName={false} />}
                  </span>
                </td>
                <td className="text-mist">{r.author}</td>
                <td className="font-black">{r.elo.toFixed(0)}</td>
                <td>{r.games}</td>
                <td>{(r.first_rate * 100).toFixed(1)}%</td>
                <td className="pr-4">{r.avg_place ? r.avg_place.toFixed(2) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </PageShell>
  );
}

/** Lv5 against people at the same tables, with the SPEC 05.7 D target. */
function AiVsHumansCard() {
  const t = useT();
  const [stats, setStats] = useState<AiVsHumans | null>(null);
  useEffect(() => {
    competition.aiVsHumans(5).then(setStats).catch(() => undefined);
  }, []);
  if (!stats) return null;
  const pct = (x: number | null) => (x === null ? "—" : `${(x * 100).toFixed(1)}%`);
  const met = stats.bot_win_rate !== null && stats.bot_win_rate > stats.target_bot_win_rate;
  return (
    <Panel className="mt-6 flex flex-wrap items-center gap-x-8 gap-y-3">
      <div>
        <p className="font-display text-lg font-black">{t("高手 AI 對真人")}</p>
        <p className="text-sm text-mist">
          {stats.hands > 0
            ? t("同桌 {n} 手；目標是 AI 胡牌率超過 {target}", { n: stats.hands, target: pct(stats.target_bot_win_rate) })
            : t("還沒有真人和高手 AI 同桌的牌局。開一桌把座位設成「AI 高手」就會開始累計。")}
        </p>
      </div>
      {stats.hands > 0 && (
        <div className="flex gap-6">
          <div className="text-center">
            <p className="text-xs text-mist">{t("AI 胡牌率")}</p>
            <p className={`tabular font-display text-3xl font-black ${met ? "text-jade" : "text-gold"}`}>{pct(stats.bot_win_rate)}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-mist">{t("真人胡牌率")}</p>
            <p className="tabular font-display text-3xl font-black">{pct(stats.human_win_rate)}</p>
          </div>
        </div>
      )}
    </Panel>
  );
}
