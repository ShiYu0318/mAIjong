"use client";

import Link from "next/link";
import { PlayerBar } from "@/components/Account/PlayerBar";
import { Avatar } from "@/components/Game/Avatar";
import { LevelBadge } from "@/components/Game/LevelBadge";
import { rankFor } from "@/lib/progression";
import { CoinIcon } from "@/components/Game/CoinCounter";
import { Panel } from "@/components/Game/Panel";
import { ProgressBar } from "@/components/Game/ProgressBar";
import { RankBadge } from "@/components/Game/RankBadge";
import { localName, useT } from "@/lib/i18n";
import { useAccount } from "@/store/accountStore";
import { GameIcon } from "@/components/Game/GameIcon";
import { Lock, Trophy } from "lucide-react";

export default function ProfilePage() {
  const t = useT();
  const profile = useAccount((s) => s.profile);
  const stats = profile?.stats ?? {};
  return (
    <main className="mx-auto max-w-6xl px-4 pt-4 pb-12 sm:px-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <Link href="/" className="font-bold text-mist hover:text-ivory">← {t("大廳")}</Link>
        <PlayerBar compact />
      </header>
      {!profile ? <p className="mt-10 text-mist">{t("載入中…")}</p> : (
        <>
          <section className="panel mt-6 flex flex-wrap items-center gap-6 p-6">
            <Avatar name={profile.user.username} size={96} progress={profile.xp / profile.xp_next}
              frame={rankFor(profile.user.elo_human).tier.colors} />
            <div className="min-w-60 flex-1">
              <h1 className="flex items-center gap-3 font-display text-4xl font-black">
                {localName(profile.user.username)}
                <LevelBadge level={profile.level} xp={profile.xp} xpNext={profile.xp_next} size={52} />
              </h1>
              <ProgressBar value={profile.xp} max={profile.xp_next} className="mt-2 max-w-md" label={t("經驗值")} />
              <p className="mt-1 text-sm text-mist tabular">{profile.xp} / {profile.xp_next} XP</p>
            </div>
            <div className="text-center">
              <RankBadge rating={profile.user.elo_human} size={48} showName={false} />
              <p className="mt-1 font-display text-2xl font-black">{t(profile.rank.name)}</p>
              {profile.rank.next && (
                <>
                  <ProgressBar value={profile.rank.progress} max={1} className="mt-2 w-40"
                    color="linear-gradient(90deg,#38d0ff,#7a5cff)" label={t("段位進度")} />
                  <p className="mt-1 text-xs text-mist">
                    {t("距離 {name} 還差 {n} 分", { name: t(profile.rank.next),
                      n: Math.max(0, Math.ceil((rankFor(profile.user.elo_human).next?.min ?? 0) - profile.user.elo_human)) })}
                  </p>
                </>
              )}
            </div>
          </section>
          <section className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              [t("打過的手數"), stats.hands ?? 0],
              [t("胡牌"), stats.wins ?? 0],
              [t("自摸"), stats.self_draws ?? 0],
              [t("完成場數"), stats.matches ?? 0],
            ].map(([label, value]) => (
              <Panel key={String(label)} className="text-center">
                <p className="text-sm text-mist">{label}</p>
                <p className="mt-1 font-display text-4xl font-black tabular">{value}</p>
              </Panel>
            ))}
          </section>
          <Panel title={t("成就")} className="mt-5">
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {profile.achievements.map((a) => (
                <li key={a.id} className={`flex items-center gap-3 rounded-2xl p-3 ${a.unlocked ? "bg-gold/15 ring-1 ring-gold/50" : "bg-black/20 opacity-60"}`}>
                  <GameIcon icon={a.unlocked ? Trophy : Lock} tone={a.unlocked ? "gold" : "slate"} size={44} />
                  <span className="flex-1">
                    <span className="block font-black">{t(a.name)}</span>
                    <span className="block text-sm text-mist">{t(a.description)}</span>
                  </span>
                  <span className="flex items-center gap-1 text-sm font-black text-gold"><CoinIcon size={16} />{a.reward}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </>
      )}
    </main>
  );
}
