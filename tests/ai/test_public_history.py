"""History must preserve public timing while excluding engine-only information."""
import numpy as np
import pytest
import torch

from ai.history import HistoryEncoder, encode_public_history
from engine.game import new_game


def test_private_draw_and_concealed_kong_fields_cannot_leak():
    state = new_game(seed=3)
    state.events = [
        {'type': 'DEAL', 'hands': [[1], [2], [3], [4]]},
        {'type': 'DRAW', 'player': 1, 'tile': 2, 'private': True},
        {'type': 'KONG', 'player': 1, 'tile': 3, 'kind': 'AN_KONG',
         'action': {'tile': 3}, 'tiles': [3] * 4},
        {'type': 'DISCARD', 'player': 1, 'tile': 7},
    ]
    before, mask = encode_public_history(state, 0, limit=8)
    state.events[0]['hands'] = [[1], [9], [10], [11]]
    state.events[1]['tile'] = 20
    state.events[2].update(tile=21, action={'tile': 21}, tiles=[21] * 4)
    after, after_mask = encode_public_history(state, 0, limit=8)
    np.testing.assert_array_equal(before, after)
    np.testing.assert_array_equal(mask, after_mask)
    assert mask.sum() == 3
    assert before[2, 2] == 8  # Public discard 7 is retained; 0 is unknown/padding.


def test_own_draw_is_visible_and_discard_order_is_retained():
    state = new_game(seed=1)
    state.events = [{'type': 'DRAW', 'player': 0, 'tile': 2},
                    {'type': 'DISCARD', 'player': 1, 'tile': 7},
                    {'type': 'DISCARD', 'player': 1, 'tile': 9}]
    tokens, mask = encode_public_history(state, 0, limit=2)
    assert tokens[:, 2].tolist() == [8, 10]
    assert mask.all()
    tokens, _ = encode_public_history(state, 0, limit=4)
    assert tokens[0, 2] == 3


def test_history_encoder_handles_empty_history_and_backpropagates():
    model = HistoryEncoder()
    state = new_game(seed=5)
    state.events = []
    tokens, mask = encode_public_history(state, 0, limit=8)
    empty = model(torch.from_numpy(tokens)[None], torch.from_numpy(mask)[None])
    assert empty.shape == (1, 256)
    assert torch.isfinite(empty).all() and torch.count_nonzero(empty) == 0
    state.events = [{'type': 'DISCARD', 'player': 1, 'tile': 7}]
    tokens, mask = encode_public_history(state, 0, limit=8)
    model(torch.from_numpy(tokens)[None], torch.from_numpy(mask)[None]).square().sum().backward()
    assert model.gru.weight_hh_l0.grad is not None


@pytest.mark.parametrize('use_history', [False, True])
def test_current_neural_policy_is_invariant_to_hidden_hands_and_wall(use_history):
    import random

    from ai.agents.neural_agent import PolicyAgent
    from ai.features import encode, mask_for
    from ai.models.ppo_model import ActorCritic

    state = new_game(seed=17)
    changed = state.clone()
    hidden = [tile for hand in changed.hands[1:] for tile in hand]
    random.Random(83).shuffle(hidden)
    offset = 0
    for seat in range(1, 4):
        n = len(changed.hands[seat])
        changed.hands[seat] = sorted(hidden[offset:offset + n])
        offset += n
    changed.wall.reverse()
    for a, b in zip(encode(state, 0), encode(changed, 0), strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(mask_for(state, 0), mask_for(changed, 0))
    model = ActorCritic(use_history=use_history)
    if use_history:
        # Exercise a learned history branch, rather than only its zero initialization.
        torch.nn.init.normal_(model.history_fuse.weight, std=0.01)
    policy = PolicyAgent(model, 'ppo', seed=9)
    before, mask = policy.scores_tensor(state, 0)
    after, after_mask = policy.scores_tensor(changed, 0)
    assert torch.equal(mask, after_mask)
    assert torch.equal(before, after)
