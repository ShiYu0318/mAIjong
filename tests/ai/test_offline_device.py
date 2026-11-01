import copy

import numpy as np
import pytest
import torch

from ai.models.ppo_model import ActorCritic
from research.iql import IQLLearner
from research.offline_device import move_learner


@pytest.mark.skipif(not torch.backends.mps.is_available(), reason='MPS hardware required')
def test_variable_minibatches_match_cpu_and_saved_actor_loads_on_cpu(tmp_path):
    from ai.agents.neural_agent import load_model

    torch.set_num_threads(1)
    torch.manual_seed(19)
    cpu = IQLLearner(ActorCritic())
    gpu = move_learner(copy.deepcopy(cpu), 'mps')
    batch = {'tiles': torch.rand(16, 34, 14), 'scalars': torch.rand(16, 13),
             'next_tiles': torch.rand(16, 34, 14), 'next_scalars': torch.rand(16, 13),
             'masks': torch.ones(16, 108, dtype=torch.bool), 'actions': torch.arange(16),
             'rewards': torch.linspace(-1, 1, 16), 'done': torch.arange(16) % 2 == 0}
    gpu_data = {key: value.to('mps') for key, value in batch.items()}
    rng = np.random.default_rng(7)
    for _ in range(3):
        ids = rng.integers(16, size=8)
        cpu.update({key: value[ids] for key, value in batch.items()})
        stats = gpu.update({key: value[ids] for key, value in gpu_data.items()})
        assert np.isfinite(list(stats.values())).all()
    for key, value in cpu.actor.state_dict().items():
        torch.testing.assert_close(value, gpu.actor.state_dict()[key].cpu(), atol=1e-4, rtol=1e-3)
    path = tmp_path / 'mps.pt'
    gpu.save_actor(path)
    model, _ = load_model(path)
    assert next(model.parameters()).device.type == 'cpu'
    logp, _ = model(batch['tiles'], batch['scalars'], batch['masks'])
    assert torch.isfinite(logp).all()


@pytest.mark.skipif(not torch.backends.mps.is_available(), reason='MPS hardware required')
def test_gpu_pilot_saves_all_three_methods_with_cpu_inference(tmp_path, monkeypatch):
    from ai.agents.neural_agent import load_model, save_checkpoint
    from research import gpu_offline_pilot as runner

    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'OUT', tmp_path / 'runs')
    runner.OUT.mkdir()
    save_checkpoint(tmp_path / 'checkpoints/ppo_v7.pt', ActorCritic(), 'ppo',
                    {'hierarchical': True})
    batch = {'tiles': torch.rand(16, 34, 14), 'scalars': torch.rand(16, 13),
             'next_tiles': torch.rand(16, 34, 14), 'next_scalars': torch.rand(16, 13),
             'masks': torch.ones(16, 108, dtype=torch.bool), 'actions': torch.arange(16),
             'rewards': torch.linspace(-1, 1, 16), 'done': torch.arange(16) % 2 == 0,
             'mc_returns': torch.linspace(-1, 1, 16)}
    fields = {key: tensor.to('mps') for key, tensor in batch.items()}
    data = {'train': fields, 'validation': fields}
    plan = {'actor_steps': 2, 'critic_warmup': 2, 'batch': 4,
            'actor_lr': 3e-5, 'critic_lr': 3e-4}
    for mode in ['bc', 'td', 'mc']:
        runner.train(mode, plan, data)
        model, _ = load_model(tmp_path / f'checkpoints/research-gpuoffline01-{mode}-20261111.pt')
        logp, _ = model(batch['tiles'], batch['scalars'], batch['masks'])
        assert torch.isfinite(logp).all()
