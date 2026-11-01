"""Agents and the difficulty-level factory (SPEC 04.4)."""

from __future__ import annotations

from ai.agents.base import Agent
from ai.agents.random_agent import RandomAgent
from ai.agents.rule_agent import RuleAgent, RuleParams

LEVEL_TEMPERATURE = {2: 3.0, 3: 1.5, 4: 0.7, 5: 0.1}
# Fallback Lv5 parameters from cross-entropy search (ai.training.cem_tune).
# Historical tuning predates the concealed-kong visibility fix. On unused deals it led
# the previous Lv5 by +2.9, +7.7 and +8.4 points/hand (36,000 paired deals in three sets,
# about +6.3 ± 1.8 combined), and plain rule by about +3.5 ± 1.5 (2026-10-30).
# These estimates require revalidation under the corrected public-information contract.
LEVEL5_PARAMS = RuleParams(w_shanten=8.9362, w_live=0.0853, honor_discard=0.1603,
                           ting_bonus=0.5166, value_pon=0.2447, flush_far=5.3785,
                           flush_near=14.1263, fold_ready=4.2321, fold_one=7.1861,
                           fold_far=37.6972, late_wall=30, fold_late_near=1.4033,
                           fold_late_far=4.2173, threat_turn=18, threat_scale=0.5941)
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
            from ai.agents.neural_agent import (
                agent_from_checkpoint,
                best_level5,
                latest_checkpoint,
                level5_spec,
            )

            if level == 5:
                spec = level5_spec()
                if spec is not None:  # a promoted rule-tuned or search agent
                    from ai.simulate import make_agent

                    return make_agent(spec, seed if seed is not None else 0)
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
        if level == 5:
            return RuleAgent(0.0, seed, params=LEVEL5_PARAMS)
        return RuleAgent(0.3, seed)
    return RuleAgent(temperature, seed)


__all__ = ["Agent", "LEVEL5_PARAMS", "LEVEL_NAMES", "RandomAgent", "RuleAgent", "create_agent"]
