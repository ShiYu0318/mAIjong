"""Benchmark the actual IQL update on CPU/MPS without modifying research checkpoints."""
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
import torch

from ai.agents.neural_agent import load_model
from research.iql import IQLLearner
from research.train_iql_ablation import KEYS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/research-20261101/offline-device-benchmark-01.json'


def main():
    if OUT.exists():
        raise ValueError('Benchmark result exists; preserve it and choose a new run name')
    torch.set_num_threads(2)
    shard = ROOT / 'data/research-offline-01/train-source0-shard000.npz'
    with np.load(shard, allow_pickle=False) as archive:
        cpu_batch = {key: torch.from_numpy(archive[key][:128].copy()) for key in KEYS}
    result = {'torch': torch.__version__, 'cpu_threads': 2, 'batch': 128,
              'warmup': 3, 'measured_updates': 20,
              'mps_fallback_environment': os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK'),
              'source_sha256': hashlib.sha256((ROOT / 'research/iql.py').read_bytes()).hexdigest(),
              'limitations': ['other local research CPU jobs were running',
                              'one repeated batch; throughput only, no playing-strength claim'],
              'devices': {}}
    devices = ['cpu'] + (['mps'] if torch.backends.mps.is_available() else [])
    for device in devices:
        try:
            torch.manual_seed(711)
            actor, _ = load_model(ROOT / 'checkpoints/ppo_v7.pt')
            learner = IQLLearner(actor)
            for key in ['actor', 'reference', 'q1', 'q2', 'value', 'q1_target', 'q2_target']:
                getattr(learner, key).to(device)
            for optimizer in [learner.actor_opt, learner.q_opt, learner.v_opt]:
                parameters = [p for g in optimizer.param_groups for p in g['params']]
                if any(p.device.type != device for p in parameters):
                    raise ValueError('Optimizer parameters were not moved with modules')
            batch = {key: value.to(device) for key, value in cpu_batch.items()}
            for _ in range(result['warmup']):
                learner.update(batch)
            if device == 'mps':
                torch.mps.synchronize()
            start = time.perf_counter()
            losses = []
            for _ in range(result['measured_updates']):
                metrics = learner.update(batch)
                if not np.isfinite(list(metrics.values())).all():
                    raise ValueError('Nonfinite IQL update')
                losses.append(metrics['q_loss'])
            if device == 'mps':
                torch.mps.synchronize()
            elapsed = time.perf_counter() - start
            result['devices'][device] = {'seconds': elapsed,
                                         'updates_per_second': result['measured_updates'] / elapsed,
                                         'first_q_loss': losses[0], 'last_q_loss': losses[-1]}
        except Exception as error:
            result['devices'][device] = {'error': type(error).__name__ + ': ' + str(error)}
        OUT.write_text(json.dumps(result, indent=2))
        print(device, json.dumps(result['devices'][device]), flush=True)


if __name__ == '__main__':
    main()
