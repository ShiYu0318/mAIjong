"""Smoke tests for the RL pipeline: env, features, models and tiny training runs."""

from pathlib import Path

import numpy as np
import pytest
import torch

pytest.importorskip("gymnasium")

from gymnasium.utils.env_checker import check_env  # noqa: E402

from ai.env import MahjongEnv  # noqa: E402
from ai.features import N_SCALARS, encode, mask_for  # noqa: E402
from ai.models.dqn_model import DuelingDQN  # noqa: E402
from ai.models.ppo_model import ActorCritic  # noqa: E402
from ai.reward import GameResult, StepData, compute_shaped_reward  # noqa: E402
from engine.game import acting_players, new_game  # noqa: E402


def test_env_passes_gymnasium_checker():
    env = MahjongEnv(seed=1)
    check_env(env, skip_render_check=True)


def test_env_episode_runs_with_legal_masks():
    env = MahjongEnv(seed=3, rotate_seat=True)
    obs, info = env.reset()
    total, done, steps = 0.0, False, 0
    rng = np.random.default_rng(0)
    while not done:
        assert obs["tiles"].shape == (34, 14) and obs["scalars"].shape == (N_SCALARS,)
        action = int(rng.choice(np.flatnonzero(info["legal_mask"])))
        obs, r, done, _, info = env.step(action)
        total += r
        steps += 1
    assert "result" in info and steps > 0
    _, info = env.reset()
    illegal = int(np.flatnonzero(~info["legal_mask"])[0])
    _, r, _, _, info = env.step(illegal)
    assert info["illegal_action"] and r <= -0.1 + 0.2


def test_features_match_hand_and_masks():
    s = new_game(seed=4)
    p = acting_players(s)[0]
    tiles, scalars = encode(s, p)
    assert tiles[:, 0].sum() == len(s.hands[p])
    assert scalars[7] == 1.0  # seat 0 is the dealer
    assert mask_for(s, p).sum() > 0


def test_reward_terminal_only_once():
    step = StepData(0, 2, 1, 10, 14, is_final=False)
    assert compute_shaped_reward(step, [], GameResult(0, 5, None, 0, False)) == pytest.approx(
        0.05 + 0.02)
    final = StepData(0, 1, 1, 10, 10, is_final=True)
    assert compute_shaped_reward(final, [], GameResult(0, 4, None, 0, False)) == 2.0
    assert compute_shaped_reward(final, [], GameResult(1, 4, 0, 4, False)) == -4.0


@pytest.mark.parametrize("hierarchical", [True, False])
def test_policy_is_a_distribution_over_legal_actions(hierarchical):
    model = ActorCritic(hierarchical=hierarchical)
    s = new_game(seed=5)
    p = acting_players(s)[0]
    t, sc = encode(s, p)
    mask = torch.from_numpy(mask_for(s, p))[None]
    logp, v = model(torch.from_numpy(t)[None], torch.from_numpy(sc)[None], mask)
    probs = logp.exp()
    assert torch.allclose(probs[mask].sum(), torch.tensor(1.0), atol=1e-4)
    assert probs[~mask].max() < 1e-6 and v.shape == (1,)
    q = DuelingDQN(noisy=True)(torch.from_numpy(t)[None], torch.from_numpy(sc)[None])
    assert q.shape == (1, 108)


def test_tiny_training_runs(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MAIJONG_RUNS_DIR", str(tmp_path / "runs"))
    import importlib

    import ai.training.metrics as metrics

    importlib.reload(metrics)
    from ai.agents.neural_agent import agent_from_checkpoint
    from ai.simulate import run_batch
    from ai.training import bc_trainer, dqn_trainer, ppo_trainer

    importlib.reload(bc_trainer)
    importlib.reload(ppo_trainer)
    importlib.reload(dqn_trainer)

    records = tmp_path / "rule.jsonl.gz"
    run_batch(["rule"] * 4, 6, seed=1, save_path=records)
    data = bc_trainer.build_dataset(records, workers=1)
    assert len(data["actions"]) > 100
    bc_ckpt = tmp_path / "bc.pt"
    best = bc_trainer.train_bc(data, bc_ckpt, epochs=2, run="bc-test")
    assert bc_ckpt.exists() and best["val_acc"] > 0

    cfg = ppo_trainer.PPOConfig(n_envs=2, rollout_steps=16, updates=2, mini_batch=16,
                                eval_every=2, eval_hands=4, snapshot_every=1)
    ppo_ckpt = tmp_path / "ppo.pt"
    res = ppo_trainer.train_ppo(cfg, ppo_ckpt, init=bc_ckpt, run="ppo-test")
    assert ppo_ckpt.exists() and "eval_win_rate" in res
    assert (tmp_path / "runs" / "ppo-test" / "metrics.jsonl").exists()

    dcfg = dqn_trainer.DQNConfig(steps=200, warmup=40, batch=16, buffer=500,
                                 eval_every=200, eval_hands=4, target_every=50)
    dqn_ckpt = tmp_path / "dqn.pt"
    dqn_trainer.train_dqn(dcfg, dqn_ckpt, run="dqn-test")
    assert dqn_ckpt.exists()

    agent = agent_from_checkpoint(ppo_ckpt, temperature=0.1, seed=0)
    s = new_game(seed=9)
    p = acting_players(s)[0]
    from engine.game import get_legal_actions

    assert agent.act(s, p, get_legal_actions(s, p)) in get_legal_actions(s, p)
