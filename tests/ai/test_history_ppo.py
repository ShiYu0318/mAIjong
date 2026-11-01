"""End-to-end contracts for warm-started public-history PPO."""
import numpy as np
import pytest
import torch

from ai.env import MahjongEnv
from ai.models.ppo_model import ActorCritic


def test_history_warm_start_preserves_policy_and_rejects_missing_base_weights():
    base = ActorCritic()
    model = ActorCritic(use_history=True)
    model.load_warm_start(base.state_dict())
    env = MahjongEnv(seed=7, history_length=16)
    obs, info = env.reset()
    t = torch.from_numpy(obs['tiles'])[None]
    s = torch.from_numpy(obs['scalars'])[None]
    m = torch.from_numpy(info['legal_mask'])[None]
    history = torch.from_numpy(obs['history'])[None]
    history_mask = torch.from_numpy(obs['history_mask'])[None]
    before, value = base(t, s, m)
    after, hist_value = model(t, s, m, history=history, history_mask=history_mask)
    assert torch.equal(before, after) and torch.equal(value, hist_value)
    broken = dict(base.state_dict())
    broken.pop('type_head.weight')
    with pytest.raises(ValueError):
        model.load_warm_start(broken)
    with pytest.raises(ValueError):
        model(t, s, m)


def test_history_env_observation_space_matches_reset_and_step():
    env = MahjongEnv(seed=8, history_length=16)
    obs, info = env.reset()
    assert env.observation_space.contains(obs)
    assert obs['history'].shape == (16, 5)
    action = int(np.flatnonzero(info['legal_mask'])[0])
    obs, *_ = env.step(action)
    assert env.observation_space.contains(obs)


def test_history_ppo_trains_and_loads_checkpoint(tmp_path, monkeypatch):
    import ai.training.metrics as metrics
    from ai.agents.neural_agent import agent_from_checkpoint, save_checkpoint
    from ai.training.ppo_trainer import PPOConfig, train_ppo
    from engine.game import acting_players, get_legal_actions, new_game

    monkeypatch.setattr(metrics, 'RUNS_DIR', tmp_path / 'runs')
    torch.set_num_threads(1)
    initial = tmp_path / 'initial.pt'
    save_checkpoint(initial, ActorCritic(), 'ppo', {'hierarchical': True})
    output = tmp_path / 'history.pt'
    cfg = PPOConfig(use_history=True, history_length=16, n_envs=2, rollout_steps=8,
                    updates=2, mini_batch=8, n_epochs=1, value_warmup=0,
                    eval_every=2, eval_hands=4, seed=91)
    train_ppo(cfg, output, init=initial, run='history-test')
    agent = agent_from_checkpoint(output, seed=4)
    assert agent.model.use_history
    assert agent.model.history_length == 16
    state = new_game(seed=10)
    seat = acting_players(state)[0]
    assert agent.act(state, seat, get_legal_actions(state, seat)) in get_legal_actions(state, seat)
    assert torch.count_nonzero(agent.model.history_fuse.weight) > 0
