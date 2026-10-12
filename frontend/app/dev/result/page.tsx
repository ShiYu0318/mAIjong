"use client";

import { useEffect } from "react";
import { ResultOverlay } from "@/components/HUD/ResultOverlay";
import type { WinPayload } from "@/lib/protocol";
import { useAccount } from "@/store/accountStore";
import { useGame } from "@/store/gameStore";

const NAMES = ["麥醬玩家", "電腦二號", "電腦三號", "電腦四號"];
const WIN: WinPayload = {
  kind: "HU", winner: 0, loser: null, self_draw: true, win_tile: 22, flower_win: null,
  hand: [9, 10, 11, 12, 13, 14, 15, 16, 17, 9, 10, 11, 13, 13, 13, 22, 22].map((t) => (t < 18 ? t : 22)),
  melds: [], flowers: [34],
  tai_breakdown: [
    { id: "T24", name: "清一色", tai: 8 }, { id: "T04", name: "自摸", tai: 1 },
    { id: "T05", name: "門清", tai: 1 }, { id: "T03", name: "宣告聽牌", tai: 1 },
  ],
  dealer_tai: 1, tai_by_payer: { "1": 11, "2": 11, "3": 12 }, payments: [1900, -650, -650, -600],
};

/** Preview of the end-of-hand sequence (docs design §11); `?draw` shows an exhaustive draw. */
export default function ResultPreview() {
  useEffect(() => {
    const draw = new URLSearchParams(window.location.search).has("draw");
    useGame.setState({
      seat: 0, gameEnd: null, nextHandAt: Date.now() + 8000,
      ...(draw
        ? { win: null, drawn: true, drawInfo: { tenpai: [true, false, true, false], declared: [true, false, false, false] } }
        : { win: WIN, drawn: false, drawInfo: null }),
    });
    const profile = useAccount.getState().profile;
    useAccount.setState({ lastXp: 58, xpBefore: profile ? { level: profile.level, xp: 20, xp_next: profile.xp_next } : null });
  }, []);
  return (
    <main className="relative h-dvh">
      <ResultOverlay names={NAMES} />
    </main>
  );
}
