"""Frozen existing checkpoint cohort, compared directly with CEM on new paired deals."""
import fcntl
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

import torch

from ai.agents import LEVEL5_PARAMS
from ai.agents.rule_agent import RuleParams
from ai.training.block_evaluate import bootstrap_interval, play_block

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/research-20261101/archived-candidate-screen-01'
CANDIDATES = {'ppo_v7': 'ppo:checkpoints/ppo_v7.pt',
              'rollq_v1': 'rollq:checkpoints/rollq_v1.pt,3',
              'rollq_v12': 'rollq:checkpoints/rollq_v12.pt,3',
              'rollq_all': 'rollq:checkpoints/rollq_all.pt,3'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def main():
    torch.set_num_threads(1)  # Rollout-Q's cached CPU loader also uses one thread.
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'runner.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()


def run():
    cem_path = ROOT / 'checkpoints/rule_cem_v1.json'
    cem = RuleParams(**json.loads(cem_path.read_text())['params'])
    if asdict(cem) != asdict(LEVEL5_PARAMS):
        raise ValueError('Rollout-Q teacher differs from CEM; revise comparison interpretation')
    sources = [*sorted(ROOT.glob('ai/**/*.py')), *sorted(ROOT.glob('engine/**/*.py')),
               *sorted(ROOT.glob('sdk/maijong_sdk/*.py')), Path(__file__).resolve()]
    plan = {'candidates': CANDIDATES, 'baseline': 'tuned:checkpoints/rule_cem_v1.json',
            'pools': ['rule', 'tuned:checkpoints/rule_cem_v1.json'], 'blocks': 128,
            'deal_seed_start': 2026135000, 'bootstrap_seed': 823, 'threads': 1,
            'candidate_sha256': {name: sha(ROOT / spec.split(':', 1)[1].split(',')[0])
                                 for name, spec in CANDIDATES.items()},
            'cem_sha256': sha(cem_path), 'current_teacher_equals_cem': True,
            'sources': {str(p.relative_to(ROOT)): sha(p) for p in sources},
            'limitations': ['eight exploratory comparisons, no automatic promotion',
                            'fixed existing models and margin=3; no test-deal tuning',
                            'archived training teacher provenance is not available',
                            'intervals cover deal variation, not training-seed variation']}
    manifest = OUT / 'manifest.json'
    if manifest.exists():
        if json.loads(manifest.read_text()) != plan:
            raise ValueError('Frozen plan, checkpoints or sources changed')
    else:
        write(manifest, plan)
        for source in sources:
            target = OUT / 'source' / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    for name, spec in plan['candidates'].items():
        hashes = [plan['candidate_sha256'][name], plan['cem_sha256']]
        for pool, opponent in enumerate(plan['pools']):
            stem = f'{name}-pool{pool}'
            write(OUT / 'status.json', {'stage': 'evaluating', 'run': stem, 'time': time.time()})
            path = OUT / (stem + '.jsonl')
            rows = [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
            if len(rows) > plan['blocks']:
                raise ValueError('Saved rows exceed fixed sample size')
            cache = {}
            for k in range(plan['blocks']):
                seed = plan['deal_seed_start'] + pool * 100000 + k
                if k < len(rows):
                    if rows[k]['seed'] != seed or rows[k]['checkpoint_hashes'] != hashes:
                        raise ValueError('Saved block provenance mismatch')
                    continue
                row = play_block(spec, plan['baseline'], opponent, seed, cache)
                row['checkpoint_hashes'] = hashes
                with path.open('a') as stream:
                    stream.write(json.dumps(row) + '\n')
                rows.append(row)
            means = [row['mean_difference'] for row in rows]
            pairs = [pair for row in rows for pair in row['pairs']]
            summary = {'candidate': name, 'baseline': 'cem', 'opponent': opponent,
                       'blocks': len(rows), 'mean_difference': sum(means) / len(means),
                       'bootstrap_ci95': bootstrap_interval(means, seed=823),
                       'win_rate_difference': sum(a['win'] - b['win'] for a, b in pairs)
                           / len(pairs),
                       'deal_in_difference': sum(a['deal_in'] - b['deal_in'] for a, b in pairs)
                           / len(pairs), 'checkpoint_hashes': hashes}
            write(OUT / (stem + '-summary.json'), summary)
            print(json.dumps(summary), flush=True)
    write(OUT / 'status.json', {'stage': 'complete', 'time': time.time()})


if __name__ == '__main__':
    main()
