"""Table helpers sent to clients: tsumogiri flags and ready-hand waits."""

from __future__ import annotations

from ai.agents import RuleAgent
from backend.ws.view import discard_flags, discard_waits, masked_state
from engine import tiles
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game
from engine.shanten import shanten


def play(seed: int, steps: int = 400):
    s = new_game(seed=seed)
    agents = [RuleAgent(0.0, seed + i) for i in range(4)]
    for _ in range(steps):
        if s.phase is Phase.ENDED:
            break
        p = acting_players(s)[0]
        yield s
        s, _ = apply_action(s, p, agents[p].act(s, p, get_legal_actions(s, p)))


def test_tsumogiri_flags_line_up_with_rivers():
    seen_true = seen_false = False
    for seed in range(5):
        for s in play(seed):
            flags = discard_flags(s)
            for p in range(4):
                assert len(flags[p]) == len(s.discards[p])
                seen_true |= any(flags[p])
                seen_false |= not all(flags[p])
    assert seen_true and seen_false
    view = masked_state(new_game(seed=1), 0)
    assert all(pl["tsumogiri"] == [] for pl in view["players"])


def test_discard_waits_are_real_waits():
    checked = 0
    for seed in range(12):
        for s in play(seed):
            if s.phase is not Phase.DISCARD:
                continue
            seat = s.turn
            waits = discard_waits(s, seat)
            for t_str, ws in waits.items():
                t = int(t_str)
                counts = tiles.to_counts(s.hands[seat])
                counts[t] -= 1
                for w, left in ws:
                    complete = list(counts)
                    complete[w] += 1
                    assert shanten(complete, len(s.melds[seat])) == -1
                    assert 0 <= left <= 4
                checked += 1
    assert checked > 0
    assert discard_waits(new_game(seed=2), 1) == {}  # not this seat's discard turn
