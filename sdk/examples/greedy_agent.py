"""A rule-based agent built on the engine's shanten tables.

python -m maijong_sdk.evaluate --agent greedy_agent:MyGreedyAgent --opponent random
"""

from maijong_sdk import Action, ActionType, BaseAgent, Observation
from maijong_sdk.agents import GreedyAgent


class MyGreedyAgent(BaseAgent):
    def __init__(self) -> None:
        self.inner = GreedyAgent()

    def decide(self, obs: Observation, legal_actions: list[Action]) -> Action:
        # always declare ready when the chosen discard allows it (+1 tai, no downside here)
        choice = self.inner.decide(obs, legal_actions)
        ting = Action(ActionType.TING, choice.tile) if choice.tile is not None else None
        if choice.type is ActionType.DISCARD and ting in legal_actions:
            return ting
        return choice
