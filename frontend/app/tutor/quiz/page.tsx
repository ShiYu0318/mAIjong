"use client";

import { PageShell } from "@/components/Game/PageShell";
import { useCallback, useEffect, useState } from "react";
import { TileImage } from "@/components/Hand/TileImage";
import { type QuizAnswer, type QuizPosition, tutor } from "@/lib/api";
import { difficultyFor, quizRate, recordQuiz } from "@/lib/progress";
import { tileName, windName } from "@/lib/tiles";
import { explainEn } from "@/lib/explain";
import { useLocale, useT } from "@/lib/i18n";
import { GameIcon } from "@/components/Game/GameIcon";
import { CircleHelp } from "lucide-react";

const VERDICT = { best: "最佳選擇", good: "不錯的選擇", worse: "還有更好的打法" };
const DIFF = ["", "入門", "中等", "進階"];

export default function QuizPage() {
  const t = useT();
  const en = useLocale((s) => s.locale) === "en";
  const [token, setToken] = useState<string | null>(null);
  const [pos, setPos] = useState<QuizPosition | null>(null);
  const [answer, setAnswer] = useState<QuizAnswer | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  const [difficulty, setDifficulty] = useState(2);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setPos(null);
    setAnswer(null);
    setPicked(null);
    setError(null);
    const d = difficultyFor(quizRate());
    setDifficulty(d);
    try {
      const q = await tutor.quiz(d);
      setToken(q.quiz_token);
      setPos(q.position);
    } catch {
      setError(t("出題失敗，請確認後端已啟動。"));
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const choose = async (tile: number) => {
    if (!token || answer) return;
    setPicked(tile);
    try {
      const a = await tutor.answer(token, tile);
      recordQuiz(a.verdict !== "worse");
      setAnswer(a);
    } catch {
      setError(t("評分失敗，請換一題。"));
    }
  };

  return (
    <PageShell icon={<GameIcon icon={CircleHelp} tone="pink" size={60} />} backHref="/tutor" backLabel={t("AI 教練")} title={t("決策問答")}>
      <p className="mt-3 text-mist">{t("輪到你打牌，選一張打出。難度：{d}（依答對率自動調整）", { d: t(DIFF[difficulty]) })}</p>
      {error && <p role="alert" className="mt-4 text-zhong">{error}</p>}
      {!pos && !error && <p className="mt-10 text-mist">{t("從牌局中抽題…")}</p>}
      {pos && (
        <>
          <p className="mt-6 text-sm text-mist">
            {t("{round}風圈・你是{seat}家・牌牆剩 {n} 張", { round: windName(pos.round_wind), seat: windName(pos.seat_wind), n: pos.drawable })}
            {pos.declared.some((d, i) => d && i !== pos.seat) ? t("・有對手已宣告聽牌") : ""}
          </p>
          <div className="mt-6 space-y-2">
            {pos.discards.map((d, p) => (
              <div key={p} className="flex items-center gap-3">
                <span className="w-20 text-sm text-mist">
                  {p === pos.seat ? t("你") : t("對手{n}", { n: p + 1 })}{pos.declared[p] ? t("（聽）") : ""}
                </span>
                <div className="flex flex-wrap gap-[1px]">{d.map((x, i) => <TileImage key={i} id={x} width={22} />)}</div>
              </div>
            ))}
          </div>
          <div className="panel mt-8 flex flex-wrap items-end gap-[3px] p-4">
            {pos.hand.map((x, i) => (
              <button key={i} onClick={() => choose(x)} disabled={!!answer}
                className={`transition ${picked === x && i === pos.hand.indexOf(x) ? "-translate-y-3 drop-shadow-[0_0_10px_rgb(56_208_255/0.8)]" : "hover:-translate-y-2"}`}
                aria-label={t("打出 {tile}", { tile: tileName(x) })}>
                <TileImage id={x} width={44} />
              </button>
            ))}
            {pos.melds.map((m, i) => (
              <span key={i} className="ml-3 flex gap-[1px]">{m.tiles.map((x, j) => <TileImage key={j} id={x} width={30} />)}</span>
            ))}
          </div>
        </>
      )}
      {answer && (
        <section className="mt-8 border-t border-felt-line pt-6">
          <p className={`font-display text-3xl ${answer.verdict === "worse" ? "text-zhong" : "text-ivory"}`}>
            {t(VERDICT[answer.verdict])}
          </p>
          <p className="mt-3 leading-relaxed">{en ? explainEn(answer.candidates, answer.chosen) : answer.explanation}</p>
          <ol className="mt-4 space-y-1 text-sm">
            {answer.candidates.map((c, i) => (
              <li key={c.tile} className="flex items-center gap-3">
                <span className="tabular w-5 text-mist">{i + 1}</span>
                <TileImage id={c.tile} width={24} />
                <span>{c.shanten_after === 0 ? t("聽牌") : t("{n} 向聽", { n: c.shanten_after })}</span>
                <span className="tabular text-mist">{t("進張 {n} 張", { n: c.uke_count })}</span>
              </li>
            ))}
          </ol>
          <button onClick={load} className="btn-game mt-6 btn-primary px-6 py-3">{t("下一題")}</button>
        </section>
      )}
    </PageShell>
  );
}
