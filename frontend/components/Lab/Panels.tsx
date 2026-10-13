"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { LineChart } from "@/components/Lab/LineChart";
import { agentLabel, StatsTable, toCsv } from "@/components/Lab/StatsTable";
import { useJob } from "@/components/Lab/useJob";
import { ApiError, lab, type LabJob, type LabRun, type MetricPoint } from "@/lib/api";

const field = "rounded-md border border-felt-line bg-felt-deep px-2 py-1.5";
const primary = "btn-game px-5 py-2.5 btn-primary disabled:opacity-50";

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

type ChartSpec = { key: string; title: string; fmt?: (v: number) => string };
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const EVAL: ChartSpec[] = [
  { key: "eval_win_rate", title: "對規則型的胡牌率", fmt: pct },
  { key: "eval_elo", title: "評估 rating", fmt: (v) => v.toFixed(0) },
  { key: "eval_avg_tai", title: "胡牌平均台數", fmt: (v) => v.toFixed(2) },
  { key: "eval_deal_in_rate", title: "放槍率", fmt: pct },
];

const CHARTS: Record<string, ChartSpec[]> = {
  ppo: [
    ...EVAL,
    { key: "policy_loss", title: "Policy loss" },
    { key: "value_loss", title: "Value loss" },
    { key: "entropy", title: "Policy entropy" },
    { key: "kl_to_init", title: "KL to initial policy" },
    { key: "explained_variance", title: "Explained variance" },
  ],
  sb3: [
    ...EVAL,
    { key: "mean_episode_reward", title: "Mean episode reward" },
    { key: "value_loss", title: "Value loss" },
    { key: "entropy", title: "Policy entropy" },
    { key: "approx_kl", title: "Approx KL" },
    { key: "clip_fraction", title: "Clip fraction", fmt: pct },
    { key: "sps", title: "Steps / s", fmt: (v) => v.toFixed(0) },
  ],
  dqn: [
    ...EVAL.slice(0, 2),
    { key: "loss", title: "TD loss" },
    { key: "epsilon", title: "ε (exploration)", fmt: (v) => v.toFixed(2) },
  ],
  bc: [
    { key: "val_acc", title: "Validation accuracy", fmt: pct },
    { key: "train_loss", title: "Train loss" },
    { key: "val_loss", title: "Validation loss" },
  ],
};

/** Kind from a job ("TRAIN_SB3") or a run config ("sb3_maskable_ppo", "ppo"…). */
function chartKind(kind: string): string {
  const k = kind.replace("TRAIN_", "").toLowerCase();
  if (k.startsWith("sb3")) return "sb3";
  return k in CHARTS ? k : "";
}

/** Known charts for the kind, or every numeric series for an unknown kind. */
function chartsFor(kind: string, series: MetricPoint[]): ChartSpec[] {
  const known = CHARTS[chartKind(kind)];
  if (known) return known;
  const keys = new Set<string>();
  for (const p of series) {
    for (const [k, v] of Object.entries(p)) if (typeof v === "number" && k !== "step" && k !== "time") keys.add(k);
  }
  return [...keys].map((key) => ({ key, title: key }));
}

type Selection = { type: "job"; id: string } | { type: "run"; id: string };

export function TrainingPanel() {
  const [jobs, setJobs] = useState<LabJob[]>([]);
  const [runs, setRuns] = useState<LabRun[]>([]);
  const [selected, setSelected] = useState<Selection | null>(null);
  const [series, setSeries] = useState<MetricPoint[]>([]);
  const [detail, setDetail] = useState<LabJob | null>(null);
  const [runKind, setRunKind] = useState("");
  const [kind, setKind] = useState("ppo");
  const [amount, setAmount] = useState(50);
  const [init, setInit] = useState("");
  const [data, setData] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    lab.jobs().then((j) => setJobs(j.filter((x) => x.kind.startsWith("TRAIN_")))).catch(() => undefined);
    lab.runs().then(setRuns).catch(() => undefined);
  };
  useEffect(() => {
    refresh();
  }, []);
  useEffect(() => {
    if (!selected) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    let last: number | undefined;
    setSeries([]);
    setDetail(null);
    const tick = async () => {
      try {
        let fresh: MetricPoint[];
        let live: boolean;
        if (selected.type === "job") {
          const d = await lab.training(selected.id, last);
          if (!alive) return;
          setDetail(d);
          fresh = d.series;
          live = d.status === "RUNNING";
        } else {
          const d = await lab.run(selected.id, last);
          if (!alive) return;
          setRunKind(String(d.config.kind ?? ""));
          fresh = d.series;
          const lastTime = fresh.length ? fresh[fresh.length - 1].time : undefined;
          live = fresh.length > 0 ? Date.now() / 1000 - (lastTime ?? 0) < 600 : last !== undefined;
        }
        if (fresh.length) {
          last = fresh[fresh.length - 1].step;
          setSeries((prev) => [...prev, ...fresh]);
        }
        if (live) timer = setTimeout(tick, 4000);
      } catch { /* retry on next selection */ }
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [selected]);

  const kindName = selected?.type === "run" ? runKind : detail?.kind ?? "";
  const charts = useMemo(() => chartsFor(kindName, series).map((c) => ({
    ...c, points: series.filter((p) => typeof p[c.key] === "number").map((p) => ({ x: p.step, y: p[c.key] })),
  })).filter((c) => c.points.length > 0), [kindName, series]);

  const start = async () => {
    setError(null);
    const config: Record<string, unknown> =
      kind === "ppo" ? { updates: amount, ...(init ? { init } : {}) } :
      kind === "sb3" ? { steps: amount, ...(data ? { bc_data: data } : {}), ...(init ? { init } : {}) } :
      kind === "dqn" ? { steps: amount } : { data };
    try {
      const { job_id } = await lab.train(kind, config);
      refresh();
      setSelected({ type: "job", id: job_id });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "無法開始訓練");
    }
  };

  const isSel = (type: Selection["type"], id: string) => selected?.type === type && selected.id === id;

  return (
    <section className="grid gap-8 lg:grid-cols-[300px_1fr]">
      <div>
        <h3 className="font-display text-xl font-black">開始訓練</h3>
        <div className="mt-3 grid gap-3 text-sm">
          <select aria-label="訓練方法" value={kind} onChange={(e) => {
            setKind(e.target.value);
            setAmount(e.target.value === "dqn" ? 50000 : e.target.value === "sb3" ? 200000 : 50);
          }} className={field}>
            <option value="sb3">SB3 MaskablePPO 自我對弈（多行程）</option>
            <option value="ppo">PPO self-play</option>
            <option value="dqn">Dueling DQN</option>
            <option value="bc">Behavior Cloning (BC)</option>
          </select>
          {kind !== "bc" && (
            <label className="flex flex-col text-mist">{kind === "ppo" ? "更新次數" : "環境步數"}
              <input type="number" value={amount} onChange={(e) => setAmount(Number(e.target.value))} className={`${field} text-ivory`} />
            </label>
          )}
          {(kind === "ppo" || kind === "sb3") && (
            <label className="flex flex-col text-mist">
              {kind === "ppo" ? "初始權重（BC checkpoint 路徑，可留空）" : "接續訓練的模型（.zip，可留空）"}
              <input value={init} onChange={(e) => setInit(e.target.value)}
                placeholder={kind === "ppo" ? "checkpoints/bc_v2.pt" : "checkpoints/sb3_best.zip"} className={`${field} text-ivory`} />
            </label>
          )}
          {(kind === "bc" || kind === "sb3") && (
            <label className="flex flex-col text-mist">{kind === "bc" ? "對局紀錄檔" : "模仿學習暖身資料（可留空）"}
              <input value={data} onChange={(e) => setData(e.target.value)} placeholder="data/bc/rule_3k.jsonl.gz" className={`${field} text-ivory`} />
            </label>
          )}
          <button onClick={start} className={primary}>開始</button>
          {error && <p role="alert" className="text-zhong">{error}</p>}
        </div>
        <h3 className="mt-8 font-display text-xl font-black">訓練任務</h3>
        <ul className="mt-2 divide-y divide-felt-line text-sm">
          {jobs.length === 0 && <li className="py-2 text-mist">還沒有從這裡啟動的訓練。</li>}
          {jobs.map((j) => (
            <li key={j.id}>
              <button onClick={() => setSelected({ type: "job", id: j.id })}
                className={`flex w-full justify-between py-2 text-left ${isSel("job", j.id) ? "text-ivory" : "text-mist"}`}>
                <span>{j.kind.replace("TRAIN_", "")}・{new Date(j.created_at).toLocaleString("zh-TW")}</span>
                <span>{j.status}</span>
              </button>
            </li>
          ))}
        </ul>
        <h3 className="mt-8 font-display text-xl font-black">所有訓練紀錄</h3>
        <p className="mt-1 text-xs text-mist">runs/ 資料夾裡的每一次訓練，包含用指令列啟動的。</p>
        <ul className="mt-2 divide-y divide-felt-line text-sm">
          {runs.length === 0 && <li className="py-2 text-mist">還沒有訓練紀錄。</li>}
          {runs.map((r) => (
            <li key={r.name}>
              <button onClick={() => setSelected({ type: "run", id: r.name })}
                className={`flex w-full justify-between gap-2 py-2 text-left ${isSel("run", r.name) ? "text-ivory" : "text-mist"}`}>
                <span className="truncate">{r.name}</span>
                <span className="tabular shrink-0">
                  {typeof r.eval_win_rate === "number" ? pct(r.eval_win_rate) : `${r.points} 筆`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div>
        {!selected ? <p className="text-mist">選一個訓練任務或紀錄查看曲線。</p> : (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <h3 className="font-display text-xl font-black">
                {selected.type === "run" ? selected.id : `${detail?.kind.replace("TRAIN_", "") ?? ""} 訓練`}
              </h3>
              {detail && <span className="text-sm text-mist">{detail.status}</span>}
              {detail?.status === "RUNNING" && (
                <button onClick={async () => { setDetail(await lab.stop(detail.id)); refresh(); }}
                  className="rounded border border-ivory/30 px-3 py-1 text-sm">停止</button>
              )}
              {detail && (detail.status === "STOPPED" || detail.status === "FAILED") && (
                <button onClick={async () => {
                  await lab.resume(detail.id);
                  setSelected(null);
                  setTimeout(() => setSelected({ type: "job", id: detail.id }), 50);
                  refresh();
                }} className="rounded border border-ivory/30 px-3 py-1 text-sm">從 checkpoint 繼續</button>
              )}
            </div>
            {charts.length === 0 && <p className="mt-4 text-mist">還沒有資料點，訓練開始後會自動更新。</p>}
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
