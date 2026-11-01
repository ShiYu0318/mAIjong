"""Matched MPS Huber/MSE counterfactual-Q experiment with fixed final checkpoints."""
from __future__ import annotations

import fcntl
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as functional

from ai.rollout_q import _centered, build_model, prior_of

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/research-20261101/counterfactual-q-01'
SEED = 20261112


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def counterfactual_loss(prediction, target, mask, kind):
    target = torch.where(mask, target, torch.zeros_like(target))
    prediction = torch.where(mask, prediction, torch.zeros_like(prediction))
    if kind == 'mse':
        error = functional.mse_loss(prediction, target, reduction='none')
    elif kind == 'huber':
        error = functional.huber_loss(prediction, target, reduction='none', delta=1.0)
    else:
        raise ValueError('Expected mse or huber')
    return (error * mask).sum() / mask.sum().clamp_min(1)


def load_data(paths):
    parts = {key: [] for key in ['tiles', 'scalars', 'q', 'chosen']}
    for path in paths:
        with np.load(path, allow_pickle=False) as archive:
            for key in parts:
                parts[key].append(archive[key])
    arrays = {key: np.concatenate(value) for key, value in parts.items()}
    del parts
    q, chosen = arrays['q'], arrays['chosen'].astype(np.int64)
    mask = ~np.isnan(q)
    valid = (chosen >= 0) & (chosen < 34) & (mask.sum(1) >= 2)
    ids = np.flatnonzero(valid)
    valid[ids] &= mask[ids, chosen[ids]]
    if np.isinf(q).any() or not valid.any():
        raise ValueError('Invalid counterfactual labels')
    n, dropped = int(valid.sum()), int((~valid).sum())
    prior = prior_of(torch.from_numpy(chosen[valid]), torch.from_numpy(mask[valid])).to('mps')
    t = torch.from_numpy(arrays['tiles'][valid]).to('mps', dtype=torch.float32)
    s = torch.from_numpy(arrays['scalars'][valid]).to('mps', dtype=torch.float32)
    q = torch.from_numpy(np.nan_to_num(q[valid])).to('mps', dtype=torch.float32)
    mask = torch.from_numpy(mask[valid]).to('mps')
    return {'tiles': t, 'scalars': s, 'target': _centered(q, mask) / 100.0,
            'mask': mask, 'prior': prior}, n, dropped


def train(kind, plan, data, n):
    name = f'research-counterq01-{kind}-{SEED}'
    result = OUT / (name + '-result.json')
    output = ROOT / 'checkpoints' / (name + '.pt')
    if result.exists():
        if sha(output) != json.loads(result.read_text())['checkpoint_sha256']:
            raise ValueError('Completed counterfactual model changed')
        return
    torch.manual_seed(SEED)
    net = build_model(str(ROOT / 'checkpoints/ppo_v7.pt')).to('mps')
    torch.nn.init.zeros_(net.head[-1].weight)
    torch.nn.init.zeros_(net.head[-1].bias)
    optimizer = torch.optim.AdamW(net.parameters(), lr=plan['lr'], weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, plan['epochs'])
    rng = np.random.default_rng(SEED)
    start = time.time()
    write(OUT / 'status.json', {'stage': 'training', 'loss': kind, 'time': start})
    with (OUT / (name + '-metrics.jsonl')).open('w') as stream:
        for epoch in range(1, plan['epochs'] + 1):
            order = rng.permutation(n)
            total, cells = 0.0, 0
            for offset in range(0, n, plan['batch']):
                ids = order[offset:offset + plan['batch']]
                mask = data['mask'][ids]
                pred = _centered(net(data['tiles'][ids], data['scalars'][ids],
                                      data['prior'][ids]), mask)
                loss = counterfactual_loss(pred, data['target'][ids], mask, kind)
                if not torch.isfinite(loss):
                    raise ValueError('Nonfinite counterfactual loss')
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                optimizer.step()
                count = int(mask.sum())
                total += float(loss.detach()) * count
                cells += count
            scheduler.step()
            row = {'epoch': epoch, 'mean_training_loss': total / cells,
                   'seconds': time.time() - start, 'lr': scheduler.get_last_lr()[0]}
            stream.write(json.dumps(row) + '\n')
            stream.flush()
            print(kind, json.dumps(row), flush=True)
    state = {key: tensor.detach().cpu() for key, tensor in net.state_dict().items()}
    torch.save({'state_dict': state, 'training_method': 'counterfactual_' + kind,
                'seed': SEED, 'epochs': plan['epochs'], 'payment_scale': 100.0}, output)
    write(result, {'checkpoint_sha256': sha(output), 'seconds': time.time() - start,
                   'final_training_loss': row['mean_training_loss']})


def main():
    if not torch.backends.mps.is_available():
        raise ValueError('This preregistered run requires MPS')
    torch.set_num_threads(2)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'runner.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        paths = sorted((ROOT / 'data/rollq').glob('*.npz'))
        sources = [*sorted(ROOT.glob('ai/**/*.py')), *sorted(ROOT.glob('engine/**/*.py')),
                   *sorted(ROOT.glob('sdk/maijong_sdk/*.py')), Path(__file__).resolve()]
        plan = {'seed': SEED, 'losses': ['huber', 'mse'], 'epochs': 4, 'batch': 512,
                'device': 'mps', 'torch': torch.__version__, 'lr': 3e-4,
                'scale': 100.0, 'zero_output_initialization': True,
                'initial_sha256': sha(ROOT / 'checkpoints/ppo_v7.pt'),
                'dataset_sha256': {str(path.relative_to(ROOT)): sha(path) for path in paths},
                'sources': {str(path.relative_to(ROOT)): sha(path) for path in sources},
                'evaluation': {'blocks': 128, 'deal_seed_start': 2026140000,
                               'pools': ['rule', 'tuned:checkpoints/rule_cem_v1.json'],
                               'margin': 3.0, 'comparisons': ['huber-cem', 'mse-cem', 'mse-huber',
                                                              'huber-old', 'mse-old']},
                'limitations': ['fixed final epochs, training loss only; no row-validation claims',
                                'archived data have no episode IDs or generator teacher hashes',
                                'one training seed, exploratory comparisons, no promotion',
                                'MSE may have higher finite-sample variance than Huber',
                                'deployment prior uses the current CEM teacher']}
        manifest = OUT / 'manifest.json'
        if manifest.exists():
            if json.loads(manifest.read_text()) != plan:
                raise ValueError('Sources or plan changed; use a new experiment directory')
        else:
            write(manifest, plan)
            for source in sources:
                target = OUT / 'source' / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        data, n, dropped = load_data(paths)
        write(OUT / 'data-counts.json', {'rows': n, 'dropped_teacher_outside_candidates': dropped})
        for kind in plan['losses']:
            train(kind, plan, data, n)
        write(OUT / 'status.json', {'stage': 'complete', 'time': time.time()})


if __name__ == '__main__':
    main()
