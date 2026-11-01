"""Fixed-size, higher-precision PPO-v7 versus CEM confirmation on fresh deal blocks."""
import fcntl
import hashlib
import json
import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import torch

from ai.training.block_evaluate import bootstrap_interval, play_block

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/research-20261101/pretrained-confirmation-visible-v2'
_CACHE = {}


def _initialize():
    global _CACHE
    _CACHE = {}
    torch.set_num_threads(1)


def _block(task):
    candidate, baseline, opponent, seed = task
    return play_block(candidate, baseline, opponent, seed, cache=_CACHE)


def parallel_blocks(candidate, baseline, opponent, seeds, workers=2):
    if workers < 1:
        raise ValueError('workers must be positive')
    tasks = ((candidate, baseline, opponent, seed) for seed in seeds)
    if workers == 1:
        _initialize()
        yield from map(_block, tasks)
    else:
        with ProcessPoolExecutor(max_workers=workers, initializer=_initialize,
                                 mp_context=multiprocessing.get_context('spawn')) as pool:
            yield from pool.map(_block, tasks, chunksize=8)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'runner.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()


def run():
    sources = [*sorted(ROOT.glob('ai/**/*.py')), *sorted(ROOT.glob('engine/**/*.py')),
               *sorted(ROOT.glob('sdk/maijong_sdk/*.py')), ROOT / 'backend/ws/view.py',
               Path(__file__).resolve()]
    hashes = [sha(ROOT / 'checkpoints/ppo_v7.pt'), sha(ROOT / 'checkpoints/rule_cem_v1.json')]
    plan = {'information_contract': 'visible-v2-ignore-opponent-concealed-kong-identities',
            'candidate': 'ppo:checkpoints/ppo_v7.pt',
            'baseline': 'tuned:checkpoints/rule_cem_v1.json',
            'pools': ['rule', 'tuned:checkpoints/rule_cem_v1.json'],
            'blocks_per_pool': 4096, 'deal_seed_start': 2026160000, 'workers': 2,
            'worker_torch_threads': 1, 'torch': torch.__version__,
            'checkpoint_hashes': hashes, 'bootstrap_seed': 823, 'bootstrap_resamples': 5000,
            'sources': {str(path.relative_to(ROOT)): sha(path) for path in sources},
            'decision': 'Fixed-model local improvement requires positive intervals in both pools',
            'limitations': ['selected existing candidate after exploratory screening',
                            'CEM parameters were historically tuned before the visibility fix',
                            'new unused deals, fixed sample size, no early significance stopping',
                            'fixed trained policy only, not unseen training-seed performance',
                            'local pools only, not a global SOTA benchmark',
                            'report both pools regardless of sign; no automatic promotion']}
    manifest = OUT / 'manifest.json'
    if manifest.exists():
        if json.loads(manifest.read_text()) != plan:
            raise ValueError('Confirmation plan, models or sources changed')
    else:
        write(manifest, plan)
        for source in sources:
            target = OUT / 'source' / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    for pool_id, opponent in enumerate(plan['pools']):
        path = OUT / f'pool{pool_id}.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        if len(rows) > plan['blocks_per_pool']:
            raise ValueError('Too many saved confirmation blocks')
        start = plan['deal_seed_start'] + pool_id * 100000
        for k, row in enumerate(rows):
            if row['seed'] != start + k or row['checkpoint_hashes'] != hashes:
                raise ValueError('Saved confirmation provenance mismatch')
        seeds = range(start + len(rows), start + plan['blocks_per_pool'])
        for row in parallel_blocks(plan['candidate'], plan['baseline'], opponent, seeds,
                                    workers=plan['workers']):
            row['checkpoint_hashes'] = hashes
            with path.open('a') as stream:
                stream.write(json.dumps(row) + '\n')
            rows.append(row)
            if len(rows) % 64 == 0:
                write(OUT / 'status.json', {'stage': 'evaluating', 'pool': pool_id,
                                            'blocks': len(rows), 'time': time.time()})
                print(json.dumps({'pool': pool_id, 'blocks': len(rows)}), flush=True)
        means = [row['mean_difference'] for row in rows]
        summary = {'opponent': opponent, 'blocks': len(rows),
                   'mean_difference': sum(means) / len(means),
                   'bootstrap_ci95': bootstrap_interval(means, seed=823, resamples=5000),
                   'checkpoint_hashes': hashes}
        write(OUT / f'pool{pool_id}-summary.json', summary)
        print(json.dumps(summary), flush=True)
    write(OUT / 'status.json', {'stage': 'complete', 'time': time.time()})


if __name__ == '__main__':
    main()
