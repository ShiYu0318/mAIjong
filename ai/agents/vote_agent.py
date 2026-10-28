"""Ensemble by vote: several strong agents of different styles each propose a move.

The ladder shows the top rule-based and network agents level in strength but different in
style, so their mistakes are not the same mistakes. The move most of them pick is played;
a tie goes to the first member (list the most trusted agent first). Networks play greedily
here, since a vote of samples would only add noise.

    vote:lv5+rule+tuned+bc_v3+ppo_v4     (names from ai.ladder.DEFAULT_POOL)
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from engine.actions import Action
from engine.game import GameState


def _member(spec: str, seed: int) -> Any:
    kind, _, arg = spec.partition(":")
    if kind in ("bc", "ppo", "dqn") and arg:
        from ai.agents.neural_agent import agent_from_checkpoint

        return agent_from_checkpoint(arg, 0.0, seed)
    if kind == "sb3" and arg:
        from ai.agents.sb3_agent import Sb3Agent

        return Sb3Agent(arg, 0.0, seed)
    from ai.simulate import make_agent

    return make_agent(spec, seed)


class VoteAgent:
    def __init__(self, specs: list[str], seed: int | None = None) -> None:
        self.members = [_member(sp, (seed or 0) * 16 + k) for k, sp in enumerate(specs)]
        self.name = "vote"

    def act(self, state: GameState, seat: int, legal: list[Action]) -> Action:
        picks = [m.act(state, seat, legal) for m in self.members]
        votes = Counter(picks)
        top = max(votes.values())
        return next(a for a in picks if votes[a] == top)  # first member breaks ties


def vote_agent(arg: str, seed: int) -> VoteAgent:
    from ai.ladder import DEFAULT_POOL

    specs = [DEFAULT_POOL.get(n, n) for n in arg.split("+") if n]
    return VoteAgent(specs, seed)
