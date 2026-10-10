"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { TileImage } from "@/components/Hand/TileImage";
import { LESSONS, lessonById } from "@/content/lessons";
import { markLessonDone } from "@/lib/progress";

export default function LessonPage() {
  const { id } = useParams<{ id: string }>();
  const lesson = lessonById(id);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  if (!lesson) return <main className="p-10">找不到這堂課。<Link href="/tutor" className="underline">回教練首頁</Link></main>;
  const idx = LESSONS.findIndex((l) => l.id === id);
  const next = LESSONS[idx + 1];
  const answered = Object.keys(answers).length === lesson.quiz.length;
  const correct = lesson.quiz.filter((q, i) => answers[i] === q.answer).length;

  return (
    <main className="mx-auto max-w-3xl px-5 py-10">
      <Link href="/tutor" className="text-mist hover:text-ivory">← AI 教練</Link>
      <p className="mt-6 text-mist">第 {idx + 1} 課</p>
      <h1 className="font-display text-5xl">{lesson.title}</h1>
      {lesson.sections.map((s) => (
        <section key={s.heading} className="mt-10">
          <h2 className="font-display text-2xl">{s.heading}</h2>
          {s.body.map((p, i) => <p key={i} className="mt-3 leading-relaxed">{p}</p>)}
          {s.tiles && (
            <div className="mt-4 flex flex-wrap gap-[3px]">
              {s.tiles.map((t, i) => <TileImage key={i} id={t} width={38} />)}
            </div>
          )}
        </section>
      ))}

      <section className="mt-12 border-t border-felt-line pt-8">
        <h2 className="font-display text-2xl">課後小測驗</h2>
        {lesson.quiz.map((q, qi) => (
          <fieldset key={qi} className="mt-6">
            <legend className="font-medium">{q.question}</legend>
            <div className="mt-3 flex flex-wrap gap-2">
              {q.options.map((o, oi) => {
                const picked = answers[qi] === oi;
                const show = answers[qi] !== undefined;
                const right = oi === q.answer;
                return (
                  <button key={oi} disabled={show}
                    onClick={() => {
                      const nextAnswers = { ...answers, [qi]: oi };
                      setAnswers(nextAnswers);
                      if (Object.keys(nextAnswers).length === lesson.quiz.length) {
                        const score = lesson.quiz.filter((qq, i) => nextAnswers[i] === qq.answer).length / lesson.quiz.length;
                        if (score === 1) markLessonDone(lesson.id, score);
                      }
                    }}
                    className={`rounded-md border px-4 py-2 ${
                      show && right ? "border-jade bg-jade/30" : show && picked ? "border-zhong bg-zhong/20" : "border-felt-line hover:bg-ivory/10"}`}>
                    {o}
                  </button>
                );
              })}
            </div>
            {answers[qi] !== undefined && <p className="mt-2 text-sm text-mist">{q.why}</p>}
          </fieldset>
        ))}
        {answered && (
          <div className="mt-8 flex items-center gap-4">
            <p>{correct === lesson.quiz.length ? "全部答對，這堂課完成了。" : `答對 ${correct} / ${lesson.quiz.length} 題，再讀一次上面的說明試試看。`}</p>
            {correct < lesson.quiz.length && (
              <button onClick={() => setAnswers({})} className="rounded-md border border-ivory/30 px-3 py-1.5">重新作答</button>
            )}
          </div>
        )}
        {next && (
          <Link href={`/tutor/lesson/${next.id}`} className="mt-8 inline-block rounded-lg bg-ivory px-5 py-2.5 text-ink">
            下一課：{next.title}
          </Link>
        )}
      </section>
    </main>
  );
}
