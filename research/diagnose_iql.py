"""python -m research.diagnose_iql --seed 20261108 --mode iql05; read-only model audit."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from ai.agents.neural_agent import load_model
from research.audit_observations import decision_groups
from research.iql import IQLLearner, advantage_weights, bellman_target, min_data_q
from research.train_iql_ablation import load_data

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/research-20261101/iql-ablation-01'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@torch.no_grad()
def diagnose(seed, mode):
    torch.set_num_threads(2)
    name = f'research-iql01-{mode}-{seed}'
    result = json.loads((OUT / (name + '-result.json')).read_text())
    state_path = OUT / (name + '-training-state.pt')
    if sha(state_path) != result['training_state_sha256']:
        raise ValueError('Training state hash mismatch')
    saved = torch.load(state_path, weights_only=False, map_location='cpu')
    plan = saved['plan']
    initial, _ = load_model(ROOT / 'checkpoints/ppo_v7.pt')
    learner = IQLLearner(initial, tau=0.5 if mode == 'iql05' else 0.7,
                         beta=plan['beta'], gamma=plan['gamma'])
    for key in ['actor', 'q1', 'q2', 'q1_target', 'q2_target', 'value']:
        getattr(learner, key).load_state_dict(saved[key])
        getattr(learner, key).eval()
    bc_path = ROOT / 'checkpoints' / f'research-iql01-bc-{seed}.pt'
    bc_result = json.loads((OUT / f'research-iql01-bc-{seed}-result.json').read_text())
    if sha(bc_path) != bc_result['checkpoint_sha256']:
        raise ValueError('BC checkpoint hash mismatch')
    bc, _ = load_model(bc_path)
    output = {'model': name, 'training_state_sha256': sha(state_path),
              'bc_sha256': sha(bc_path), 'folds': {},
              'limitations': ['validation may have been seen by the initial actor',
                              'TD error is self-consistency, not proof of optimal Q',
                              'grouped diagnostics do not establish playing strength']}
    for fold, data in load_data().items():
        rng = np.random.default_rng(231)
        ids = rng.choice(len(data['actions']), min(4096, len(data['actions'])), replace=False)
        subset = {k: v[ids] for k, v in data.items()}
        groups = decision_groups(subset['tiles'].numpy(), subset['scalars'].numpy(),
                                 subset['masks'].numpy())
        groups.update(terminal=subset['done'].numpy(), nonterminal=~subset['done'].numpy())
        vectors = {}
        for start in range(0, len(ids), 128):
            batch = {k: v[start:start + 128] for k, v in subset.items()}
            t, s, a, mask = batch['tiles'], batch['scalars'], batch['actions'], batch['masks']
            logp, _ = learner.actor(t, s, mask)
            bc_logp, _ = bc(t, s, mask)
            q1, q2 = learner.q1(t, s), learner.q2(t, s)
            q = min_data_q(q1, q2, a)
            q_target = min_data_q(learner.q1_target(t, s), learner.q2_target(t, s), a)
            v = learner.value(t, s).squeeze(1)
            next_v = learner.value(batch['next_tiles'], batch['next_scalars']).squeeze(1)
            target = bellman_target(batch['rewards'], batch['done'], next_v, plan['gamma'])
            weights = advantage_weights(q_target, v, plan['beta'], 100.0)
            items = {'q': q, 'value': v, 'advantage': q_target - v, 'weights': weights,
                     'td_squared': (q - target).square(),
                     'nll': -logp.gather(1, a[:, None]).squeeze(1),
                     'bc_nll': -bc_logp.gather(1, a[:, None]).squeeze(1),
                     'kl_from_bc': (bc_logp.exp() * (bc_logp - logp).masked_fill(
                         ~mask, 0)).sum(1),
                     'greedy_agreement_bc': (logp.argmax(1) == bc_logp.argmax(1)).float(),
                     'twin_gap': (q1.gather(1, a[:, None]) - q2.gather(1, a[:, None])).abs()
                         .squeeze(1)}
            for key, value in items.items():
                vectors.setdefault(key, []).append(value.numpy())
        vectors = {key: np.concatenate(parts) for key, parts in vectors.items()}
        stats = {}
        for group, mask in groups.items():
            if not mask.any():
                stats[group] = {'count': 0}
                continue
            means = {key: float(value[mask].mean()) for key, value in vectors.items()}
            weights = vectors['weights'][mask]
            means.update(count=int(mask.sum()), td_rmse=means.pop('td_squared') ** 0.5,
                         advantage_std=float(vectors['advantage'][mask].std()),
                         weight_ess_fraction=float(weights.sum() ** 2
                                                   / (len(weights) * (weights ** 2).sum())),
                         weight_quantiles=np.quantile(weights, [0.05, 0.5, 0.95]).tolist())
            stats[group] = means
        output['folds'][fold] = stats
    (OUT / (name + '-diagnostics.json')).write_text(json.dumps(output, indent=2))
    print(json.dumps({fold: stats['choice'] for fold, stats in output['folds'].items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261108)
    parser.add_argument('--mode', choices=['iql05', 'iql07'], default='iql05')
    args = parser.parse_args()
    diagnose(args.seed, args.mode)
