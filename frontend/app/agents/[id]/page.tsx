"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AccountBar } from "@/components/Account/AccountBar";
import { LineChart } from "@/components/Lab/LineChart";
import { type AgentInfo, agentsApi, ApiError, competition } from "@/lib/api";
import { useAccount } from "@/store/accountStore";

export default function AgentDetail() {
  const { id } = useParams<{ id: string }>();
  const user = useAccount((s) => s.user);
  const [agent, setAgent] = useState<AgentInfo | null>(null);
  const [others, setOthers] = useState<AgentInfo[]>([]);
  const [opponent, setOpponent] = useState("");
  const [challenge, setChallenge] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    agentsApi.get(id).then(setAgent).catch(() => undefined);
    agentsApi.list().then((l) => setOthers(l.filter((a) => a.id !== id))).catch(() => undefined);
  }, [id]);

  useEffect(() => {
    if (!challenge) return;
    const t = setInterval(async () => {
      const c = await competition.getChallenge(challenge);
      if (c.status === "DONE" || c.status === "FAILED") {
        clearInterval(t);
        if (c.status === "FAILED") setResult(`挑戰失敗：${c.result.error}`);
        else {
          const name = (aid: string) => (aid === id ? agent?.name : others.find((o) => o.id === aid)?.name) ?? aid;
          const scores = Object.entries(c.result.total_score ?? {}).map(([k, v]) => `${name(k)} ${v}`).join("、");
          setResult(`結果：${scores}。勝者：${name(c.result.winner ?? "")}`);
        }
      }
    }, 1500);
    return () => clearInterval(t);
  }, [challenge, id, agent, others]);

  if (!agent) return <main className="p-10 text-mist">載入中…</main>;
  const history = (agent.elo_history ?? []).map((h, i) => ({ x: i + 1, y: h.elo }));

  return (
    <main className="mx-auto max-w-4xl px-5 py-8">
      <div className="flex items-center justify-between">
        <Link href="/leaderboard" className="text-mist hover:text-ivory">← 排行榜</Link>
        <AccountBar />
      </div>
      <h1 className="mt-4 font-display text-5xl">{agent.name} <span className="text-3xl text-mist">v{agent.version}</span></h1>
      <p className="mt-2 text-mist">作者：{agent.owner ?? "官方"}・rating {agent.elo.toFixed(0)}・{agent.games_played} 場</p>
      {agent.description && <p className="mt-3">{agent.description}</p>}

      <div className="mt-6 max-w-md">
        <LineChart title="rating 變化" points={history} format={(v) => v.toFixed(0)} xLabel="場次" />
      </div>

      {agent.validation && (
        <section className="mt-6 text-sm">
          <h2 className="font-display text-xl">驗證結果</h2>
          <p className="mt-1">
            {agent.validation.passed ? "通過" : "未通過"}
            {agent.validation.max_decision_s !== undefined && agent.validation.max_decision_s !== null
              ? `・最慢一次決策 ${agent.validation.max_decision_s.toFixed(3)} 秒` : ""}
          </p>
          {agent.validation.errors.map((e, i) => <p key={i} className="text-zhong">{e}</p>)}
        </section>
      )}

      {user && agent.status === "ACTIVE" && (
        <section className="mt-8">
          <h2 className="font-display text-xl">發起挑戰賽</h2>
          <p className="mt-1 text-sm text-mist">兩個代理程式加上兩位官方 Bot，打 10 場不計分的系列賽。</p>
          <div className="mt-3 flex gap-2">
            <select aria-label="對手" value={opponent} onChange={(e) => setOpponent(e.target.value)}
              className="rounded-md border border-felt-line bg-felt-deep px-2 py-1.5">
              <option value="">選擇對手</option>
              {others.map((o) => <option key={o.id} value={o.id}>{o.name} v{o.version}</option>)}
            </select>
            <button disabled={!opponent} onClick={async () => {
              setResult("挑戰進行中…");
              try {
                setChallenge((await competition.challenge(agent.id, opponent, 10)).id);
              } catch (e) {
                setResult(e instanceof ApiError ? e.message : "無法發起挑戰");
              }
            }} className="rounded-lg bg-ivory px-4 py-1.5 text-ink disabled:opacity-50">開始</button>
          </div>
          {result && <p role="status" className="mt-3">{result}</p>}
        </section>
      )}
    </main>
  );
}
