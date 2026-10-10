"""Run hands between BaseAgents locally (no backend needed)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game
from maijong_sdk.base_agent import BaseAgent
from maijong_sdk.types import GameInfo, observe


@dataclass
class HandOutcome:
    result: dict[str, Any]
    actions: list[list[int]] = field(default_factory=list)


def play_hand(agents: list[BaseAgent], seed: int, dealer: int = 0) -> HandOutcome:
    from engine.actions import encode_action

    s = new_game(seed, dealer=dealer)
    for p, agent in enumerate(agents):
        agent.on_game_start(p, GameInfo(p, s.seat_wind(p), s.round_wind, s.dealer))
    actions: list[list[int]] = []
    while s.phase is not Phase.ENDED:
        p = acting_players(s)[0]
        legal = get_legal_actions(s, p)
        a = agents[p].decide(observe(s, p), legal)
        if a not in legal:
            raise ValueError(f"agent {p} returned an illegal action {a}")
        actions.append([p, encode_action(a)])
        s, _ = apply_action(s, p, a)
    assert s.result is not None
    for agent in agents:
        agent.on_game_end(list(s.result["payments"]))
    return HandOutcome(s.result, actions)
