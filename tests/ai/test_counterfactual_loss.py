import pytest
import torch

from research.train_counterfactual_q import counterfactual_loss


@pytest.mark.parametrize(('kind', 'expected'), [('mse', 0.25), ('huber', 0.125)])
def test_unlabeled_actions_do_not_enter_loss_or_gradients(kind, expected):
    prediction = torch.tensor([[0.5, 123.0]], requires_grad=True)
    target = torch.tensor([[0.0, float('nan')]])
    mask = torch.tensor([[True, False]])
    loss = counterfactual_loss(prediction, target, mask, kind)
    assert loss.item() == pytest.approx(expected)
    loss.backward()
    assert torch.isfinite(prediction.grad).all()
    assert prediction.grad[0, 1] == 0


def test_huber_and_mean_objectives_differ_for_asymmetric_tail_payments():
    # In 100-point units: 99% zero, 1% +1000 points. Expected payment is +10.
    target = torch.zeros(100, 1)
    target[-1] = 10
    mask = torch.ones_like(target, dtype=torch.bool)
    mean = torch.tensor(0.1, requires_grad=True)
    counterfactual_loss(mean.expand_as(target), target, mask, 'mse').backward()
    assert mean.grad.item() == pytest.approx(0.0, abs=1e-6)
    mean.grad = None
    counterfactual_loss(mean.expand_as(target), target, mask, 'huber').backward()
    assert mean.grad.item() == pytest.approx(0.089, abs=1e-6)


@pytest.mark.skipif(not torch.backends.mps.is_available(), reason='MPS hardware required')
def test_counterfactual_mps_loading_training_and_cpu_deployment(tmp_path, monkeypatch):
    import numpy as np

    import research.train_counterfactual_q as runner
    from ai.agents.neural_agent import save_checkpoint
    from ai.models.ppo_model import ActorCritic
    from ai.rollout_q import RolloutQAgent
    from engine.game import get_legal_actions, new_game

    torch.set_num_threads(1)
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'OUT', tmp_path / 'runs')
    runner.OUT.mkdir()
    save_checkpoint(tmp_path / 'checkpoints/ppo_v7.pt', ActorCritic(), 'ppo',
                    {'hierarchical': True})
    path = tmp_path / 'data.npz'
    q = np.full((8, 34), np.nan, dtype=np.float32)
    q[:, 0], q[:, 1] = 0, 100
    chosen = np.zeros(8, dtype=np.int64)
    chosen[-1] = 2  # The archived teacher pick is outside the evaluated candidate set.
    np.savez(path, tiles=np.zeros((8, 34, 14), np.float16),
             scalars=np.zeros((8, 13), np.float16), q=q, chosen=chosen)
    data, n, dropped = runner.load_data([path])
    assert (n, dropped) == (7, 1)
    assert data['prior'].device.type == 'mps'
    for kind in ['huber', 'mse']:
        runner.train(kind, {'epochs': 1, 'batch': 4, 'lr': 3e-4}, data, n)
        output = tmp_path / f'checkpoints/research-counterq01-{kind}-20261112.pt'
        agent = RolloutQAgent(str(output), seed=7)
        state = new_game(seed=18)
        legal = get_legal_actions(state, 0)
        assert agent.act(state, 0, legal) in legal
