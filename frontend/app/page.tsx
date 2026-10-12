"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { PlayerBar } from "@/components/Account/PlayerBar";
import { CoinIcon } from "@/components/Game/CoinCounter";
import { GameButton } from "@/components/Game/GameButton";
import { Panel } from "@/components/Game/Panel";
import { ProgressBar } from "@/components/Game/ProgressBar";
import { TileImage } from "@/components/Hand/TileImage";
import { ApiError, profileApi, rooms, saveTicket } from "@/lib/api";
import { translate, useT } from "@/lib/i18n";
import { sfx } from "@/lib/sfx";
import { useAccount } from "@/store/accountStore";

// a real 平胡 hand: 123萬 456萬 789筒 234條 678條 + 55筒
const SAMPLE_HAND = [0, 1, 2, 3, 4, 5, 24, 25, 26, 10, 11, 12, 14, 15, 16, 22, 22];
const FLOATING = [31, 27, 22, 9, 33, 4];
const LEVELS = [
  { v: 1, label: "初學" },
  { v: 2, label: "入門" },
  { v: 3, label: "普通" },
  { v: 4, label: "進階" },
  { v: 5, label: "高手" },
];
const select = "rounded-xl border border-white/10 bg-felt-deep px-2 py-2 text-sm text-ivory";

export default function Lobby() {
  const router = useRouter();
  const t = useT();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [timeLimit, setTimeLimit] = useState<number | null>(30);
  const [rounds, setRounds] = useState(1);
  const [seats, setSeats] = useState<(number | null)[]>([null, 3, 3, 3]);

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError(null);
    try {
      await fn();
    } catch (e) {
      sfx.error();
      setError(e instanceof ApiError ? describeError(e) : t("連不上伺服器，請確認後端已啟動。"));
      setBusy(null);
    }
  }

  const quick = () =>
    run("quick", async () => {
      const j = await rooms.quick();
      saveTicket(j.room.room_id, j);
      router.push(`/room/${j.room.room_id}`);
    });

  const create = () =>
    run("create", async () => {
      const r = await rooms.create("PRIVATE", { time_limit: timeLimit, rounds, bot_levels: seats });
      const j = await rooms.join(r.room_id, undefined, 0);
      saveTicket(r.room_id, j);
      router.push(`/room/${r.room_id}`);
    });

  const joinByCode = () =>
    run("code", async () => {
      const room = await rooms.get(code.trim().toUpperCase());
      const j = await rooms.join(room.room_id);
      saveTicket(room.room_id, j);
      router.push(`/room/${room.room_id}`);
    });

  return (
    <main className="mx-auto max-w-7xl px-4 pt-4 pb-12 sm:px-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <Link href="/" className="font-display text-2xl font-black tracking-wide">
          <span className="bg-gradient-to-r from-gold to-amber bg-clip-text text-transparent">{t("麥醬")}</span>
          <span className="ml-1 text-sm font-bold text-mist">mAIjong</span>
        </Link>
        <PlayerBar />
      </header>

      <section className="relative mt-8 grid items-center gap-8 lg:grid-cols-[1.2fr_1fr]">
        <div className="min-w-0 animate-rise">
          <h1 className="font-display text-6xl leading-none font-black sm:text-8xl">
            <span className="bg-gradient-to-b from-white to-ivory-dim bg-clip-text text-transparent drop-shadow-[0_6px_0_rgb(0_0_0_/_0.25)]">
              {t("麥醬")}
            </span>
          </h1>
          <p className="mt-4 max-w-lg text-lg text-ivory-dim">
            {t("台灣十六張麻將。和 AI 對手同桌練功，或開一桌邀朋友來打。")}
          </p>
          <div className="mt-6 flex max-w-full gap-[2px] overflow-x-auto pb-2" aria-label={t("平胡牌型範例")}>
            {SAMPLE_HAND.map((tile, i) => (
              <TileImage key={i} id={tile} width={34} className={`shrink-0 ${i === 16 ? "ml-2 -translate-y-2" : ""}`} />
            ))}
          </div>
        </div>
        <div className="relative hidden h-56 lg:block" aria-hidden="true">
          {FLOATING.map((tile, i) => (
            <span key={i} className="absolute animate-float"
              style={{ left: `${8 + (i % 3) * 30}%`, top: `${i < 3 ? 6 : 46}%`, animationDelay: `${i * 0.4}s` }}>
              <span className="block" style={{ transform: `rotate(${(i % 2 ? 1 : -1) * (6 + i * 2)}deg)` }}>
                <TileImage id={tile} width={70} />
              </span>
            </span>
          ))}
        </div>
      </section>

      {error && (
        <p role="alert" className="mt-6 animate-wiggle rounded-2xl border border-zhong/60 bg-zhong/15 px-4 py-3 font-bold">
          {error}
        </p>
      )}

      <section className="mt-8 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_340px]">
        <ModeCard tone="amber" icon="⚡" className="lg:row-span-2">
          <h2 className="font-display text-3xl font-black">{t("快速配對")}</h2>
          <p className="mt-2 text-white/85">{t("和正在等待的玩家湊一桌；30 秒內沒湊滿就由 AI 補位。")}</p>
          <div className="relative my-6 flex min-h-28 flex-1 scale-75 items-center justify-center sm:scale-100" aria-hidden="true">
            {[27, 31, 0, 32, 28].map((tile, i) => (
              <span key={i} className="absolute transition-transform"
                style={{ transform: `translateX(${(i - 2) * 46}px) translateY(${Math.abs(i - 2) * 10}px) rotate(${(i - 2) * 9}deg)` }}>
                <TileImage id={tile} width={64} />
              </span>
            ))}
          </div>
          <div className="flex flex-wrap gap-2 text-sm font-bold">
            {[t("1 秒湊桌"), t("AI 30 秒補位"), t("可得經驗值與金幣")].map((tag) => (
              <span key={tag} className="rounded-full bg-black/20 px-3 py-1">{tag}</span>
            ))}
          </div>
          <div className="mt-auto pt-6">
            <GameButton size="xl" className="w-full" onClick={quick} disabled={busy !== null}>
              {busy === "quick" ? t("配對中…") : t("開始配對")}
            </GameButton>
          </div>
        </ModeCard>

        <ModeCard tone="blue" icon="🀄" className="lg:row-span-2">
          <h2 className="font-display text-3xl font-black">{t("開一桌")}</h2>
          <fieldset className="mt-4">
            <legend className="text-sm text-white/80">{t("座位")}</legend>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {seats.map((lvl, i) => (
                <select key={i} aria-label={t("座位 {n}", { n: i + 1 })}
                  value={i === 0 ? "me" : lvl === null ? "open" : String(lvl)} disabled={i === 0}
                  onChange={(e) => {
                    const v = e.target.value;
                    setSeats(seats.map((x, j) => (j === i ? (v === "open" ? null : Number(v)) : x)));
                  }} className={select}>
                  {i === 0 && <option value="me">{t("你")}</option>}
                  <option value="open">{t("留給玩家")}</option>
                  {LEVELS.map((l) => (
                    <option key={l.v} value={l.v}>{t("AI {level}", { level: t(l.label) })}</option>
                  ))}
                </select>
              ))}
            </div>
          </fieldset>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-sm text-white/80">
              {t("每次行動時限")}
              <select value={timeLimit ?? "none"} className={select}
                onChange={(e) => setTimeLimit(e.target.value === "none" ? null : Number(e.target.value))}>
                <option value={15}>{t("{n} 秒", { n: 15 })}</option>
                <option value={30}>{t("{n} 秒", { n: 30 })}</option>
                <option value={60}>{t("{n} 秒", { n: 60 })}</option>
                <option value="none">{t("不限時")}</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm text-white/80">
              {t("打幾圈")}
              <select value={rounds} onChange={(e) => setRounds(Number(e.target.value))} className={select}>
                <option value={1}>{t("東風圈")}</option>
                <option value={2}>{t("東南兩圈")}</option>
                <option value={3}>{t("三圈")}</option>
                <option value={4}>{t("一將（四圈）")}</option>
              </select>
            </label>
          </div>
          <div className="mt-auto pt-6">
            <GameButton variant="blue" size="lg" className="w-full" onClick={create} disabled={busy !== null}>
              {busy === "create" ? t("開桌中…") : t("開桌")}
            </GameButton>
          </div>
        </ModeCard>

        <div className="flex flex-col gap-5 lg:row-span-2">
          <DailyBonus />
          <Missions />
        </div>
      </section>

      <section className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <SmallCard href="/practice" tone="green" icon="🎯" title={t("單人練習")} desc={t("情境、速度、防守三種練習")} />
        <SmallCard href="/tutor" tone="pink" icon="📘" title={t("AI 教練")} desc={t("第一次玩？從 AI 教練開始")} />
        <SmallCard href="/leaderboard" tone="violet" icon="🏆" title={t("排位賽")} desc={t("挑戰段位、登上排行榜")} />
        <Panel className="flex flex-col justify-between">
          <h2 className="font-display text-xl font-black">{t("用房間碼加入")}</h2>
          <form className="mt-3 flex gap-2" onSubmit={(e) => {
            e.preventDefault();
            if (code.trim().length === 6) joinByCode();
          }}>
            <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase().slice(0, 6))} placeholder="XK49AB"
              aria-label={t("六碼房間碼")}
              className="tabular w-full min-w-0 rounded-xl border border-white/10 bg-felt-deep px-3 py-2 text-lg tracking-[0.2em] uppercase" />
            <GameButton type="submit" variant="ghost" className="shrink-0 whitespace-nowrap"
              disabled={busy !== null || code.trim().length !== 6}>
              {t("加入")}
            </GameButton>
          </form>
        </Panel>
      </section>

      <nav className="mt-8 flex flex-wrap justify-center gap-3 text-sm" aria-label={t("更多")}>
        {[
          ["/shop", "🎨", t("外觀商店")],
          ["/profile", "🎖️", t("成就與檔案")],
          ["/agents", "🤖", t("社群 AI")],
          ["/lab", "🧪", t("實驗室")],
        ].map(([href, icon, label]) => (
          <Link key={href} href={href}
            className="rounded-full bg-black/25 px-4 py-2 font-bold text-ivory-dim transition hover:-translate-y-0.5 hover:bg-black/40 hover:text-ivory">
            <span aria-hidden="true">{icon}</span> {label}
          </Link>
        ))}
      </nav>
    </main>
  );
}

const TONES = {
  amber: "from-[#ff9f1c] via-[#ff7a3d] to-[#e8486b]",
  blue: "from-[#4f8dff] via-[#3b5be8] to-[#6a3fe0]",
  green: "from-[#22c58b] to-[#0f8f8a]",
  pink: "from-[#ff5c9a] to-[#a35cff]",
  violet: "from-[#7a5cff] to-[#3b82f6]",
} as const;

function ModeCard({ tone, icon, className = "", children }: {
  tone: keyof typeof TONES; icon: string; className?: string; children: React.ReactNode;
}) {
  return (
    <section className={`relative flex animate-rise flex-col overflow-hidden rounded-3xl bg-gradient-to-br p-6 shadow-[0_14px_40px_rgb(5_6_25/0.5)] ring-1 ring-white/15 ${TONES[tone]} ${className}`}>
      <span className="pointer-events-none absolute -top-6 -right-4 text-[9rem] leading-none opacity-20" aria-hidden="true">
        {icon}
      </span>
      <div className="relative flex flex-1 flex-col">{children}</div>
    </section>
  );
}

function SmallCard({ href, tone, icon, title, desc }: {
  href: string; tone: keyof typeof TONES; icon: string; title: string; desc: string;
}) {
  return (
    <Link href={href} onClick={() => sfx.tap()}
      className={`group relative flex animate-rise items-center gap-4 overflow-hidden rounded-3xl bg-gradient-to-br p-5 shadow-[0_10px_30px_rgb(5_6_25/0.45)] ring-1 ring-white/15 transition hover:-translate-y-1 active:translate-y-0.5 ${TONES[tone]}`}>
      <span className="text-5xl drop-shadow transition group-hover:scale-110" aria-hidden="true">{icon}</span>
      <span>
        <span className="block font-display text-xl font-black">{title}</span>
        <span className="block text-sm text-white/85">{desc}</span>
      </span>
    </Link>
  );
}

function DailyBonus() {
  const t = useT();
  const profile = useAccount((s) => s.profile);
  const refresh = useAccount((s) => s.refreshProfile);
  const [claimed, setClaimed] = useState<number | null>(null);
  if (!profile) return <Panel className="h-32 animate-pulse" aria-hidden="true">{null}</Panel>;
  const { bonus } = profile;
  return (
    <Panel className={`relative overflow-hidden ${bonus.available ? "ring-2 ring-gold/70" : ""}`}>
      <div className="flex items-center gap-4">
        <span className={`text-5xl ${bonus.available ? "animate-float" : "grayscale"}`} aria-hidden="true">🎁</span>
        <div className="flex-1">
          <h2 className="font-display text-xl font-black">{t("每日補助")}</h2>
          <p className="text-sm text-mist">
            {bonus.available
              ? t("連續 {n} 天・今天可領 {coins}", { n: bonus.streak, coins: bonus.amount })
              : t("今天已領取，明天再來！")}
          </p>
        </div>
      </div>
      {claimed !== null && (
        <p className="absolute top-3 right-4 animate-stamp text-2xl font-black text-gold" aria-live="polite">+{claimed}</p>
      )}
      <GameButton variant="primary" size="md" className={`mt-4 w-full ${bonus.available ? "animate-pulse-glow" : ""}`}
        disabled={!bonus.available}
        onClick={async () => {
          try {
            const r = await profileApi.claimBonus();
            setClaimed(r.amount);
            sfx.coin();
            await refresh();
          } catch {
            sfx.error();
          }
        }}>
        <CoinIcon size={20} /> {bonus.available ? t("領取 {n}", { n: bonus.amount }) : t("已領取")}
      </GameButton>
    </Panel>
  );
}

function Missions() {
  const t = useT();
  const profile = useAccount((s) => s.profile);
  const refresh = useAccount((s) => s.refreshProfile);
  if (!profile) return <Panel className="h-56 animate-pulse" aria-hidden="true">{null}</Panel>;
  return (
    <Panel title={t("今日任務")} className="flex-1">
      <ul className="space-y-3">
        {profile.missions.map((m, i) => {
          const done = m.progress >= m.target;
          return (
            <li key={m.id} className="animate-rise rounded-2xl bg-black/20 p-3" style={{ animationDelay: `${i * 60}ms` }}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-bold">{translate(m.name)}</span>
                <span className="flex items-center gap-1 text-sm font-black text-gold"><CoinIcon size={16} />{m.reward}</span>
              </div>
              <div className="mt-2 flex items-center gap-3">
                <ProgressBar value={m.progress} max={m.target} className="flex-1"
                  color={done ? "linear-gradient(90deg,#43e0a3,#16a874)" : undefined} label={translate(m.name)} />
                {m.claimed ? (
                  <span className="text-sm text-jade">✓ {t("已領")}</span>
                ) : done ? (
                  <GameButton size="sm" variant="green" className="animate-pulse-glow" onClick={async () => {
                    try {
                      await profileApi.claimMission(m.id);
                      sfx.coin();
                      await refresh();
                    } catch {
                      sfx.error();
                    }
                  }}>{t("領取")}</GameButton>
                ) : (
                  <span className="tabular text-sm text-mist">{m.progress}/{m.target}</span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

function describeError(e: ApiError): string {
  if (e.status === 404) return translate("找不到這個房間，請確認房間碼。");
  if (e.status === 409) return translate("無法加入：{msg}", { msg: e.message });
  return translate("發生錯誤：{msg}", { msg: e.message });
}
