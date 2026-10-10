"""Neural agents (DQN Lv4, PPO Lv5) loaded from checkpoints."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import torch

from ai.features import encode, mask_for
from engine.actions import Action, decode_action, encode_action
from engine.game import GameState

CHECKPOINT_DIR = Path(os.environ.get("MAIJONG_CHECKPOINT_DIR", "checkpoints"))


def decide_with_temperature(logits: torch.Tensor, temperature: float,
                            legal_mask: torch.Tensor, gen: torch.Generator | None = None) -> int:
    """SPEC 04.4: greedy below T=0.01, otherwise sample softmax(logits / T) over legal moves."""
    masked = logits.masked_fill(~legal_mask, float("-inf"))
    if temperature < 0.01:
        return int(masked.argmax().item())
    probs = torch.softmax(masked / temperature, dim=-1)
    return int(torch.multinomial(probs, 1, generator=gen).item())


class PolicyAgent:
    """Wraps an ActorCritic (log-prob logits) or DuelingDQN (Q-values)."""

    def __init__(self, model: torch.nn.Module, kind: str, temperature: float = 0.1,
                 seed: int | None = None, name: str | None = None) -> None:
        self.model = model.eval()
        self.kind = kind
        self.temperature = temperature
        self.name = name or kind
        self.gen = torch.Generator().manual_seed(seed if seed is not None else 0)

    @torch.no_grad()
    def scores_tensor(self, state: GameState, seat: int) -> tuple[torch.Tensor, torch.Tensor]:
        t, s = encode(state, seat)
        mask = torch.from_numpy(mask_for(state, seat)).unsqueeze(0)
        tt = torch.from_numpy(t).unsqueeze(0)
        ss = torch.from_numpy(s).unsqueeze(0)
        if self.kind == "ppo":
            out, _ = self.model(tt, ss, mask)
        else:
            out = self.model(tt, ss)
        return out[0], mask[0]

    def scores(self, state: GameState, seat: int, legal: list[Action]) -> dict[Action, float]:
        out, _ = self.scores_tensor(state, seat)
        return {a: float(out[encode_action(a)]) for a in legal}

    def act(self, state: GameState, seat: int, legal: list[Action]) -> Action:
        out, mask = self.scores_tensor(state, seat)
        return decode_action(decide_with_temperature(out, self.temperature, mask, self.gen))


def load_model(path: Path) -> tuple[torch.nn.Module, str]:
    from ai.models.dqn_model import DuelingDQN
    from ai.models.ppo_model import ActorCritic

    ckpt: dict[str, Any] = torch.load(path, map_location="cpu", weights_only=False)
    kind = ckpt["kind"]
    cfg = ckpt.get("model_config", {})
    model: torch.nn.Module = ActorCritic(**cfg) if kind in ("ppo", "bc") else DuelingDQN(**cfg)
    model.load_state_dict(ckpt["state_dict"])
    return model, "ppo" if kind in ("ppo", "bc") else "dqn"


def save_checkpoint(path: Path, model: torch.nn.Module, kind: str,
                    model_config: dict[str, Any], **extra: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"kind": kind, "model_config": model_config,
                "state_dict": model.state_dict(), **extra}, path)


def agent_from_checkpoint(path: str | Path, temperature: float = 0.1,
                          seed: int | None = None) -> PolicyAgent:
    model, kind = load_model(Path(path))
    return PolicyAgent(model, kind, temperature, seed, name=f"{kind}:{Path(path).name}")


def latest_checkpoint(kind: str) -> Path | None:
    p = CHECKPOINT_DIR / f"{kind}_latest.pt"
    return p if p.exists() else None


__all__ = ["PolicyAgent", "agent_from_checkpoint", "decide_with_temperature",
           "latest_checkpoint", "load_model", "save_checkpoint"]
