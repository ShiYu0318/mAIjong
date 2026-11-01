"""Larger-data MPS pilot: BC versus TD-IQL versus MC-initialized IQL, fixed final models."""
import fcntl
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch

from ai.agents.neural_agent import load_model, save_checkpoint
from research.critic_warmstart_pilot import load_with_returns
from research.iql import IQLLearner
from research.mc_pretrain import warm_start_critics
from research.offline_device import move_learner
from research.train_iql_ablation import take

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/research-20261101/gpu-offline-pilot-01'
DATA = ROOT / 'data/research-offline-02'
SEED = 20261111


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def train(mode, plan, data):
    name = f'research-gpuoffline01-{mode}-{SEED}'
    output = ROOT / 'checkpoints' / (name + '.pt')
    result = OUT / (name + '-result.json')
    if result.exists():
        if sha(output) != json.loads(result.read_text())['checkpoint_sha256']:
            raise ValueError('Completed checkpoint changed')
        return
    write(OUT / 'status.json', {'stage': 'training', 'mode': mode, 'time': time.time()})
    torch.manual_seed(SEED)
    actor, _ = load_model(ROOT / 'checkpoints/ppo_v7.pt')
    actor_rng = np.random.default_rng(SEED)
    warm_rng = np.random.default_rng(SEED + 100000)
    start = time.time()
    with (OUT / (name + '-metrics.jsonl')).open('w') as stream:
        def record(phase, stats):
            row = {'phase': phase, 'seconds': time.time() - start, **stats}
            stream.write(json.dumps(row) + '\n')
            stream.flush()
            print(mode, json.dumps(row), flush=True)
        if mode == 'bc':
            learner = None
            actor.to('mps').train()
            reference, _ = load_model(ROOT / 'checkpoints/ppo_v7.pt')
            reference.to('mps').eval().requires_grad_(False)
            optimizer = torch.optim.Adam(actor.parameters(), lr=plan['actor_lr'])
        else:
            learner = move_learner(IQLLearner(actor, tau=0.7, beta=3.0, gamma=1.0), 'mps')
            if mode == 'mc':
                warm_start_critics(learner, data['train'], updates=plan['critic_warmup'],
                                  batch_size=plan['batch'], seed=SEED + 100000,
                                  log=lambda stats: record('warmup', stats))
            else:
                for step in range(1, plan['critic_warmup'] + 1):
                    stats = learner.update(take(data['train'], warm_rng, plan['batch']), False)
                    if step % 100 == 0:
                        record('warmup', {'step': step, **stats})
            for key in ['q1', 'q2']:
                target = getattr(learner, key + '_target')
                target.load_state_dict(getattr(learner, key).state_dict())
            # Both initializers enter actor training with fresh critic optimizer moments.
            learner.q_opt = torch.optim.Adam([*learner.q1.parameters(), *learner.q2.parameters()],
                                              lr=plan['critic_lr'])
            learner.v_opt = torch.optim.Adam(learner.value.parameters(), lr=plan['critic_lr'])
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
            if step % 100 == 0:
                record('actor', {'step': step, **stats})
        training_state_hash = None
        if learner is None:
            save_checkpoint(output, actor, 'ppo', {'hierarchical': actor.hierarchical},
                            training_method='bc', device='mps', actor_steps=plan['actor_steps'])
            diagnostics = {}
        else:
            learner.save_actor(output, seed=SEED, critic_init=mode, device='mps', beta=3.0,
                               actor_steps=plan['actor_steps'])
            validation = take(data['validation'], np.random.default_rng(711), 4096)
            # Bound memory during validation forward passes.
            pieces = [{key: value[i:i + 128] for key, value in validation.items()}
                      for i in range(0, 4096, 128)]
            measured = [learner.diagnostics(piece) for piece in pieces]
            diagnostics = {}
            for key in set().union(*(piece.keys() for piece in measured)):
                counts = [int(piece['done'].sum()) if key == 'terminal_td_rmse'
                          else int((~piece['done']).sum()) if key == 'nonterminal_td_rmse'
                          else len(piece['done']) for piece in pieces]
                powers = 2 if key.endswith('_td_rmse') else 1
                total = sum(m[key] ** powers * n for m, n in zip(measured, counts, strict=True)
                            if key in m)
                diagnostics[key] = float((total / sum(counts)) ** (1 / powers))
            state = {key: getattr(learner, key).state_dict() for key in
                     ['actor', 'q1', 'q2', 'q1_target', 'q2_target', 'value',
                      'actor_opt', 'q_opt', 'v_opt']}
            state_path = OUT / (name + '-training-state.pt')
            torch.save({**state, 'plan': plan, 'actor_rng': actor_rng.bit_generator.state,
                        'torch_rng': torch.get_rng_state()}, state_path)
            training_state_hash = sha(state_path)
        write(result, {'checkpoint_sha256': sha(output), 'diagnostics': diagnostics,
                       'training_state_sha256': training_state_hash,
                       'seconds': time.time() - start})


def main():
    if not torch.backends.mps.is_available():
        raise ValueError('MPS is required; do not silently change this experiment device')
    torch.set_num_threads(2)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'runner.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        status = json.loads((DATA / 'status.json').read_text())
        if not status.get('complete'):
            raise ValueError('Dataset is not complete; wait for conversion before launching')
        sources = [*sorted(ROOT.glob('ai/**/*.py')), *sorted(ROOT.glob('engine/**/*.py')),
                   *[ROOT / 'research' / name for name in ['iql.py', 'offline_device.py',
                     'mc_pretrain.py', 'critic_warmstart_pilot.py', 'train_iql_ablation.py']],
                   Path(__file__).resolve()]
        plan = {'seed': SEED, 'device': 'mps', 'torch': torch.__version__,
                'modes': ['bc', 'td', 'mc'], 'actor_steps': 3000, 'critic_warmup': 3000,
                'batch': 256, 'beta': 3.0, 'tau': 0.7, 'gamma': 1.0,
                'actor_lr': 3e-5, 'critic_lr': 3e-4, 'hands': status['hands'],
                'initial_sha256': sha(ROOT / 'checkpoints/ppo_v7.pt'),
                'dataset_manifest_sha256': sha(DATA / 'manifest.json'),
                'dataset_status_sha256': sha(DATA / 'status.json'),
                'sources': {str(p.relative_to(ROOT)): sha(p) for p in sources},
                'evaluation': {'blocks': 128, 'deal_seed_start': 2026130000,
                               'pools': ['rule', 'tuned:checkpoints/rule_cem_v1.json'],
                               'comparisons': ['bc-initial', 'td-bc', 'mc-bc', 'mc-td']},
                'limitations': ['single-seed exploratory pilot, no SOTA claim',
                                'larger data/budget/backend than first IQL screen',
                                'both critic optimizers reset and both targets refreshed',
                                'fixed final checkpoint, no promotion or test-based selection']}
        manifest = OUT / 'manifest.json'
        if manifest.exists():
            if json.loads(manifest.read_text()) != plan:
                raise ValueError('Plan or sources changed; use a new experiment directory')
        else:
            write(manifest, plan)
            for source in sources:
                target = OUT / 'source' / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        data = {fold: {key: tensor.to('mps') for key, tensor in fields.items()}
                for fold, fields in load_with_returns(DATA).items()}
        for mode in plan['modes']:
            train(mode, plan, data)
        write(OUT / 'status.json', {'stage': 'complete', 'time': time.time()})


if __name__ == '__main__':
    main()
