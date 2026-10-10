"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { TileImage } from "@/components/Hand/TileImage";
import { ApiError, type DefenseState, practice, saveTicket, type Scenario, type SpeedState } from "@/lib/api";
import { tileName } from "@/lib/tiles";

const TABS = [
  { id: "scenario", label: "情境練習" },
  { id: "speed", label: "速度挑戰" },
  { id: "defense", label: "防守練習" },
] as const;
const CATEGORY: Record<string, string> = {
  one_away: "一向聽", ready_choice: "聽牌選擇", defense: "防守", call: "吃碰判斷", early: "早巡整理",
};

function Hand({ tiles, drawn, onPick, disabled, mark }: {
  tiles: number[]; drawn: number | null; onPick: (t: number) => void; disabled?: boolean; mark?: number | null;
}) {
  const rest = [...tiles];
  if (drawn !== null) rest.splice(rest.lastIndexOf(drawn), 1);
  return (
    <div className="flex flex-wrap items-end gap-[3px]">
      {rest.map((t, i) => (
        <button key={i} disabled={disabled} onClick={() => onPick(t)} aria-label={`打出 ${tileName(t)}`}
          className="transition hover:-translate-y-1 disabled:hover:translate-y-0">
          <TileImage id={t} width={44} className={mark === t ? "ring-2 ring-zhong rounded-md" : ""} />
        </button>
      ))}
      {drawn !== null && (
        <button disabled={disabled} onClick={() => onPick(drawn)} aria-label={`打出剛摸到的 ${tileName(drawn)}`}
          className="ml-4 transition hover:-translate-y-1">
          <TileImage id={drawn} width={44} />
        </button>
      )}
    </div>
  );
}

function ScenarioPanel() {
  const router = useRouter();
  const [list, setList] = useState<Scenario[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    practice.scenarios().then(setList).catch(() => setError("無法載入情境，請確認後端已啟動。"));
  }, []);
  const groups = Object.entries(CATEGORY).map(([k, label]) => [label, list.filter((s) => s.category === k)] as const);
  return (
    <div>
      <p className="text-mist">從真實牌局中挑出的局面，你接手後和 AI 打完這一手。</p>
      {error && <p role="alert" className="mt-3 text-zhong">{error}</p>}
      <div className="mt-6 grid gap-8 md:grid-cols-2">
        {groups.map(([label, items]) => items.length > 0 && (
          <section key={label}>
            <h3 className="font-display text-2xl">{label}</h3>
            <ul className="mt-2 divide-y divide-felt-line">
              {items.map((s) => (
                <li key={s.id}>
                  <button onClick={async () => {
                    try {
                      const j = await practice.playScenario(s.id);
                      saveTicket(j.room.room_id, j);
                      router.push(`/room/${j.room.room_id}`);
                    } catch (e) {
                      setError(e instanceof ApiError ? e.message : "無法開始");
                    }
                  }} className="w-full py-2 text-left hover:bg-ivory/5">
                    <span>{s.title}</span>
                    <span className="block text-sm text-mist">{s.description}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

function SpeedPanel() {
  const [st, setSt] = useState<SpeedState | null>(null);
  const [busy, setBusy] = useState(false);
  const start = async () => setSt(await practice.speedStart());
  const pick = async (t: number) => {
    if (!st || st.done || busy) return;
    setBusy(true);
    try { setSt(await practice.speedDiscard(st.token, t)); } finally { setBusy(false); }
  };
  return (
    <div>
      <p className="text-mist">每回合摸一張、打一張，用最快速度打到聽牌。得分 = 聽牌時牌牆還剩幾張。</p>
      <button onClick={start} className="mt-4 rounded-lg bg-ivory px-4 py-2 text-ink">{st ? "重新開始" : "開始"}</button>
      {st && (
        <div className="mt-6">
          <p className="tabular">
            {st.done
              ? st.tenpai ? <span className="font-display text-3xl">聽牌！得分 {st.score}</span> : "牌牆摸完了，沒有聽牌。"
              : <>目前 {st.shanten === 0 ? "聽牌" : `${st.shanten} 向聽`}・牌牆剩 {st.drawable} 張</>}
          </p>
          <div className="mt-4"><Hand tiles={st.hand} drawn={st.drawn} onPick={pick} disabled={st.done || busy} /></div>
        </div>
      )}
    </div>
  );
}

function DefensePanel() {
  const [st, setSt] = useState<DefenseState | null>(null);
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const start = async () => {
    setError(null);
    setLast(null);
    setBusy(true);
    try { setSt(await practice.defenseStart()); } catch { setError("出題失敗，請再試一次。"); } finally { setBusy(false); }
  };
  const pick = async (t: number) => {
    if (!st || st.done || busy) return;
    setBusy(true);
    setLast(t);
    try { setSt(await practice.defenseDiscard(st.token, t)); } finally { setBusy(false); }
  };
  return (
    <div>
      <p className="text-mist">對手已宣告聽牌，你要撐過 5 次出牌不放槍。宣告後他打出、或別人打出他沒胡的牌就是安全牌。</p>
      <button onClick={start} disabled={busy} className="mt-4 rounded-lg bg-ivory px-4 py-2 text-ink">{st ? "下一題" : "開始"}</button>
      {error && <p role="alert" className="mt-3 text-zhong">{error}</p>}
      {st && (
        <div className="mt-6 space-y-2">
          {st.discards.map((d, p) => (
            <div key={p} className="flex items-center gap-3">
              <span className={`w-20 text-sm ${st.declared.includes(p) ? "text-zhong" : "text-mist"}`}>
                {p === st.seat ? "你" : `對手 ${p + 1}`}{st.declared.includes(p) ? "（聽）" : ""}
              </span>
              <div className="flex flex-wrap gap-[1px]">{d.map((t, i) => <TileImage key={i} id={t} width={22} />)}</div>
              {(st.melds[p] ?? []).map((m, i) => (
                <span key={`m${i}`} className="ml-2 flex gap-[1px] border-l border-felt-line pl-2">
                  {m.tiles.map((t, j) => <TileImage key={j} id={m.type === "AN_KONG" && p !== st.seat ? null : t} width={22} />)}
                </span>
              ))}
            </div>
          ))}
          <p className="pt-4 tabular">
            {st.done
              ? st.dealt_in ? <span className="text-zhong">放槍了，打出 {last !== null ? tileName(last) : ""} 正好被胡。</span>
                : <span className="font-display text-2xl">成功守住！</span>
              : `已撐過 ${st.survived} / ${st.turns} 次出牌`}
          </p>
          {st.done && st.waits && (
            <p className="text-sm text-mist">
              對手聽的牌：{Object.values(st.waits).flat().map(tileName).join("、") || "（已胡牌）"}
            </p>
          )}
          <div className="pt-2">
            <Hand tiles={st.hand} drawn={st.drawn} onPick={pick} disabled={st.done || busy}
              mark={st.dealt_in ? last : null} />
          </div>
        </div>
      )}
    </div>
  );
}

export default function PracticePage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("scenario");
  return (
    <main className="mx-auto max-w-5xl px-5 py-8">
      <Link href="/" className="text-mist hover:text-ivory">← 大廳</Link>
      <h1 className="mt-4 font-display text-5xl">單人練習</h1>
      <p className="mt-2 text-mist">想自選三位 AI 對手的自由練習，請回大廳用「開一桌」。這裡的練習不影響 rating。</p>
      <div role="tablist" className="mt-6 flex gap-1 border-b border-felt-line">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-4 py-2 ${tab === t.id ? "border-ivory text-ivory" : "border-transparent text-mist"}`}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="mt-6">
        {tab === "scenario" && <ScenarioPanel />}
        {tab === "speed" && <SpeedPanel />}
        {tab === "defense" && <DefensePanel />}
      </div>
    </main>
  );
}
