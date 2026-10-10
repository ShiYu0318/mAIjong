"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { TileImage } from "@/components/Hand/TileImage";
import { ApiError, rooms, saveTicket } from "@/lib/api";

// a real 平胡 hand: 123萬 456萬 789筒 234條 678條 + 55筒
const SAMPLE_HAND = [0, 1, 2, 3, 4, 5, 24, 25, 26, 10, 11, 12, 14, 15, 16, 22, 22];
const LEVELS = [
  { v: 1, label: "初學" },
  { v: 2, label: "入門" },
  { v: 3, label: "普通" },
  { v: 4, label: "進階" },
  { v: 5, label: "高手" },
];
const NAME_KEY = "maijong.name";

export default function Lobby() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [timeLimit, setTimeLimit] = useState<number | null>(30);
  const [rounds, setRounds] = useState(1);
  const [seats, setSeats] = useState<(number | null)[]>([null, 3, 3, 3]);

  useEffect(() => {
    try {
      setName(localStorage.getItem(NAME_KEY) ?? "");
    } catch {
      /* ignore */
    }
  }, []);

  const rememberName = () => {
    try {
      if (name) localStorage.setItem(NAME_KEY, name);
    } catch {
      /* ignore */
    }
  };

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError(null);
    rememberName();
    try {
      await fn();
    } catch (e) {
      setError(e instanceof ApiError ? describeError(e) : "連不上伺服器，請確認後端已啟動。");
      setBusy(null);
    }
  }

  const quick = () =>
    run("quick", async () => {
      const j = await rooms.quick(name || undefined);
      saveTicket(j.room.room_id, j);
      router.push(`/room/${j.room.room_id}`);
    });

  const create = () =>
    run("create", async () => {
      const r = await rooms.create("PRIVATE", {
        time_limit: timeLimit, rounds, bot_levels: seats,
      });
      const j = await rooms.join(r.room_id, name || undefined, 0);
      saveTicket(r.room_id, j);
      router.push(`/room/${r.room_id}`);
    });

  const joinByCode = () =>
    run("code", async () => {
      const room = await rooms.get(code.trim().toUpperCase());
      const j = await rooms.join(room.room_id, name || undefined);
      saveTicket(room.room_id, j);
      router.push(`/room/${room.room_id}`);
    });

  return (
    <main className="mx-auto max-w-6xl px-5 py-10 sm:px-10 sm:py-16">
      <header className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <h1 className="font-display text-6xl leading-none sm:text-8xl">麥醬</h1>
          <p className="mt-4 max-w-md text-lg text-mist">
            台灣十六張麻將。和 AI 對手同桌練功，或開一桌邀朋友來打。
          </p>
          <nav className="mt-3 flex gap-5">
            <Link href="/tutor" className="text-ivory underline underline-offset-4">第一次玩？從 AI 教練開始</Link>
            <Link href="/lab" className="text-mist underline underline-offset-4 hover:text-ivory">實驗室</Link>
          </nav>
        </div>
        <label className="flex flex-col gap-1 text-sm text-mist">
          你的暱稱
          <input
            value={name}
            onChange={(e) => setName(e.target.value.slice(0, 20))}
            placeholder="不填就用訪客名稱"
            className="w-56 rounded-md border border-felt-line bg-felt-deep px-3 py-2 text-ivory placeholder:text-mist/60"
          />
        </label>
      </header>

      <div className="mt-10 flex flex-wrap gap-[3px]" aria-label="平胡牌型範例">
        {SAMPLE_HAND.map((t, i) => (
          <TileImage key={i} id={t} width={44} className={i === 16 ? "ml-3 -translate-y-2" : ""} />
        ))}
      </div>

      {error && (
        <p role="alert" className="mt-8 rounded-md border border-zhong/60 bg-zhong/15 px-4 py-3">
          {error}
        </p>
      )}

      <section className="mt-12 grid gap-10 lg:grid-cols-[1.1fr_1.4fr_0.9fr]">
        <div>
          <h2 className="font-display text-3xl">快速配對</h2>
          <p className="mt-2 text-mist">和正在等待的玩家湊一桌；30 秒內沒湊滿就由 AI 補位。</p>
          <button
            onClick={quick}
            disabled={busy !== null}
            className="mt-6 w-full rounded-lg bg-ivory px-6 py-4 font-display text-2xl text-ink transition hover:bg-white disabled:opacity-60"
          >
            {busy === "quick" ? "配對中…" : "開始配對"}
          </button>
        </div>

        <div className="border-felt-line lg:border-x lg:px-10">
          <h2 className="font-display text-3xl">開一桌</h2>
          <div className="mt-5 grid gap-5">
            <fieldset>
              <legend className="text-sm text-mist">座位</legend>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {seats.map((lvl, i) => (
                  <select
                    key={i}
                    aria-label={`座位 ${i + 1}`}
                    value={i === 0 ? "me" : lvl === null ? "open" : String(lvl)}
                    disabled={i === 0}
                    onChange={(e) => {
                      const v = e.target.value;
                      setSeats(seats.map((x, j) => (j === i ? (v === "open" ? null : Number(v)) : x)));
                    }}
                    className="rounded-md border border-felt-line bg-felt-deep px-2 py-2 text-sm"
                  >
                    {i === 0 && <option value="me">你</option>}
                    <option value="open">留給玩家</option>
                    {LEVELS.map((l) => (
                      <option key={l.v} value={l.v}>AI {l.label}</option>
                    ))}
                  </select>
                ))}
              </div>
            </fieldset>
            <div className="flex flex-wrap gap-6">
              <label className="flex flex-col gap-1 text-sm text-mist">
                每次行動時限
                <select
                  value={timeLimit ?? "none"}
                  onChange={(e) => setTimeLimit(e.target.value === "none" ? null : Number(e.target.value))}
                  className="rounded-md border border-felt-line bg-felt-deep px-2 py-2 text-ivory"
                >
                  <option value={15}>15 秒</option>
                  <option value={30}>30 秒</option>
                  <option value={60}>60 秒</option>
                  <option value="none">不限時</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm text-mist">
                打幾圈
                <select
                  value={rounds}
                  onChange={(e) => setRounds(Number(e.target.value))}
                  className="rounded-md border border-felt-line bg-felt-deep px-2 py-2 text-ivory"
                >
                  <option value={1}>東風圈</option>
                  <option value={2}>東南兩圈</option>
                  <option value={3}>三圈</option>
                  <option value={4}>一將（四圈）</option>
                </select>
              </label>
            </div>
            <button
              onClick={create}
              disabled={busy !== null}
              className="w-fit rounded-lg bg-tong px-6 py-3 font-medium text-ivory transition hover:brightness-110 disabled:opacity-60"
            >
              {busy === "create" ? "開桌中…" : "開桌"}
            </button>
          </div>
        </div>

        <div>
          <h2 className="font-display text-3xl">用房間碼加入</h2>
          <form
            className="mt-5 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (code.trim().length === 6) joinByCode();
            }}
          >
            <input
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase().slice(0, 6))}
              placeholder="XK49AB"
              aria-label="六碼房間碼"
              className="tabular w-36 rounded-md border border-felt-line bg-felt-deep px-3 py-2 text-lg tracking-[0.2em] uppercase"
            />
            <button
              type="submit"
              disabled={busy !== null || code.trim().length !== 6}
              className="rounded-md border border-ivory/40 px-4 py-2 transition hover:bg-ivory/10 disabled:opacity-40"
            >
              加入
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}

function describeError(e: ApiError): string {
  if (e.status === 404) return "找不到這個房間，請確認房間碼。";
  if (e.status === 409) return `無法加入：${e.message}`;
  return `發生錯誤：${e.message}`;
}
