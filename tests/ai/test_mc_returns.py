import numpy as np
import pytest

from research.mc_pretrain import monte_carlo_returns


def test_returns_follow_each_seat_and_discount_remaining_own_decisions():
    data = {'hand_seeds': np.array([1, 1, 1, 1]), 'seats': np.array([0, 1, 0, 1]),
            'decision_index': np.array([0, 0, 1, 1]),
            'done': np.array([False, False, True, True]),
            'rewards': np.array([0.0, 0.0, 2.0, -2.0])}
    np.testing.assert_array_equal(monte_carlo_returns(data), [2, -2, 2, -2])
    np.testing.assert_array_equal(monte_carlo_returns(data, gamma=0.5), [1, -1, 2, -2])


def test_incomplete_or_duplicate_trajectories_are_rejected():
    data = {'hand_seeds': np.array([1, 1]), 'seats': np.array([0, 0]),
            'decision_index': np.array([0, 1]), 'done': np.array([False, False]),
            'rewards': np.zeros(2)}
    with pytest.raises(ValueError):
        monte_carlo_returns(data)
    data['done'][1] = True
    data['decision_index'][1] = 0
    with pytest.raises(ValueError):
        monte_carlo_returns(data)


def test_mc_warmup_changes_only_critics_and_synchronizes_targets():
    import torch

    from ai.models.ppo_model import ActorCritic
    from research.iql import IQLLearner
    from research.mc_pretrain import warm_start_critics

    torch.set_num_threads(1)
    torch.manual_seed(71)
    learner = IQLLearner(ActorCritic(), critic_lr=1e-3)
    before = {key: value.clone() for key, value in learner.actor.state_dict().items()}
    data = {'tiles': torch.zeros(4, 34, 14), 'scalars': torch.zeros(4, 13),
            'actions': torch.zeros(4, dtype=torch.int64), 'mc_returns': torch.ones(4)}
    stats = warm_start_critics(learner, data, updates=50, batch_size=4)
    assert stats['mc_q_loss'] < 0.1
    assert all(torch.equal(before[key], value) for key, value in learner.actor.state_dict().items())
    assert all(torch.equal(value, learner.q1_target.state_dict()[key])
               for key, value in learner.q1.state_dict().items())
