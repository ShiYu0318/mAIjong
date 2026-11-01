"""Audit feature aliasing and public decision strata in the actual offline shards."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/research-offline-01'


def decision_groups(tiles: np.ndarray, scalars: np.ndarray, masks: np.ndarray
                    ) -> dict[str, np.ndarray]:
    legal = masks.sum(1)
    discard = masks[:, :34].any(1)
    threat = (scalars[:, 10:13] >= 0.5).any(1)
    shanten = np.rint(scalars[:, 8] * 8)
    return {'all': np.ones(len(masks), dtype=bool), 'forced': legal == 1,
            'choice': legal > 1, 'discard_choice': discard & (legal > 1),
            'response_choice': ~discard & (legal > 1),
            'threatened_choice': threat & (legal > 1),
            'tenpai_choice': (shanten <= 0) & (legal > 1),
            'late_choice': (tiles[:, 0, 9] * 64 <= 16) & (legal > 1)}


def main():
    status = json.loads((DATA / 'status.json').read_text())
    if not status.get('complete'):
        raise ValueError('Dataset is incomplete')
    buckets = {}
    counts = {}
    examples = []
    for shard in status['shards']:
        path = DATA / shard['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != shard['sha256']:
            raise ValueError('Shard changed')
        with np.load(path, allow_pickle=False) as data:
            # NPZ entries decompress on access; materialize once per shard.
            tiles, scalars, masks = data['tiles'], data['scalars'], data['masks']
            seeds, seats, decisions = data['hand_seeds'], data['seats'], data['decision_index']
            groups = decision_groups(tiles, scalars, masks)
            for group, mask in groups.items():
                counts[group] = counts.get(group, 0) + int(mask.sum())
            for i in range(len(masks)):
                key = hashlib.sha256(tiles[i].tobytes() + scalars[i].tobytes()).digest()
                mask = np.packbits(masks[i]).tobytes()
                identity = [shard['path'], int(seeds[i]), int(seats[i]), int(decisions[i])]
                if key not in buckets:
                    buckets[key] = {'masks': {mask}, 'count': 1, 'first': identity}
                else:
                    bucket = buckets[key]
                    bucket['count'] += 1
                    if mask not in bucket['masks'] and len(examples) < 10:
                        examples.append({'first': bucket['first'], 'other': identity,
                                         'other_legal_actions': np.flatnonzero(
                                             masks[i]).tolist()})
                    bucket['masks'].add(mask)
    aliased = [b for b in buckets.values() if len(b['masks']) > 1]
    result = {'transitions': status['transitions'], 'group_counts': counts,
              'distinct_cnn_observations': len(buckets),
              'observations_with_multiple_legal_masks': len(aliased),
              'transitions_in_mask_aliased_buckets': sum(b['count'] for b in aliased),
              'examples': examples,
              'note': 'Equal features with differing masks prove omitted public context; '
                      'the absence of exact collisions does not prove a Markov observation.'}
    out = ROOT / 'runs/research-20261101/offline-observation-audit.json'
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
