"""Learned deal-in danger: P(a tile is one of an opponent's waits) from public information.

Self-play knows every hidden hand, so at each discard decision we can label all 34 tiles
exactly (is it a wait of any opponent right now?) while the model only sees what the seat
sees: each opponent's discards (and the latest ones), melds, whether they declared ready
and what they let pass since, how many copies of each tile are visible, and the wall left.
Training on a pool that includes opponents who never declare teaches it to read silent
ready hands, which is what people do.

    uv run python -m ai.danger_model generate --hands 8000 --out data/danger/v1.npz
    uv run python -m ai.danger_model train --data data/danger/v1.npz --out checkpoints/danger_v1.pt
"""

from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from ai.danger import safe_against
from engine import tiles
from engine.game import GameState, Phase, acting_players, apply_action, get_legal_actions, new_game
from engine.hand import MeldType
from engine.ting import waiting_tiles

N_TILES = 34
PER_OPP = 34 * 4 + 3
N_FEATURES = 3 * PER_OPP + 34 + 1
POOL = ("rule", "rulex:declare=never", "rulex:calls=near", "rulex:flush=13")


def features(state: GameState, seat: int) -> np.ndarray:
    """Public view of `seat` (raw counts, uint8-friendly; scaled in the model)."""
    x = np.zeros(N_FEATURES, dtype=np.float32)
    seen = tiles.to_counts(state.hands[seat])
    for p in range(4):
        for t in state.discards[p]:
            if t < N_TILES:
                seen[t] += 1
        for m in state.melds[p]:
            hidden = m.type is MeldType.AN_KONG and p != seat
            for t in m.tiles:
                if not hidden and t is not None and t < N_TILES:
                    seen[t] += 1
    for k in range(3):
        p = (seat + 1 + k) % 4
        base = k * PER_OPP
        river = [t for t in state.discards[p] if t < N_TILES]
        for t in river:
            x[base + t] += 1
        for t in river[-6:]:
            x[base + 34 + t] += 1
        for t in safe_against(state, p):
            if t < N_TILES:
                x[base + 68 + t] = 1
        for m in state.melds[p]:
            if m.type is MeldType.AN_KONG:
                continue
            for t in m.tiles:
                if t is not None and t < N_TILES:
                    x[base + 102 + t] += 1
        x[base + 136] = len(state.melds[p])
        x[base + 137] = len(river)
        x[base + 138] = float(state.declared_ting[p])
    x[3 * PER_OPP: 3 * PER_OPP + 34] = seen
    x[-1] = state.drawable()
    return x


def labels(state: GameState, seat: int) -> np.ndarray:
    """1 for every tile that is a wait of at least one opponent right now (oracle)."""
    y = np.zeros(N_TILES, dtype=np.uint8)
    for p in range(4):
        if p == seat:
            continue
        hand = state.hands[p]
        if len(hand) % 3 != 1:
            continue
        for w in waiting_tiles(tiles.to_counts(hand), len(state.melds[p])):
            y[w] = 1
    return y


def _gen_chunk(args: tuple[list[int], int]) -> tuple[np.ndarray, np.ndarray]:
    from ai.simulate import make_agent

    seeds, _ = args
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    for seed in seeds:
        agents = [make_agent(POOL[(seed + p) % len(POOL)], seed * 4 + p) for p in range(4)]
        s = new_game(seed=seed)
        while s.phase is not Phase.ENDED:
            p = acting_players(s)[0]
            if s.phase is Phase.DISCARD and s.turn == p:
                xs.append(features(s, p).astype(np.uint8))
                ys.append(labels(s, p))
            s, _ = apply_action(s, p, agents[p].act(s, p, get_legal_actions(s, p)))
    return np.stack(xs), np.stack(ys)


def generate(hands: int, out: Path, workers: int, seed: int = 200_000) -> None:
    seeds = list(range(seed, seed + hands))
    jobs = [(seeds[i::workers], i) for i in range(workers)]
    t0 = time.time()
    with ProcessPoolExecutor(workers) as pool:
        parts = list(pool.map(_gen_chunk, jobs))
    x = np.concatenate([p[0] for p in parts])
    y = np.concatenate([p[1] for p in parts])
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, x=x, y=y)
    print(f"{len(x)} samples from {hands} hands in {time.time() - t0:.0f}s; "
          f"{y.mean():.3f} of tiles are waits → {out}")


# ------------------------------------------------------------------ model
def _scale() -> np.ndarray:
    s = np.ones(N_FEATURES, dtype=np.float32)
    for k in range(3):
        base = k * PER_OPP
        s[base:base + 34] = 0.25
        s[base + 102:base + 136] = 0.25
        s[base + 136] = 0.2
        s[base + 137] = 1 / 30
    s[3 * PER_OPP:3 * PER_OPP + 34] = 0.25
    s[-1] = 1 / 100
    return s


def build_model(hidden: int = 256) -> Any:
    import torch

    return torch.nn.Sequential(
        torch.nn.Linear(N_FEATURES, hidden), torch.nn.ReLU(),
        torch.nn.Linear(hidden, hidden), torch.nn.ReLU(),
        torch.nn.Linear(hidden, N_TILES),
    )


def train(data: Path, out: Path, epochs: int = 8, batch: int = 1024, lr: float = 1e-3,
          device: str = "auto", seed: int = 0) -> dict[str, float]:
    import torch

    from ai.training.device import pick_device

    torch.manual_seed(seed)
    dev = pick_device(device)
    d = np.load(data)
    x = torch.from_numpy(d["x"].astype(np.float32) * _scale())
    y = torch.from_numpy(d["y"].astype(np.float32))
    n = len(x)
    idx = torch.randperm(n)
    n_val = max(1, n // 20)
    val, tr = idx[:n_val], idx[n_val:]
    model = build_model().to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    lossf = torch.nn.BCEWithLogitsLoss()
    base_rate = float(y[tr].mean())
    best = {"val_loss": float("inf")}
    for epoch in range(1, epochs + 1):
        model.train()
        perm = tr[torch.randperm(len(tr))]
        for i in range(0, len(perm), batch):
            b = perm[i:i + batch]
            loss = lossf(model(x[b].to(dev)), y[b].to(dev))
            opt.zero_grad()
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            logits = torch.cat([model(x[val[i:i + 8192]].to(dev)).cpu()
                                for i in range(0, n_val, 8192)])
            vl = float(lossf(logits, y[val]))
            # how much better than always predicting the base rate
            p0 = torch.full_like(y[val], base_rate)
            base_loss = float(torch.nn.functional.binary_cross_entropy(p0, y[val]))
        print(f"epoch {epoch}: val loss {vl:.4f} (base rate {base_loss:.4f})", flush=True)
        if vl < best["val_loss"]:
            best = {"val_loss": vl, "base_loss": base_loss, "epoch": epoch}
            out.parent.mkdir(parents=True, exist_ok=True)
            state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
            torch.save({"state_dict": state, "n_features": N_FEATURES, **best}, out)
    return best


@lru_cache(maxsize=4)
def _load(path: str) -> Any:
    import torch

    torch.set_num_threads(1)  # many evaluation workers run side by side
    model = build_model()
    ck = torch.load(path, map_location="cpu", weights_only=False)
    model.load_state_dict(ck["state_dict"])
    model.eval()
    return model


_SCALE = _scale()


def predict(path: str, state: GameState, seat: int) -> np.ndarray:
    """P(each tile is a wait of some opponent) from `seat`'s view."""
    import torch

    model = _load(path)
    with torch.no_grad():
        logits = model(torch.from_numpy(features(state, seat) * _SCALE)[None])[0]
    return torch.sigmoid(logits).numpy()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--hands", type=int, default=8000)
    g.add_argument("--out", type=Path, default=Path("data/danger/v1.npz"))
    g.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    t = sub.add_parser("train")
    t.add_argument("--data", type=Path, default=Path("data/danger/v1.npz"))
    t.add_argument("--out", type=Path, default=Path("checkpoints/danger_v1.pt"))
    t.add_argument("--epochs", type=int, default=8)
    t.add_argument("--device", default="auto")
    args = ap.parse_args()
    if args.cmd == "generate":
        generate(args.hands, args.out, args.workers)
    else:
        print(train(args.data, args.out, args.epochs, device=args.device))


if __name__ == "__main__":
    main()
