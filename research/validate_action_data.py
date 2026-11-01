"""Replay every visible-v2 sample and regenerate one rollout target per teacher-action type."""
import hashlib
import json
from pathlib import Path

import numpy as np

from ai.features import encode, mask_for
from ai.history import encode_public_history
from engine.actions import decode_action
from engine.game import Phase, apply_action, new_game
from research.action_counterfactuals import label_actions
from research.offline_data import fold_for_seed

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/research-action-q-v2-pilot-01'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((DATA / 'manifest.json').read_text())
    status = json.loads((DATA / 'status.json').read_text())
    valid_contract = manifest['information_contract'].startswith('visible-v2')
    if status['stage'] != 'complete' or not valid_contract:
        raise ValueError('Completed visible-v2 data required')
    for name, expected in manifest['sources'].items():
        if sha(DATA / 'source' / name) != expected:
            raise ValueError('Archived source hash changed')
        runtime_dependency = name.startswith(('ai/', 'engine/', 'sdk/', 'backend/')) \
            or name == 'research/action_counterfactuals.py'
        if runtime_dependency and sha(ROOT / name) != expected:
            raise ValueError('Runtime changed; validate with the archived runtime instead')
    checked, regenerated, folds = 0, {}, {}
    for item in status['files']:
        seed = item['seed']
        correct_record = sha(DATA / item['record']) == item['record_sha256']
        if item['fold'] != fold_for_seed(seed) or not correct_record:
            raise ValueError('Record or grouped fold mismatch')
        record = json.loads((DATA / item['record']).read_text())
        if item['samples']:
            if sha(DATA / item['path']) != item['sha256']:
                raise ValueError('Shard hash changed')
            with np.load(DATA / item['path'], allow_pickle=False) as archive:
                data = {key: archive[key] for key in archive.files}
            if len(data['q']) != item['samples']:
                raise ValueError('Sample count mismatch')
            row_at = {int(index): row for row, index in enumerate(data['action_index'])}
            if len(row_at) != item['samples']:
                raise ValueError('Duplicate sample pointer')
        else:
            row_at = {}
        state = new_game(seed=seed)
        for index, (seat, aid) in enumerate(record['actions']):
            if index in row_at:
                row = row_at[index]
                if int(data['seat'][row]) != seat or int(data['teacher_action'][row]) != aid:
                    raise ValueError('Teacher action or actor mismatch')
                tiles, scalars = encode(state, seat)
                history, history_mask = encode_public_history(
                    state, seat, manifest['history_length'])
                expected = {'tiles': tiles.astype(np.float16),
                            'scalars': scalars.astype(np.float16),
                            'history': history, 'history_mask': history_mask,
                            'legal_mask': mask_for(state, seat)}
                for key, value in expected.items():
                    np.testing.assert_array_equal(data[key][row], value)
                mask, samples = data['candidate_mask'][row], data['world_payments'][row]
                if not mask[aid] or (mask & ~data['legal_mask'][row]).any():
                    raise ValueError('Candidate legality mismatch')
                np.testing.assert_allclose(data['q'][row, mask], samples[:, mask].mean(0))
                action = decode_action(aid)
                if action.type.value not in regenerated:
                    actions = [action] + [decode_action(int(a))
                                          for a in np.flatnonzero(mask) if a != aid]
                    q, se, worlds = label_actions(state, seat, actions,
                                                  seed=seed * 10000 + index,
                                                  worlds=manifest['worlds'])
                    np.testing.assert_allclose(q, data['q'][row], equal_nan=True)
                    np.testing.assert_allclose(se, data['paired_wall_se'][row], equal_nan=True)
                    np.testing.assert_array_equal(worlds, samples)
                    regenerated[action.type.value] = {'seed': seed, 'action_index': index}
                checked += 1
            state, _ = apply_action(state, seat, decode_action(aid))
        # JSON represents tai_by_payer keys as strings; compare canonical JSON.
        same_result = json.dumps(state.result, sort_keys=True) \
            == json.dumps(record['result'], sort_keys=True)
        if state.phase is not Phase.ENDED or not same_result:
            raise ValueError('Replayed terminal result mismatch')
        folds[item['fold']] = folds.get(item['fold'], 0) + 1
    if checked != status['samples']:
        raise ValueError('Total sample count mismatch')
    result = {'information_contract': manifest['information_contract'], 'hands': status['hands'],
              'samples_checked': checked, 'fold_hands': folds, 'regenerated_types': regenerated,
              'manifest_sha256': sha(DATA / 'manifest.json'),
              'status_sha256': sha(DATA / 'status.json')}
    (DATA / 'validation.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
