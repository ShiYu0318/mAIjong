"""Server-side agent interface.

Agents receive the full engine state for convenience but must only use information
visible to their seat (own hand, public melds/discards/flowers). The public SDK
(sdk/) exposes a masked Observation instead.
"""

from __future__ import annotations

from typing import Protocol

from engine.actions import Action
from engine.game import GameState


class Agent(Protocol):
    name: str

    def act(self, state: GameState, seat: int, legal: list[Action]) -> Action: ...
