"""Actor-critic with flat or hierarchical policy head (SPEC 05.5.2, 05.5.4).

The hierarchical head picks an action type (9) then a tile (34) for tile-bearing types.
It is converted into exact log-probabilities over the flat 108 actions, so training and
sampling use one masked categorical distribution either way.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

from ai.models.backbone import LATENT, MahjongEncoder
from engine.actions import (
    CHI_HIGH_ID,
    CHI_LOW_ID,
    CHI_MID_ID,
    HU_ID,
    KONG_OFFSET,
    N_ACTIONS,
    PASS_ID,
    PON_ID,
    TING_OFFSET,
)

# action type index per flat id: 0 DISCARD, 1 TING, 2 KONG, 3 PON, 4-6 CHI, 7 HU, 8 PASS
N_TYPES = 9
TILE_TYPES = (0, 1, 2)
_type = np.zeros(N_ACTIONS, dtype=np.int64)
_tile = np.full(N_ACTIONS, -1, dtype=np.int64)
for t in range(34):
    _type[t], _tile[t] = 0, t
    _type[TING_OFFSET + t], _tile[TING_OFFSET + t] = 1, t
    _type[KONG_OFFSET + t], _tile[KONG_OFFSET + t] = 2, t
for i, aid in enumerate((PON_ID, CHI_LOW_ID, CHI_MID_ID, CHI_HIGH_ID, HU_ID, PASS_ID)):
    _type[aid] = 3 + i
TYPE_OF = torch.from_numpy(_type)
TILE_OF = torch.from_numpy(_tile)
NEG = -1e9


class ActorCritic(nn.Module):
    def __init__(self, hierarchical: bool = True, use_transformer: bool = False) -> None:
        super().__init__()
        self.hierarchical = hierarchical
        self.encoder = MahjongEncoder(use_transformer)
        if hierarchical:
            self.type_head = nn.Linear(LATENT, N_TYPES)
            self.type_emb = nn.Embedding(len(TILE_TYPES), LATENT)
            self.tile_head = nn.Linear(LATENT, 34)
        else:
            self.policy = nn.Linear(LATENT, N_ACTIONS)
        self.value = nn.Sequential(nn.Linear(LATENT, 128), nn.ReLU(), nn.Linear(128, 1))

    def logits(self, h: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """Masked flat log-probabilities (B, 108); illegal actions get -1e9."""
        if not self.hierarchical:
            return torch.log_softmax(self.policy(h).masked_fill(~mask, NEG), dim=-1)
        b = h.shape[0]
        type_of = TYPE_OF.to(h.device)
        tile_of = TILE_OF.to(h.device)
        # a type is legal if any of its flat actions is legal
        type_mask = torch.zeros(b, N_TYPES, dtype=torch.bool, device=h.device)
        type_mask.scatter_reduce_(1, type_of.expand(b, -1), mask, reduce="amax")
        type_logp = torch.log_softmax(self.type_head(h).masked_fill(~type_mask, NEG), dim=-1)
        flat = type_logp[:, type_of]  # (B, 108)
        for k, ty in enumerate(TILE_TYPES):
            ids = (type_of == ty).nonzero(as_tuple=True)[0]  # 34 flat ids of this type
            cond = h + self.type_emb.weight[k]
            tile_logits = self.tile_head(cond)[:, tile_of[ids]]
            tile_logp = torch.log_softmax(tile_logits.masked_fill(~mask[:, ids], NEG), dim=-1)
            flat[:, ids] = flat[:, ids] + tile_logp
        return flat.masked_fill(~mask, NEG)

    def forward(self, tiles: torch.Tensor, scalars: torch.Tensor, mask: torch.Tensor
                ) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.encoder(tiles, scalars)
        return self.logits(h, mask), self.value(h).squeeze(-1)
