"""Dueling DQN with optional noisy layers (SPEC 05.5.3)."""

from __future__ import annotations

import math

import torch
from torch import nn

from ai.models.backbone import LATENT, MahjongEncoder
from engine.actions import N_ACTIONS


class NoisyLinear(nn.Module):
    """Factorised Gaussian noise layer (Fortunato et al.)."""

    def __init__(self, n_in: int, n_out: int, sigma0: float = 0.5) -> None:
        super().__init__()
        self.n_in, self.n_out = n_in, n_out
        self.mu_w = nn.Parameter(torch.empty(n_out, n_in))
        self.sigma_w = nn.Parameter(torch.empty(n_out, n_in))
        self.mu_b = nn.Parameter(torch.empty(n_out))
        self.sigma_b = nn.Parameter(torch.empty(n_out))
        self.register_buffer("eps_in", torch.zeros(n_in))
        self.register_buffer("eps_out", torch.zeros(n_out))
        bound = 1 / math.sqrt(n_in)
        nn.init.uniform_(self.mu_w, -bound, bound)
        nn.init.uniform_(self.mu_b, -bound, bound)
        nn.init.constant_(self.sigma_w, sigma0 / math.sqrt(n_in))
        nn.init.constant_(self.sigma_b, sigma0 / math.sqrt(n_in))
        self.reset_noise()

    @staticmethod
    def _f(x: torch.Tensor) -> torch.Tensor:
        return x.sign() * x.abs().sqrt()

    def reset_noise(self) -> None:
        self.eps_in.copy_(self._f(torch.randn(self.n_in)))
        self.eps_out.copy_(self._f(torch.randn(self.n_out)))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if not self.training:
            return nn.functional.linear(x, self.mu_w, self.mu_b)
        w = self.mu_w + self.sigma_w * torch.outer(self.eps_out, self.eps_in)
        b = self.mu_b + self.sigma_b * self.eps_out
        return nn.functional.linear(x, w, b)


class DuelingDQN(nn.Module):
    def __init__(self, noisy: bool = False, use_transformer: bool = False) -> None:
        super().__init__()
        self.encoder = MahjongEncoder(use_transformer)
        lin = (lambda i, o: NoisyLinear(i, o)) if noisy else nn.Linear
        self.value = nn.Sequential(lin(LATENT, 128), nn.ReLU(), lin(128, 1))
        self.adv = nn.Sequential(lin(LATENT, 128), nn.ReLU(), lin(128, N_ACTIONS))

    def forward(self, tiles: torch.Tensor, scalars: torch.Tensor) -> torch.Tensor:
        h = self.encoder(tiles, scalars)
        a = self.adv(h)
        return self.value(h) + a - a.mean(dim=1, keepdim=True)

    def reset_noise(self) -> None:
        for m in self.modules():
            if isinstance(m, NoisyLinear):
                m.reset_noise()
