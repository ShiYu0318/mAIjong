"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { GameButton } from "@/components/Game/GameButton";
import { PageShell, PillTabs } from "@/components/Game/PageShell";
import { Panel } from "@/components/Game/Panel";
import { TileImage } from "@/components/Hand/TileImage";
import { ApiError, type DefenseState, practice, saveTicket, type Scenario, type SpeedState } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { sfx } from "@/lib/sfx";
import { tileName } from "@/lib/tiles";

type Tab = "scenario" | "speed" | "defense";
const CATEGORY: Record<string, { label: string; icon: string; tone: string }> = {
  one_away: { label: "一向聽", icon: "🎯", tone: "from-[#22c58b] to-[#0f8f8a]" },
  ready_choice: { label: "聽牌選擇", icon: "🀄", tone: "from-[#4f8dff] to-[#6a3fe0]" },
  defense: { label: "防守", icon: "🛡️", tone: "from-[#ff5c9a] to-[#a35cff]" },
  call: { label: "吃碰判斷", icon: "🤔", tone: "from-[#ff9f1c] to-[#e8486b]" },
  early: { label: "早巡整理", icon: "🌱", tone: "from-[#38d0ff] to-[#3b82f6]" },
};

function Hand({ tiles, drawn, onPick, disabled, mark }: {
  tiles: number[]; drawn: number | null; onPick: (t: number) => void; disabled?: boolean; mark?: number | null;
}) {
  const rest = [...tiles];
  if (drawn !== null) rest.splice(rest.lastIndexOf(drawn), 1);
  return (
    <div className="flex flex-wrap items-end gap-[3px]">
      {rest.map((t, i) => (
        <button key={i} disabled={disabled} onClick={() => { sfx.discard(); onPick(t); }} aria-label={`打出 ${tileName(t)}`}
          className="transition hover:-translate-y-2 disabled:hover:translate-y-0">
          <TileImage id={t} width={46} className={mark === t ? "rounded-md ring-4 ring-zhong" : ""} />
        </button>
      ))}
      {drawn !== null && (
        <button disabled={disabled} onClick={() => { sfx.discard(); onPick(drawn); }} aria-label={`打出剛摸到的 ${tileName(drawn)}`}
          className="ml-4 transition hover:-translate-y-2">
          <TileImage id={drawn} width={46} />
        </button>
      )}
    </div>
  );
}

function ScenarioPanel() {
  const router = useRouter();
  const t = useT();
  const [list, setList] = useState<Scenario[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    practice.scenarios().then(setList).catch(() => setError(t("無法載入情境，請確認後端已啟動。")));
  }, [t]);
  return (
    <div>
      <p className="text-mist">{t("從真實牌局中挑出的局面，你接手後和 AI 打完這一手。")}</p>
      {error && <p role="alert" className="mt-3 text-zhong">{error}</p>}
      <div className="mt-6 space-y-8">
        {Object.entries(CATEGORY).map(([key, cat]) => {
          const items = list.filter((s) => s.category === key);
          if (!items.length) return null;
          return (
            <section key={key}>
              <h3 className="flex items-center gap-2 font-display text-2xl font-black">
                <span aria-hidden="true">{cat.icon}</span>{t(cat.label)}
                <span className="rounded-full bg-black/25 px-2 text-sm text-mist">{items.length}</span>
              </h3>
              <ul className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((s, i) => (
                  <li key={s.id}>
                    <button onClick={async () => {
                      sfx.tap();
                      try {
                        const j = await practice.playScenario(s.id);
                        saveTicket(j.room.room_id, j);
                        router.push(`/room/${j.room.room_id}`);
                      } catch (e) {
                        sfx.error();
                        setError(e instanceof ApiError ? e.message : t("無法開始"));
                      }
                    }} className={`group relative h-full w-full animate-rise overflow-hidden rounded-2xl bg-gradient-to-br p-4 text-left shadow-[0_8px_20px_rgb(5_6_25/0.4)] ring-1 ring-white/15 transition hover:-translate-y-1 ${cat.tone}`}
                      style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}>
                      <span className="absolute -right-2 -bottom-4 text-6xl opacity-20 transition group-hover:scale-110" aria-hidden="true">{cat.icon}</span>
                      <span className="relative block font-black">{s.title}</span>
                      <span className="relative mt-1 block text-sm text-white/85">{s.description}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function SpeedPanel() {
  const t = useT();
  const [st, setSt] = useState<SpeedState | null>(null);
  const [busy, setBusy] = useState(false);
  const start = async () => setSt(await practice.speedStart());
  const pick = async (tile: number) => {
    if (!st || st.done || busy) return;
    setBusy(true);
    try {
      const next = await practice.speedDiscard(st.token, tile);
      if (next.done && next.tenpai) sfx.win();
      setSt(next);
    } finally { setBusy(false); }
  };
  return (
    <Panel>
      <p className="text-mist">{t("每回合摸一張、打一張，用最快速度打到聽牌。得分 = 聽牌時牌牆還剩幾張。")}</p>
      <GameButton className="mt-4" onClick={start}>{st ? t("重新開始") : t("開始")}</GameButton>
      {st && (
        <div className="mt-6">
          <div className="tabular">
            {st.done
              ? st.tenpai
                ? <p className="animate-stamp font-display text-5xl font-black text-gold">{t("聽牌！得分 {n}", { n: st.score ?? 0 })}</p>
                : <p className="text-lg text-mist">{t("牌牆摸完了，沒有聽牌。")}</p>
              : (
                <div className="flex flex-wrap gap-3">
                  <span className="rounded-full bg-black/25 px-4 py-1.5 font-black">
                    {st.shanten === 0 ? t("聽牌") : t("{n} 向聽", { n: st.shanten })}
                  </span>
                  <span className="rounded-full bg-black/25 px-4 py-1.5 font-black">{t("牌牆剩 {n} 張", { n: st.drawable })}</span>
                </div>
              )}
          </div>
          <div className="mt-5"><Hand tiles={st.hand} drawn={st.drawn} onPick={pick} disabled={st.done || busy} /></div>
        </div>
      )}
    </Panel>
  );
}

function DefensePanel() {
  const t = useT();
  const [st, setSt] = useState<DefenseState | null>(null);
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const start = async () => {
    setError(null);
    setLast(null);
    setBusy(true);
    try { setSt(await practice.defenseStart()); } catch { setError(t("出題失敗，請再試一次。")); } finally { setBusy(false); }
  };
  const pick = async (tile: number) => {
    if (!st || st.done || busy) return;
    setBusy(true);
    setLast(tile);
    try {
      const next = await practice.defenseDiscard(st.token, tile);
      if (next.done) (next.dealt_in ? sfx.lose : sfx.win)();
      setSt(next);
    } finally { setBusy(false); }
  };
  return (
    <Panel>
      <p className="text-mist">{t("對手已宣告聽牌，你要撐過 5 次出牌不放槍。宣告後他打出、或別人打出他沒胡的牌就是安全牌。")}</p>
      <GameButton variant="pink" className="mt-4" onClick={start} disabled={busy}>{st ? t("下一題") : t("開始")}</GameButton>
      {error && <p role="alert" className="mt-3 text-zhong">{error}</p>}
      {st && (
        <div className="mt-6 space-y-2">
          {st.discards.map((d, p) => (
            <div key={p} className={`flex flex-wrap items-center gap-3 rounded-xl px-3 py-2 ${st.declared.includes(p) ? "bg-zhong/15 ring-1 ring-zhong/40" : "bg-black/20"}`}>
              <span className={`w-24 text-sm font-black ${st.declared.includes(p) ? "text-zhong" : "text-mist"}`}>
                {p === st.seat ? t("你") : t("對手 {n}", { n: p + 1 })}{st.declared.includes(p) ? t("（聽）") : ""}
              </span>
              <div className="flex flex-wrap gap-[1px]">{d.map((tile, i) => <TileImage key={i} id={tile} width={24} />)}</div>
              {(st.melds[p] ?? []).map((m, i) => (
                <span key={`m${i}`} className="ml-2 flex gap-[1px] border-l border-white/15 pl-2">
                  {m.tiles.map((tile, j) => <TileImage key={j} id={m.type === "AN_KONG" && p !== st.seat ? null : tile} width={24} />)}
                </span>
              ))}
            </div>
          ))}
          <div className="pt-4 tabular">
            {st.done
              ? st.dealt_in
                ? <p className="animate-wiggle text-lg font-black text-zhong">{t("放槍了，打出 {tile} 正好被胡。", { tile: last !== null ? tileName(last) : "" })}</p>
                : <p className="animate-stamp font-display text-4xl font-black text-jade">{t("成功守住！")}</p>
              : <p className="font-black">{t("已撐過 {n} / {m} 次出牌", { n: st.survived, m: st.turns })}</p>}
          </div>
          {st.done && st.waits && (
            <p className="text-sm text-mist">
              {t("對手聽的牌：")}{Object.values(st.waits).flat().map(tileName).join("、") || t("（已胡牌）")}
            </p>
          )}
          <div className="pt-2">
            <Hand tiles={st.hand} drawn={st.drawn} onPick={pick} disabled={st.done || busy} mark={st.dealt_in ? last : null} />
          </div>
        </div>
      )}
    </Panel>
  );
}

export default function PracticePage() {
  const t = useT();
  const [tab, setTab] = useState<Tab>("scenario");
  return (
    <PageShell icon="🎯" title={t("單人練習")}
      subtitle={t("想自選三位 AI 對手的自由練習，請回大廳用「開一桌」。這裡的練習不影響 rating。")}>
      <PillTabs<Tab> value={tab} onChange={(v) => { sfx.tap(); setTab(v); }} tabs={[
        { id: "scenario", label: t("情境練習") },
        { id: "speed", label: t("速度挑戰") },
        { id: "defense", label: t("防守練習") },
      ]} />
      <div className="mt-6">
        {tab === "scenario" && <ScenarioPanel />}
        {tab === "speed" && <SpeedPanel />}
        {tab === "defense" && <DefensePanel />}
      </div>
    </PageShell>
  );
}
