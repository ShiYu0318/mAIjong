"use client";

import { PageShell } from "@/components/Game/PageShell";
import Link from "next/link";
import { useEffect, useState } from "react";
import { type AgentInfo, agentsApi, ApiError } from "@/lib/api";
import { localName, useT } from "@/lib/i18n";
import { useAccount } from "@/store/accountStore";
import { GameIcon } from "@/components/Game/GameIcon";
import { Bot } from "lucide-react";

const STATUS: Record<string, string> = {
  PENDING: "驗證中", ACTIVE: "已上場", REJECTED: "驗證未通過", BANNED: "已停權", DELETED: "已刪除",
};

export default function AgentsPage() {
  const t = useT();
  const user = useAccount((s) => s.user);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const refresh = () => agentsApi.list(true).then(setAgents).catch(() => undefined);
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, []);
  const mine = agents.filter((a) => user && a.owner_id === user.id);

  return (
    <PageShell icon={<GameIcon icon={Bot} tone="cyan" size={60} />} title={t("社群 AI")}>
      <p className="mt-3 max-w-2xl text-mist">
        {t("用 pip install maijong-sdk 寫好代理程式後，執行 maijong pack 產生 submission.zip 再上傳。平台會在隔離環境跑 10 手測試，通過後以 rating 1500 加入競技場。")}
      </p>

      <section className="mt-8">
        <h2 className="font-display text-2xl font-black">{t("上傳")}</h2>
        {!user ? <p className="mt-2 text-mist">{t("登入後才能上傳。")}</p> : (
          <form className="mt-3 flex flex-wrap items-center gap-3" onSubmit={async (e) => {
            e.preventDefault();
            if (!file) return;
            setBusy(true);
            setMsg(null);
            try {
              const a = await agentsApi.submit(file);
              setMsg(t("已收到「{name}」v{version}，驗證中。", { name: a.name, version: a.version }));
              refresh();
            } catch (err) {
              setMsg(err instanceof ApiError ? t("上傳失敗：{msg}", { msg: err.message }) : t("上傳失敗"));
            } finally {
              setBusy(false);
            }
          }}>
            <input type="file" accept=".zip" aria-label="submission.zip"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
            <button disabled={!file || busy} className="btn-game px-5 py-2.5 btn-primary disabled:opacity-50">
              {busy ? t("上傳中…") : t("上傳")}
            </button>
            {msg && <p role="status" className="w-full text-sm">{msg}</p>}
          </form>
        )}
      </section>

      {mine.length > 0 && (
        <section className="mt-8">
          <h2 className="font-display text-2xl font-black">{t("我的代理程式")}</h2>
          <AgentTable rows={mine} />
        </section>
      )}
      <section className="mt-8">
        <h2 className="font-display text-2xl font-black">{t("全部")}</h2>
        <AgentTable rows={agents.filter((a) => a.status === "ACTIVE")} />
      </section>
    </PageShell>
  );
}

function AgentTable({ rows }: { rows: AgentInfo[] }) {
  const t = useT();
  return (
    <table className="mt-3 w-full text-left text-sm">
      <thead className="text-mist">
        <tr className="border-b border-felt-line">
          <th className="py-2 font-normal">{t("名稱")}</th><th className="font-normal">{t("作者")}</th>
          <th className="font-normal">{t("狀態")}</th><th className="font-normal">rating</th>
          <th className="font-normal">{t("場數")}</th>
        </tr>
      </thead>
      <tbody className="tabular">
        {rows.map((a) => (
          <tr key={a.id} className="border-b border-felt-line/50">
            <td className="py-2"><Link href={`/agents/${a.id}`} className="underline">{localName(a.name)} v{a.version}</Link></td>
            <td className="text-mist">{a.owner ?? t("官方")}</td>
            <td className={a.status === "ACTIVE" ? "" : "text-mist"}>{STATUS[a.status] ? t(STATUS[a.status]) : a.status}</td>
            <td>{a.elo.toFixed(0)}</td>
            <td>{a.games_played}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
