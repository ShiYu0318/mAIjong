"""Action-complete oracle training labels; student inputs must remain player-visible."""
from __future__ import annotations

import random

import numpy as np

from ai.rollout_q import _rollout
from engine.actions import N_ACTIONS, Action, ActionType, encode_action
from engine.game import apply_action


def action_candidates(agent, state, seat, legal, teacher, limit=6):
    """Keep the actual teacher action and explicit declaration/claim alternatives."""
    if limit < 2 or teacher not in legal:
        raise ValueError('At least two candidate slots and a legal teacher action required')
    chosen = [teacher]
    if teacher.type is ActionType.TING:
        alternate = Action(ActionType.DISCARD, teacher.tile)
        if alternate in legal:
            chosen.append(alternate)
    elif teacher.type is ActionType.DISCARD:
        alternate = Action(ActionType.TING, teacher.tile)
        if alternate in legal:
            chosen.append(alternate)
    passing = Action(ActionType.PASS)
    if passing in legal and passing not in chosen:
        chosen.append(passing)
    scores = agent.scores(state, seat, legal)
    for action in sorted(legal, key=lambda a: (-scores[a], encode_action(a))):
        if len(chosen) >= limit:
            break
        if action not in chosen:
            chosen.append(action)
    return chosen[:limit]


def label_actions(state, seat, actions, seed, worlds=4, rollout=_rollout):
    """Apply exact actions to identical pre-action future walls.

    Opponent concealed hands remain the real oracle training state. Only the
    future wall is averaged here; this is not a public-belief search algorithm.
    Standard errors cover paired future-wall differences, not hidden-hand or
    neural approximation uncertainty. One-world standard errors remain unknown.
    """
    if worlds < 1 or not actions:
        raise ValueError('Positive world count and nonempty actions required')
    ids = [encode_action(action) for action in actions]
    if len(set(ids)) != len(ids):
        raise ValueError('Candidate actions must be distinct')
    samples = np.full((worlds, N_ACTIONS), np.nan, dtype=np.float32)
    for world_id in range(worlds):
        world = state.clone()
        random.Random(int(seed) * 1009 + world_id).shuffle(world.wall)
        for action, aid in zip(actions, ids, strict=True):
            after, _ = apply_action(world, seat, action)
            value = float(rollout(after, seat, int(seed) + world_id))
            if not np.isfinite(value):
                raise ValueError('Nonfinite rollout payment')
            samples[world_id, aid] = value
    q = np.full(N_ACTIONS, np.nan, dtype=np.float32)
    se = np.full(N_ACTIONS, np.nan, dtype=np.float32)
    q[ids] = samples[:, ids].mean(axis=0)
    if worlds > 1:
        differences = samples[:, ids] - samples[:, ids[0]][:, None]
        se[ids] = differences.std(axis=0, ddof=1) / np.sqrt(worlds)
    return q, se, samples
