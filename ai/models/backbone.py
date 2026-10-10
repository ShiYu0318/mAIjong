"""Shared encoder (SPEC 05.5.1): tile tensor (+ scalars) → 256-d latent."""

from __future__ import annotations

import torch
from torch import nn

from ai.features import N_CHANNELS, N_SCALARS

LATENT = 256


class MahjongEncoder(nn.Module):
    """Input tiles (B, 34, 14) as produced by ai.features, scalars (B, 13)."""

    def __init__(self, use_transformer: bool = False, latent: int = LATENT) -> None:
        super().__init__()
        self.use_transformer = use_transformer
        if use_transformer:
            self.proj = nn.Linear(N_CHANNELS, 64)
            self.pos_emb = nn.Parameter(torch.zeros(34, 64))
            layer = nn.TransformerEncoderLayer(d_model=64, nhead=4, dim_feedforward=256,
                                               batch_first=True, dropout=0.0)
            self.tf = nn.TransformerEncoder(layer, num_layers=4)
            self.out = nn.Linear(64, latent)
        else:
            self.cnn = nn.Sequential(
                nn.Conv1d(N_CHANNELS, 64, kernel_size=3, padding=1), nn.ReLU(),
                nn.Conv1d(64, 128, kernel_size=3, padding=1), nn.ReLU(),
                nn.Conv1d(128, 128, kernel_size=3, padding=1), nn.ReLU(),
            )
            self.out = nn.Linear(128 * 34, latent)
        self.fuse = nn.Sequential(nn.Linear(latent + N_SCALARS, latent), nn.ReLU())

    def forward(self, tiles: torch.Tensor, scalars: torch.Tensor) -> torch.Tensor:
        if self.use_transformer:
            h = self.tf(self.proj(tiles) + self.pos_emb)  # (B, 34, 64)
            h = torch.relu(self.out(h.mean(dim=1)))
        else:
            h = self.cnn(tiles.transpose(1, 2))  # (B, C, 34)
            h = torch.relu(self.out(h.flatten(1)))
        return self.fuse(torch.cat([h, scalars], dim=1))
