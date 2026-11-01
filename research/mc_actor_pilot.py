"""Single-seed MC/TD critic initialization followed by matched IQL actor training."""
from __future__ import annotations

import fcntl
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch

from ai.agents.neural_agent import load_model
from ai.training.block_evaluate import bootstrap_interval, play_block
from research.iql import IQLLearner
from research.train_iql_ablation import load_data, take

ROOT = Path(__file__).resolve().parents[1]
WARM = ROOT / 'runs/research-20261101/critic-warmstart-pilot-01'
OUT = ROOT / 'runs/research-20261101/mc-actor-pilot-01'
SEED = 20261108


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def prepare_learner(initial, critic_path, expected_hash, seed):
    if sha(critic_path) != expected_hash:
        raise ValueError('Critic initialization hash changed')
    torch.manual_seed(seed)
    actor, _ = load_model(initial)
    learner = IQLLearner(actor, tau=0.7, beta=3.0, gamma=1.0)
    saved = torch.load(critic_path, map_location='cpu', weights_only=False)
    for key in ['q1', 'q2', 'value']:
        getattr(learner, key).load_state_dict(saved[key])
    # Both branches refresh targets and reset optimizers, isolating the warm-start labels.
    learner.q1_target.load_state_dict(learner.q1.state_dict())
    learner.q2_target.load_state_dict(learner.q2.state_dict())
    return learner


def train(mode, plan, data):
    name = f'research-mcactor01-{mode}-{SEED}'
    checkpoint = ROOT / 'checkpoints' / (name + '.pt')
    result_path = OUT / (name + '-result.json')
    if result_path.exists():
        if sha(checkpoint) != json.loads(result_path.read_text())['checkpoint_sha256']:
            raise ValueError('Completed actor changed')
        return checkpoint
    learner = prepare_learner(ROOT / 'checkpoints/ppo_v7.pt', WARM / (mode + '-critics.pt'),
                              plan['critic_hashes'][mode], SEED)
    rng = np.random.default_rng(SEED)
    t0 = time.time()
    write(OUT / 'status.json', {'stage': 'training', 'mode': mode, 'time': t0})
    with (OUT / (name + '-metrics.jsonl')).open('w') as log:
        for step in range(1, plan['actor_steps'] + 1):
            stats = learner.update(take(data['train'], rng, plan['batch']))
            if step % 50 == 0:
                row = {'step': step, 'seconds': time.time() - t0, **stats}
                log.write(json.dumps(row) + '\n')
                log.flush()
                print(mode, json.dumps(row), flush=True)
    learner.save_actor(checkpoint, seed=SEED, critic_init=mode, beta=3.0,
                       actor_steps=plan['actor_steps'])
    validation = take(data['validation'], np.random.default_rng(711), 2048)
    state_path = OUT / (name + '-training-state.pt')
    state = {key: getattr(learner, key).state_dict() for key in
             ['actor', 'q1', 'q2', 'q1_target', 'q2_target', 'value',
              'actor_opt', 'q_opt', 'v_opt']}
    torch.save({**state, 'rng': rng.bit_generator.state, 'torch_rng': torch.get_rng_state(),
                'plan': plan}, state_path)
    write(result_path, {'checkpoint_sha256': sha(checkpoint),
                        'training_state_sha256': sha(state_path),
                        'diagnostics': learner.diagnostics(validation),
                        'seconds': time.time() - t0})
    return checkpoint


def evaluate(paths, plan):
    for label, left, right in [('td-bc', paths['td'], paths['bc']),
                               ('mc-bc', paths['mc'], paths['bc']),
                               ('mc-td', paths['mc'], paths['td'])]:
        hashes = [sha(left), sha(right)]
        for pool, opponent in enumerate(plan['pools']):
            stem = f'{label}-pool{pool}'
            write(OUT / 'status.json', {'stage': 'evaluating', 'run': stem, 'time': time.time()})
            path = OUT / (stem + '.jsonl')
            rows = [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
            if len(rows) > plan['blocks']:
                raise ValueError('Too many saved evaluation rows')
            cache = {}
            for k in range(plan['blocks']):
                seed = plan['deal_seed_start'] + pool * 100000 + k
                if k < len(rows):
                    if rows[k]['seed'] != seed or rows[k]['checkpoint_hashes'] != hashes:
                        raise ValueError('Saved evaluation row mismatch')
                    continue
                row = play_block('ppo:' + str(left), 'ppo:' + str(right), opponent, seed, cache)
                row['checkpoint_hashes'] = hashes
                with path.open('a') as stream:
                    stream.write(json.dumps(row) + '\n')
                rows.append(row)
            means = [r['mean_difference'] for r in rows]
            summary = {'comparison': label, 'opponent': opponent, 'blocks': len(rows),
                       'mean_difference': sum(means) / len(means),
                       'bootstrap_ci95': bootstrap_interval(means, seed=823),
                       'checkpoint_hashes': hashes}
            write(OUT / (stem + '-summary.json'), summary)
            print(json.dumps(summary), flush=True)


def main():
    torch.set_num_threads(2)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'runner.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        initial = ROOT / 'checkpoints/ppo_v7.pt'
        bc = ROOT / f'checkpoints/research-iql01-bc-{SEED}.pt'
        warm_manifest = json.loads((WARM / 'manifest.json').read_text())
        if sha(initial) != warm_manifest['initial_sha256']:
            raise ValueError('Original warm-start actor changed')
        sources = sorted([*ROOT.glob('ai/**/*.py'), *ROOT.glob('engine/**/*.py'),
                          ROOT / 'research/iql.py', ROOT / 'research/train_iql_ablation.py',
                          Path(__file__).resolve()])
        plan = {'seed': SEED, 'beta': 3.0, 'gamma': 1.0, 'tau': 0.7,
                'actor_steps': 600, 'batch': 128, 'blocks': 128,
                'actor_lr': 3e-5, 'critic_lr': 3e-4,
                'pools': ['rule', 'tuned:checkpoints/rule_cem_v1.json'],
                'deal_seed_start': 2026126000,
                'initial_sha256': sha(initial), 'bc_sha256': sha(bc),
                'warm_manifest_sha256': sha(WARM / 'manifest.json'),
                'critic_hashes': {mode: json.loads((WARM / (mode + '-result.json')).read_text())
                                  ['checkpoint_sha256'] for mode in ['td', 'mc']},
                'cem_sha256': sha(ROOT / 'checkpoints/rule_cem_v1.json'),
                'dataset_status_sha256': sha(ROOT / 'data/research-offline-01/status.json'),
                'sources': {str(p.relative_to(ROOT)): sha(p) for p in sources},
                'limitations': ['single-seed exploratory pilot, six comparisons',
                                'both target critics refreshed, both optimizers reset',
                                'beta3 differs from original beta1 IQL ablation',
                                'actor initialized from original model in both branches',
                                'no automatic promotion; fixed final checkpoint']}
        manifest = OUT / 'manifest.json'
        if manifest.exists():
            if json.loads(manifest.read_text()) != plan:
                raise ValueError('Source or plan changed; use a new directory')
        else:
            write(manifest, plan)
            for source in sources:
                target = OUT / 'source' / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        data = load_data()
        paths = {mode: train(mode, plan, data) for mode in ['td', 'mc']}
        paths['bc'] = bc
        if sha(bc) != plan['bc_sha256']:
            raise ValueError('BC baseline changed during training')
        evaluate(paths, plan)
        write(OUT / 'status.json', {'stage': 'complete', 'time': time.time()})


if __name__ == '__main__':
    main()
