"use client";

import { PageShell } from "@/components/Game/PageShell";
import Link from "next/link";
import { useEffect, useState } from "react";
import { type AgentInfo, agentsApi, ApiError } from "@/lib/api";
import { useAccount } from "@/store/accountStore";

const STATUS: Record<string, string> = {
  PENDING: "驗證中", ACTIVE: "已上場", REJECTED: "驗證未通過", BANNED: "已停權", DELETED: "已刪除",
};

export default function AgentsPage() {
  const user = useAccount((s) => s.user);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const refresh = () => agentsApi.list(true).then(setAgents).catch(() => undefined);
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, []);
  const mine = agents.filter((a) => user && a.owner_id === user.id);

  return (
    <PageShell icon="🤖" title="社群 AI">
      <p className="mt-3 max-w-2xl text-mist">
        用 <code>pip install maijong-sdk</code> 寫好代理程式後，執行 <code>maijong pack</code> 產生 submission.zip 再上傳。
        平台會在隔離環境跑 10 手測試，通過後以 rating 1500 加入競技場。
      </p>

      <section className="mt-8">
        <h2 className="font-display text-2xl font-black">上傳</h2>
        {!user ? <p className="mt-2 text-mist">登入後才能上傳。</p> : (
          <form className="mt-3 flex flex-wrap items-center gap-3" onSubmit={async (e) => {
            e.preventDefault();
            if (!file) return;
            setBusy(true);
            setMsg(null);
            try {
              const a = await agentsApi.submit(file);
              setMsg(`已收到「${a.name}」v${a.version}，驗證中。`);
              refresh();
            } catch (err) {
              setMsg(err instanceof ApiError ? `上傳失敗：${err.message}` : "上傳失敗");
            } finally {
              setBusy(false);
            }
          }}>
            <input type="file" accept=".zip" aria-label="submission.zip"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
            <button disabled={!file || busy} className="btn-game px-5 py-2.5 bg-gradient-to-b from-[#ffb547] to-[#ff7a3d] disabled:opacity-50">
              {busy ? "上傳中…" : "上傳"}
            </button>
            {msg && <p role="status" className="w-full text-sm">{msg}</p>}
          </form>
        )}
      </section>

      {mine.length > 0 && (
        <section className="mt-8">
          <h2 className="font-display text-2xl font-black">我的代理程式</h2>
          <AgentTable rows={mine} />
        </section>
      )}
      <section className="mt-8">
        <h2 className="font-display text-2xl font-black">全部</h2>
        <AgentTable rows={agents.filter((a) => a.status === "ACTIVE")} />
      </section>
    </PageShell>
  );
}

function AgentTable({ rows }: { rows: AgentInfo[] }) {
  return (
    <table className="mt-3 w-full text-left text-sm">
      <thead className="text-mist">
        <tr className="border-b border-felt-line">
          <th className="py-2 font-normal">名稱</th><th className="font-normal">作者</th>
          <th className="font-normal">狀態</th><th className="font-normal">rating</th><th className="font-normal">場數</th>
        </tr>
      </thead>
      <tbody className="tabular">
        {rows.map((a) => (
          <tr key={a.id} className="border-b border-felt-line/50">
            <td className="py-2"><Link href={`/agents/${a.id}`} className="underline">{a.name} v{a.version}</Link></td>
            <td className="text-mist">{a.owner ?? "官方"}</td>
            <td className={a.status === "ACTIVE" ? "" : "text-mist"}>{STATUS[a.status] ?? a.status}</td>
            <td>{a.elo.toFixed(0)}</td>
            <td>{a.games_played}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
