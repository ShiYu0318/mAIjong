"use client";

import { PageShell } from "@/components/Game/PageShell";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { LineChart } from "@/components/Lab/LineChart";
import { type AgentInfo, agentsApi, ApiError, competition } from "@/lib/api";
import { localName, useT } from "@/lib/i18n";
import { useAccount } from "@/store/accountStore";
import Link from "next/link";
import { GameIcon } from "@/components/Game/GameIcon";
import { Bot } from "lucide-react";

export default function AgentDetail() {
  const { id } = useParams<{ id: string }>();
  const t = useT();
  const user = useAccount((s) => s.user);
  const [missing, setMissing] = useState(false);
  const [agent, setAgent] = useState<AgentInfo | null>(null);
  const [others, setOthers] = useState<AgentInfo[]>([]);
  const [opponent, setOpponent] = useState("");
  const [challenge, setChallenge] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    agentsApi.get(id).then(setAgent).catch(() => setMissing(true));
    agentsApi.list().then((l) => setOthers(l.filter((a) => a.id !== id))).catch(() => undefined);
  }, [id]);

  useEffect(() => {
    if (!challenge) return;
    const timer = setInterval(async () => {
      const c = await competition.getChallenge(challenge).catch(() => null);
      if (!c) return;  // a network blip: try again on the next tick
      if (c.status === "DONE" || c.status === "FAILED") {
        clearInterval(timer);
        if (c.status === "FAILED") setResult(t("挑戰失敗：{msg}", { msg: c.result.error ?? "" }));
        else {
          const name = (aid: string) => localName(
            (aid === id ? agent?.name : others.find((o) => o.id === aid)?.name) ?? aid);
          const scores = Object.entries(c.result.total_score ?? {}).map(([k, v]) => `${name(k)} ${v}`)
            .join(t("、"));
          setResult(t("結果：{scores}。勝者：{winner}", { scores, winner: name(c.result.winner ?? "") }));
        }
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [challenge, id, agent, others, t]);

  if (missing) {
    return (
      <main className="p-10 text-mist">
        {t("找不到這個代理程式。")} <Link href="/agents" className="underline">{t("回社群 AI")}</Link>
      </main>
    );
  }
  if (!agent) return <main className="p-10 text-mist">{t("載入中…")}</main>;
  const history = (agent.elo_history ?? []).map((h, i) => ({ x: i + 1, y: h.elo }));

  return (
    <PageShell icon={<GameIcon icon={Bot} tone="cyan" size={60} />} backHref="/leaderboard" backLabel={t("排行榜")}
      title={<>{localName(agent.name)} <span className="text-3xl text-mist">v{agent.version}</span></>}>
      <p className="mt-2 text-mist">
        {t("作者：{owner}・rating {elo}・{n} 場", { owner: agent.owner ?? t("官方"), elo: agent.elo.toFixed(0),
          n: agent.games_played })}
      </p>
      {agent.description && <p className="mt-3">{t(agent.description)}</p>}

      <div className="mt-6 max-w-md">
        <LineChart title={t("rating 變化")} points={history} format={(v) => v.toFixed(0)} xLabel={t("場次")} />
      </div>

      {agent.validation && (
        <section className="mt-6 text-sm">
          <h2 className="font-display text-xl font-black">{t("驗證結果")}</h2>
          <p className="mt-1">
            {agent.validation.passed ? t("通過") : t("未通過")}
            {agent.validation.max_decision_s !== undefined && agent.validation.max_decision_s !== null
              ? t("・最慢一次決策 {s} 秒", { s: agent.validation.max_decision_s.toFixed(3) }) : ""}
          </p>
          {agent.validation.errors.map((e, i) => <p key={i} className="text-zhong">{e}</p>)}
        </section>
      )}

      {user && agent.status === "ACTIVE" && (
        <section className="mt-8">
          <h2 className="font-display text-xl font-black">{t("發起挑戰賽")}</h2>
          <p className="mt-1 text-sm text-mist">{t("兩個代理程式加上兩位官方 Bot，打 10 場不計分的系列賽。")}</p>
          <div className="mt-3 flex gap-2">
            <select aria-label={t("對手")} value={opponent} onChange={(e) => setOpponent(e.target.value)}
              className="rounded-md border border-felt-line bg-felt-deep px-2 py-1.5">
              <option value="">{t("選擇對手")}</option>
              {others.map((o) => <option key={o.id} value={o.id}>{localName(o.name)} v{o.version}</option>)}
            </select>
            <button disabled={!opponent} onClick={async () => {
              setResult(t("挑戰進行中…"));
              try {
                setChallenge((await competition.challenge(agent.id, opponent, 10)).id);
              } catch (e) {
                setResult(e instanceof ApiError ? e.message : t("無法發起挑戰"));
              }
            }} className="btn-game btn-primary px-5 py-2 disabled:opacity-50">{t("開始")}</button>
          </div>
          {result && <p role="status" className="mt-3">{result}</p>}
        </section>
      )}
    </PageShell>
  );
}
