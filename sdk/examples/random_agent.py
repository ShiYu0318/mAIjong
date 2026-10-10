"""The smallest possible agent: pick any legal action."""

import random

from maijong_sdk import Action, BaseAgent, Observation


class MyRandomAgent(BaseAgent):
    def __init__(self) -> None:
        self.rng = random.Random(0)

    def decide(self, obs: Observation, legal_actions: list[Action]) -> Action:
        return self.rng.choice(legal_actions)
