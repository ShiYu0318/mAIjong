import hashlib

import pytest
import torch

from ai.agents.neural_agent import save_checkpoint
from ai.models.ppo_model import ActorCritic
from research.iql import IQLLearner
from research.mc_actor_pilot import prepare_learner


def test_critic_initialization_preserves_actor_and_treats_target_refresh_identically(tmp_path):
    torch.set_num_threads(1)
    actor = ActorCritic()
    initial = tmp_path / 'initial.pt'
    save_checkpoint(initial, actor, 'ppo', {'hierarchical': True})
    critic = IQLLearner(actor)
    with torch.no_grad():
        critic.q1.head[-1].bias.fill_(2.0)
    path = tmp_path / 'critics.pt'
    torch.save({key: getattr(critic, key).state_dict() for key in
                ['q1', 'q2', 'q1_target', 'q2_target', 'value']}, path)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    learner = prepare_learner(initial, path, expected, seed=4)
    assert all(torch.equal(value, learner.actor.state_dict()[key])
               for key, value in actor.state_dict().items())
    assert learner.q1.head[-1].bias[0] == 2
    assert all(torch.equal(value, learner.q1_target.state_dict()[key])
               for key, value in learner.q1.state_dict().items())
    with pytest.raises(ValueError):
        prepare_learner(initial, path, 'changed', seed=4)
