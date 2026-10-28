"""Rollout Q distillation: candidate discards, deterministic labels, a legal-playing agent."""

from __future__ import annotations

import numpy as np
import pytest

from ai.rollout_q import TOP_K, _lv5, candidates, label
from engine.actions import ActionType
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game


def _first_discard(seed: int):
    s = new_game(seed=seed)
    agents = [_lv5(p) for p in range(4)]
    while not (s.phase is Phase.DISCARD and s.turn == acting_players(s)[0]):
        p = acting_players(s)[0]
        s, _ = apply_action(s, p, agents[p].act(s, p, get_legal_actions(s, p)))
    return s, s.turn


def test_candidates_are_legal_discards_and_labels_repeat():
    s, p = _first_discard(11)
    legal = get_legal_actions(s, p)
    tiles = candidates(_lv5(0), s, p, legal)
    legal_tiles = {a.tile for a in legal if a.type is ActionType.DISCARD}
    assert 2 <= len(tiles) <= TOP_K and set(tiles) <= legal_tiles
    q = label(s, p, tiles, seed=5)
    assert set(np.flatnonzero(~np.isnan(q))) == set(tiles)
    assert np.array_equal(q, label(s, p, tiles, seed=5), equal_nan=True)  # same seeds, same play


def test_rollout_q_agent_plays_legal_moves(tmp_path):
    torch = pytest.importorskip("torch")
    from ai.rollout_q import build_model
    from ai.simulate import make_agent

    path = tmp_path / "q.pt"
    torch.save({"state_dict": build_model().state_dict()}, path)
    agents = [make_agent(f"rollq:{path},0", 1)] + [_lv5(p) for p in range(1, 4)]
    s = new_game(seed=2)
    while s.phase is not Phase.ENDED:
        p = acting_players(s)[0]
        legal = get_legal_actions(s, p)
        a = agents[p].act(s, p, legal)
        assert a in legal
        s, _ = apply_action(s, p, a)
