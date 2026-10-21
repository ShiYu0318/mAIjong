"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { GameButton } from "@/components/Game/GameButton";
import { PageShell } from "@/components/Game/PageShell";
import { Panel } from "@/components/Game/Panel";
import { ProgressBar } from "@/components/Game/ProgressBar";
import { LESSONS, localLesson } from "@/content/lessons";
import { startGuidedGame } from "@/lib/api";
import { useLocale, useT } from "@/lib/i18n";
import { completedLessons, syncLessons } from "@/lib/progress";
import { sfx } from "@/lib/sfx";
import { GameIcon } from "@/components/Game/GameIcon";
import { Check, CircleHelp, GraduationCap, ScanSearch, Users } from "lucide-react";

export default function TutorHome() {
  const router = useRouter();
  const t = useT();
  const locale = useLocale((s) => s.locale);
  const [done, setDone] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setDone(completedLessons());
    void syncLessons().then(setDone);
  }, []);
  const finished = LESSONS.filter((l) => done.has(l.id)).length;
  const next = LESSONS.find((l) => !done.has(l.id));

  return (
    <PageShell icon={<GameIcon icon={GraduationCap} tone="pink" size={60} />} title={t("AI 教練")}
      subtitle={t("從認識牌張開始，學完規則後和初學 AI 打一手，教練會解說每一張打出的牌。")}>
      <section className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <Panel title={t("課程")} action={<span className="tabular font-black text-gold">{finished} / {LESSONS.length}</span>}>
          <ProgressBar value={finished} max={LESSONS.length} label={t("課程進度")}
            color="linear-gradient(90deg,#43e0a3,#16a874)" />
          <ol className="mt-4 grid gap-2">
            {LESSONS.map((l, i) => {
              const isDone = done.has(l.id);
              const isNext = next?.id === l.id;
              return (
                <li key={l.id} className="animate-rise" style={{ animationDelay: `${i * 40}ms` }}>
                  <Link href={`/tutor/lesson/${l.id}`} onClick={() => sfx.tap()}
                    className={`flex items-center gap-4 rounded-2xl p-3 transition hover:-translate-y-0.5 ${
                      isNext ? "bg-gold/15 ring-2 ring-gold/70" : "bg-black/20 hover:bg-black/30"}`}>
                    <span className={`flex size-10 shrink-0 items-center justify-center rounded-full font-black ${
                      isDone ? "bg-jade text-ink" : isNext ? "bg-gold text-ink" : "bg-white/10 text-mist"}`}>
                      {isDone ? <Check size={18} strokeWidth={3.2} aria-label={t("已完成")} /> : i + 1}
                    </span>
                    <span className="flex-1">
                      <span className="block font-black">{localLesson(l, locale).title}</span>
                      <span className="block text-sm text-mist">{localLesson(l, locale).summary}</span>
                    </span>
                    {isNext && <span className="rounded-full bg-gold px-3 py-1 text-xs font-black text-ink">{t("下一課")}</span>}
                    {isDone && <span className="text-sm font-bold text-jade">{t("已完成")}</span>}
                  </Link>
                </li>
              );
            })}
          </ol>
        </Panel>
        <div className="space-y-5">
          <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#d14200] via-[#d8301f] to-[#e31f4a] p-6 shadow-[0_14px_40px_rgb(5_6_25/0.5)] ring-1 ring-white/15">
            <Users className="pointer-events-none absolute -top-3 -right-3 opacity-20" size={120} strokeWidth={1.6} aria-hidden="true" />
            <h2 className="font-display text-2xl font-black">{t("引導對局")}</h2>
            <p className="mt-1 text-white/85">{t("和三位初學 AI 打一圈，不限時，每次出牌都有教練解說。")}</p>
            <GameButton size="lg" className="mt-4 w-full" disabled={busy} onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                router.push(`/room/${await startGuidedGame()}`);
              } catch {
                sfx.error();
                setError(t("連不上伺服器，請確認後端已啟動。"));
                setBusy(false);
              }
            }}>
              {busy ? t("準備牌桌…") : t("開始引導對局")}
            </GameButton>
            {error && <p role="alert" className="mt-2 font-bold">{error}</p>}
          </section>
          <Link href="/tutor/analyze" onClick={() => sfx.tap()}
            className="block rounded-3xl bg-gradient-to-br from-[#196aff] to-[#6a3fe0] p-6 shadow-[0_10px_30px_rgb(5_6_25/0.45)] ring-1 ring-white/15 transition hover:-translate-y-1">
            <h2 className="flex items-center gap-2 font-display text-2xl font-black"><GameIcon icon={ScanSearch} tone="blue" size={34} />{t("手牌分析")}</h2>
            <p className="mt-1 text-white/85">{t("拼出任何一手牌，看向聽數、每張牌打出後的進張與聽牌台數。")}</p>
            <span className="mt-3 inline-block font-black underline">{t("打開手牌分析")}</span>
          </Link>
          <Link href="/tutor/quiz" onClick={() => sfx.tap()}
            className="block rounded-3xl bg-gradient-to-br from-[#e60057] to-[#9542ff] p-6 shadow-[0_10px_30px_rgb(5_6_25/0.45)] ring-1 ring-white/15 transition hover:-translate-y-1">
            <h2 className="flex items-center gap-2 font-display text-2xl font-black"><GameIcon icon={CircleHelp} tone="pink" size={34} />{t("決策問答")}</h2>
            <p className="mt-1 text-white/85">{t("從真實牌局抽出一個局面，你決定打哪張，教練評分並說明理由。")}</p>
            <span className="mt-3 inline-block font-black underline">{t("開始問答")}</span>
          </Link>
        </div>
      </section>
    </PageShell>
  );
}
