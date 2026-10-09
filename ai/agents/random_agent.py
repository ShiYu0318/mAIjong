"""Level 1: uniformly random legal action."""

from __future__ import annotations

import random

from engine.actions import Action
from engine.game import GameState


class RandomAgent:
    name = "random"

    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)

    def act(self, state: GameState, seat: int, legal: list[Action]) -> Action:
        return self.rng.choice(legal)
