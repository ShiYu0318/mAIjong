"""Compare 300 MC versus TD critic-only updates; no actor or playing-strength claims."""
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from ai.agents.neural_agent import load_model
from research.iql import IQLLearner, min_data_q
from research.mc_pretrain import monte_carlo_returns, warm_start_critics
from research.train_iql_ablation import KEYS, take

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/research-offline-01'
OUT = ROOT / 'runs/research-20261101/critic-warmstart-pilot-01'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_with_returns(directory: Path = DATA):
    status = json.loads((directory / 'status.json').read_text())
    if not status.get('complete'):
        raise ValueError('Dataset conversion is incomplete')
    parts = {'train': [], 'validation': []}
    for shard in status['shards']:
        if shard['fold'] not in parts:
            continue
        path = directory / shard['path']
        if sha(path) != shard['sha256']:
            raise ValueError('Dataset shard changed')
        with np.load(path, allow_pickle=False) as archive:
            fields = {key: archive[key] for key in
                      [*KEYS, 'hand_seeds', 'seats', 'decision_index']}
        returns = monte_carlo_returns(fields)
        parts[shard['fold']].append({**{key: fields[key] for key in KEYS}, 'mc_returns': returns})
    return {fold: {key: torch.from_numpy(np.concatenate([part[key] for part in rows]))
                   for key in rows[0]} for fold, rows in parts.items()}


@torch.no_grad()
def score(learner, data):
    indices = np.random.default_rng(231).choice(len(data['actions']),
                                               min(4096, len(data['actions'])), replace=False)
    q_error, v_error, labels = [], [], []
    for start in range(0, len(indices), 128):
        ids = indices[start:start + 128]
        t, s, a, y = (data[k][ids] for k in ['tiles', 'scalars', 'actions', 'mc_returns'])
        q = min_data_q(learner.q1(t, s), learner.q2(t, s), a)
        v = learner.value(t, s).squeeze(1)
        q_error.extend((q - y).square().tolist())
        v_error.extend((v - y).square().tolist())
        labels.extend(y.square().tolist())
    return {'mc_data_q_rmse': float(np.mean(q_error) ** 0.5),
            'mc_value_rmse': float(np.mean(v_error) ** 0.5),
            'zero_predictor_rmse': float(np.mean(labels) ** 0.5)}


def main():
    torch.set_num_threads(2)
    OUT.mkdir(parents=True, exist_ok=False)
    seed = 20261108
    sources = [Path(__file__).resolve(), ROOT / 'research/iql.py', ROOT / 'research/mc_pretrain.py',
               *sorted(ROOT.glob('ai/models/*.py'))]
    manifest = {'seed': seed, 'updates': 300, 'batch': 128, 'gamma': 1.0, 'tau': 0.7,
                'initial_sha256': sha(ROOT / 'checkpoints/ppo_v7.pt'),
                'dataset_status_sha256': sha(DATA / 'status.json'),
                'sources': {str(p.relative_to(ROOT)): sha(p) for p in sources},
                'limitations': ['single seed, critic-only diagnostic',
                                'MC target is noisy behavior-policy payment, not optimal Q',
                                'initial actor may have seen validation records',
                                'no actor improvement or playing strength tested']}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    for source in sources:
        target = OUT / 'source' / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    data = load_with_returns()
    for mode in ['td', 'mc']:
        torch.manual_seed(seed)
        actor, _ = load_model(ROOT / 'checkpoints/ppo_v7.pt')
        learner = IQLLearner(actor, tau=0.7)
        (OUT / 'status.json').write_text(json.dumps({'stage': 'training', 'mode': mode}))
        with (OUT / (mode + '-metrics.jsonl')).open('w') as log:
            def record(stats):
                log.write(json.dumps(stats) + '\n')
                log.flush()
            if mode == 'mc':
                warm_start_critics(learner, data['train'], updates=300, batch_size=128,
                                  seed=seed + 100000, log=record)
            else:
                rng = np.random.default_rng(seed + 100000)
                for step in range(1, 301):
                    stats = learner.update(take(data['train'], rng, 128), train_actor=False)
                    if step % 50 == 0:
                        record({'step': step, **stats})
        result = {fold: score(learner, fields) for fold, fields in data.items()}
        state_path = OUT / (mode + '-critics.pt')
        torch.save({key: getattr(learner, key).state_dict() for key in
                    ['q1', 'q2', 'q1_target', 'q2_target', 'value']}, state_path)
        result['checkpoint_sha256'] = sha(state_path)
        (OUT / (mode + '-result.json')).write_text(json.dumps(result, indent=2))
        print(mode, json.dumps(result), flush=True)
    (OUT / 'status.json').write_text(json.dumps({'stage': 'complete'}))


if __name__ == '__main__':
    main()
