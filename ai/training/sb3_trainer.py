"""Self-play training with sb3-contrib MaskablePPO (SPEC 05.6.2).

    python -m ai.training.sb3_trainer --steps 2000000 --envs 8 \\
        --bc-data data/bc/rule_3k.jsonl.gz --run sb3-v1

- Environments run in parallel processes (SubprocVecEnv); illegal actions are masked.
- Optional behaviour-cloning warm start from simulated rule-agent hands.
- Opponents: a pool of rule agents and past snapshots of the learner (self-play league).
- Every `--eval-every` steps the policy plays rule agents; only the best model is kept
  (checkpoints/sb3_best.zip + .json) and metrics go to runs/<run>/metrics.jsonl.
"""

from __future__ import annotations

import argparse
import functools
import json
import random
import time
from collections import OrderedDict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.logger import KVWriter, Logger
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecEnv

from ai.agents import Agent
from ai.agents.sb3_agent import Sb3Agent, load_sb3
from ai.env import MahjongEnv
from ai.models.sb3_extractor import MahjongExtractor
from ai.reward import REWARD_PRESETS
from ai.simulate import make_agent
from ai.training.evaluate import evaluate
from ai.training.metrics import MetricsLogger


class SelfPlayEnv(MahjongEnv):
    """MahjongEnv whose three opponents are redrawn from a league on every reset."""

    def __init__(self, seed: int, rule_share: float = 0.7, cache: int = 4,
                 snapshot_temperature: float = 0.3, reward: str = "potential") -> None:
        super().__init__(rotate_seat=True, seed=seed, reward_config=REWARD_PRESETS[reward])
        self.rule_share = rule_share
        self.snapshots: list[str] = []
        self._loaded: OrderedDict[str, Any] = OrderedDict()
        self._cache = cache
        self._pick = random.Random(seed)
        self.snapshot_temperature = snapshot_temperature

    def add_snapshot(self, path: str) -> None:
        self.snapshots.append(path)

    def _snapshot(self, path: str) -> Agent:
        if path not in self._loaded:
            self._loaded[path] = load_sb3(path)
            while len(self._loaded) > self._cache:
                self._loaded.popitem(last=False)
        self._loaded.move_to_end(path)
        return Sb3Agent(model=self._loaded[path], temperature=self.snapshot_temperature,
                        seed=self._pick.randrange(2**31))

    def _draw_opponent(self) -> Agent:
        if not self.snapshots or self._pick.random() < self.rule_share:
            spec = self._pick.choice(["rule", "rule", "rule:1.5"])
            return make_agent(spec, self._pick.randrange(2**31))
        recent = self.snapshots[-3:]
        pool = recent if self._pick.random() < 0.7 else self.snapshots
        return self._snapshot(self._pick.choice(pool))

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None
              ) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        self.opponent_agents = [self._draw_opponent() for _ in range(3)]
        return super().reset(seed=seed, options=options)


def _make_env(seed: int, rule_share: float, reward: str = "potential") -> SelfPlayEnv:
    return SelfPlayEnv(seed, rule_share, reward=reward)


class MetricsWriter(KVWriter):
    """Forward SB3 logger output to the lab's metrics.jsonl."""

    RENAME = {"train/value_loss": "value_loss", "train/policy_gradient_loss": "policy_loss",
              "train/approx_kl": "approx_kl", "train/clip_fraction": "clip_fraction",
              "train/explained_variance": "explained_variance", "train/learning_rate": "lr",
              "rollout/ep_rew_mean": "mean_episode_reward", "rollout/ep_len_mean": "episode_len",
              "time/fps": "sps"}

    def __init__(self, metrics: MetricsLogger) -> None:
        self.metrics = metrics

    def write(self, key_values: dict[str, Any], key_excluded: dict[str, Any],
              step: int = 0) -> None:
        out: dict[str, float] = {}
        for k, v in key_values.items():
            if not isinstance(v, (int, float)):
                continue
            if k == "train/entropy_loss":
                out["entropy"] = -float(v)
            elif k in self.RENAME:
                out[self.RENAME[k]] = float(v)
            elif k.startswith("eval/"):
                out[k[5:]] = float(v)
        if out:
            self.metrics.log(step, **out)

    def close(self) -> None:
        pass


class LeagueCallback(BaseCallback):
    """Snapshots for self-play, periodic evaluation against rule agents, best-model saving."""

    def __init__(self, out_dir: Path, snapshot_every: int, eval_every: int, eval_hands: int,
                 best_name: str = "sb3_best", value_warmup: int = 0) -> None:
        super().__init__()
        self.value_warmup = value_warmup
        self.out_dir = out_dir
        self.snap_dir = out_dir / "sb3_snapshots"
        self.snapshot_every = snapshot_every
        self.eval_every = eval_every
        self.eval_hands = eval_hands
        self.best_name = best_name
        self.best: dict[str, float] = {}
        self._next_snap = snapshot_every
        self._next_eval = eval_every

    def _policy_params(self) -> list[torch.nn.Parameter]:
        pol = self.model.policy
        mods = [pol.pi_features_extractor, pol.mlp_extractor.policy_net, pol.action_net]
        return [prm for m in mods for prm in m.parameters()]

    def _on_rollout_end(self) -> None:
        """Before each update: keep the cloned policy fixed while the value head warms up."""
        frozen = self.num_timesteps < self.value_warmup
        for prm in self._policy_params():
            prm.requires_grad_(not frozen)

    def _on_step(self) -> bool:
        if self.num_timesteps >= self._next_snap:
            self._next_snap += self.snapshot_every
            self.snap_dir.mkdir(parents=True, exist_ok=True)
            path = self.snap_dir / f"snap_{self.num_timesteps}.zip"
            self.model.save(path)
            self.training_env.env_method("add_snapshot", str(path))
        if self.num_timesteps >= self._next_eval:
            self._next_eval += self.eval_every
            self.run_eval()
        return True

    def run_eval(self) -> dict[str, float]:
        model = self.model
        res = evaluate(lambda s: Sb3Agent(model=model, temperature=0.1, seed=s), "rule",
                       self.eval_hands).as_dict()
        for k, v in res.items():
            self.logger.record(f"eval/{k}", v)
        self.logger.dump(self.num_timesteps)
        key = (res["eval_win_rate"], res["eval_avg_score"])
        if not self.best or key > (self.best["eval_win_rate"], self.best["eval_avg_score"]):
            self.best = {**res, "timesteps": float(self.num_timesteps)}
            path = self.out_dir / f"{self.best_name}.zip"
            model.save(path)
            path.with_suffix(".json").write_text(json.dumps(self.best, indent=2))
        return res


def behaviour_clone(model: MaskablePPO, data_path: Path, epochs: int, limit: int | None,
                    lr: float = 1e-3, batch: int = 512, chunk_hands: int = 0,
                    val_hands: int = 1000) -> float:
    """Supervised warm start of the policy on rule-agent decisions; returns val accuracy.
    With `chunk_hands` the records are streamed (first `val_hands` hands validate)."""
    from ai.training.bc_trainer import build_dataset, iter_chunks

    rng = np.random.default_rng(0)
    if chunk_hands:
        val_data = build_dataset(data_path, val_hands)

        def train_sets() -> Iterator[dict[str, np.ndarray]]:
            return iter_chunks(data_path, chunk_hands, skip=val_hands)
    else:
        data = build_dataset(data_path, limit)
        idx = rng.permutation(len(data["actions"]))
        cut = max(1, len(idx) // 10)
        val_data = {k: v[idx[:cut]] for k, v in data.items()}
        train_only = {k: v[idx[cut:]] for k, v in data.items()}

        def train_sets() -> Iterator[dict[str, np.ndarray]]:
            return iter([train_only])

    policy = model.policy
    opt = torch.optim.Adam(policy.parameters(), lr=lr)

    def dist(t: dict[str, torch.Tensor], ids: Any) -> Any:
        obs = {"tiles": t["tiles"][ids], "scalars": t["scalars"][ids]}
        return policy.get_distribution(obs, action_masks=t["masks"][ids].numpy())

    vt = {k: torch.from_numpy(v) for k, v in val_data.items()}
    n_val = len(val_data["actions"])
    acc = 0.0
    for _ in range(epochs):
        for chunk in train_sets():
            t = {k: torch.from_numpy(v) for k, v in chunk.items()}
            order = rng.permutation(len(chunk["actions"]))
            policy.train()
            for i in range(0, len(order), batch):
                b = order[i:i + batch]
                loss = -dist(t, b).log_prob(t["actions"][b]).mean()
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
                opt.step()
        policy.eval()
        hits = 0.0
        with torch.no_grad():
            for i in range(0, n_val, batch):
                b = np.arange(i, min(i + batch, n_val))
                pred = dist(vt, b).distribution.logits.argmax(1)
                hits += float((pred == vt["actions"][b]).float().sum())
        acc = hits / n_val
        print(f"bc epoch acc {acc:.3f}", flush=True)
    return acc


def build_model(env: VecEnv, lr: float, n_steps: int, batch: int, seed: int,
                use_transformer: bool = False) -> MaskablePPO:
    return MaskablePPO(
        "MultiInputPolicy", env, learning_rate=lr, n_steps=n_steps, batch_size=batch,
        n_epochs=4, gamma=0.99, gae_lambda=0.95, clip_range=0.1, ent_coef=0.001,
        vf_coef=0.5, max_grad_norm=0.5, target_kl=0.015, seed=seed, device="cpu", verbose=0,
        policy_kwargs={"features_extractor_class": MahjongExtractor,
                       "features_extractor_kwargs": {"use_transformer": use_transformer},
                       "net_arch": {"pi": [], "vf": [128]},
                       # a separate value encoder keeps value learning from moving the
                       # cloned policy's features
                       "share_features_extractor": False, "ortho_init": False},
    )


def train(steps: int, envs: int, out_dir: Path, run: str, *, bc_data: Path | None = None,
          bc_epochs: int = 8, bc_limit: int | None = None, lr: float = 3e-5,
          n_steps: int = 512, batch: int = 1024, rule_share: float = 0.7,
          value_warmup: int = 100_000, bc_chunk_hands: int = 0, reward: str = "potential",
          snapshot_every: int = 100_000, eval_every: int = 100_000, eval_hands: int = 200,
          seed: int = 0, subprocess: bool = True, init: Path | None = None) -> dict[str, float]:
    factories = [functools.partial(_make_env, seed * 1000 + i, rule_share, reward)
                 for i in range(envs)]
    vec: VecEnv = SubprocVecEnv(factories) if subprocess and envs > 1 else DummyVecEnv(factories)
    config = {"kind": "sb3_maskable_ppo", "steps": steps, "envs": envs, "lr": lr,
              "n_steps": n_steps, "batch": batch, "rule_share": rule_share,
              "bc_data": str(bc_data) if bc_data else None, "init": str(init) if init else None,
              "value_warmup": value_warmup, "reward": reward}
    metrics = MetricsLogger(run, config)
    if init is not None:
        model = MaskablePPO.load(str(init), env=vec, device="cpu", learning_rate=lr)
    else:
        model = build_model(vec, lr, n_steps, batch, seed)
    model.set_logger(Logger(None, [MetricsWriter(metrics)]))
    out_dir.mkdir(parents=True, exist_ok=True)
    cb = LeagueCallback(out_dir, snapshot_every, eval_every, eval_hands,
                        value_warmup=value_warmup)
    cb.init_callback(model)
    if bc_data is not None:
        acc = behaviour_clone(model, bc_data, bc_epochs, bc_limit, chunk_hands=bc_chunk_hands)
        metrics.log(0, bc_val_acc=acc)
        model.save(out_dir / "sb3_bc.zip")  # reuse with --init to skip cloning next time
        cb.run_eval()  # the cloned policy is the first "best"
    t0 = time.time()
    model.learn(total_timesteps=steps, callback=cb, reset_num_timesteps=init is None)
    cb.run_eval()
    model.save(out_dir / "sb3_last.zip")
    metrics.log(model.num_timesteps, wall_seconds=time.time() - t0)
    metrics.close()
    vec.close()
    return cb.best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", type=int, default=2_000_000)
    ap.add_argument("--envs", type=int, default=8)
    ap.add_argument("--out-dir", type=Path, default=Path("checkpoints"))
    ap.add_argument("--run", default=f"sb3-{int(time.time())}")
    ap.add_argument("--bc-data", type=Path, default=None)
    ap.add_argument("--bc-epochs", type=int, default=8)
    ap.add_argument("--bc-limit", type=int, default=None)
    ap.add_argument("--bc-chunk-hands", type=int, default=0,
                    help="stream large BC record files this many hands at a time")
    ap.add_argument("--init", type=Path, default=None, help="continue from a saved zip")
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--n-steps", type=int, default=512, help="rollout length per env")
    ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--rule-share", type=float, default=0.7)
    ap.add_argument("--reward", choices=list(REWARD_PRESETS), default="potential")
    ap.add_argument("--value-warmup", type=int, default=100_000,
                    help="steps that train only the value network")
    ap.add_argument("--snapshot-every", type=int, default=100_000)
    ap.add_argument("--eval-every", type=int, default=100_000)
    ap.add_argument("--eval-hands", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    best = train(args.steps, args.envs, args.out_dir, args.run, bc_data=args.bc_data,
                 bc_epochs=args.bc_epochs, bc_limit=args.bc_limit, lr=args.lr,
                 n_steps=args.n_steps, batch=args.batch, rule_share=args.rule_share,
                 value_warmup=args.value_warmup, bc_chunk_hands=args.bc_chunk_hands,
                 reward=args.reward,
                 snapshot_every=args.snapshot_every, eval_every=args.eval_every,
                 eval_hands=args.eval_hands, seed=args.seed, init=args.init)
    print(json.dumps(best, indent=2))


if __name__ == "__main__":
    main()
