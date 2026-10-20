"""Parameterised rule agent, duplicate evaluation and the tuner's helpers."""

from __future__ import annotations

from dataclasses import asdict

from ai.agents.rule_agent import RuleParams
from ai.simulate import make_agent
from ai.training.duplicate import paired
from ai.training.tune import alternatives, spec


def test_default_parameters_are_the_original_rule_agent():
    res = paired("rulex:", "rule", hands=12, workers=1)
    assert res.mean_diff == 0 and res.se == 0
    mixed = paired("rulex:flush=13", "rule", hands=8,
                   opponent="rule|rulex:declare=never|rulex:calls=near", workers=1)
    assert mixed.hands == 8


def test_spec_round_trip_and_alternatives():
    params = {**asdict(RuleParams()), "flush": 13, "w_live": 0.15, "declare": 4}
    s = spec(params)
    assert s == "rulex:declare=4,flush=13,w_live=0.15"
    agent = make_agent(s, 0)
    assert agent.params.flush == 13 and agent.params.w_live == 0.15 and agent.params.declare == 4
    assert spec(asdict(RuleParams())) == "rulex:"
    for name, value in asdict(RuleParams()).items():
        assert value not in alternatives(name, value)
    assert alternatives("declare", "always") == ["never", 3, 4, 5, 6]


def test_level5_can_be_a_promoted_agent_spec(tmp_path, monkeypatch):
    import json

    import ai.agents.neural_agent as na
    from ai.agents import RuleAgent, create_agent

    monkeypatch.setattr(na, "CHECKPOINT_DIR", tmp_path)
    (tmp_path / "level5.json").write_text(json.dumps({"kind": "spec", "path": "rulex:flush=13"}))
    agent = create_agent(5, seed=1)
    assert isinstance(agent, RuleAgent) and agent.params.flush == 13
    (tmp_path / "level5.json").write_text(json.dumps({"kind": "rule", "path": "rule"}))
    assert na.level5_spec() is None
