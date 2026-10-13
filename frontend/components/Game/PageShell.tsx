"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { PlayerBar } from "@/components/Account/PlayerBar";
import { useT } from "@/lib/i18n";

/** Common page frame: back to lobby, player bar, big title with an icon. */
export function PageShell({ icon, title, subtitle, actions, children, wide = false, backHref = "/", backLabel }: {
  icon?: ReactNode; title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; children: ReactNode; wide?: boolean;
  backHref?: string; backLabel?: string;
}) {
  const t = useT();
  return (
    <main className={`mx-auto ${wide ? "max-w-7xl" : "max-w-6xl"} px-4 pt-4 pb-12 sm:px-8`}>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <Link href={backHref} className="rounded-full bg-black/25 px-4 py-2 font-bold text-ivory-dim hover:bg-black/40 hover:text-ivory">
          ← {backLabel ?? t("大廳")}
        </Link>
        <PlayerBar compact />
      </header>
      <div className="mt-6 flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-center gap-4">
          {icon && <span className="animate-pop-in" aria-hidden="true">{icon}</span>}
          <div>
            <h1 className="font-display text-4xl font-black sm:text-5xl">{title}</h1>
            {subtitle && <p className="mt-1 max-w-2xl text-mist">{subtitle}</p>}
          </div>
        </div>
        {actions}
      </div>
      <div className="mt-6">{children}</div>
    </main>
  );
}

/** Pill tabs used across pages. */
export function PillTabs<T extends string>({ tabs, value, onChange, label }: {
  tabs: { id: T; label: ReactNode }[]; value: T; onChange: (v: T) => void; label?: string;
}) {
  return (
    <div className="flex flex-wrap gap-2" role="tablist" aria-label={label}>
      {tabs.map((tab) => (
        <button key={tab.id} role="tab" aria-selected={value === tab.id} onClick={() => onChange(tab.id)}
          className={`rounded-full px-5 py-2 font-black transition ${value === tab.id
            ? "bg-ivory text-ink shadow-[0_4px_0_rgb(0_0_0/0.25)]" : "bg-black/25 text-mist hover:text-ivory"}`}>
          {tab.label}
        </button>
      ))}
    </div>
  );
}
