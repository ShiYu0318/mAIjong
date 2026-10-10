"use client";

import { TileImage } from "@/components/Hand/TileImage";
import type { Action } from "@/lib/protocol";
import { tileName } from "@/lib/tiles";
import { useGame } from "@/store/gameStore";

const CHI_OFFSETS: Record<string, [number, number, number]> = {
  CHI_LOW: [-2, -1, 0],
  CHI_MID: [-1, 0, 1],
  CHI_HIGH: [0, 1, 2],
};

const base = "rounded-lg px-4 py-2.5 font-medium transition focus-visible:outline-2 disabled:opacity-50";

export function ActionBar() {
  const legal = useGame((s) => s.legal);
  const selected = useGame((s) => s.selected);
  const view = useGame((s) => s.view);
  const act = useGame((s) => s.act);
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
    <div className="flex flex-wrap items-center justify-end gap-2" role="group" aria-label="可執行的動作">
      {discardPhase && selected === null && !hu && kongs.length === 0 && (
        <p className="text-sm text-mist">點一張牌選取，再點一次打出。</p>
      )}
      {chis.map((a) => (
        <button key={a.action_type} onClick={() => act(a)} className={`${base} flex items-center gap-1 bg-ivory/90 text-ink hover:bg-ivory`}>
          吃
          {lastTile !== null && CHI_OFFSETS[a.action_type].map((o) => (
            <TileImage key={o} id={lastTile + o} width={20} />
          ))}
        </button>
      ))}
      {pon && (
        <button onClick={() => act(pon)} className={`${base} bg-ivory/90 text-ink hover:bg-ivory`}>
          碰 {lastTile !== null ? tileName(lastTile) : ""}
        </button>
      )}
      {kongs.map((a) => (
        <button key={a.tile} onClick={() => act(a)} className={`${base} bg-ivory/90 text-ink hover:bg-ivory`}>
          槓 {tileName(a.tile as number)}
        </button>
      ))}
      {ting && (
        <button onClick={() => act(ting)} className={`${base} bg-jade text-ivory hover:brightness-110`}>
          打出 {tileName(selected as number)} 並宣告聽牌
        </button>
      )}
      {discard && (
        <button onClick={() => act(discard)} className={`${base} bg-tong text-ivory hover:brightness-110`}>
          打出 {tileName(selected as number)}
        </button>
      )}
      {pass && (
        <button onClick={() => act(pass)} className={`${base} border border-ivory/40 hover:bg-ivory/10`}>
          過
        </button>
      )}
      {hu && (
        <button onClick={() => act(hu)} className={`${base} bg-zhong px-6 font-display text-2xl text-ivory hover:brightness-110`}>
          {discardPhase ? "自摸" : "胡"}
        </button>
      )}
    </div>
  );
}
