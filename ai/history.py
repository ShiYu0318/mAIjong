"""Whitelisted, per-seat visible event history for recurrent policy experiments.

Never pass raw engine event dictionaries to a model: DEAL, private DRAW and
concealed-KONG actions contain information unavailable to the acting player.
"""
from __future__ import annotations

import numpy as np
import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence

from engine.game import GameState

EVENTS = {name: i + 1 for i, name in enumerate(
    ['DRAW', 'DISCARD', 'TING', 'PON', 'CHI', 'KONG', 'FLOWER', 'FLOWER_ROB', 'PASS'])}
KINDS = {name: i + 1 for i, name in enumerate(['AN_KONG', 'MING_KONG', 'ADD_KONG'])}
SOURCES = {name: i + 1 for i, name in enumerate(['WALL', 'FLOWER', 'KONG', 'MING_KONG'])}


def encode_public_history(state: GameState, seat: int, limit: int = 128
                          ) -> tuple[np.ndarray, np.ndarray]:
    """Return right-padded (limit, 5) tokens and boolean validity mask.

    Columns: event type, relative player+1, visible tile+1, kong kind, draw source.
    Zero means unknown/padding. Terminal result fields are deliberately excluded.
    """
    if seat not in range(4) or limit < 1:
        raise ValueError('seat must be 0..3 and limit must be positive')
    rows = []
    for event in state.events:
        kind = event.get('type')
        if kind not in EVENTS:
            continue
        player = event.get('player')
        tile = event.get('tile')
        concealed = kind == 'KONG' and event.get('kind') == 'AN_KONG'
        hidden = player != seat and (kind == 'DRAW' or concealed or event.get('private'))
        tile_id = 0 if hidden or tile is None else int(tile) + 1
        rows.append([EVENTS[kind], 0 if player is None else (int(player) - seat) % 4 + 1,
                     tile_id, KINDS.get(event.get('kind'), 0),
                     SOURCES.get(event.get('source'), 0)])
    rows = rows[-limit:]
    tokens = np.zeros((limit, 5), dtype=np.int64)
    mask = np.zeros(limit, dtype=bool)
    if rows:
        tokens[:len(rows)] = rows
        mask[:len(rows)] = True
    return tokens, mask


class HistoryEncoder(nn.Module):
    """Bounded ordered history, re-encoded per decision without persistent hidden state."""

    def __init__(self, latent: int = 256) -> None:
        super().__init__()
        self.embeddings = nn.ModuleList([
            nn.Embedding(len(EVENTS) + 1, 16, padding_idx=0),
            nn.Embedding(5, 8, padding_idx=0),
            nn.Embedding(43, 24, padding_idx=0),
            nn.Embedding(len(KINDS) + 1, 8, padding_idx=0),
            nn.Embedding(len(SOURCES) + 1, 8, padding_idx=0),
        ])
        self.gru = nn.GRU(64, 128, batch_first=True)
        self.output = nn.Linear(128, latent)

    def forward(self, tokens: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        features = torch.cat([embed(tokens[:, :, k])
                              for k, embed in enumerate(self.embeddings)], dim=-1)
        lengths = mask.sum(dim=1)
        packed = pack_padded_sequence(features, lengths.clamp_min(1).cpu(),
                                      batch_first=True, enforce_sorted=False)
        _, hidden = self.gru(packed)
        latent = self.output(hidden[-1])
        return latent * (lengths > 0).unsqueeze(-1)
