"""Stable-Baselines3 (MaskablePPO) self-play trainer and the PettingZoo multi-agent env."""

import importlib
import json

import numpy as np
import pytest

pytest.importorskip("sb3_contrib")
pytest.importorskip("pettingzoo")

from pettingzoo.test import api_test  # noqa: E402

from ai.marl import env as aec_env  # noqa: E402
from engine.game import acting_players, get_legal_actions, new_game  # noqa: E402


def test_pettingzoo_api():
    api_test(aec_env(), num_cycles=200)


def test_pettingzoo_hand_pays_out_zero_sum():
    e = aec_env()
    e.reset(seed=4)
    rng = np.random.default_rng(0)
    totals = {a: 0.0 for a in e.possible_agents}
    for agent in e.agent_iter(max_iter=5000):
        obs, reward, term, trunc, _ = e.last()
        totals[agent] += reward
        if term or trunc:
            e.step(None)
            continue
        e.step(int(rng.choice(np.flatnonzero(obs["action_mask"]))))
    assert not e.agents
    assert abs(sum(totals.values())) < 1e-6


def test_maskable_ppo_self_play_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("MAIJONG_RUNS_DIR", str(tmp_path / "runs"))
    import ai.training.metrics as metrics

    importlib.reload(metrics)
    from ai.training import sb3_trainer

    importlib.reload(sb3_trainer)
    from ai.agents.sb3_agent import Sb3Agent, sb3_meta
    from ai.simulate import make_agent, run_batch

    records = tmp_path / "rule.jsonl.gz"
    run_batch(["rule"] * 4, 4, seed=1, save_path=records)
    best = sb3_trainer.train(
        steps=256, envs=2, out_dir=tmp_path / "ckpt", run="sb3-test", bc_data=records,
        bc_epochs=1, n_steps=64, batch=64, snapshot_every=128, eval_every=10**9,
        eval_hands=4, subprocess=False,
    )
    assert "eval_win_rate" in best
    best_zip = tmp_path / "ckpt" / "sb3_best.zip"
    assert best_zip.exists() and sb3_meta(best_zip)["eval_win_rate"] == best["eval_win_rate"]
    assert list((tmp_path / "ckpt" / "sb3_snapshots").glob("snap_*.zip"))
    lines = (tmp_path / "runs" / "sb3-test" / "metrics.jsonl").read_text().splitlines()
    keys = set().union(*(json.loads(x) for x in lines))
    assert {"bc_val_acc", "eval_win_rate"} <= keys

    for agent in (Sb3Agent(best_zip, 0.1, 0), make_agent(f"sb3:{best_zip}", 1)):
        s = new_game(seed=9)
        p = acting_players(s)[0]
        legal = get_legal_actions(s, p)
        assert agent.act(s, p, legal) in legal
