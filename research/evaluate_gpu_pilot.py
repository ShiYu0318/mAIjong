"""Independent, resumable four-seat block evaluation of completed larger-data GPU actors."""
import fcntl
import hashlib
import json
import time
from pathlib import Path

import torch

from ai.training.block_evaluate import bootstrap_interval, play_block

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / 'runs/research-20261101/gpu-offline-pilot-01'
OUT = ROOT / 'runs/research-20261101/gpu-offline-eval-01'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def completed(mode, seed):
    name = f'research-gpuoffline01-{mode}-{seed}'
    result = TRAIN / (name + '-result.json')
    if not result.exists():
        return None
    path = ROOT / 'checkpoints' / (name + '.pt')
    if sha(path) != json.loads(result.read_text())['checkpoint_sha256']:
        raise ValueError('Completed actor checkpoint changed')
    return path


def main():
    torch.set_num_threads(2)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'runner.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()


def run():
    training = json.loads((TRAIN / 'manifest.json').read_text())
    initial = ROOT / 'checkpoints/ppo_v7.pt'
    if sha(initial) != training['initial_sha256']:
        raise ValueError('Initial baseline changed')
    sources = [*sorted(ROOT.glob('ai/**/*.py')), *sorted(ROOT.glob('engine/**/*.py')),
               *sorted(ROOT.glob('sdk/maijong_sdk/*.py')), Path(__file__).resolve()]
    plan = {**training['evaluation'], 'seed': training['seed'],
            'initial_sha256': sha(initial),
            'training_manifest_sha256': sha(TRAIN / 'manifest.json'),
            'cem_sha256': sha(ROOT / 'checkpoints/rule_cem_v1.json'),
            'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sources}}
    manifest = OUT / 'manifest.json'
    if manifest.exists():
        if json.loads(manifest.read_text()) != plan:
            raise ValueError('Evaluation source or plan changed')
    else:
        write(manifest, plan)
        for source in sources:
            target = OUT / 'source' / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    count = 0
    for comparison in plan['comparisons']:
        left, right = comparison.split('-')
        candidate = completed(left, plan['seed'])
        baseline = initial if right == 'initial' else completed(right, plan['seed'])
        if candidate is None or baseline is None:
            continue
        hashes = [sha(candidate), sha(baseline)]
        for pool, opponent in enumerate(plan['pools']):
            stem = f'{comparison}-pool{pool}'
            write(OUT / 'status.json', {'stage': 'evaluating', 'run': stem, 'time': time.time()})
            path = OUT / (stem + '.jsonl')
            rows = [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
            if len(rows) > plan['blocks']:
                raise ValueError('Too many evaluation rows')
            cache = {}
            for k in range(plan['blocks']):
                seed = plan['deal_seed_start'] + pool * 100000 + k
                if k < len(rows):
                    if rows[k]['seed'] != seed or rows[k]['checkpoint_hashes'] != hashes:
                        raise ValueError('Saved evaluation block mismatch')
                    continue
                row = play_block('ppo:' + str(candidate), 'ppo:' + str(baseline),
                                 opponent, seed, cache)
                row['checkpoint_hashes'] = hashes
                with path.open('a') as stream:
                    stream.write(json.dumps(row) + '\n')
                rows.append(row)
            means = [row['mean_difference'] for row in rows]
            summary = {'comparison': comparison, 'opponent': opponent, 'blocks': len(rows),
                       'mean_difference': sum(means) / len(means),
                       'bootstrap_ci95': bootstrap_interval(means, seed=823),
                       'checkpoint_hashes': hashes}
            write(OUT / (stem + '-summary.json'), summary)
            print(json.dumps(summary), flush=True)
            count += 1
    expected = len(plan['comparisons']) * len(plan['pools'])
    write(OUT / 'status.json', {'stage': 'complete' if count == expected else 'partial',
                               'evaluated': count, 'expected': expected, 'time': time.time()})


if __name__ == '__main__':
    main()
