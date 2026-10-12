"""Fair head-to-head promotion of the Lv5 model."""

import json

import pytest

pytest.importorskip("torch")


def test_head_to_head_and_level5_pointer(tmp_path, monkeypatch):
    import ai.agents.neural_agent as na
    from ai.agents import create_agent
    from ai.agents.neural_agent import save_checkpoint
    from ai.models.ppo_model import ActorCritic
    from ai.training.promote import head_to_head, promote

    paths = []
    for i in range(2):
        model = ActorCritic(hierarchical=True)
        p = tmp_path / f"cand{i}.pt"
        save_checkpoint(p, model, "bc", {"hierarchical": True, "use_transformer": False})
        paths.append(str(p))
    rows = head_to_head(paths, hands=8, workers=2)
    assert {r["path"] for r in rows} == set(paths) and all(r["hands"] == 8 for r in rows)
    assert rows[0]["eval_win_rate"] >= rows[1]["eval_win_rate"]

    out = tmp_path / "level5.json"
    rec = promote(rows, out)
    assert json.loads(out.read_text())["path"] == rec["path"] == rows[0]["path"]

    monkeypatch.setattr(na, "CHECKPOINT_DIR", tmp_path)
    assert na.best_level5(min_win_rate=0.0) == ("ppo", tmp_path / rows[0]["path"].split("/")[-1])
    agent = create_agent(5, seed=0) if rows[0]["eval_win_rate"] >= na.MIN_EVAL_WIN_RATE else None
    if agent is not None:
        assert getattr(agent, "kind", "") == "ppo"
