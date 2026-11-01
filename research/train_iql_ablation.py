"""python -m research.train_iql_ablation: audited local IQL / BC screening."""
from __future__ import annotations

import fcntl
import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import torch

from ai.agents.neural_agent import load_model, save_checkpoint
from research.iql import IQLLearner

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/research-20261101/iql-ablation-01'
DATA = ROOT / 'data/research-offline-01'
SEEDS = [20261108, 20261109, 20261110]
MODES = ['bc', 'iql05', 'iql07']
KEYS = ['tiles', 'scalars', 'masks', 'actions', 'next_tiles', 'next_scalars', 'rewards', 'done']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def load_data():
    status = json.loads((DATA / 'status.json').read_text())
    if not status.get('complete'):
        raise ValueError('Dataset conversion is incomplete')
    parts = {fold: [] for fold in ['train', 'validation', 'test']}
    groups = {fold: set() for fold in parts}
    for shard in status['shards']:
        path = DATA / shard['path']
        if sha(path) != shard['sha256']:
            raise ValueError('Dataset shard hash mismatch')
        with np.load(path, allow_pickle=False) as data:
            groups[shard['fold']].update(data['hand_seeds'].tolist())
            if shard['fold'] != 'test':
                parts[shard['fold']].append({key: data[key] for key in KEYS})
    for left, right in [('train', 'validation'), ('train', 'test'), ('validation', 'test')]:
        if groups[left] & groups[right]:
            raise ValueError('Same shuffled wall appears in multiple folds')
    return {fold: {key: torch.from_numpy(np.concatenate([p[key] for p in parts[fold]]))
                   for key in KEYS} for fold in ['train', 'validation']}


def take(data, rng, size):
    ids = rng.integers(len(data['actions']), size=size)
    return {key: value[ids] for key, value in data.items()}


def train_one(seed, mode, plan, data):
    name = f'research-iql01-{mode}-{seed}'
    checkpoint = ROOT / 'checkpoints' / (name + '.pt')
    result_path = OUT / (name + '-result.json')
    if result_path.exists():
        if sha(checkpoint) != json.loads(result_path.read_text())['checkpoint_sha256']:
            raise ValueError('Completed actor checkpoint changed')
        return
    torch.manual_seed(seed)
    actor, _ = load_model(ROOT / 'checkpoints/ppo_v7.pt')
    actor.train()
    # Dedicated actor sampling stream is identical for BC and both IQL variants.
    actor_rng = np.random.default_rng(seed)
    critic_rng = np.random.default_rng(seed + 100000)
    val_rng = np.random.default_rng(711)
    validation = take(data['validation'], val_rng, min(2048, len(data['validation']['actions'])))
    t0 = time.time()
    write(OUT / 'status.json', {'stage': 'training', 'run': name, 'time': t0})
    metrics_path = OUT / (name + '-metrics.jsonl')
    with metrics_path.open('w') as log:
        if mode == 'bc':
            optimizer = torch.optim.Adam(actor.parameters(), lr=plan['actor_lr'])
            reference, _ = load_model(ROOT / 'checkpoints/ppo_v7.pt')
            reference.eval().requires_grad_(False)
            learner = None
        else:
            learner = IQLLearner(actor, tau=0.5 if mode == 'iql05' else 0.7,
                                 actor_lr=plan['actor_lr'], critic_lr=plan['critic_lr'],
                                 beta=plan['beta'], gamma=plan['gamma'])
            for step in range(plan['critic_warmup']):
                stats = learner.update(take(data['train'], critic_rng, plan['batch']),
                                       train_actor=False)
                if (step + 1) % 50 == 0:
                    log.write(json.dumps({'phase': 'critic_warmup', 'step': step + 1,
                                          **stats}) + '\n')
                    log.flush()
            actor = learner.actor
        for step in range(1, plan['actor_steps'] + 1):
            batch = take(data['train'], actor_rng, plan['batch'])
            if learner is not None:
                stats = learner.update(batch)
            else:
                logp, _ = actor(batch['tiles'], batch['scalars'], batch['masks'])
                loss = -logp.gather(1, batch['actions'][:, None]).mean()
                with torch.no_grad():
                    ref, _ = reference(batch['tiles'], batch['scalars'], batch['masks'])
                    kl = (ref.exp() * (ref - logp).masked_fill(~batch['masks'], 0)).sum(1).mean()
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(actor.parameters(), 1.0)
                optimizer.step()
                stats = {'actor_loss': float(loss.detach()), 'kl_to_initial': float(kl)}
            if step % 50 == 0:
                metrics = {'phase': 'actor', 'step': step, 'seconds': time.time() - t0, **stats}
                log.write(json.dumps(metrics) + '\n')
                log.flush()
                print(name, json.dumps(metrics), flush=True)
    if learner is not None:
        diagnostics = learner.diagnostics(validation)
        learner.save_actor(checkpoint, actor_steps=plan['actor_steps'], seed=seed, tau=learner.tau)
        training_state = {
            'actor': actor.state_dict(), 'q1': learner.q1.state_dict(),
            'q2': learner.q2.state_dict(), 'q1_target': learner.q1_target.state_dict(),
            'q2_target': learner.q2_target.state_dict(), 'value': learner.value.state_dict(),
            'q_opt': learner.q_opt.state_dict(), 'v_opt': learner.v_opt.state_dict(),
            'actor_opt': learner.actor_opt.state_dict()}
    else:
        with torch.no_grad():
            logp, _ = actor(validation['tiles'], validation['scalars'], validation['masks'])
            diagnostics = {'nll': float(-logp.gather(1, validation['actions'][:, None]).mean())}
        save_checkpoint(checkpoint, actor, 'ppo', {'hierarchical': actor.hierarchical,
                        'use_transformer': actor.encoder.use_transformer},
                        training_method='bc', actor_steps=plan['actor_steps'], seed=seed)
        training_state = {'actor': actor.state_dict(), 'actor_opt': optimizer.state_dict()}
    state_path = OUT / (name + '-training-state.pt')
    torch.save({**training_state, 'torch_rng': torch.get_rng_state(),
                'actor_rng': actor_rng.bit_generator.state,
                'critic_rng': critic_rng.bit_generator.state, 'plan': plan}, state_path)
    write(result_path, {'checkpoint_sha256': sha(checkpoint), 'diagnostics': diagnostics,
                        'seconds': time.time() - t0, 'training_state_sha256': sha(state_path)})


def main():
    torch.set_num_threads(2)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'runner.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sources = sorted([*ROOT.glob('ai/**/*.py'), *ROOT.glob('engine/**/*.py'),
                          ROOT / 'research/iql.py', Path(__file__).resolve()])
        plan = {'seeds': SEEDS, 'modes': MODES, 'actor_steps': 600, 'critic_warmup': 300,
                'batch': 128, 'actor_lr': 3e-5, 'critic_lr': 3e-4, 'beta': 1.0, 'gamma': 1.0,
                'selection': 'fixed final step, no playing-strength model selection',
                'initial_sha256': sha(ROOT / 'checkpoints/ppo_v7.pt'),
                'dataset_status_sha256': sha(DATA / 'status.json'),
                'dataset_manifest_sha256': sha(DATA / 'manifest.json'),
                'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                                 text=True).strip(),
                'sources': {str(p.relative_to(ROOT)): sha(p) for p in sources},
                'evaluation': {'blocks': 128,
                               'pools': ['rule', 'tuned:checkpoints/rule_cem_v1.json'],
                               'deal_seed_start': 2026122000,
                               'baseline': 'BC with matching training seed',
                               'comparisons': ['iql05-bc', 'iql07-bc', 'bc-initial']},
                'limitations': ['matched actor updates, IQL has extra critic compute',
                                'initial actor may have seen source records',
                                'no public history in first offline prototype',
                                'three seeds, exploratory screen, no automatic promotion']}
        manifest = OUT / 'manifest.json'
        if manifest.exists():
            if json.loads(manifest.read_text()) != plan:
                raise ValueError('Source or plan changed; start a new experiment directory')
        else:
            write(manifest, plan)
            for source in sources:
                target = OUT / 'source' / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        data = load_data()
        for seed in SEEDS:
            for mode in MODES:
                train_one(seed, mode, plan, data)
        write(OUT / 'status.json', {'stage': 'complete', 'time': time.time()})


if __name__ == '__main__':
    main()
