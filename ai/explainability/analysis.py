"""Stand-alone hand analysis and decision-quiz generation for the AI tutor."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from ai.agents.rule_agent import RuleAgent
from ai.explainability.candidate_scorer import best_tai_for_waits, score_all_discards
from engine import tiles
from engine.actions import ActionType
from engine.game import GameState, Phase, acting_players, apply_action, get_legal_actions, new_game
from engine.hand import Meld
from engine.shanten import discard_table, shanten, uke_ire


@dataclass
class HandInput:
    concealed: list[int]
    melds: list[Meld]
    flowers: list[int]
    seat_wind: int = 0
    round_wind: int = 0


def analyze_hand(h: HandInput) -> dict[str, Any]:
    """Shanten, discard ranking (3n+2 hands) or waits with tai (3n+1 hands)."""
    n_melds = len(h.melds)
    counts = tiles.to_counts(h.concealed)
    size = len(h.concealed)
    need = 3 * (5 - n_melds)
    if size not in (need + 1, need + 2) or max(counts, default=0) > 4:
        raise ValueError(f"手牌應有 {need + 1} 或 {need + 2} 張（目前 {size} 張）")
    out: dict[str, Any] = {"tiles": size, "melds": n_melds}
    if size == need + 2:
        out["shanten"] = shanten(counts, n_melds)
        table = discard_table(counts, n_melds)
        ranked = []
        for t, (sh, uke) in table.items():
            live = sum(4 - counts[u] + (1 if u == t else 0) for u in uke)
            entry: dict[str, Any] = {"tile": t, "name": tiles.name(t), "shanten_after": sh,
                                     "uke_ire": uke, "uke_count": live}
            if sh == 0:
                rest = list(h.concealed)
                rest.remove(t)
                entry["waits"] = uke
                entry["best_tai"] = best_tai_for_waits(rest, h.melds, h.flowers, h.seat_wind,
                                                       h.round_wind, uke)
            ranked.append(entry)
        ranked.sort(key=lambda e: (e["shanten_after"], -e["uke_count"], e["tile"]))
        out["discards"] = ranked
    else:
        sh = shanten(counts, n_melds)
        out["shanten"] = sh
        uke = uke_ire(counts, n_melds)
        out["uke_ire"] = uke
        out["uke_count"] = sum(4 - counts[u] for u in uke)
        if sh == 0:
            out["waits"] = [
                {"tile": w, "name": tiles.name(w),
                 "tai": best_tai_for_waits(h.concealed, h.melds, h.flowers, h.seat_wind,
                                           h.round_wind, [w])}
                for w in uke
            ]
    return out


# ------------------------------------------------------------------ quiz


@dataclass
class QuizPosition:
    seed: int
    step: int
    seat: int
    state: GameState


def _replay_to(seed: int, step: int) -> GameState:
    agents = [RuleAgent(0.0, seed * 4 + i) for i in range(4)]
    s = new_game(seed=seed)
    for _ in range(step):
        p = acting_players(s)[0]
        s, _ = apply_action(s, p, agents[p].act(s, p, get_legal_actions(s, p)))
    return s


def generate_quiz(rng: random.Random, difficulty: int = 2) -> QuizPosition:
    """Pick a discard decision from rule-agent self-play.

    difficulty 1: far from ready, one clearly best tile; 3: close to ready with
    several near-equal candidates.
    """
    for _ in range(200):
        seed = rng.randrange(2**31)
        agents = [RuleAgent(0.0, seed * 4 + i) for i in range(4)]
        s = new_game(seed=seed)
        positions: list[tuple[int, int]] = []
        step = 0
        while s.phase is not Phase.ENDED and step < 400:
            p = acting_players(s)[0]
            legal = get_legal_actions(s, p)
            if s.phase is Phase.DISCARD and not s.declared_ting[p] and \
                    sum(a.type is ActionType.DISCARD for a in legal) >= 4:
                positions.append((step, p))
            s, _ = apply_action(s, p, agents[p].act(s, p, legal))
            step += 1
        rng.shuffle(positions)
        for step, seat in positions[:12]:
            st = _replay_to(seed, step)
            cands = score_all_discards(st, seat)
            if len(cands) < 4:
                continue
            best, second = cands[0], cands[1]
            gap = (second.shanten_after - best.shanten_after) * 100 + \
                (best.uke_count - second.uke_count)
            sh = best.shanten_after
            ok = {1: sh >= 2 and gap >= 8, 2: sh <= 2 and gap >= 3,
                  3: sh <= 1 and 0 < gap <= 6}.get(difficulty, True)
            if ok:
                return QuizPosition(seed, step, seat, st)
    raise RuntimeError("could not generate a quiz position")


def quiz_view(q: QuizPosition) -> dict[str, Any]:
    s = q.state
    return {
        "seat": q.seat,
        "hand": list(s.hands[q.seat]),
        "last_draw": s.last_draw,
        "melds": [m.to_dict() for m in s.melds[q.seat]],
        "flowers": list(s.flowers[q.seat]),
        "discards": [list(d) for d in s.discards],
        "opponent_melds": [[m.to_dict() for m in s.melds[p]] for p in range(4)],
        "declared": list(s.declared_ting),
        "seat_wind": s.seat_wind(q.seat),
        "round_wind": s.round_wind,
        "drawable": s.drawable(),
    }


def load_quiz(seed: int, step: int, seat: int) -> QuizPosition:
    return QuizPosition(seed, step, seat, _replay_to(seed, step))
