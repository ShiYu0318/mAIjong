"""Batch self-play simulation with per-seat statistics.

Agent specs: "random", "rule" (T=0), "rule:1.5", "lv1".."lv5", and any extra specs
registered with `register_agent` (e.g. neural agents loading checkpoints).

Records are stored compactly as {"seed", "agents", "actions": [[player, action_id], …]}:
the engine is deterministic, so every intermediate state can be replayed exactly.
"""

from __future__ import annotations

import contextlib
import gzip
import json
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai.agents import Agent, RandomAgent, RuleAgent, create_agent
from engine.actions import decode_action, encode_action
from engine.game import GameState, Phase, acting_players, apply_action, get_legal_actions, new_game

AgentFactory = Callable[[str, int], Agent]
_REGISTRY: dict[str, AgentFactory] = {}


def register_agent(prefix: str, factory: AgentFactory) -> None:
    _REGISTRY[prefix] = factory


def make_agent(spec: str, seed: int) -> Agent:
    name, _, arg = spec.partition(":")
    if name == "random":
        return RandomAgent(seed)
    if name == "rule":
        return RuleAgent(float(arg) if arg else 0.0, seed)
    if name.startswith("lv") and name[2:].isdigit():
        return create_agent(int(name[2:]), seed)
    if name in _REGISTRY:
        return _REGISTRY[name](arg, seed)
    raise ValueError(f"unknown agent spec {spec!r}")


def play_hand(agents: list[Agent], seed: int) -> tuple[GameState, list[list[int]]]:
    s = new_game(seed=seed)
    actions: list[list[int]] = []
    while s.phase is not Phase.ENDED:
        p = acting_players(s)[0]
        a = agents[p].act(s, p, get_legal_actions(s, p))
        actions.append([p, encode_action(a)])
        s, _ = apply_action(s, p, a)
    return s, actions


def replay_states(seed: int, actions: list[list[int]]) -> Iterator[tuple[GameState, int, int]]:
    """Yield (state before action, player, action_id) for a recorded hand."""
    s = new_game(seed=seed)
    for p, aid in actions:
        yield s, p, aid
        s, _ = apply_action(s, p, decode_action(aid))


@dataclass
class SeatStats:
    hands: int = 0
    wins: int = 0
    self_draws: int = 0
    deal_ins: int = 0
    tai_on_win: int = 0
    score: int = 0

    def add(self, other: SeatStats) -> None:
        for k in self.__dataclass_fields__:
            setattr(self, k, getattr(self, k) + getattr(other, k))

    def summary(self) -> dict[str, float]:
        n = max(1, self.hands)
        return {
            "hands": self.hands,
            "win_rate": self.wins / n,
            "self_draw_rate": self.self_draws / n,
            "deal_in_rate": self.deal_ins / n,
            "avg_tai_on_win": self.tai_on_win / max(1, self.wins),
            "avg_score": self.score / n,
        }


@dataclass
class BatchResult:
    agents: list[str]
    seats: list[SeatStats] = field(default_factory=lambda: [SeatStats() for _ in range(4)])
    draws: int = 0
    hands: int = 0

    def merge(self, other: BatchResult) -> None:
        for a, b in zip(self.seats, other.seats, strict=True):
            a.add(b)
        self.draws += other.draws
        self.hands += other.hands

    def summary(self) -> dict[str, Any]:
        return {
            "hands": self.hands,
            "draw_rate": self.draws / max(1, self.hands),
            "seats": [{"agent": a, **s.summary()} for a, s in
                      zip(self.agents, self.seats, strict=True)],
        }


def _record(res: BatchResult, s: GameState) -> None:
    res.hands += 1
    r = s.result
    assert r is not None
    for p in range(4):
        st = res.seats[p]
        st.hands += 1
        st.score += r["payments"][p]
    if r["kind"] == "DRAW":
        res.draws += 1
        return
    w = r["winner"]
    res.seats[w].wins += 1
    res.seats[w].tai_on_win += sum(i["tai"] for i in r["tai_breakdown"])
    if r["self_draw"]:
        res.seats[w].self_draws += 1
    elif r.get("loser") is not None:
        res.seats[r["loser"]].deal_ins += 1


def _run_chunk(args: tuple[list[str], list[int], bool, int]) -> tuple[BatchResult, list[str]]:
    specs, seeds, keep, rotate = args
    res = BatchResult(list(specs))
    lines: list[str] = []
    for seed in seeds:
        # rotate seats so no agent always sits as the first dealer
        shift = seed % 4 if rotate else 0
        order = [specs[(p - shift) % 4] for p in range(4)]
        agents = [make_agent(spec, seed * 4 + i) for i, spec in enumerate(order)]
        s, actions = play_hand(agents, seed)
        rotated = BatchResult(order)
        _record(rotated, s)
        for p in range(4):
            res.seats[(p - shift) % 4].add(rotated.seats[p])
        res.draws += rotated.draws
        res.hands += 1
        if keep:
            lines.append(json.dumps({"seed": seed, "agents": order, "actions": actions,
                                     "result": s.result}, ensure_ascii=False))
    return res, lines


def run_batch(
    specs: list[str],
    n_hands: int,
    seed: int = 0,
    workers: int = 1,
    save_path: Path | None = None,
    rotate: bool = True,
    progress: Callable[[int], None] | None = None,
) -> BatchResult:
    if len(specs) != 4:
        raise ValueError("need four agent specs")
    seeds = list(range(seed, seed + n_hands))
    chunk = max(1, min(200, n_hands // max(1, workers * 4)))
    jobs = [(specs, seeds[i:i + chunk], save_path is not None, int(rotate))
            for i in range(0, n_hands, chunk)]
    total = BatchResult(list(specs))
    done = 0
    with contextlib.ExitStack() as stack:
        out = stack.enter_context(gzip.open(save_path, "wt", encoding="utf-8")) \
            if save_path else None
        if workers <= 1:
            results: Iterator[tuple[BatchResult, list[str]]] = map(_run_chunk, jobs)
        else:
            pool = stack.enter_context(ProcessPoolExecutor(workers))
            results = pool.map(_run_chunk, jobs)
        for res, lines in results:
            total.merge(res)
            if out is not None:
                for line in lines:
                    out.write(line + "\n")
            done += res.hands
            if progress:
                progress(done)
    return total


def read_records(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
