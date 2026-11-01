"""Offline trajectories advance to the same player's next decision, not the next actor."""
import copy

import numpy as np
import pytest

from ai.features import encode
from ai.simulate import make_agent, play_hand, replay_states
from research.offline_data import fold_for_seed, transitions_from_record


def record():
    state, actions = play_hand([make_agent('rule', i) for i in range(4)], seed=73)
    return {'seed': 73, 'actions': actions, 'result': state.result}


def test_same_seat_next_observation_and_terminal_payment():
    rec = record()
    data = transitions_from_record(rec, history_length=8)
    assert len(data['actions']) == len(rec['actions'])
    assert data['masks'][np.arange(len(data['actions'])), data['actions']].all()
    replay = list(replay_states(rec['seed'], rec['actions']))
    for seat in range(4):
        indices = np.flatnonzero(data['seats'] == seat)
        states = [s for s, p, _ in replay if p == seat]
        assert len(indices) == len(states)
        for i, current in enumerate(indices[:-1]):
            tiles, scalars = encode(states[i + 1], seat)
            np.testing.assert_array_equal(data['next_tiles'][current], tiles)
            np.testing.assert_array_equal(data['next_scalars'][current], scalars)
            assert not data['done'][current]
            assert data['rewards'][current] == 0
        final = indices[-1]
        assert data['done'][final]
        assert not data['next_masks'][final].any()
        assert not data['next_tiles'][final].any()
        assert data['rewards'][final] == pytest.approx(rec['result']['payments'][seat] * 0.005)
    assert data['done'].sum() == 4


def test_truncated_and_payment_mismatched_records_are_rejected():
    rec = record()
    truncated = copy.deepcopy(rec)
    truncated['actions'] = truncated['actions'][:-1]
    with pytest.raises(ValueError):
        transitions_from_record(truncated)
    rec['result']['payments'][0] += 1
    with pytest.raises(ValueError):
        transitions_from_record(rec)


def test_fold_is_per_hand_seed_and_reproducible():
    folds = [fold_for_seed(seed) for seed in range(100)]
    assert folds == [fold_for_seed(seed) for seed in range(100)]
    assert {'train', 'validation', 'test'} == set(folds)
