"use client";

import { Avatar } from "@/components/Game/Avatar";
import { CoinCounter } from "@/components/Game/CoinCounter";
import { GameButton } from "@/components/Game/GameButton";
import { LevelBadge } from "@/components/Game/LevelBadge";
import { Panel } from "@/components/Game/Panel";
import { ProgressBar } from "@/components/Game/ProgressBar";
import { RankBadge } from "@/components/Game/RankBadge";
import { SoundToggle } from "@/components/Game/SoundToggle";
import { useToasts } from "@/components/Game/Toasts";
import { TileImage } from "@/components/Hand/TileImage";
import { TILE_BACKS, type TileBack } from "@/lib/tilePainter";
import { useState } from "react";
import { RANKS } from "@/lib/progression";
import { useAccount } from "@/store/accountStore";

const HAND = [0, 1, 2, 12, 13, 14, 22, 22, 27, 27, 27, 31, 32, 33, 34, 40];

/** Design-system gallery (docs/DESIGN.md §4–6). */
export default function UiGallery() {
  const [coins, setCoins] = useState(12450);
  const push = useToasts((s) => s.push);
  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-4xl font-black">設計系統</h1>
        <div className="flex items-center gap-3">
          <CoinCounter value={coins} />
          <SoundToggle />
        </div>
      </div>
      <Panel title="按鈕">
        <div className="flex flex-wrap items-center gap-4">
          <GameButton size="xl">⚡ 快速配對</GameButton>
          <GameButton variant="blue" size="lg">開桌</GameButton>
          <GameButton variant="green">碰</GameButton>
          <GameButton variant="danger" size="lg">胡</GameButton>
          <GameButton variant="pink" size="sm">領取</GameButton>
          <GameButton variant="ghost">過</GameButton>
          <GameButton disabled>不能按</GameButton>
          <GameButton variant="green" onClick={() => setCoins((c) => c + 500)}>+500 金幣</GameButton>
          <GameButton variant="blue" onClick={() => push({ icon: "🏆", title: "成就解鎖：初胡", body: "+200 金幣" })}>
            通知
          </GameButton>
          <GameButton variant="pink" onClick={() => useAccount.setState({ levelUp: { level: 12, coins: 240 } })}>
            升級演出
          </GameButton>
        </div>
      </Panel>
      <Panel title="頭像、等級、段位">
        <div className="flex flex-wrap items-center gap-6">
          <Avatar name="麥醬" size={56} progress={0.62} />
          <Avatar name="電腦一號" size={44} active />
          <Avatar name="alice" size={44} progress={0.2} ringColor="#38d0ff" />
          {[1300, 1500, 1600, 1700, 1800, 1950].map((r) => <RankBadge key={r} rating={r} />)}
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-6">
          <LevelBadge level={7} xp={130} xpNext={340} />
          <LevelBadge level={42} xp={900} xpNext={1740} size={72} />
          {RANKS.map((r) => <Avatar key={r.id} name={r.name} size={44} frame={r.colors} />)}
          <RankBadge rating={1610} showProgress />
          <RankBadge rating={1930} showProgress />
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <ProgressBar value={42} max={140} label="經驗值" />
          <ProgressBar value={2} max={3} color="linear-gradient(90deg,#43e0a3,#16a874)" label="任務" />
          <ProgressBar value={3} max={3} color="linear-gradient(90deg,#ff86bd,#a35cff)" label="完成" />
        </div>
      </Panel>
      <Panel title="立體牌與牌背">
        <div className="flex flex-wrap gap-1">
          {HAND.map((t, i) => <TileImage key={i} id={t} width={52} />)}
        </div>
        <div className="mt-4 flex flex-wrap gap-6">
          {(Object.keys(TILE_BACKS) as TileBack[]).map((b) => (
            <div key={b} className="flex items-end gap-1">
              <TileImage id={null} width={44} back={b} />
              <TileImage id={null} width={44} back={b} />
              <span className="ml-1 text-sm text-mist">{b}</span>
            </div>
          ))}
        </div>
      </Panel>
    </main>
  );
}
