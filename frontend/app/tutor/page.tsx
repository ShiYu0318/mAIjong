"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LESSONS } from "@/content/lessons";
import { startGuidedGame } from "@/lib/api";
import { completedLessons } from "@/lib/progress";

export default function TutorHome() {
  const router = useRouter();
  const [done, setDone] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setDone(completedLessons());
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-5 py-10 sm:px-10">
      <Link href="/" className="text-mist hover:text-ivory">← 大廳</Link>
      <h1 className="mt-4 font-display text-5xl">AI 教練</h1>
      <p className="mt-3 max-w-xl text-mist">從認識牌張開始，學完規則後和初學 AI 打一手，教練會解說每一張打出的牌。</p>

      <section className="mt-10 grid gap-10 lg:grid-cols-[1.3fr_1fr]">
        <div>
          <h2 className="font-display text-3xl">課程</h2>
          <ol className="mt-4 divide-y divide-felt-line border-y border-felt-line">
            {LESSONS.map((l, i) => (
              <li key={l.id}>
                <Link href={`/tutor/lesson/${l.id}`} className="flex items-baseline gap-4 py-3 hover:bg-ivory/5">
                  <span className="tabular w-6 text-mist">{i + 1}</span>
                  <span className="flex-1">
                    <span className="text-lg">{l.title}</span>
                    <span className="block text-sm text-mist">{l.summary}</span>
                  </span>
                  {done.has(l.id) && <span className="text-sm text-jade">已完成</span>}
                </Link>
              </li>
            ))}
          </ol>
        </div>
        <div className="space-y-8">
          <div>
            <h2 className="font-display text-3xl">引導對局</h2>
            <p className="mt-2 text-mist">和三位初學 AI 打一圈，不限時，每次出牌都有教練解說。</p>
            <button disabled={busy} onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                router.push(`/room/${await startGuidedGame()}`);
              } catch {
                setError("連不上伺服器，請確認後端已啟動。");
                setBusy(false);
              }
            }} className="mt-4 rounded-lg bg-ivory px-5 py-3 font-display text-xl text-ink hover:bg-white disabled:opacity-60">
              {busy ? "準備牌桌…" : "開始引導對局"}
            </button>
            {error && <p role="alert" className="mt-2 text-zhong">{error}</p>}
          </div>
          <div>
            <h2 className="font-display text-3xl">手牌分析</h2>
            <p className="mt-2 text-mist">拼出任何一手牌，看向聽數、每張牌打出後的進張與聽牌台數。</p>
            <Link href="/tutor/analyze" className="mt-3 inline-block underline">打開手牌分析</Link>
          </div>
          <div>
            <h2 className="font-display text-3xl">決策問答</h2>
            <p className="mt-2 text-mist">從真實牌局抽出一個局面，你決定打哪張，教練評分並說明理由。</p>
            <Link href="/tutor/quiz" className="mt-3 inline-block underline">開始問答</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
