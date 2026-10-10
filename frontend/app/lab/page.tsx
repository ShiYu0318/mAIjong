"use client";

import Link from "next/link";
import { useState } from "react";
import { ComparePanel, ReplayExplorer, SimulatorPanel, TrainingPanel } from "@/components/Lab/Panels";

const TABS = [
  { id: "training", label: "訓練監控" },
  { id: "compare", label: "策略比較" },
  { id: "simulate", label: "模擬執行器" },
  { id: "replays", label: "錄影探索器" },
] as const;

export default function LabPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("training");
  return (
    <main className="mx-auto max-w-7xl px-5 py-8">
      <Link href="/" className="text-mist hover:text-ivory">← 大廳</Link>
      <h1 className="mt-4 font-display text-5xl">實驗室</h1>
      <div role="tablist" className="mt-6 flex gap-1 border-b border-felt-line">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-4 py-2 ${tab === t.id ? "border-ivory text-ivory" : "border-transparent text-mist"}`}>
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
    </main>
  );
}
