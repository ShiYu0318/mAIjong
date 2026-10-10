"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { TileImage } from "@/components/Hand/TileImage";
import { type QuizAnswer, type QuizPosition, tutor } from "@/lib/api";
import { difficultyFor, quizRate, recordQuiz } from "@/lib/progress";
import { WINDS } from "@/lib/tiles";

const VERDICT = { best: "最佳選擇", good: "不錯的選擇", worse: "還有更好的打法" };
const DIFF = ["", "入門", "中等", "進階"];

export default function QuizPage() {
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
      setError("出題失敗，請確認後端已啟動。");
    }
  }, []);

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
      setError("評分失敗，請換一題。");
    }
  };

  return (
    <main className="mx-auto max-w-4xl px-5 py-10">
      <Link href="/tutor" className="text-mist hover:text-ivory">← AI 教練</Link>
      <h1 className="mt-4 font-display text-5xl">決策問答</h1>
      <p className="mt-3 text-mist">輪到你打牌，選一張打出。難度：{DIFF[difficulty]}（依答對率自動調整）</p>
      {error && <p role="alert" className="mt-4 text-zhong">{error}</p>}
      {!pos && !error && <p className="mt-10 text-mist">從牌局中抽題…</p>}
      {pos && (
        <>
          <p className="mt-6 text-sm text-mist">
            {WINDS[pos.round_wind]}風圈・你是{WINDS[pos.seat_wind]}家・牌牆剩 {pos.drawable} 張
            {pos.declared.some((d, i) => d && i !== pos.seat) ? "・有對手已宣告聽牌" : ""}
          </p>
          <div className="mt-6 space-y-2">
            {pos.discards.map((d, p) => (
              <div key={p} className="flex items-center gap-3">
                <span className="w-16 text-sm text-mist">{p === pos.seat ? "你" : `對手${p + 1}`}{pos.declared[p] ? "（聽）" : ""}</span>
                <div className="flex flex-wrap gap-[1px]">{d.map((t, i) => <TileImage key={i} id={t} width={22} />)}</div>
              </div>
            ))}
          </div>
          <div className="mt-8 flex flex-wrap items-end gap-[3px]">
            {pos.hand.map((t, i) => (
              <button key={i} onClick={() => choose(t)} disabled={!!answer}
                className={`transition ${picked === t && i === pos.hand.indexOf(t) ? "-translate-y-2" : "hover:-translate-y-1"}`}
                aria-label={`打出 ${t}`}>
                <TileImage id={t} width={44} />
              </button>
            ))}
            {pos.melds.map((m, i) => (
              <span key={i} className="ml-3 flex gap-[1px]">{m.tiles.map((t, j) => <TileImage key={j} id={t} width={30} />)}</span>
            ))}
          </div>
        </>
      )}
      {answer && (
        <section className="mt-8 border-t border-felt-line pt-6">
          <p className={`font-display text-3xl ${answer.verdict === "worse" ? "text-zhong" : "text-ivory"}`}>
            {VERDICT[answer.verdict]}
          </p>
          <p className="mt-3 leading-relaxed">{answer.explanation}</p>
          <ol className="mt-4 space-y-1 text-sm">
            {answer.candidates.map((c, i) => (
              <li key={c.tile} className="flex items-center gap-3">
                <span className="tabular w-5 text-mist">{i + 1}</span>
                <TileImage id={c.tile} width={24} />
                <span>{c.shanten_after === 0 ? "聽牌" : `${c.shanten_after} 向聽`}</span>
                <span className="tabular text-mist">進張 {c.uke_count} 張</span>
              </li>
            ))}
          </ol>
          <button onClick={load} className="mt-6 rounded-lg bg-ivory px-5 py-2.5 text-ink">下一題</button>
        </section>
      )}
    </main>
  );
}
