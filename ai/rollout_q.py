"""Rollout Q distillation: learn which discard pays, from rollouts of the true game.

At sampled discard decisions in Lv5 self-play, every distinct legal discard is played out to
the end of the hand from the *real* state (true wall and hands) by four Lv5 agents with the
same seeds, so the only difference between two rollouts is the discard itself. A network
that sees only the discarding seat's public view is trained to predict each discard's payoff
relative to the mean over the candidates. Averaged over many positions that is the
discard's value under hidden information, which is what perfect-information Monte Carlo
tries to estimate at play time, but learned once from correct samples instead of guessed
ones, and answered with one forward pass.

The agent plays Lv5 everywhere except the choice of discard, where it switches to the
network's pick only when that is predicted to be at least `margin` points better.

    uv run python -m ai.rollout_q generate --hands 20000 --out data/rollq/v1.npz
    uv run python -m ai.rollout_q train --data data/rollq/v1.npz --out checkpoints/rollq_v1.pt
    uv run python -m ai.training.duplicate rollq:checkpoints/rollq_v1.pt --baseline lv5
"""

from __future__ import annotations

import argparse
import os
import random
import time
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from ai.agents import LEVEL5_PARAMS
from ai.agents.rule_agent import RuleAgent
from ai.features import encode
from engine.actions import Action, ActionType
from engine.game import GameState, Phase, acting_players, apply_action, get_legal_actions, new_game

GEN_SEED = 400_000
TOP_K = 6  # only Lv5's best few discards are compared; the rest are rarely right


def _lv5(seed: int) -> RuleAgent:
    return RuleAgent(0.0, seed, params=LEVEL5_PARAMS)


def _rollout(state: GameState, seat: int, seed: int) -> int:
    agents = [_lv5(seed * 4 + p) for p in range(4)]  # same seeds for every candidate
    s = state
    while s.phase is not Phase.ENDED:
        p = acting_players(s)[0]
        s, _ = apply_action(s, p, agents[p].act(s, p, get_legal_actions(s, p)))
    assert s.result is not None
    return int(s.result["payments"][seat])


def candidates(agent: RuleAgent, state: GameState, seat: int, legal: list[Action]) -> list[int]:
    """The discards Lv5 rates highest (by its own scores), at most TOP_K distinct tiles."""
    scored = agent.scores(state, seat, legal)
    best: dict[int, float] = {}
    for a, v in scored.items():
        if a.type in (ActionType.DISCARD, ActionType.TING) and a.tile is not None:
            best[a.tile] = max(v, best.get(a.tile, -1e18))
    legal_tiles = {a.tile for a in legal if a.type is ActionType.DISCARD}
    ranked = sorted((t for t in best if t in legal_tiles), key=lambda t: -best[t])
    return ranked[:TOP_K]


def label(state: GameState, seat: int, tiles: list[int], seed: int) -> np.ndarray:
    """Payoff of each candidate discard (NaN for the other tiles)."""
    q = np.full(34, np.nan, dtype=np.float32)
    for t in tiles:
        nxt, _ = apply_action(state, seat, Action(ActionType.DISCARD, t))
        q[t] = _rollout(nxt, seat, seed)
    return q


def _gen_chunk(args: tuple[list[int], float]) -> dict[str, np.ndarray]:
    seeds, rate = args
    tiles: list[np.ndarray] = []
    scal: list[np.ndarray] = []
    qs: list[np.ndarray] = []
    chosen: list[int] = []
    for seed in seeds:
        rng = random.Random(seed)
        agents = [_lv5(seed * 4 + p) for p in range(4)]
        s = new_game(seed=seed)
        while s.phase is not Phase.ENDED:
            p = acting_players(s)[0]
            legal = get_legal_actions(s, p)
            a = agents[p].act(s, p, legal)
            if (s.phase is Phase.DISCARD and s.turn == p and rng.random() < rate
                    and a.type in (ActionType.DISCARD, ActionType.TING)):
                q = label(s, p, candidates(agents[p], s, p, legal), seed * 131 + len(qs))
                if np.count_nonzero(~np.isnan(q)) >= 2:
                    t, sc = encode(s, p)
                    tiles.append(t.astype(np.float16))
                    scal.append(sc.astype(np.float16))
                    qs.append(q)
                    chosen.append(a.tile if a.tile is not None else -1)
            s, _ = apply_action(s, p, a)
    if not qs:
        return {}
    return {"tiles": np.stack(tiles), "scalars": np.stack(scal), "q": np.stack(qs),
            "chosen": np.array(chosen, dtype=np.int8)}


def generate(hands: int, out: Path, workers: int, rate: float = 0.08,
             start: int = GEN_SEED) -> None:
    seeds = list(range(start, start + hands))
    per = max(1, min(50, hands // (workers * 4) or 1))
    jobs = [(seeds[i:i + per], rate) for i in range(0, len(seeds), per)]
    parts: list[dict[str, np.ndarray]] = []
    t0 = time.time()
    with ProcessPoolExecutor(workers) as ex:
        for k, part in enumerate(ex.map(_gen_chunk, jobs), 1):
            if part:
                parts.append(part)
            if k % 20 == 0 or k == len(jobs):
                n = sum(len(x["q"]) for x in parts)
                print(f"{k * per}/{hands} hands, {n} positions, {time.time() - t0:.0f}s",
                      flush=True)
    data = {key: np.concatenate([x[key] for x in parts]) for key in parts[0]}
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, **data)
    print(f"{len(data['q'])} positions from {hands} hands → {out}")


# ------------------------------------------------------------------ model
def build_model(init: str | None = None) -> Any:
    import torch

    from ai.models.backbone import LATENT, MahjongEncoder

    class QNet(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = MahjongEncoder()
            self.head = torch.nn.Sequential(torch.nn.Linear(LATENT, 256), torch.nn.ReLU(),
                                            torch.nn.Linear(256, 34))

        def forward(self, tiles: torch.Tensor, scalars: torch.Tensor) -> torch.Tensor:
            out: torch.Tensor = self.head(self.encoder(tiles, scalars))
            return out

    net = QNet()
    if init:  # start from a policy network's encoder (it already reads the table)
        from ai.agents.neural_agent import load_model

        model, _ = load_model(Path(init))
        net.encoder.load_state_dict(model.encoder.state_dict())
    return net


def _centered(pred: Any, mask: Any) -> Any:
    """Predictions relative to their mean over the candidate discards."""
    import torch

    m = mask.float()
    mean = (pred * m).sum(1, keepdim=True) / m.sum(1, keepdim=True)
    return torch.where(mask, pred - mean, torch.zeros_like(pred))


def train(data: Path, out: Path, init: str | None, epochs: int = 12, batch: int = 512,
          lr: float = 3e-4, device: str = "auto", seed: int = 0) -> dict[str, float]:
    import torch

    from ai.training.device import pick_device

    torch.manual_seed(seed)
    dev = pick_device(device)
    d = np.load(data)
    tiles = torch.from_numpy(d["tiles"].astype(np.float32))
    scal = torch.from_numpy(d["scalars"].astype(np.float32))
    q = torch.from_numpy(d["q"])
    mask = ~torch.isnan(q)
    qz = torch.nan_to_num(q)
    target = _centered(qz, mask) / 100.0  # points → roughly unit scale
    n = len(q)
    idx = torch.randperm(n)
    n_val = max(256, n // 10)
    val, tr = idx[:n_val], idx[n_val:]
    net = build_model(init).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)

    def loss_on(ix: torch.Tensor) -> torch.Tensor:
        b_mask = mask[ix].to(dev)
        pred = _centered(net(tiles[ix].to(dev), scal[ix].to(dev)), b_mask)
        err = (pred - target[ix].to(dev)) ** 2
        return (err * b_mask).sum() / b_mask.sum()

    def evaluate() -> dict[str, float]:
        """Validation loss, and how much the network's pick gains over Lv5's own choice."""
        net.eval()
        with torch.no_grad():
            losses, gain, agree, k = [], 0.0, 0, 0
            for i in range(0, n_val, 4096):
                ix = val[i:i + 4096]
                losses.append(float(loss_on(ix)) * len(ix))
                b_mask = mask[ix].to(dev)
                pred = net(tiles[ix].to(dev), scal[ix].to(dev)).masked_fill(~b_mask, -1e9)
                pick = pred.argmax(1).cpu()
                ch = torch.from_numpy(d["chosen"][ix.numpy()].astype(np.int64))
                ok = ch >= 0
                qv = qz[ix]
                rows = torch.arange(len(ix))
                gain += float((qv[rows, pick] - qv[rows, ch.clamp(min=0)])[ok].sum())
                agree += int((pick == ch)[ok].sum())
                k += int(ok.sum())
        net.train()
        base = float(((target[val] ** 2) * mask[val]).sum() / mask[val].sum())
        return {"val_loss": sum(losses) / n_val, "base_loss": base,
                "gain_vs_lv5": gain / max(1, k), "agree_lv5": agree / max(1, k)}

    best: dict[str, float] = {"val_loss": float("inf")}
    for epoch in range(1, epochs + 1):
        perm = tr[torch.randperm(len(tr))]
        for i in range(0, len(perm), batch):
            loss = loss_on(perm[i:i + batch])
            opt.zero_grad()
            loss.backward()
            opt.step()
        sched.step()
        m = evaluate()
        print(f"epoch {epoch}: val {m['val_loss']:.4f} (predict-zero {m['base_loss']:.4f}), "
              f"pick vs Lv5 {m['gain_vs_lv5']:+.2f} points, agree {m['agree_lv5']:.1%}",
              flush=True)
        if m["val_loss"] < best["val_loss"]:
            best = {**m, "epoch": epoch}
            out.parent.mkdir(parents=True, exist_ok=True)
            state = {k: v.detach().cpu() for k, v in net.state_dict().items()}
            torch.save({"state_dict": state, **best}, out)
    return best


@lru_cache(maxsize=4)
def _load(path: str) -> Any:
    import torch

    torch.set_num_threads(1)
    net = build_model()
    ck = torch.load(path, map_location="cpu", weights_only=False)
    net.load_state_dict(ck["state_dict"])
    net.eval()
    return net


class RolloutQAgent(RuleAgent):
    """Lv5, except the discard, which follows the network when it is clearly better."""

    def __init__(self, path: str, margin: float = 3.0, seed: int | None = None) -> None:
        super().__init__(0.0, seed, params=LEVEL5_PARAMS)
        self.path = path
        self.margin = margin / 100.0

    def act(self, state: GameState, seat: int, legal: list[Action]) -> Action:
        a = super().act(state, seat, legal)
        if a.type not in (ActionType.DISCARD, ActionType.TING) or a.tile is None:
            return a
        tiles = candidates(self, state, seat, legal)
        if len(tiles) < 2 or a.tile not in tiles:
            return a
        import torch

        t, sc = encode(state, seat)
        with torch.no_grad():
            pred = _load(self.path)(torch.from_numpy(t)[None], torch.from_numpy(sc)[None])[0]
        best = max(tiles, key=lambda x: float(pred[x]))
        if best == a.tile or float(pred[best]) - float(pred[a.tile]) < self.margin:
            return a
        ting = Action(ActionType.TING, best)
        if a.type is ActionType.TING and ting in legal:
            return ting
        return Action(ActionType.DISCARD, best)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--hands", type=int, default=20000)
    g.add_argument("--out", type=Path, required=True)
    g.add_argument("--rate", type=float, default=0.08, help="share of discards to label")
    g.add_argument("--start", type=int, default=GEN_SEED)
    g.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    t = sub.add_parser("train")
    t.add_argument("--data", type=Path, nargs="+", required=True)
    t.add_argument("--out", type=Path, required=True)
    t.add_argument("--init", default="checkpoints/bc_lv5.pt")
    t.add_argument("--epochs", type=int, default=12)
    t.add_argument("--device", default="auto")
    args = ap.parse_args()
    if args.cmd == "generate":
        generate(args.hands, args.out, args.workers, args.rate, args.start)
    else:
        data = args.data[0]
        if len(args.data) > 1:  # merge several generated files
            parts = [np.load(p) for p in args.data]
            merged = args.out.with_suffix(".merged.npz")
            np.savez(merged, **{k: np.concatenate([p[k] for p in parts]) for k in parts[0].files})
            data = merged
        print(train(data, args.out, args.init or None, args.epochs, device=args.device))


if __name__ == "__main__":
    main()
