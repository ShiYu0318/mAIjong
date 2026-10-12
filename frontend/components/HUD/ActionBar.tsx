"use client";

import { GameButton } from "@/components/Game/GameButton";
import { TileImage } from "@/components/Hand/TileImage";
import { HintButton } from "@/components/HUD/HintPanel";
import { useT } from "@/lib/i18n";
import type { Action } from "@/lib/protocol";
import { tileName } from "@/lib/tiles";
import { useGame } from "@/store/gameStore";

const CHI_OFFSETS: Record<string, [number, number, number]> = {
  CHI_LOW: [-2, -1, 0],
  CHI_MID: [-1, 0, 1],
  CHI_HIGH: [0, 1, 2],
};

/** Tiles the hand would wait on after discarding the selected tile, with copies left. */
function WaitsPreview({ tile }: { tile: number }) {
  const t = useT();
  const waits = useGame((s) => s.waits[String(tile)]);
  if (!waits?.length) return null;
  const total = waits.reduce((n, [, left]) => n + left, 0);
  return (
    <div className="panel flex animate-pop-in items-center gap-2 px-3 py-2" aria-live="polite">
      <span className="text-sm font-black text-jade">{t("聽")}</span>
      {waits.map(([w, left]) => (
        <span key={w} className="flex flex-col items-center">
          <TileImage id={w} width={26} />
          <span className={`tabular text-xs font-black ${left === 0 ? "text-zhong" : "text-ivory"}`}>×{left}</span>
        </span>
      ))}
      <span className="text-xs text-mist">{t("共 {n} 張", { n: total })}</span>
    </div>
  );
}

export function ActionBar() {
  const legal = useGame((s) => s.legal);
  const selected = useGame((s) => s.selected);
  const view = useGame((s) => s.view);
  const act = useGame((s) => s.act);
  const deadline = useGame((s) => s.deadline);
  const send = useGame((s) => s.sender);
  const t = useT();
  if (!view || legal.length === 0) return null;

  const discardPhase = view.phase === "DISCARD";
  const find = (type: Action["action_type"], tile: number | null = null) =>
    legal.find((a) => a.action_type === type && (tile === null || a.tile === tile));
  const hu = find("HU");
  const pass = find("PASS");
  const pon = find("PON");
  const kongs = legal.filter((a) => a.action_type === "KONG");
  const chis = legal.filter((a) => a.action_type.startsWith("CHI"));
  const discard = selected !== null ? find("DISCARD", selected) : undefined;
  const ting = selected !== null ? find("TING", selected) : undefined;
  const lastTile = view.last_discard?.[1] ?? null;

  return (
    <div className="flex flex-wrap items-end justify-end gap-3" role="group" aria-label={t("可執行的動作")}>
      {selected !== null && discardPhase && <WaitsPreview tile={selected} />}
      {discardPhase && selected === null && !hu && kongs.length === 0 && (
        <p className="rounded-full bg-black/40 px-4 py-2 text-sm text-ivory-dim">
          {t("點一張牌選取，再點一次打出（鍵盤：← → 選牌、Enter 打出）。")}
        </p>
      )}
      <HintButton />
      {deadline !== null && (
        <GameButton variant="ghost" size="sm" onClick={() => send?.({ type: "EXTEND_TIME" })}>
          {t("延長 15 秒")}
        </GameButton>
      )}
      {chis.map((a) => (
        <GameButton key={a.action_type} variant="blue" size="lg" aria-keyshortcuts="C" className="animate-pop-in"
          onClick={() => act(a)}>
          {t("吃")}
          {lastTile !== null && (
            <span className="flex gap-[1px]">
              {CHI_OFFSETS[a.action_type].map((o) => <TileImage key={o} id={lastTile + o} width={22} />)}
            </span>
          )}
        </GameButton>
      ))}
      {pon && (
        <GameButton variant="green" size="lg" aria-keyshortcuts="P" className="animate-pop-in" onClick={() => act(pon)}>
          {t("碰")} {lastTile !== null ? tileName(lastTile) : ""}
        </GameButton>
      )}
      {kongs.map((a) => (
        <GameButton key={a.tile} variant="primary" size="lg" aria-keyshortcuts="K" className="animate-pop-in"
          onClick={() => act(a)}>
          {t("槓")} {tileName(a.tile as number)}
        </GameButton>
      ))}
      {ting && (
        <GameButton variant="pink" size="lg" aria-keyshortcuts="T" className="animate-pop-in" onClick={() => act(ting)}>
          {t("打出 {tile} 並宣告聽牌", { tile: tileName(selected as number) })}
        </GameButton>
      )}
      {discard && (
        <GameButton variant="blue" size="lg" aria-keyshortcuts="Enter" className="animate-pop-in" onClick={() => act(discard)}>
          {t("打出 {tile}", { tile: tileName(selected as number) })}
        </GameButton>
      )}
      {pass && (
        <GameButton variant="ghost" size="lg" aria-keyshortcuts="X" onClick={() => act(pass)}>
          {t("過")}
        </GameButton>
      )}
      {hu && (
        <GameButton variant="danger" size="xl" aria-keyshortcuts="H" className="animate-pulse-glow px-10 font-display"
          onClick={() => act(hu)}>
          {discardPhase ? t("自摸") : t("胡")}
        </GameButton>
      )}
    </div>
  );
}
