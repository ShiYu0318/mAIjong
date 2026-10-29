"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CircleCheck, CircleX, ThumbsUp } from "lucide-react";
import { GameButton } from "@/components/Game/GameButton";
import { TileImage } from "@/components/Hand/TileImage";
import { ApiError, practice, saveTicket } from "@/lib/api";
import { explainEn } from "@/lib/explain";
import { useLocale, useT } from "@/lib/i18n";
import type { ScenarioInfo, ScenarioResult } from "@/lib/protocol";
import { scenarioDescriptionEn, scenarioTitleEn } from "@/lib/scenarioText";
import { tileName } from "@/lib/tiles";
import { useGame } from "@/store/gameStore";

const VERDICT = { best: "最佳選擇", good: "不錯的選擇", worse: "還有更好的打法" } as const;
const ACTION_WORD: Record<string, string> = {
  PON: "碰", KONG: "槓", HU: "胡", PASS: "過", CHI_LOW: "吃", CHI_MID: "吃", CHI_HIGH: "吃",
  DISCARD: "打出", TING: "打出並宣告聽牌",
};

function useScenarioNav(info: ScenarioInfo) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const t = useT();
  const go = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      const j = await practice.playScenario(id);
      saveTicket(j.room.room_id, j);
      router.push(`/room/${j.room.room_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("無法開始"));
      setBusy(false);
    }
  };
  const next = async () => {
    try {
      const all = await practice.scenarios();
      const same = all.filter((s) => s.category === info.category);
      const at = same.findIndex((s) => s.id === info.id);
      await go(same[(at + 1) % same.length].id);
    } catch {
      setError(t("無法開始"));
    }
  };
  return { retry: () => go(info.id), next, busy, error };
}

function useScenarioText(info: ScenarioInfo) {
  const en = useLocale((s) => s.locale) === "en";
  return {
    title: en ? scenarioTitleEn(info.title) : info.title,
    description: en ? scenarioDescriptionEn(info.description) : info.description,
  };
}

/** The question, shown above the table for the whole hand. */
export function ScenarioBanner({ info }: { info: ScenarioInfo }) {
  const t = useT();
  const { title, description } = useScenarioText(info);
  return (
    <section aria-label={t("練習題目")}
      className="absolute top-3 left-1/2 z-10 w-[min(560px,calc(100%-1.5rem))] -translate-x-1/2 rounded-2xl bg-black/70 px-4 py-2 text-center shadow-lg">
      <p className="font-black text-gold">{title}</p>
      <p className="text-sm text-ivory-dim">{description}</p>
    </section>
  );
}

function ResultLine({ result }: { result: ScenarioResult }) {
  const t = useT();
  const en = useLocale((s) => s.locale) === "en";
  if (result.kind === "discard") {
    return <>{en ? explainEn(result.candidates ?? [], result.chosen as never) : result.explanation}</>;
  }
  const best = result.best as { action_type: string; tile: number | null };
  const mine = result.chosen as { action_type: string; tile: number | null };
  const word = (a: { action_type: string; tile: number | null }) =>
    `${t(ACTION_WORD[a.action_type] ?? a.action_type)}${a.tile !== null ? ` ${tileName(a.tile)}` : ""}`;
  return <>{result.verdict === "best"
    ? t("和 AI 高手的選擇一樣：{best}。", { best: word(best) })
    : t("AI 高手在這裡會選擇「{best}」，你選了「{mine}」。", { best: word(best), mine: word(mine) })}</>;
}

function Verdict({ result }: { result: ScenarioResult }) {
  const t = useT();
  const Icon = result.verdict === "best" ? CircleCheck : result.verdict === "good" ? ThumbsUp : CircleX;
  const tone = result.verdict === "worse" ? "text-zhong" : "text-jade";
  return (
    <p className={`flex items-center gap-2 font-display text-3xl font-black ${tone}`}>
      <Icon size={30} strokeWidth={2.6} aria-hidden="true" />{t(VERDICT[result.verdict])}
    </p>
  );
}

function Actions({ info, children }: { info: ScenarioInfo; children?: React.ReactNode }) {
  const t = useT();
  const nav = useScenarioNav(info);
  return (
    <>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {children}
        <GameButton size="sm" onClick={nav.retry} disabled={nav.busy}>{t("再試一次")}</GameButton>
        <GameButton size="sm" variant="blue" onClick={nav.next} disabled={nav.busy}>{t("下一題")}</GameButton>
        <Link href="/practice" className="ml-1 text-sm text-mist underline">{t("回練習列表")}</Link>
      </div>
      {nav.error && <p role="alert" className="mt-2 text-sm font-bold text-zhong">{nav.error}</p>}
    </>
  );
}

/** Right after the key move: was it right, and why. */
export function ScenarioFeedback({ info }: { info: ScenarioInfo }) {
  const t = useT();
  const result = useGame((s) => s.scenarioResult);
  const gameEnd = useGame((s) => s.gameEnd);
  const [open, setOpen] = useState(true);
  if (!result || !open || gameEnd) return null;
  return (
    <section role="dialog" aria-label={t("這一手的判定")}
      className="absolute top-24 left-1/2 z-30 w-[min(520px,calc(100%-1.5rem))] -translate-x-1/2 animate-pop-in rounded-2xl border border-white/10 bg-felt-deep/95 p-5 shadow-2xl">
      <Verdict result={result} />
      <p className="mt-2 leading-relaxed"><ResultLine result={result} /></p>
      {result.kind === "discard" && result.candidates && (
        <ol className="mt-3 space-y-1 text-sm">
          {result.candidates.slice(0, 4).map((c, i) => (
            <li key={c.tile} className={`flex items-center gap-3 rounded-lg px-2 py-1 ${
              c.tile === result.chosen.tile ? "bg-gold/15 ring-1 ring-gold/50" : ""}`}>
              <span className="tabular w-4 text-mist">{i + 1}</span>
              <TileImage id={c.tile} width={24} />
              <span>{c.shanten_after === 0 ? t("聽牌") : t("{n} 向聽", { n: c.shanten_after })}</span>
              <span className="tabular text-mist">{t("進張 {n} 張", { n: c.uke_count })}</span>
              {c.tile === result.chosen.tile && <span className="ml-auto text-xs font-black text-gold">{t("你的選擇")}</span>}
            </li>
          ))}
        </ol>
      )}
      <Actions info={info}>
        <GameButton size="sm" variant="ghost" onClick={() => setOpen(false)}>{t("繼續打完這手")}</GameButton>
      </Actions>
    </section>
  );
}

/** Replaces the final ranking when a practice hand ends. */
export function ScenarioWrapUp({ info }: { info: ScenarioInfo }) {
  const t = useT();
  const result = useGame((s) => s.scenarioResult);
  const { title } = useScenarioText(info);
  return (
    <div className="mt-6">
      <h3 className="font-display text-2xl font-black">{title}</h3>
      {result ? (
        <div className="mt-2">
          <Verdict result={result} />
          <p className="mt-1 text-sm leading-relaxed text-ivory-dim"><ResultLine result={result} /></p>
        </div>
      ) : <p className="mt-2 text-mist">{t("這一手沒有輪到你做關鍵決定。")}</p>}
      <Actions info={info} />
    </div>
  );
}
