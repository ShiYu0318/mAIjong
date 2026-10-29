"""CEM tuner: parameter mapping, off-switches, and a fair shared-deal evaluation."""

from __future__ import annotations

from dataclasses import asdict

import numpy as np

from ai.agents import LEVEL5_PARAMS
from ai.agents.rule_agent import RuleParams
from ai.training.cem_tune import SPACE, evaluate, from_params, to_params


def test_known_agents_survive_the_round_trip():
    for p in (RuleParams(), LEVEL5_PARAMS):
        assert asdict(to_params(from_params(p))) == asdict(p)


def test_switches_turn_off_at_the_edges():
    low = to_params(np.zeros(len(SPACE)))
    assert low.flush == 0 and low.declare == "always"
    high = to_params(np.ones(len(SPACE)))
    assert high.threat_melds == 0 and high.threat_turn == 0 and high.declare == 8  # round(7.5) is 8


def test_the_baseline_itself_scores_exactly_zero():
    diff = evaluate([RuleParams(), LEVEL5_PARAMS], "rule", ["rule"], list(range(30_000, 30_008)), 2)
    assert diff[0] == 0.0  # same agent, same deals, same seats
    assert diff.shape == (2,)
