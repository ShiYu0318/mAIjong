from pathlib import Path

import numpy as np
import pytest
from maijong_sdk.agents import GreedyAgent, RandomAgent
from maijong_sdk.cli import pack, validate
from maijong_sdk.evaluate import evaluate
from maijong_sdk.runner import play_hand

EXAMPLES = Path(__file__).resolve().parents[2] / "sdk" / "examples"


def test_runner_and_evaluate():
    out = play_hand([GreedyAgent(), RandomAgent(1), RandomAgent(2), RandomAgent(3)], seed=4)
    assert out.result["kind"] in ("HU", "DRAW") and out.actions
    res = evaluate(GreedyAgent(), "random", games=8)
    assert res["games"] == 8 and 0 <= res["win_rate"] <= 1


def test_pack_and_validate_example(tmp_path: Path):
    z = pack(f"{EXAMPLES / 'greedy_agent.py'}:MyGreedyAgent", None, "Greedy", "demo", None,
             tmp_path / "s.zip")
    report = validate(z, games=4)
    assert report["passed"], report
    assert report["decisions"] > 10 and report["max_decision_s"] < 5


def test_validation_rejects_illegal_agent(tmp_path: Path):
    src = tmp_path / "bad.py"
    src.write_text(
        "from maijong_sdk import Action, ActionType, BaseAgent\n"
        "class Bad(BaseAgent):\n"
        "    def decide(self, obs, legal):\n"
        "        return Action(ActionType.PON)\n")
    report = validate(pack(f"{src}:Bad", None, "Bad", "", None, tmp_path / "b.zip"), games=2)
    assert not report["passed"] and "illegal" in report["errors"][0]


def test_pack_rejects_disallowed_requirements(tmp_path: Path):
    req = tmp_path / "requirements.txt"
    req.write_text("requests==2.0\n")
    with pytest.raises(SystemExit):
        pack(f"{EXAMPLES / 'random_agent.py'}:MyRandomAgent", None, "x", "", req,
             tmp_path / "x.zip")


def test_sdk_env_and_feature_parity():
    pytest.importorskip("gymnasium")
    from gymnasium.utils.env_checker import check_env
    from maijong_sdk.env import MahjongEnv
    from maijong_sdk.features import encode as sdk_encode
    from maijong_sdk.types import observe

    from ai.features import encode as platform_encode
    from engine.game import acting_players, new_game

    check_env(MahjongEnv(seed=2), skip_render_check=True)
    s = new_game(seed=7)
    p = acting_players(s)[0]
    a, b = platform_encode(s, p), sdk_encode(observe(s, p))
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
