"""Terminal front end for the rule engine.

    python -m engine.cli watch [--seed N] [--rounds R]   # four bots play a match
    python -m engine.cli play  [--seed N] [--rounds R]   # you are seat 0 (甲家)
"""

from __future__ import annotations

import argparse
import random
import sys
from typing import Any

from engine import tiles
from engine.actions import Action, ActionType
from engine.game import GameState, Phase, acting_players, apply_action, get_legal_actions
from engine.match import finish_hand, new_match, ranks, start_hand
from engine.shanten import shanten, uke_ire
from engine.ting import waiting_tiles

SEAT_NAMES = ("甲家", "乙家", "丙家", "丁家")
ACTION_NAMES = {
    ActionType.DISCARD: "打", ActionType.KONG: "槓", ActionType.PON: "碰",
    ActionType.CHI_LOW: "吃(低)", ActionType.CHI_MID: "吃(中)", ActionType.CHI_HIGH: "吃(高)",
    ActionType.HU: "胡", ActionType.PASS: "過", ActionType.TING: "打並宣告聽牌",
}


def describe(a: Action) -> str:
    name = ACTION_NAMES[a.type]
    return f"{name} {tiles.name(a.tile)}" if a.tile is not None else name


# ---------------------------------------------------------------- greedy bot


def greedy_action(s: GameState, p: int, rng: random.Random) -> Action:
    legal = get_legal_actions(s, p)
    by_type: dict[ActionType, list[Action]] = {}
    for a in legal:
        by_type.setdefault(a.type, []).append(a)
    if ActionType.HU in by_type:
        return by_type[ActionType.HU][0]
    n_melds = len(s.melds[p])
    counts = tiles.to_counts(s.hands[p])

    if s.phase is Phase.DISCARD:
        best: tuple[int, int, float] | None = None
        choice = legal[0]
        for a in legal:
            if a.type not in (ActionType.DISCARD, ActionType.TING):
                continue
            assert a.tile is not None
            counts[a.tile] -= 1
            key = (shanten(counts, n_melds), -len(uke_ire(counts, n_melds)), rng.random())
            counts[a.tile] += 1
            if best is None or key < best:
                best, choice = key, a
        # prefer declaring ready when the chosen discard leaves the hand tenpai
        assert choice.tile is not None
        ting = Action(ActionType.TING, choice.tile)
        return ting if ting in legal else choice

    # responses: call only when it lowers shanten
    assert s.last_discard is not None
    _, t = s.last_discard
    base = shanten(counts, n_melds)
    for a in legal:
        if a.type is ActionType.PON:
            c = list(counts)
            c[t] -= 2
            if _best_after_call(c, n_melds + 1) < base:
                return a
    for a in legal:
        if a.type in (ActionType.CHI_LOW, ActionType.CHI_MID, ActionType.CHI_HIGH):
            off = {ActionType.CHI_LOW: (-2, -1), ActionType.CHI_MID: (-1, 1),
                   ActionType.CHI_HIGH: (1, 2)}[a.type]
            c = list(counts)
            c[t + off[0]] -= 1
            c[t + off[1]] -= 1
            if _best_after_call(c, n_melds + 1) < base:
                return a
    return Action(ActionType.PASS)


def _best_after_call(counts: list[int], n_melds: int) -> int:
    best = 99
    for t in range(34):
        if counts[t]:
            counts[t] -= 1
            best = min(best, shanten(counts, n_melds))
            counts[t] += 1
    return best


# ---------------------------------------------------------------- rendering


def render_table(s: GameState, viewer: int | None) -> str:
    lines = [f"── {tiles.WIND_NAMES[s.round_wind]}風圈  莊家：{SEAT_NAMES[s.dealer]}"
             f"（連{s.dealer_streak}）  可摸：{s.drawable()} 張 ──"]
    for p in range(4):
        wind = tiles.WIND_NAMES[s.seat_wind(p)]
        tag = "★" if p == s.turn and s.phase is Phase.DISCARD else " "
        if viewer is None or viewer == p:
            hand = tiles.names(s.hands[p])
        else:
            hand = f"[{len(s.hands[p])} 張]"
        melds = " ".join("(" + tiles.names(list(m.tiles)) + ")" for m in s.melds[p])
        flowers = tiles.names(s.flowers[p])
        ting = " 〔聽〕" if s.declared_ting[p] else ""
        lines.append(f"{tag}{SEAT_NAMES[p]}({wind}) 分數 {s.scores[p]:>6}{ting}")
        lines.append(f"    手牌：{hand}  {melds}  花：{flowers}")
        lines.append(f"    棄牌：{tiles.names(s.discards[p])}")
    return "\n".join(lines)


def render_result(s: GameState) -> str:
    r = s.result
    assert r is not None
    if r["kind"] == "DRAW":
        return "海底流局，莊家連莊。"
    who = SEAT_NAMES[r["winner"]]
    how = "自摸" if r["self_draw"] else (
        f"食和（{SEAT_NAMES[r['loser']]}放槍）" if r.get("loser") is not None else "花牌胡")
    win = tiles.name(r["win_tile"]) if r["win_tile"] is not None else "—"
    lines = [f"{who} {how}！胡牌張：{win}"]
    lines.append("台數：" + "、".join(f"{i['name']} {i['tai']}" for i in r["tai_breakdown"]))
    if r["dealer_tai"]:
        lines.append(f"莊家台（莊家與對方之間）：{r['dealer_tai']}")
    for p, tai in r["tai_by_payer"].items():
        lines.append(f"  {SEAT_NAMES[int(p)]} 付 {tai} 台 → {-r['payments'][int(p)]} 點")
    return "\n".join(lines)


# ---------------------------------------------------------------- loops


def ask_human(s: GameState, p: int) -> Action:
    legal = get_legal_actions(s, p)
    print(render_table(s, viewer=p))
    if s.phase is not Phase.DISCARD and s.last_discard:
        d, t = s.last_discard
        print(f"{SEAT_NAMES[d]} 打出 {tiles.name(t)}")
    counts = tiles.to_counts(s.hands[p])
    n_melds = len(s.melds[p])
    if s.phase is Phase.DISCARD:
        print(f"向聽數：{shanten(counts, n_melds)}")
    else:
        waits = waiting_tiles(counts, n_melds)
        if waits:
            print(f"聽：{tiles.names(waits)}")
    for i, a in enumerate(legal):
        print(f"  [{i}] {describe(a)}")
    while True:
        raw = input("選擇編號＞ ").strip()
        if raw.isdigit() and int(raw) < len(legal):
            return legal[int(raw)]
        print("請輸入列表中的編號。")


def run(human: int | None, seed: int | None, rounds: int, delay_events: bool = False) -> None:
    rng = random.Random(seed)
    m = new_match(rounds=rounds)
    while not m.finished:
        s = start_hand(m, seed=rng.randrange(2**31))
        print(f"\n===== 第 {m.hands_played + 1} 手 =====")
        while s.phase is not Phase.ENDED:
            for p in acting_players(s):
                if p not in acting_players(s):  # an earlier response may have ended the hand
                    continue
                a = ask_human(s, p) if p == human else greedy_action(s, p, rng)
                s, events = apply_action(s, p, a)
                for ev in events:
                    line = _event_line(ev, human)
                    if line:
                        print(line)
        print(render_result(s))
        m = finish_hand(m, s)
        print("目前分數：" + "  ".join(f"{SEAT_NAMES[p]} {m.scores[p]}" for p in range(4)))
    order = ranks(m.scores)
    print("\n===== 一將結束 =====")
    for p in sorted(range(4), key=lambda x: order[x]):
        print(f"第 {order[p]} 名：{SEAT_NAMES[p]} {m.scores[p]}")


def _event_line(ev: dict[str, Any], human: int | None) -> str | None:
    p = ev.get("player")
    who = SEAT_NAMES[p] if p is not None else ""
    t = ev.get("tile")
    name = tiles.name(t) if t is not None else ""
    kind = ev["type"]
    if kind == "DRAW":
        return f"  {who} 摸 {name}" if human is None or p == human else None
    labels = {"DISCARD": "打出", "TING": "打出並宣告聽牌", "FLOWER": "補花", "PON": "碰",
              "CHI": "吃", "KONG": "槓", "FLOWER_ROB": "搶花"}
    if kind in labels:
        return f"  {who} {labels[kind]} {name}"
    return None


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m engine.cli", description=__doc__)
    ap.add_argument("mode", choices=["watch", "play"])
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--rounds", type=int, default=1, help="圈數 1-4（預設 1 圈）")
    args = ap.parse_args(argv)
    try:
        run(0 if args.mode == "play" else None, args.seed, args.rounds)
    except (KeyboardInterrupt, EOFError):
        print("\n結束。")
        sys.exit(0)


if __name__ == "__main__":
    main()
