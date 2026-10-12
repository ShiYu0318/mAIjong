"""Stable-Baselines3 features extractor reusing the project's MahjongEncoder."""

from __future__ import annotations

import torch
from gymnasium import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor

from ai.models.backbone import LATENT, MahjongEncoder


class MahjongExtractor(BaseFeaturesExtractor):
    def __init__(self, observation_space: spaces.Dict, use_transformer: bool = False) -> None:
        super().__init__(observation_space, features_dim=LATENT)
        self.encoder = MahjongEncoder(use_transformer)

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        return self.encoder(observations["tiles"], observations["scalars"])
