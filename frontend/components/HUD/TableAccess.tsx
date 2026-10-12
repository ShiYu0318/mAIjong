"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { translate, useT } from "@/lib/i18n";
import type { Action, GameView } from "@/lib/protocol";
import { tileName } from "@/lib/tiles";
import { useGame } from "@/store/gameStore";

/** Hand order as drawn on the canvas: concealed tiles, then the fresh draw on the right. */
export function handOrder(view: GameView, seat: number | null): number[] {
  if (seat === null) return [];
  const p = view.players[seat];
  const hand = p?.hand ?? [];
  const draw = view.last_draw;
  if (draw !== null && view.turn === seat && view.phase === "DISCARD") {
    const idx = hand.lastIndexOf(draw);
    if (idx >= 0) return [...hand.slice(0, idx), ...hand.slice(idx + 1), draw];
  }
  return hand;
}

const ACTION_WORDS: Partial<Record<Action["action_type"], string>> = {
  HU: "胡", PON: "碰", KONG: "槓", CHI_LOW: "吃", CHI_MID: "吃", CHI_HIGH: "吃", PASS: "過",
};

function describeLegal(legal: Action[], phase: GameView["phase"]): string {
  const words = new Set<string>();
  for (const a of legal) {
    if (a.action_type === "HU" && phase === "DISCARD") words.add(translate("自摸"));
    else if (ACTION_WORDS[a.action_type]) words.add(translate(ACTION_WORDS[a.action_type]!));
  }
  if (legal.some((a) => a.action_type === "DISCARD")) words.add(translate("打牌"));
  if (legal.some((a) => a.action_type === "TING")) words.add(translate("宣告聽牌"));
  return [...words].join(translate("、"));
}

const typing = (el: EventTarget | null) =>
  el instanceof HTMLElement && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));

/**
 * Keyboard play for the table (SPEC P11-5):
 * ← → choose a tile, Enter / Space discard it, T discard and declare ready,
 * H win, P pon, K kong, C chi (repeat to cycle), X or Esc pass, ? hint.
 */
export function useTableKeys() {
  const chiIdx = useRef(0);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || typing(e.target)) return;
      const st = useGame.getState();
      const { view, legal, selected, seat } = st;
      if (!view || legal.length === 0) return;
      const find = (type: Action["action_type"], tile?: number | null) =>
        legal.find((a) => a.action_type === type && (tile === undefined || a.tile === tile));
      const playable = handOrder(view, seat).filter((t) =>
        legal.some((a) => (a.action_type === "DISCARD" || a.action_type === "TING") && a.tile === t));
      const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      let handled = true;
      switch (key) {
        case "ArrowLeft":
        case "ArrowRight": {
          if (playable.length === 0) { handled = false; break; }
          const cur = selected === null ? -1 : playable.lastIndexOf(selected);
          const step = key === "ArrowRight" ? 1 : -1;
          const next = cur < 0 ? (step > 0 ? 0 : playable.length - 1)
            : (cur + step + playable.length) % playable.length;
          st.select(playable[next]);
          break;
        }
        case "Enter":
        case " ": {
          const a = selected !== null ? find("DISCARD", selected) ?? find("TING", selected) : undefined;
          if (a) st.act(a);
          else if (playable.length) st.select(playable[playable.length - 1]);
          else handled = false;
          break;
        }
        case "t": {
          const a = selected !== null ? find("TING", selected) : undefined;
          if (a) st.act(a); else handled = false;
          break;
        }
        case "h": { const a = find("HU"); if (a) st.act(a); else handled = false; break; }
        case "p": { const a = find("PON"); if (a) st.act(a); else handled = false; break; }
        case "k": { const a = find("KONG"); if (a) st.act(a); else handled = false; break; }
        case "c": {
          const chis = legal.filter((a) => a.action_type.startsWith("CHI"));
          if (chis.length) st.act(chis[chiIdx.current++ % chis.length]); else handled = false;
          break;
        }
        case "x":
        case "Escape": { const a = find("PASS"); if (a) st.act(a); else handled = false; break; }
        case "?": st.requestHint(); break;
        default: handled = false;
      }
      if (handled) e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}

/** Screen-reader announcements: table events, your turn, selection, results. */
export function TableAnnouncer() {
  const log = useGame((s) => s.log);
  const legal = useGame((s) => s.legal);
  const view = useGame((s) => s.view);
  const selected = useGame((s) => s.selected);
  const win = useGame((s) => s.win);
  const drawn = useGame((s) => s.drawn);
  const seats = useGame((s) => s.room?.seats);
  const t = useT();
  const [polite, setPolite] = useState("");

  const last = log[log.length - 1];
  useEffect(() => { if (last) setPolite(last); }, [last, log.length]);
  useEffect(() => {
    if (view && legal.length) setPolite(t("輪到你。可以：{list}", { list: describeLegal(legal, view.phase) }));
  }, [legal, view, t]);
  useEffect(() => { if (selected !== null) setPolite(t("選取 {tile}", { tile: tileName(selected) })); }, [selected, t]);

  const assertive = win
    ? t(win.self_draw ? "{who} 自摸，共 {n} 台" : "{who} 胡牌，共 {n} 台", {
      who: seats?.[win.winner]?.name ?? `#${win.winner + 1}`,
      n: (win.tai_breakdown ?? []).reduce((n, x) => n + x.tai, 0),
    })
    : drawn ? t("流局") : "";

  return (
    <>
      <p className="sr-only" aria-live="polite" aria-atomic="true">{polite}</p>
      <p className="sr-only" aria-live="assertive" aria-atomic="true">{assertive}</p>
    </>
  );
}

/** Focusable list of your tiles; hidden until it receives keyboard focus. */
export function HandList() {
  const view = useGame((s) => s.view);
  const seat = useGame((s) => s.seat);
  const legal = useGame((s) => s.legal);
  const selected = useGame((s) => s.selected);
  const select = useGame((s) => s.select);
  const act = useGame((s) => s.act);
  const t = useT();
  const order = useMemo(() => (view ? handOrder(view, seat) : []), [view, seat]);
  // the store selects a tile kind; like the canvas, mark only its first copy in the hand
  const pressedIndex = selected === null ? -1 : order.indexOf(selected);
  if (!view || seat === null) return null;
  const me = view.players[seat];
  const flowers = me?.flowers ?? [];
  return (
    <section aria-label={t("你的手牌")}
      className="sr-only focus-within:not-sr-only focus-within:absolute focus-within:top-2 focus-within:left-2 focus-within:z-30 focus-within:max-w-[90%] focus-within:rounded-md focus-within:bg-felt-deep focus-within:p-3 focus-within:shadow-lg">
      <p className="mb-2 text-sm text-mist">
        {t("鍵盤：← → 選牌、Enter 打出、T 打出並聽牌、H 胡、P 碰、K 槓、C 吃、X 過、? 提示")}
      </p>
      <ul className="flex flex-wrap gap-1">
        {order.map((tile, i) => {
          const playable = legal.some((a) => (a.action_type === "DISCARD" || a.action_type === "TING") && a.tile === tile);
          const isDraw = i === order.length - 1 && view.last_draw === tile && view.turn === seat && view.phase === "DISCARD";
          return (
            <li key={`${tile}-${i}`}>
              <button type="button" disabled={!playable} aria-pressed={i === pressedIndex}
                onClick={() => {
                  if (selected === tile) {
                    const a = legal.find((x) => x.action_type === "DISCARD" && x.tile === tile)
                      ?? legal.find((x) => x.action_type === "TING" && x.tile === tile);
                    if (a) act(a);
                  } else select(tile);
                }}
                className="rounded border border-felt-line px-2 py-1 text-sm aria-pressed:bg-ivory aria-pressed:text-ink disabled:opacity-60">
                {tileName(tile)}{isDraw ? t("（剛摸）") : ""}
              </button>
            </li>
          );
        })}
      </ul>
      {(me?.melds.length ?? 0) > 0 && (
        <p className="mt-2 text-sm">{t("副露：{m}", { m: me!.melds.map((m) => m.tiles.map((x) => (x === null ? t("暗") : tileName(x))).join(" ")).join(t("、")) })}</p>
      )}
      {flowers.length > 0 && <p className="mt-1 text-sm">{t("花牌：{f}", { f: flowers.map(tileName).join(t("、")) })}</p>}
    </section>
  );
}
