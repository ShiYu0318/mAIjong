"""Behaviour cloning warm start (SPEC 05.6.1).

1. scripts/simulate_batch.py --agents rule rule rule rule --save data/bc/rule.jsonl.gz
2. python -m ai.training.bc_trainer --data data/bc/rule.jsonl.gz --out checkpoints/bc_v1.pt

Large record files (e.g. 100k hands, ~4.7M decisions) do not fit in memory as tensors;
--chunk-hands N streams them N hands at a time (validation uses the first --val-hands).

Every decision with more than one legal action becomes a (observation, mask, action)
sample; the policy is trained with cross-entropy over the masked log-probabilities.
"""

from __future__ import annotations

import argparse
import itertools
import time
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ai.agents.neural_agent import save_checkpoint
from ai.features import encode, mask_for
from ai.models.ppo_model import ActorCritic
from ai.simulate import read_records, replay_states
from ai.training.metrics import MetricsLogger


def _samples(rec: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    tiles, scalars, masks, actions = [], [], [], []
    for state, player, aid in replay_states(rec["seed"], rec["actions"]):
        mask = mask_for(state, player)
        if mask.sum() <= 1:
            continue
        t, s = encode(state, player)
        tiles.append(t)
        scalars.append(s)
        masks.append(mask)
        actions.append(aid)
    if not actions:
        return (np.zeros((0, 34, 14), np.float32), np.zeros((0, 13), np.float32),
                np.zeros((0, 108), bool), np.zeros(0, np.int64))
    return (np.stack(tiles), np.stack(scalars), np.stack(masks),
            np.array(actions, dtype=np.int64))


def build_dataset(path: Path, limit: int | None = None, workers: int = 4
                  ) -> dict[str, np.ndarray]:
    return dataset_from_records(list(itertools.islice(read_records(path), limit)), workers)


def iter_chunks(path: Path, chunk_hands: int, skip: int = 0, workers: int = 4
                ) -> Iterator[dict[str, np.ndarray]]:
    """Tensor datasets of `chunk_hands` hands each, after skipping the first `skip`."""
    records = itertools.islice(read_records(path), skip, None)
    while batch := list(itertools.islice(records, chunk_hands)):
        yield dataset_from_records(batch, workers)


def dataset_from_records(records: list[dict[str, Any]], workers: int = 4
                         ) -> dict[str, np.ndarray]:
    parts: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]
    if workers > 1:
        with ProcessPoolExecutor(workers) as pool:
            parts = list(pool.map(_samples, records, chunksize=16))
    else:
        parts = [_samples(r) for r in records]
    return {
        "tiles": np.concatenate([p[0] for p in parts]),
        "scalars": np.concatenate([p[1] for p in parts]),
        "masks": np.concatenate([p[2] for p in parts]),
        "actions": np.concatenate([p[3] for p in parts]),
    }


def train_bc(data: dict[str, np.ndarray], out: Path, epochs: int = 50, batch: int = 512,
             lr: float = 1e-3, target_acc: float = 0.6, hierarchical: bool = True,
             run: str = "bc", seed: int = 0, log_every: int = 1) -> dict[str, float]:
    torch.manual_seed(seed)
    n = len(data["actions"])
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    n_val = max(1, n // 10)
    val, tr = idx[:n_val], idx[n_val:]
    tensors = {k: torch.from_numpy(v) for k, v in data.items()}
    config = {"hierarchical": hierarchical, "use_transformer": False}
    model = ActorCritic(**config)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    logger = MetricsLogger(run, {"kind": "bc", "samples": n, "epochs": epochs, **config})

    def run_batch(ids: np.ndarray, train: bool) -> tuple[float, float]:
        t = tensors["tiles"][ids]
        s = tensors["scalars"][ids]
        m = tensors["masks"][ids]
        a = tensors["actions"][ids]
        logp, _ = model(t, s, m)
        loss = torch.nn.functional.nll_loss(logp, a)
        if train:
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        acc = (logp.argmax(dim=1) == a).float().mean()
        return float(loss.detach()), float(acc)

    best = {"val_acc": 0.0, "epoch": 0}
    for epoch in range(1, epochs + 1):
        model.train()
        rng.shuffle(tr)
        losses = [run_batch(tr[i:i + batch], True)[0] for i in range(0, len(tr), batch)]
        model.eval()
        with torch.no_grad():
            vals = [run_batch(val[i:i + batch], False) for i in range(0, len(val), batch)]
        val_loss = float(np.mean([v[0] for v in vals]))
        val_acc = float(np.mean([v[1] for v in vals]))
        if epoch % log_every == 0:
            logger.log(epoch, train_loss=float(np.mean(losses)), val_loss=val_loss,
                       val_acc=val_acc)
        if val_acc > best["val_acc"]:
            best = {"val_acc": val_acc, "epoch": epoch}
            save_checkpoint(out, model, "bc", config, val_acc=val_acc, epoch=epoch)
        if val_acc >= target_acc:
            break
    logger.close()
    return best


def train_bc_stream(path: Path, out: Path, epochs: int = 3, chunk_hands: int = 5000,
                    val_hands: int = 1000, batch: int = 512, lr: float = 1e-3,
                    hierarchical: bool = True, run: str = "bc", workers: int = 4,
                    seed: int = 0) -> dict[str, float]:
    """Behaviour cloning over a record file too large for memory: the first `val_hands`
    hands are the validation set; the rest are streamed `chunk_hands` at a time."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    val = dataset_from_records(list(itertools.islice(read_records(path), val_hands)), workers)
    vt = {k: torch.from_numpy(v) for k, v in val.items()}
    config = {"hierarchical": hierarchical, "use_transformer": False}
    model = ActorCritic(**config)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    logger = MetricsLogger(run, {"kind": "bc", "stream": True, "chunk_hands": chunk_hands,
                                 "epochs": epochs, **config})

    def step(t: dict[str, torch.Tensor], ids: np.ndarray, train: bool) -> tuple[float, float]:
        logp, _ = model(t["tiles"][ids], t["scalars"][ids], t["masks"][ids])
        loss = torch.nn.functional.nll_loss(logp, t["actions"][ids])
        if train:
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        return float(loss.detach()), float((logp.argmax(1) == t["actions"][ids]).float().mean())

    best = {"val_acc": 0.0, "epoch": 0}
    n_val = len(val["actions"])
    logged = 0
    for epoch in range(1, epochs + 1):
        for chunk in iter_chunks(path, chunk_hands, skip=val_hands, workers=workers):
            t = {k: torch.from_numpy(v) for k, v in chunk.items()}
            idx = rng.permutation(len(chunk["actions"]))
            model.train()
            losses = [step(t, idx[i:i + batch], True)[0] for i in range(0, len(idx), batch)]
            model.eval()
            with torch.no_grad():
                vals = [step(vt, np.arange(i, min(i + batch, n_val)), False)
                        for i in range(0, n_val, batch)]
            val_acc = float(np.mean([v[1] for v in vals]))
            logged += 1
            logger.log(logged, epoch=epoch, train_loss=float(np.mean(losses)),
                       val_loss=float(np.mean([v[0] for v in vals])), val_acc=val_acc)
            if val_acc > best["val_acc"]:
                best = {"val_acc": val_acc, "epoch": epoch}
                save_checkpoint(out, model, "bc", config, val_acc=val_acc, epoch=epoch)
        print(f"epoch {epoch}: best val accuracy so far {best['val_acc']:.3f}", flush=True)
    logger.close()
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("checkpoints/bc_v1.pt"))
    ap.add_argument("--limit", type=int, default=None, help="use only the first N hands")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--target-acc", type=float, default=0.6,
                    help="stop early at this validation accuracy (SPEC: 0.6)")
    ap.add_argument("--run", default=f"bc-{int(time.time())}")
    ap.add_argument("--chunk-hands", type=int, default=0,
                    help="stream the records this many hands at a time (large files)")
    ap.add_argument("--val-hands", type=int, default=1000)
    args = ap.parse_args()
    if args.chunk_hands:
        best = train_bc_stream(args.data, args.out, epochs=args.epochs,
                               chunk_hands=args.chunk_hands, val_hands=args.val_hands,
                               run=args.run, workers=args.workers)
        print(f"best val accuracy {best['val_acc']:.3f} at epoch {best['epoch']} → {args.out}")
        return
    t0 = time.time()
    data = build_dataset(args.data, args.limit, args.workers)
    print(f"{len(data['actions'])} samples in {time.time() - t0:.0f}s")
    best = train_bc(data, args.out, epochs=args.epochs, run=args.run, target_acc=args.target_acc)
    print(f"best val accuracy {best['val_acc']:.3f} at epoch {best['epoch']} → {args.out}")


if __name__ == "__main__":
    main()
