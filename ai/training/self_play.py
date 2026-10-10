"""League of past policy snapshots used as self-play opponents (SPEC 05.6.2, P7-8)."""

from __future__ import annotations

import copy
import random
from typing import Any

import torch

from ai.agents import Agent
from ai.agents.neural_agent import PolicyAgent
from ai.models.ppo_model import ActorCritic
from ai.simulate import make_agent


class League:
    def __init__(self, model_config: dict[str, Any], recent: int = 3, rule_share: float = 0.25,
                 seed: int = 0) -> None:
        self.model_config = model_config
        self.snapshots: list[dict[str, torch.Tensor]] = []
        self.recent = recent
        self.rule_share = rule_share
        self.rng = random.Random(seed)

    def add(self, model: torch.nn.Module) -> None:
        self.snapshots.append(copy.deepcopy(model.state_dict()))

    def _snapshot_agent(self, state: dict[str, torch.Tensor]) -> Agent:
        model = ActorCritic(**self.model_config)
        model.load_state_dict(state)
        return PolicyAgent(model, "ppo", temperature=1.0, seed=self.rng.randrange(2**31))

    def opponents(self) -> list[Agent]:
        """Three opponents: 70% recent snapshots, 30% any snapshot, plus some rule agents."""
        out: list[Agent] = []
        for _ in range(3):
            if not self.snapshots or self.rng.random() < self.rule_share:
                out.append(make_agent(self.rng.choice(["rule", "rule:1.5"]),
                                      self.rng.randrange(2**31)))
                continue
            pool = self.snapshots[-self.recent:] if self.rng.random() < 0.7 else self.snapshots
            out.append(self._snapshot_agent(self.rng.choice(pool)))
        return out
