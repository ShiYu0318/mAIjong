"""Frozen-margin fresh-game evaluation of final Huber/MSE counterfactual Q checkpoints."""
import fcntl
import hashlib
import json
import time
from pathlib import Path

import torch

from ai.training.block_evaluate import bootstrap_interval, play_block

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / 'runs/research-20261101/counterfactual-q-01'
OUT = ROOT / 'runs/research-20261101/counterfactual-q-eval-01'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def ready_model(kind, seed):
    stem = f'research-counterq01-{kind}-{seed}'
    result = TRAIN / (stem + '-result.json')
    if not result.exists():
        return None
    path = ROOT / 'checkpoints' / (stem + '.pt')
    if sha(path) != json.loads(result.read_text())['checkpoint_sha256']:
        raise ValueError('Completed model changed')
    return path


def main():
    torch.set_num_threads(1)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'runner.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()


def run():
    training = json.loads((TRAIN / 'manifest.json').read_text())
    cem, old = ROOT / 'checkpoints/rule_cem_v1.json', ROOT / 'checkpoints/rollq_all.pt'
    sources = [*sorted(ROOT.glob('ai/**/*.py')), *sorted(ROOT.glob('engine/**/*.py')),
               *sorted(ROOT.glob('sdk/maijong_sdk/*.py')), Path(__file__).resolve()]
    plan = {**training['evaluation'], 'seed': training['seed'],
            'training_manifest_sha256': sha(TRAIN / 'manifest.json'),
            'cem_sha256': sha(cem), 'old_sha256': sha(old),
            'sources': {str(path.relative_to(ROOT)): sha(path) for path in sources},
            'limitations': ['one seed; ten exploratory comparisons; no automatic promotion',
                            'fixed epoch/margin; no selection on test games']}
    manifest = OUT / 'manifest.json'
    if manifest.exists():
        if json.loads(manifest.read_text()) != plan:
            raise ValueError('Evaluation plan or sources changed')
    else:
        write(manifest, plan)
        for source in sources:
            target = OUT / 'source' / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    paths = {'huber': ready_model('huber', plan['seed']), 'mse': ready_model('mse', plan['seed']),
             'cem': cem, 'old': old}
    count = 0
    for comparison in plan['comparisons']:
        left, right = comparison.split('-')
        if paths[left] is None or paths[right] is None:
            continue
        def spec(name):
            return 'tuned:' + str(cem) if name == 'cem' \
                else 'rollq:' + str(paths[name]) + ',' + str(plan['margin'])
        candidate, baseline = spec(left), spec(right)
        hashes = [sha(paths[left]), sha(paths[right])]
        for pool, opponent in enumerate(plan['pools']):
            stem = f'{comparison}-pool{pool}'
            write(OUT / 'status.json', {'stage': 'evaluating', 'run': stem, 'time': time.time()})
            path = OUT / (stem + '.jsonl')
            rows = [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
            if len(rows) > plan['blocks']:
                raise ValueError('Too many saved blocks')
            cache = {}
            for k in range(plan['blocks']):
                seed = plan['deal_seed_start'] + pool * 100000 + k
                if k < len(rows):
                    if rows[k]['seed'] != seed or rows[k]['checkpoint_hashes'] != hashes:
                        raise ValueError('Saved block does not match fixed plan')
                    continue
                row = play_block(candidate, baseline, opponent, seed, cache)
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
