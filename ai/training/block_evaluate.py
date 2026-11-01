"""Reproducible paired four-seat deal blocks with block-level uncertainty."""
from __future__ import annotations

import random
from typing import Any

import numpy as np

from ai.simulate import make_agent
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game


def _hand(spec: str, opponent: str, seed: int, seat: int,
          cache: dict[tuple[str, int], Any]) -> dict[str, int]:
    agents = []
    for p in range(4):
        name = spec if p == seat else opponent
        key = (name, p)
        if key not in cache:
            cache[key] = make_agent(name, seed * 4 + p)
        agent = cache[key]
        # Reset per hand so process scheduling and previously evaluated deals cannot
        # change action sampling. Supports the rule/random/neural evaluation pool.
        rng = getattr(agent, 'rng', None)
        if isinstance(rng, random.Random):
            rng.seed(seed * 4 + p)
        gen = getattr(agent, 'gen', None)
        if gen is not None:
            gen.manual_seed(seed * 4 + p)
        agents.append(agent)
    game = new_game(seed=seed)
    while game.phase is not Phase.ENDED:
        p = acting_players(game)[0]
        game, _ = apply_action(game, p, agents[p].act(game, p, get_legal_actions(game, p)))
    assert game.result is not None
    r = game.result
    return {'score': int(r['payments'][seat]),
            'win': int(r.get('winner') == seat),
            'deal_in': int(r.get('loser') == seat and not r.get('self_draw'))}


def play_block(candidate: str, baseline: str, opponent: str, seed: int,
               cache: dict[tuple[str, int], Any] | None = None) -> dict[str, Any]:
    """One shuffled wall, each candidate/baseline occupying all four seats separately."""
    cache = {} if cache is None else cache
    pairs = [(_hand(candidate, opponent, seed, seat, cache),
              _hand(baseline, opponent, seed, seat, cache)) for seat in range(4)]
    differences = [a['score'] - b['score'] for a, b in pairs]
    return {'seed': seed, 'hands': 8, 'differences': differences,
            'mean_difference': sum(differences) / 4, 'pairs': pairs}


def bootstrap_interval(block_means: list[float], seed: int = 0,
                       resamples: int = 2000) -> tuple[float, float]:
    """Percentile 95% interval resampling complete independent deal blocks."""
    if not block_means or resamples < 1:
        raise ValueError('nonempty blocks and positive resamples required')
    values = np.asarray(block_means, dtype=float)
    rng = np.random.default_rng(seed)
    means = values[rng.integers(len(values), size=(resamples, len(values)))].mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return float(low), float(high)
