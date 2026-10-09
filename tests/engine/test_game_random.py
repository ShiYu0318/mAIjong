"""Integration: play many random games to the end and check invariants (P1-8)."""

from __future__ import annotations

import random
from collections import Counter

from engine import tiles
from engine.actions import ActionType
from engine.game import GameState, Phase, acting_players, apply_action, get_legal_actions, new_game


def tile_census(s: GameState) -> Counter[int]:
    c: Counter[int] = Counter()
    for p in range(4):
        c.update(s.hands[p])
        c.update(s.flowers[p])
        c.update(s.discards[p])
        for m in s.melds[p]:
            c.update(m.tiles)
    c.update(s.wall)
    return c


EXPECTED = Counter(tiles.full_wall())


def play_random(seed: int, hu_bias: float = 0.9) -> tuple[GameState, int]:
    rng = random.Random(seed)
    s = new_game(seed=seed)
    steps = 0
    while s.phase is not Phase.ENDED:
        players = acting_players(s)
        assert players, f"no one to act in {s.phase}"
        p = players[0]
        legal = get_legal_actions(s, p)
        assert legal
        hu = [a for a in legal if a.type is ActionType.HU]
        a = hu[0] if hu and rng.random() < hu_bias else rng.choice(legal)
        s, _ = apply_action(s, p, a)
        steps += 1
        assert tile_census(s) == EXPECTED, f"tile conservation broken at step {steps}"
        assert steps < 2000
    return s, steps


def test_thousand_random_games_terminate_with_invariants():
    kinds: Counter[str] = Counter()
    for seed in range(1000):
        s, _ = play_random(seed)
        assert s.result is not None
        assert sum(s.scores) == 0
        kinds[s.result["kind"]] += 1
        if s.result["kind"] == "HU":
            assert s.result["payments"][s.result["winner"]] > 0
    assert kinds["HU"] > 0 and kinds["DRAW"] > 0


def test_determinism_same_seed_same_game():
    a, _ = play_random(42)
    b, _ = play_random(42)
    da, db = a.to_dict(), b.to_dict()
    da.pop("game_id"), db.pop("game_id")
    assert da == db


def test_input_state_not_mutated():
    s = new_game(seed=7)
    before = s.to_dict()
    p = acting_players(s)[0]
    apply_action(s, p, get_legal_actions(s, p)[0])
    assert s.to_dict() == before
