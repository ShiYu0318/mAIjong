"""Agents and the difficulty-level factory (SPEC 04.4)."""

from __future__ import annotations

from ai.agents.base import Agent
from ai.agents.random_agent import RandomAgent
from ai.agents.rule_agent import RuleAgent

LEVEL_TEMPERATURE = {2: 3.0, 3: 1.5, 4: 0.7, 5: 0.1}
LEVEL_NAMES = {1: "初學", 2: "入門", 3: "普通", 4: "進階", 5: "高手"}


def create_agent(level: int, seed: int | None = None) -> Agent:
    """Lv1 random; Lv2-3 rule-based; Lv4 DQN and Lv5 PPO when a checkpoint exists
    (checkpoints/dqn_latest.pt, checkpoints/ppo_latest.pt), otherwise a low-temperature
    rule agent."""
    if level <= 1:
        return RandomAgent(seed)
    temperature = LEVEL_TEMPERATURE.get(level, 1.5)
    if level >= 4:
        try:
            from ai.agents.neural_agent import agent_from_checkpoint, best_level5, latest_checkpoint

            if level == 5:
                best = best_level5()
                if best is not None and best[0] == "sb3":
                    from ai.agents.sb3_agent import Sb3Agent

                    return Sb3Agent(best[1], temperature, seed)
                path = best[1] if best is not None else None
            else:
                path = latest_checkpoint("dqn")
            if path is not None:
                return agent_from_checkpoint(path, temperature, seed)
        except ImportError:  # torch not installed: serve rule agents only
            pass
        return RuleAgent(0.3 if level == 4 else 0.0, seed)
    return RuleAgent(temperature, seed)


__all__ = ["Agent", "LEVEL_NAMES", "RandomAgent", "RuleAgent", "create_agent"]
