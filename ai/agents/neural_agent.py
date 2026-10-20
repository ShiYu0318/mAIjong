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
    # always CPU tensors, so a checkpoint trained on a GPU loads on any machine
    state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
    torch.save({"kind": kind, "model_config": model_config, "state_dict": state, **extra}, path)


def agent_from_checkpoint(path: str | Path, temperature: float = 0.1,
                          seed: int | None = None) -> PolicyAgent:
    model, kind = load_model(Path(path))
    return PolicyAgent(model, kind, temperature, seed, name=f"{kind}:{Path(path).name}")


MIN_EVAL_WIN_RATE = 0.25  # must at least match a rule agent's share at a table of four


def latest_checkpoint(kind: str, min_win_rate: float = MIN_EVAL_WIN_RATE) -> Path | None:
    """The deployable checkpoint for Lv4 (dqn) / Lv5 (ppo), only if its recorded
    evaluation against rule agents reaches `min_win_rate`."""
    p = CHECKPOINT_DIR / f"{kind}_latest.pt"
    if not p.exists():
        return None
    try:
        meta = torch.load(p, map_location="cpu", weights_only=False)
    except Exception:
        return None
    return p if float(meta.get("eval_win_rate", 0.0)) >= min_win_rate else None


def best_level5(min_win_rate: float = MIN_EVAL_WIN_RATE) -> tuple[str, Path] | None:
    """Strongest deployable Lv5 model: the custom PPO checkpoint or the SB3 MaskablePPO
    best model, whichever recorded the higher win rate against rule agents."""
    import json

    promoted = CHECKPOINT_DIR / "level5.json"  # head-to-head result from ai.training.promote
    if promoted.exists():
        try:
            rec = json.loads(promoted.read_text())
            if rec.get("kind") == "rule":
                return None  # no model beat the rule agent on the same deals
            path = Path(rec["path"])
            if not path.is_absolute() and not path.exists():
                path = CHECKPOINT_DIR.parent / path
            if path.exists():
                return ("sb3" if path.suffix == ".zip" else "ppo"), path
        except (ValueError, KeyError, OSError):
            pass  # fall back to the per-checkpoint records below

    found: list[tuple[float, str, Path]] = []
    ppo = latest_checkpoint("ppo", min_win_rate)
    if ppo is not None:
        meta = torch.load(ppo, map_location="cpu", weights_only=False)
        found.append((float(meta.get("eval_win_rate", 0.0)), "ppo", ppo))
    sb3 = CHECKPOINT_DIR / "sb3_best.zip"
    meta_path = sb3.with_suffix(".json")
    if sb3.exists() and meta_path.exists():
        try:
            rate = float(json.loads(meta_path.read_text()).get("eval_win_rate", 0.0))
        except (ValueError, OSError):
            rate = 0.0
        if rate >= min_win_rate:
            found.append((rate, "sb3", sb3))
    if not found:
        return None
    _, kind, path = max(found, key=lambda x: x[0])
    return kind, path


__all__ = ["PolicyAgent", "best_level5", "agent_from_checkpoint", "decide_with_temperature",
           "latest_checkpoint", "load_model", "save_checkpoint"]
