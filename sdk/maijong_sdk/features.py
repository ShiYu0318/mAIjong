"""Observation → tensors (SPEC 05.2). Requires numpy (pip install maijong-sdk[rl]).

tiles: (34, 14) float32 channels
  0 own hand counts · 1 own melds · 2 own discards · 3-5 discards of next/opposite/previous
  6-8 melds of next/opposite/previous · 9 wall remaining (broadcast) · 10 never discarded
  11 effective tiles · 12 seat wind · 13 round wind
scalars: (13,) dealer streak, own score, 3 opponent scores, discards so far, own flower tai,
  is dealer, shanten, own ready flag, 3 opponent ready flags
"""

from __future__ import annotations

import numpy as np

from engine.actions import Action, encode_action
from engine.score import flower_items
from engine.shanten import shanten, shanten_after_discards, uke_ire
from maijong_sdk.types import Observation

N_CHANNELS = 14
N_SCALARS = 13
N_ACTIONS = 108
MAX_DRAWABLE = 64.0
SCORE_SCALE = 1000.0


def effective_tiles(counts: list[int], n_melds: int) -> tuple[int, list[int]]:
    """Shanten and effective tiles; for a 3n+2 hand, after the best discard."""
    if sum(counts) % 3 == 1:
        return shanten(counts, n_melds), uke_ire(counts, n_melds)
    after = shanten_after_discards(counts, n_melds)
    best = min(after, key=lambda t: (after[t], t))
    c = list(counts)
    c[best] -= 1
    return after[best], uke_ire(c, n_melds)


def encode(obs: Observation) -> tuple[np.ndarray, np.ndarray]:
    seat = obs.seat
    x = np.zeros((34, N_CHANNELS), dtype=np.float32)
    counts = [0] * 34
    for t in obs.hand:
        counts[t] += 1
    x[:, 0] = counts
    others = [(seat + k) % 4 for k in (1, 2, 3)]
    for m in obs.melds[seat]:
        for mt in m.tiles:
            if mt is not None:
                x[mt, 1] = 1.0
    seen = np.zeros(34, dtype=bool)
    for t in obs.discards[seat]:
        x[t, 2] = 1.0
        seen[t] = True
    for k, p in enumerate(others):
        for t in obs.discards[p]:
            x[t, 3 + k] = 1.0
            seen[t] = True
        for m in obs.melds[p]:
            for mt in m.tiles:
                if mt is not None:
                    x[mt, 6 + k] = 1.0
    x[:, 9] = max(0, obs.drawable) / MAX_DRAWABLE
    x[:, 10] = (~seen).astype(np.float32)
    sh, uke = effective_tiles(counts, len(obs.melds[seat]))
    for t in uke:
        x[t, 11] = 1.0
    x[27 + obs.seat_winds[seat], 12] = 1.0
    x[27 + obs.round_wind, 13] = 1.0

    s = np.zeros(N_SCALARS, dtype=np.float32)
    s[0] = obs.dealer_streak / 9.0
    s[1] = obs.scores[seat] / SCORE_SCALE
    for k, p in enumerate(others):
        s[2 + k] = obs.scores[p] / SCORE_SCALE
    s[5] = sum(len(d) for d in obs.discards) / 80.0
    s[6] = sum(i.tai for i in flower_items(obs.flowers[seat], obs.seat_winds[seat])) / 8.0
    s[7] = 1.0 if obs.dealer == seat else 0.0
    s[8] = max(-1, sh) / 8.0
    s[9] = 1.0 if obs.declared_ting[seat] else 0.0
    for k, p in enumerate(others):
        s[10 + k] = 1.0 if obs.declared_ting[p] else 0.0
    return x, s


def legal_mask(legal: list[Action]) -> np.ndarray:
    mask = np.zeros(N_ACTIONS, dtype=bool)
    for a in legal:
        mask[encode_action(a)] = True
    return mask
