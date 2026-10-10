"""Observation encoding (SPEC 05.2), shared with the public SDK so models trained on
either side see identical inputs."""

from __future__ import annotations

import numpy as np
from maijong_sdk.features import N_CHANNELS, N_SCALARS, effective_tiles
from maijong_sdk.features import encode as encode_observation
from maijong_sdk.features import legal_mask as _legal_mask
from maijong_sdk.types import observe

from engine.game import GameState, get_legal_actions

_effective_tiles = effective_tiles

__all__ = ["N_CHANNELS", "N_SCALARS", "encode", "mask_for"]


def encode(state: GameState, seat: int) -> tuple[np.ndarray, np.ndarray]:
    return encode_observation(observe(state, seat))


def mask_for(state: GameState, seat: int) -> np.ndarray:
    return _legal_mask(get_legal_actions(state, seat))
