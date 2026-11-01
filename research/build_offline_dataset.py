"""Build a small, audited offline dataset from local recorded games."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

from ai.simulate import read_records
from research.offline_data import fold_for_seed, transitions_from_record

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/research-offline-01'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(out: Path = OUT, hands_per_source: int = 512, hands_per_shard: int = 128):
    if hands_per_source < 1 or hands_per_shard < 1:
        raise ValueError('Positive hand and shard sizes required')
    out.mkdir(parents=True, exist_ok=False)
    sources = [ROOT / 'data/bc/rule_100k.jsonl.gz', ROOT / 'data/bc/lv5_100k.jsonl.gz']
    code = [Path(__file__).resolve(), ROOT / 'research/offline_data.py', ROOT / 'ai/features.py',
            ROOT / 'ai/history.py', ROOT / 'sdk/maijong_sdk/features.py',
            ROOT / 'sdk/maijong_sdk/types.py', *sorted(ROOT.glob('engine/*.py'))]
    plan = {'hands_per_source': hands_per_source, 'hands_per_shard': hands_per_shard,
            'history_length': 0,
            'gamma': 1.0, 'payment_scale': 0.005, 'keep_forced_actions': True,
            'fold': 'sha256 of hand seed; train80/validation10/test10; all seats stay together',
            'sources': {str(p.relative_to(ROOT)): sha(p) for p in sources},
            'code': {str(p.relative_to(ROOT)): sha(p) for p in code},
            'limitations': ['existing PPO initialization may have seen these source games',
                            'fold test is a critic diagnostic, not independent playing strength',
                            'opponent mixture is not a stationary universal Mahjong MDP',
                            'no-history observation aliases hidden beliefs and public timing']}
    (out / 'manifest.json').write_text(json.dumps(plan, indent=2))
    for source in code:
        target = out / 'source' / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    stats = {'hands': 0, 'transitions': 0, 'shards': [], 'fold_hands': {}, 'terminal': 0}
    for source_id, source in enumerate(sources):
        source_hands = 0
        records = iter(itertools.islice(read_records(source), plan['hands_per_source']))
        for shard_id in itertools.count():
            chunk = list(itertools.islice(records, plan['hands_per_shard']))
            if not chunk:
                break
            folds = {fold: [] for fold in ['train', 'validation', 'test']}
            for record in chunk:
                fold = fold_for_seed(int(record['seed']))
                folds[fold].append(transitions_from_record(record))
                stats['hands'] += 1
                source_hands += 1
                stats['fold_hands'][fold] = stats['fold_hands'].get(fold, 0) + 1
            for fold, parts in folds.items():
                if not parts:
                    continue
                data = {key: np.concatenate([part[key] for part in parts]) for key in parts[0]}
                path = out / f'{fold}-source{source_id}-shard{shard_id:03d}.npz'
                np.savez_compressed(path, **data)
                stats['transitions'] += len(data['actions'])
                stats['terminal'] += int(data['done'].sum())
                stats['shards'].append({'path': path.name, 'sha256': sha(path),
                                        'transitions': len(data['actions']), 'fold': fold})
            temporary = out / 'status.json.tmp'
            temporary.write_text(json.dumps(stats, indent=2))
            temporary.replace(out / 'status.json')
            print(json.dumps({k: v for k, v in stats.items() if k != 'shards'}), flush=True)
        if source_hands != hands_per_source:
            raise ValueError('Source ended before the requested hand budget')
    stats['complete'] = True
    temporary = out / 'status.json.tmp'
    temporary.write_text(json.dumps(stats, indent=2))
    temporary.replace(out / 'status.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--hands', type=int, default=512, help='hands per source')
    parser.add_argument('--chunk', type=int, default=128)
    args = parser.parse_args()
    main((ROOT / args.out).resolve(), args.hands, args.chunk)
