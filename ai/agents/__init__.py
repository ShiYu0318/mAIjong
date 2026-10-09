"""Agents and the difficulty-level factory (SPEC 04.4)."""

from __future__ import annotations

from ai.agents.base import Agent
from ai.agents.random_agent import RandomAgent
from ai.agents.rule_agent import RuleAgent

LEVEL_TEMPERATURE = {2: 3.0, 3: 1.5, 4: 0.7, 5: 0.1}
LEVEL_NAMES = {1: "初學", 2: "入門", 3: "普通", 4: "進階", 5: "高手"}


def create_agent(level: int, seed: int | None = None) -> Agent:
    """Lv1 random; Lv2-3 rule-based. Lv4/5 use neural agents once trained,
    falling back to a low-temperature rule agent."""
    if level <= 1:
        return RandomAgent(seed)
    return RuleAgent(LEVEL_TEMPERATURE.get(level, 1.5), seed)


__all__ = ["Agent", "LEVEL_NAMES", "RandomAgent", "RuleAgent", "create_agent"]
