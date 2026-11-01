"""Algorithmic contracts for the discrete, masked IQL research implementation."""
import pytest
import torch

from ai.models.ppo_model import ActorCritic
from research.iql import IQLLearner, advantage_weights, bellman_target, expectile_loss, min_data_q


def test_expectile_weights_positive_residual_more_heavily():
    residual = torch.tensor([-1.0, 1.0], requires_grad=True)
    loss = expectile_loss(residual, tau=0.7)
    loss.backward()
    assert loss.item() == pytest.approx(0.5)
    assert residual.grad.tolist() == pytest.approx([-0.3, 0.7])


def test_terminal_never_bootstraps_even_if_terminal_value_is_nan():
    reward = torch.tensor([2.0, 1.0])
    next_value = torch.tensor([float('nan'), 3.0], requires_grad=True)
    target = bellman_target(reward, torch.tensor([True, False]), next_value, gamma=0.9)
    assert target.tolist() == pytest.approx([2.0, 3.7])
    assert not target.requires_grad


def test_unseen_actions_are_not_read_for_data_q_or_targets():
    q1, q2 = torch.tensor([[2.0, 1e20]]), torch.tensor([[3.0, 1e30]])
    assert min_data_q(q1, q2, torch.tensor([0])).item() == 2.0


def test_advantage_weights_detached_clipped_and_stable():
    q = torch.tensor([-10000.0, 0.0, 10000.0], requires_grad=True)
    value = torch.zeros(3, requires_grad=True)
    weights = advantage_weights(q, value, beta=3.0, max_weight=100.0)
    assert torch.isfinite(weights).all()
    assert weights.tolist() == pytest.approx([0.0, 1.0, 100.0], abs=1e-4)
    assert not weights.requires_grad


def batch():
    masks = torch.zeros((4, 108), dtype=torch.bool)
    masks[:, :2] = True
    return {'tiles': torch.rand(4, 34, 14), 'scalars': torch.zeros(4, 13),
            'next_tiles': torch.zeros(4, 34, 14), 'next_scalars': torch.zeros(4, 13),
            'masks': masks, 'actions': torch.tensor([0, 1, 0, 1]),
            'rewards': torch.tensor([2.0, -1.0, 1.0, -2.0]),
            'done': torch.ones(4, dtype=torch.bool)}


def test_learner_updates_critics_without_updating_actor_during_warmup(tmp_path):
    from ai.agents.neural_agent import agent_from_checkpoint
    from engine.game import acting_players, get_legal_actions, new_game

    torch.set_num_threads(1)
    initial = ActorCritic()
    learner = IQLLearner(initial)
    before = {k: v.clone() for k, v in learner.actor.state_dict().items()}
    stats = learner.update(batch(), train_actor=False)
    assert stats['q_loss'] > 0
    assert all(torch.equal(before[k], v) for k, v in learner.actor.state_dict().items())
    assert any(torch.count_nonzero(p) > 0 for p in learner.q1.head[-1].parameters())
    learner.update(batch(), train_actor=True)
    assert any(not torch.equal(before[k], v) for k, v in learner.actor.state_dict().items())
    assert all(p.grad is None for p in learner.q1_target.parameters())
    output = tmp_path / 'iql.pt'
    learner.save_actor(output)
    agent = agent_from_checkpoint(output)
    state = new_game(seed=84)
    seat = acting_players(state)[0]
    assert agent.act(state, seat, get_legal_actions(state, seat)) in get_legal_actions(state, seat)


def test_bad_hyperparameters_and_illegal_dataset_actions_are_rejected():
    for kwargs in [{'tau': 1.0}, {'beta': -1.0}, {'polyak': 0.0}]:
        with pytest.raises(ValueError):
            IQLLearner(ActorCritic(), **kwargs)
    data = batch()
    data['actions'][0] = 5
    with pytest.raises(ValueError):
        IQLLearner(ActorCritic()).update(data)


def test_ablation_runner_saves_methods_and_rejects_changed_model(tmp_path, monkeypatch):
    import json

    import research.train_iql_ablation as runner
    from ai.agents.neural_agent import load_model, save_checkpoint

    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'OUT', tmp_path / 'runs')
    runner.OUT.mkdir()
    save_checkpoint(tmp_path / 'checkpoints/ppo_v7.pt', ActorCritic(), 'ppo',
                    {'hierarchical': True})
    plan = {'actor_steps': 2, 'critic_warmup': 1, 'batch': 2,
            'actor_lr': 1e-4, 'critic_lr': 1e-3, 'gamma': 1.0, 'beta': 1.0}
    data = {'train': batch(), 'validation': batch()}
    for mode in ['bc', 'iql07']:
        runner.train_one(42, mode, plan, data)
        path = tmp_path / f'checkpoints/research-iql01-{mode}-42.pt'
        model, kind = load_model(path)
        assert isinstance(model, ActorCritic) and kind == 'ppo'
        result = json.loads((runner.OUT / f'research-iql01-{mode}-42-result.json').read_text())
        assert result['checkpoint_sha256'] == runner.sha(path)
        path.write_bytes(path.read_bytes() + b'changed')
        with pytest.raises(ValueError):
            runner.train_one(42, mode, plan, data)


def test_terminal_payments_can_be_learned_without_bootstrap():
    torch.set_num_threads(1)
    torch.manual_seed(73)
    learner = IQLLearner(ActorCritic(), critic_lr=1e-3)
    data = batch()
    before = learner.diagnostics(data)['terminal_td_rmse']
    for _ in range(80):
        learner.update(data, train_actor=False)
    after = learner.diagnostics(data)['terminal_td_rmse']
    assert after < before * 0.25
