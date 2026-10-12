"""Agent backed by an sb3-contrib MaskablePPO model (zip saved by ai.training.sb3_trainer)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ai.agents.neural_agent import decide_with_temperature
from ai.features import encode, mask_for
from engine.actions import Action, decode_action, encode_action
from engine.game import GameState


def load_sb3(path: str | Path) -> Any:
    from sb3_contrib import MaskablePPO

    return MaskablePPO.load(str(path), device="cpu")


class Sb3Agent:
    def __init__(self, path: str | Path | None = None, temperature: float = 0.1,
                 seed: int | None = None, name: str | None = None, model: Any = None) -> None:
        if model is None and path is None:
            raise ValueError("need a path or a loaded model")
        self.model = model if model is not None else load_sb3(path)  # type: ignore[arg-type]
        self.temperature = temperature
        self.name = name or (f"sb3:{Path(path).name}" if path else "sb3")
        self.gen = torch.Generator().manual_seed(seed if seed is not None else 0)

    @torch.no_grad()
    def logits(self, state: GameState, seat: int) -> tuple[torch.Tensor, np.ndarray]:
        t, s = encode(state, seat)
        mask = mask_for(state, seat)
        policy = self.model.policy
        obs, _ = policy.obs_to_tensor({"tiles": t[None], "scalars": s[None]})
        dist = policy.get_distribution(obs, action_masks=mask[None])
        return dist.distribution.logits[0].cpu(), mask

    def scores(self, state: GameState, seat: int, legal: list[Action]) -> dict[Action, float]:
        out, _ = self.logits(state, seat)
        return {a: float(out[encode_action(a)]) for a in legal}

    def act(self, state: GameState, seat: int, legal: list[Action]) -> Action:
        out, mask = self.logits(state, seat)
        idx = decide_with_temperature(out, self.temperature, torch.from_numpy(mask), self.gen)
        return decode_action(idx)


def sb3_meta(path: str | Path) -> dict[str, Any]:
    """Evaluation record written next to a saved model (`<name>.json`)."""
    meta = Path(path).with_suffix(".json")
    if not meta.exists():
        return {}
    data: dict[str, Any] = json.loads(meta.read_text())
    return data
