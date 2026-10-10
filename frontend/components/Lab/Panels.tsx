"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { LineChart } from "@/components/Lab/LineChart";
import { agentLabel, StatsTable, toCsv } from "@/components/Lab/StatsTable";
import { useJob } from "@/components/Lab/useJob";
import { ApiError, lab, type LabJob, type MetricPoint } from "@/lib/api";

const field = "rounded-md border border-felt-line bg-felt-deep px-2 py-1.5";
const primary = "rounded-lg bg-ivory px-4 py-2 text-ink disabled:opacity-50";

function AgentSelect({ value, onChange, agents, label }: {
  value: string; onChange: (v: string) => void; agents: string[]; label: string;
}) {
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} className={field}>
      {agents.map((a) => <option key={a} value={a}>{agentLabel(a)}</option>)}
    </select>
  );
}

function useAgents(): string[] {
  const [agents, setAgents] = useState<string[]>(["random", "rule"]);
  useEffect(() => {
    lab.agents().then(setAgents).catch(() => undefined);
  }, []);
  return agents;
}

function Progress({ job }: { job: LabJob | null }) {
  if (!job) return null;
  const p = job.metrics.progress ?? 0;
  return (
    <div className="mt-4">
      <div className="h-2 overflow-hidden rounded bg-felt-deep" role="progressbar" aria-valuenow={Math.round(p * 100)}
        aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full bg-ivory transition-[width]" style={{ width: `${p * 100}%` }} />
      </div>
      <p className="mt-1 text-sm text-mist">
        {job.status === "FAILED" ? `失敗：${job.metrics.error}` : job.status === "DONE" ? "完成" : `進行中 ${(p * 100).toFixed(0)}%`}
      </p>
    </div>
  );
}

export function SimulatorPanel() {
  const agents = useAgents();
  const [seats, setSeats] = useState(["rule", "random", "random", "random"]);
  const [n, setN] = useState(200);
  const [seed, setSeed] = useState(0);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const job = useJob(jobId);
  const rows = job?.metrics.summary?.seats ?? [];
  return (
    <section>
      <p className="text-mist">設定四個座位的代理程式，跑 N 手牌並統計各座位表現（座位每手輪換）。</p>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        {seats.map((s, i) => (
          <AgentSelect key={i} label={`座位 ${i + 1}`} value={s} agents={agents}
            onChange={(v) => setSeats(seats.map((x, j) => (j === i ? v : x)))} />
        ))}
        <label className="flex flex-col text-sm text-mist">手數
          <input type="number" min={1} max={100000} value={n} onChange={(e) => setN(Number(e.target.value))} className={`${field} w-28 text-ivory`} />
        </label>
        <label className="flex flex-col text-sm text-mist">隨機種子
          <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} className={`${field} w-24 text-ivory`} />
        </label>
        <button className={primary} onClick={async () => {
          setError(null);
          try { setJobId((await lab.simulate(seats, n, seed)).job_id); } catch (e) {
            setError(e instanceof ApiError ? e.message : "連不上伺服器");
          }
        }}>開始模擬</button>
      </div>
      {error && <p role="alert" className="mt-3 text-zhong">{error}</p>}
      <Progress job={job} />
      {rows.length > 0 && (
        <div className="mt-6">
          <p className="mb-2 text-sm text-mist">
            共 {job?.metrics.summary?.hands} 手，流局率 {((job?.metrics.summary?.draw_rate ?? 0) * 100).toFixed(1)}%
          </p>
          <StatsTable rows={rows} />
          <a className="mt-3 inline-block text-sm underline" download="simulation.csv"
            href={`data:text/csv;charset=utf-8,${encodeURIComponent(toCsv(rows))}`}>匯出 CSV</a>
        </div>
      )}
    </section>
  );
}

export function ComparePanel() {
  const agents = useAgents();
  const [picked, setPicked] = useState(["rule", "random"]);
  const [n, setN] = useState(400);
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJob(jobId);
  return (
    <section>
      <p className="text-mist">選 2 到 4 個代理程式輪流入座比較；p 值檢驗胡牌占比是否偏離座位比例。</p>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        {picked.map((s, i) => (
          <AgentSelect key={i} label={`代理程式 ${i + 1}`} value={s} agents={agents}
            onChange={(v) => setPicked(picked.map((x, j) => (j === i ? v : x)))} />
        ))}
        {picked.length < 4 && <button onClick={() => setPicked([...picked, "rule:1.5"])} className="text-sm underline">加一個</button>}
        {picked.length > 2 && <button onClick={() => setPicked(picked.slice(0, -1))} className="text-sm underline">移除一個</button>}
        <label className="flex flex-col text-sm text-mist">手數
          <input type="number" min={4} value={n} onChange={(e) => setN(Number(e.target.value))} className={`${field} w-28 text-ivory`} />
        </label>
        <button className={primary} onClick={async () => setJobId((await lab.compare(picked, n)).job_id)}>開始比較</button>
      </div>
      <Progress job={job} />
      {job?.metrics.agents && <div className="mt-6"><StatsTable rows={job.metrics.agents} showP /></div>}
    </section>
  );
}

const CHARTS: Record<string, { key: string; title: string; fmt?: (v: number) => string }[]> = {
  ppo: [
    { key: "eval_win_rate", title: "對規則型的胡牌率", fmt: (v) => `${(v * 100).toFixed(1)}%` },
    { key: "eval_elo", title: "評估 rating", fmt: (v) => v.toFixed(0) },
    { key: "eval_avg_tai", title: "胡牌平均台數", fmt: (v) => v.toFixed(2) },
    { key: "eval_deal_in_rate", title: "放槍率", fmt: (v) => `${(v * 100).toFixed(1)}%` },
    { key: "policy_loss", title: "策略損失" },
    { key: "value_loss", title: "價值損失" },
    { key: "entropy", title: "策略熵" },
    { key: "explained_variance", title: "解釋變異" },
  ],
  dqn: [
    { key: "eval_win_rate", title: "對規則型的胡牌率", fmt: (v) => `${(v * 100).toFixed(1)}%` },
    { key: "eval_elo", title: "評估 rating", fmt: (v) => v.toFixed(0) },
    { key: "loss", title: "TD 損失" },
    { key: "epsilon", title: "探索率 ε", fmt: (v) => v.toFixed(2) },
  ],
  bc: [
    { key: "val_acc", title: "驗證集準確率", fmt: (v) => `${(v * 100).toFixed(1)}%` },
    { key: "train_loss", title: "訓練損失" },
    { key: "val_loss", title: "驗證損失" },
  ],
};

export function TrainingPanel() {
  const [jobs, setJobs] = useState<LabJob[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [series, setSeries] = useState<MetricPoint[]>([]);
  const [detail, setDetail] = useState<LabJob | null>(null);
  const [kind, setKind] = useState("ppo");
  const [amount, setAmount] = useState(50);
  const [init, setInit] = useState("");
  const [data, setData] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = () => lab.jobs().then((j) => setJobs(j.filter((x) => x.kind.startsWith("TRAIN_")))).catch(() => undefined);
  useEffect(() => {
    refresh();
  }, []);
  useEffect(() => {
    if (!selected) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const d = await lab.training(selected);
        if (!alive) return;
        setDetail(d);
        setSeries(d.series);
        if (d.status === "RUNNING") timer = setTimeout(tick, 3000);
      } catch { /* retry on next selection */ }
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [selected]);

  const charts = useMemo(() => {
    const k = detail?.kind.replace("TRAIN_", "").toLowerCase() ?? "ppo";
    return (CHARTS[k] ?? []).map((c) => ({
      ...c, points: series.filter((p) => typeof p[c.key] === "number").map((p) => ({ x: p.step, y: p[c.key] })),
    }));
  }, [detail, series]);

  const start = async () => {
    setError(null);
    const config: Record<string, unknown> =
      kind === "ppo" ? { updates: amount, ...(init ? { init } : {}) } :
      kind === "dqn" ? { steps: amount } : { data };
    try {
      const { job_id } = await lab.train(kind, config);
      await refresh();
      setSelected(job_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "無法開始訓練");
    }
  };

  return (
    <section className="grid gap-8 lg:grid-cols-[280px_1fr]">
      <div>
        <h3 className="font-display text-xl">開始訓練</h3>
        <div className="mt-3 grid gap-3 text-sm">
          <select aria-label="訓練方法" value={kind} onChange={(e) => {
            setKind(e.target.value);
            setAmount(e.target.value === "dqn" ? 50000 : 50);
          }} className={field}>
            <option value="ppo">PPO 自對弈</option>
            <option value="dqn">Dueling DQN</option>
            <option value="bc">行為克隆</option>
          </select>
          {kind !== "bc" && (
            <label className="flex flex-col text-mist">{kind === "ppo" ? "更新次數" : "環境步數"}
              <input type="number" value={amount} onChange={(e) => setAmount(Number(e.target.value))} className={`${field} text-ivory`} />
            </label>
          )}
          {kind === "ppo" && (
            <label className="flex flex-col text-mist">初始權重（BC 檢查點路徑，可留空）
              <input value={init} onChange={(e) => setInit(e.target.value)} placeholder="checkpoints/bc_v1.pt" className={`${field} text-ivory`} />
            </label>
          )}
          {kind === "bc" && (
            <label className="flex flex-col text-mist">對局紀錄檔
              <input value={data} onChange={(e) => setData(e.target.value)} placeholder="data/bc/rule.jsonl.gz" className={`${field} text-ivory`} />
            </label>
          )}
          <button onClick={start} className={primary}>開始</button>
          {error && <p role="alert" className="text-zhong">{error}</p>}
        </div>
        <h3 className="mt-8 font-display text-xl">訓練任務</h3>
        <ul className="mt-2 divide-y divide-felt-line text-sm">
          {jobs.length === 0 && <li className="py-2 text-mist">還沒有訓練任務。</li>}
          {jobs.map((j) => (
            <li key={j.id}>
              <button onClick={() => setSelected(j.id)}
                className={`flex w-full justify-between py-2 text-left ${selected === j.id ? "text-ivory" : "text-mist"}`}>
                <span>{j.kind.replace("TRAIN_", "")}・{new Date(j.created_at).toLocaleString("zh-TW")}</span>
                <span>{j.status}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div>
        {!detail ? <p className="text-mist">選一個訓練任務查看曲線。</p> : (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <h3 className="font-display text-xl">{detail.kind.replace("TRAIN_", "")} 訓練</h3>
              <span className="text-sm text-mist">{detail.status}</span>
              {detail.status === "RUNNING" && (
                <button onClick={async () => { setDetail(await lab.stop(detail.id)); refresh(); }}
                  className="rounded border border-ivory/30 px-3 py-1 text-sm">停止</button>
              )}
              {(detail.status === "STOPPED" || detail.status === "FAILED") && (
                <button onClick={async () => { await lab.resume(detail.id); setSelected(null); setTimeout(() => setSelected(detail.id), 50); refresh(); }}
                  className="rounded border border-ivory/30 px-3 py-1 text-sm">從檢查點繼續</button>
              )}
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {charts.map((c) => <LineChart key={c.key} title={c.title} points={c.points} format={c.fmt} />)}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

export function ReplayExplorer() {
  const [agent, setAgent] = useState("");
  const [result, setResult] = useState("");
  const [minTai, setMinTai] = useState(0);
  const [taiId, setTaiId] = useState("");
  const [rows, setRows] = useState<Awaited<ReturnType<typeof lab.replays>>>([]);
  const search = async () => {
    const q: Record<string, string> = { include_private: "true", min_tai: String(minTai) };
    if (agent) q.agent = agent;
    if (result) q.result = result;
    if (taiId) q.tai_id = taiId;
    setRows(await lab.replays(q));
  };
  useEffect(() => {
    search().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <section>
      <form className="flex flex-wrap items-end gap-3 text-sm" onSubmit={(e) => { e.preventDefault(); search(); }}>
        <label className="flex flex-col text-mist">座位名稱包含
          <input value={agent} onChange={(e) => setAgent(e.target.value)} placeholder="例如 高手" className={`${field} text-ivory`} />
        </label>
        <label className="flex flex-col text-mist">結果
          <select value={result} onChange={(e) => setResult(e.target.value)} className={`${field} text-ivory`}>
            <option value="">全部</option><option value="HU">胡牌</option><option value="SELF_DRAW">自摸</option>
            <option value="DEAL_IN">放槍</option><option value="DRAW">流局</option>
          </select>
        </label>
        <label className="flex flex-col text-mist">最少台數
          <input type="number" min={0} value={minTai} onChange={(e) => setMinTai(Number(e.target.value))} className={`${field} w-20 text-ivory`} />
        </label>
        <label className="flex flex-col text-mist">包含台型
          <select value={taiId} onChange={(e) => setTaiId(e.target.value)} className={`${field} text-ivory`}>
            <option value="">不限</option><option value="T24">清一色</option><option value="T25">湊一色</option>
            <option value="T29">碰碰胡</option><option value="T30">平胡</option><option value="T21">大三元</option>
            <option value="T06">門清自摸</option><option value="T13">八仙過海</option>
          </select>
        </label>
        <button className={primary}>搜尋</button>
      </form>
      <ul className="mt-6 divide-y divide-felt-line">
        {rows.length === 0 && <li className="py-3 text-mist">沒有符合的對局。</li>}
        {rows.map((r) => {
          const names = r.seats.map((s, i) => s?.name ?? `座位${i + 1}`);
          const tai = (r.result.tai_breakdown ?? []).reduce((a, b) => a + b.tai, 0);
          return (
            <li key={r.id} className="flex flex-wrap items-baseline gap-x-4 py-2 text-sm">
              <Link href={`/replay/${r.id}`} className="underline">看錄影</Link>
              <span>{r.result.kind === "DRAW" ? "流局" : `${names[r.result.winner!]} ${r.result.self_draw ? "自摸" : "胡牌"} ${tai} 台`}</span>
              <span className="text-mist">{(r.result.tai_breakdown ?? []).map((t) => t.name).join("、")}</span>
              <span className="ml-auto text-mist">{new Date(r.created_at).toLocaleString("zh-TW")}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
