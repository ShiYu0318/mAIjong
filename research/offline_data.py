"""Replay engine-verified records into per-seat offline transitions; local research API."""
from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from ai.features import encode, mask_for
from ai.history import encode_public_history
from engine.actions import decode_action
from engine.game import Phase, acting_players, apply_action, new_game


def fold_for_seed(seed: int) -> str:
    """Keep the same shuffled wall in one fold across all seats and source files."""
    bucket = int.from_bytes(hashlib.sha256(f'maijong-offline-v1:{seed}'.encode()).digest()[:8],
                            'big') % 100
    return 'test' if bucket < 10 else 'validation' if bucket < 20 else 'train'


def _observation(state, seat, history_length):
    tiles, scalars = encode(state, seat)
    observation = {'tiles': tiles, 'scalars': scalars, 'masks': mask_for(state, seat)}
    if history_length:
        history, mask = encode_public_history(state, seat, history_length)
        observation.update(history=history, history_mask=mask)
    return observation


def transitions_from_record(record: dict[str, Any], history_length: int = 0
                            ) -> dict[str, np.ndarray]:
    """One step ends at the same seat's next decision or the actual hand terminal.

    All decisions, including forced actions, are kept. Rewards are only scaled
    terminal payments. Public observations contain no engine result fields.
    Incomplete hands are rejected, never treated as terminal zero-reward samples.
    """
    if history_length < 0:
        raise ValueError('history_length must be nonnegative')
    state = new_game(seed=int(record['seed']))
    rows = []
    pending = {}
    decisions = [0] * 4
    for seat, action in record['actions']:
        if state.phase is Phase.ENDED or seat not in acting_players(state):
            raise ValueError('Record action is out of turn or occurs after terminal')
        obs = _observation(state, seat, history_length)
        if action < 0 or action >= len(obs['masks']) or not obs['masks'][action]:
            raise ValueError('Record contains illegal action')
        if seat in pending:
            rows[pending[seat]].update({'next_' + k: v for k, v in obs.items()})
        pending[seat] = len(rows)
        rows.append({**obs, 'actions': int(action), 'seats': seat,
                     'hand_seeds': int(record['seed']), 'decision_index': decisions[seat],
                     'rewards': 0.0, 'done': False})
        decisions[seat] += 1
        state, _ = apply_action(state, seat, decode_action(action))
    if state.phase is not Phase.ENDED or state.result is None:
        raise ValueError('Incomplete hand: terminal payment is unknown')
    if list(record.get('result', {}).get('payments', [])) != list(state.result['payments']):
        raise ValueError('Recorded payments do not match replayed engine payments')
    for seat, index in pending.items():
        row = rows[index]
        row['done'] = True
        row['rewards'] = float(state.result['payments'][seat]) * 0.005
        for key in ('tiles', 'scalars', 'masks', 'history', 'history_mask'):
            if key in row:
                row['next_' + key] = np.zeros_like(row[key])
    if not rows:
        raise ValueError('Hand has no player decisions')
    data = {key: np.stack([row[key] for row in rows]) for key in rows[0]}
    data['rewards'] = data['rewards'].astype(np.float32)
    return data
