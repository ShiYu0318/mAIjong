import { authToken, tutor } from "./api";

const KEY = "maijong.lessons";

export function completedLessons(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(KEY) ?? "[]") as string[]);
  } catch {
    return new Set();
  }
}

export function markLessonDone(id: string, score: number) {
  const done = completedLessons();
  done.add(id);
  try {
    localStorage.setItem(KEY, JSON.stringify([...done]));
  } catch {
    /* ignore */
  }
  if (authToken()) tutor.setProgress(id, "COMPLETED", score).catch(() => undefined);
}

const QUIZ_KEY = "maijong.quizRate";

export function quizRate(): number {
  try {
    return Number(localStorage.getItem(QUIZ_KEY) ?? "0.5");
  } catch {
    return 0.5;
  }
}

export function recordQuiz(correct: boolean): number {
  const rate = quizRate() * 0.8 + (correct ? 0.2 : 0);
  try {
    localStorage.setItem(QUIZ_KEY, String(rate));
  } catch {
    /* ignore */
  }
  return rate;
}

/** Adaptive difficulty from the moving success rate. */
export const difficultyFor = (rate: number) => (rate > 0.75 ? 3 : rate < 0.4 ? 1 : 2);
