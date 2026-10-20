"""Efficiency agent: own-draw look-ahead on top of the rule agent."""

from __future__ import annotations

import random
import time

from ai.agents import RuleAgent
from ai.agents.efficiency_agent import EfficiencyAgent, win_probability
from engine import tiles
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game


def test_win_probability_orders_hands_by_how_close_they_are():
    rng = random.Random(0)
    pool = [t for t in range(34) for _ in range(3)]
    draws = [rng.sample(pool, 12) for _ in range(200)]
    # 16 tiles, five complete sets and a lone 1-man: ready, waiting on 1-man (7 tiles left)
    ready = tiles.to_counts([0, 1, 2, 3, 4, 5, 9, 10, 11, 12, 13, 14, 27, 27, 27, 0])
    # the honour set split into three lone winds: two away
    far = tiles.to_counts([0, 1, 2, 3, 4, 5, 9, 10, 11, 12, 13, 14, 27, 28, 29, 0])
    p_ready = win_probability(ready, 0, draws)
    p_far = win_probability(far, 0, draws)
    assert p_ready > p_far + 0.2
    done = tiles.to_counts([0, 1, 2, 3, 4, 5, 9, 10, 11, 12, 13, 14, 27, 27, 27, 0])
    assert win_probability(done, 0, [[0]]) == 1.0  # drawing the second 1-man completes it


def test_efficiency_agent_plays_legal_moves_quickly():
    agent = EfficiencyAgent(0.0, 1, samples=16)
    others = [RuleAgent(0.0, i) for i in range(3)]
    worst = 0.0
    for seed in (5, 6):
        s = new_game(seed=seed)
        while s.phase is not Phase.ENDED:
            p = acting_players(s)[0]
            legal = get_legal_actions(s, p)
            if p == 0:
                t0 = time.perf_counter()
                a = agent.act(s, p, legal)
                worst = max(worst, time.perf_counter() - t0)
            else:
                a = others[p - 1].act(s, p, legal)
            assert a in legal
            s, _ = apply_action(s, p, a)
    assert worst < 2.0  # SPEC 1.2: Lv5 answers within 2 s
