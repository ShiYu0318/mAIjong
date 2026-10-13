"use client";

import { PageShell } from "@/components/Game/PageShell";
import { useState } from "react";
import { ComparePanel, ReplayExplorer, SimulatorPanel, TrainingPanel } from "@/components/Lab/Panels";
import { GameIcon } from "@/components/Game/GameIcon";
import { FlaskConical } from "lucide-react";

const TABS = [
  { id: "training", label: "訓練監控" },
  { id: "compare", label: "策略比較" },
  { id: "simulate", label: "模擬執行器" },
  { id: "replays", label: "錄影探索器" },
] as const;

export default function LabPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("training");
  return (
    <PageShell icon={<GameIcon icon={FlaskConical} tone="green" size={60} />} title="實驗室" wide>
      <div role="tablist" className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
            className={`rounded-full px-5 py-2 font-black transition ${tab === t.id ? "bg-ivory text-ink shadow-[0_4px_0_rgb(0_0_0/0.25)]" : "bg-black/25 text-mist hover:text-ivory"}`}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="mt-6">
        {tab === "training" && <TrainingPanel />}
        {tab === "compare" && <ComparePanel />}
        {tab === "simulate" && <SimulatorPanel />}
        {tab === "replays" && <ReplayExplorer />}
      </div>
    </PageShell>
  );
}
