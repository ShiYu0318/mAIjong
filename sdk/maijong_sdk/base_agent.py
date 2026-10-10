"""Agent interface contract (SPEC 06.2).

Hard limits enforced by the platform (violations disqualify the submission):
  - decide() returns within 5 seconds of wall-clock time;
  - decide() makes no network calls and touches no files (load models in __init__);
  - memory stays below 2 GB;
  - the returned action is one of legal_actions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from maijong_sdk.types import Action, GameInfo, Observation


class BaseAgent(ABC):
    def on_game_start(self, seat: int, info: GameInfo) -> None:  # noqa: B027
        """Called once at the start of every hand. Optional."""

    def on_game_end(self, final_scores: list[int]) -> None:  # noqa: B027
        """Called once when a hand ends. Optional."""

    @abstractmethod
    def decide(self, obs: Observation, legal_actions: list[Action]) -> Action:
        """Return one of `legal_actions` for the current decision."""
