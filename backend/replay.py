"""Rebuild replay frames from a stored hand (seed + action sequence)."""

from __future__ import annotations

from typing import Any

from backend.ws.view import masked_state, visible_event
from engine.actions import decode_action
from engine.game import GameState, apply_action, new_game
from engine.score import ScoringRules


class ReplayError(ValueError):
    pass


def _header(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[list[int]]]:
    if not records or records[0].get("type") != "META":
        raise ReplayError("missing replay header")
    meta = records[0]
    actions = meta.get("actions") or []
    if not actions:
        raise ReplayError("this replay has no action log")
    return meta, actions


def _start(meta: dict[str, Any]) -> GameState:
    """The position the recorded actions start from."""
    if meta.get("scenario"):
        from ai.explainability.analysis import _replay_to

        return _replay_to(int(meta["scenario"]["seed"]), int(meta["scenario"]["step"]))
    rules = ScoringRules(**meta["rules"]) if meta.get("rules") else ScoringRules()
    return new_game(
        int(meta["seed"]), dealer=meta["dealer"], round_wind=meta["round_wind"],
        dealer_streak=meta["dealer_streak"], scores=meta.get("scores_before"), rules=rules,
        game_id=meta["game_id"],
    )


def _event_key(ev: dict[str, Any]) -> tuple[Any, ...]:
    return (ev.get("seq"), ev.get("type"), ev.get("player"), ev.get("tile"))


def verify_records(records: list[dict[str, Any]]) -> None:
    """Re-run a stored hand from its start and action log; the event log and the result
    must match what was saved. Raises ReplayError on any difference."""
    meta, actions = _header(records)
    s = _start(meta)
    for seat, aid in actions:
        s, _ = apply_action(s, seat, decode_action(aid))
    if s.result != meta["result"]:
        raise ReplayError("replay diverged from the stored result")
    stored = [_event_key(ev) for ev in records[1:]]
    if [_event_key(ev) for ev in s.events] != stored:
        raise ReplayError("replay events differ from the stored log")


def build_frames(records: list[dict[str, Any]]) -> dict[str, Any]:
    """records: lines of a stored .jsonl replay (META first, then events)."""
    meta, actions = _header(records)
    decisions = {ev["seq"]: ev["ai_decision"] for ev in records[1:] if "ai_decision" in ev}
    s = _start(meta)
    frames: list[dict[str, Any]] = [{"index": 0, "actor": None, "action": None, "events": [],
               "view": masked_state(s, None, reveal_all=True), "decision": None}]
    for i, (seat, aid) in enumerate(actions, start=1):
        seq = len(s.events)
        action = decode_action(aid)
        s, events = apply_action(s, seat, action)
        frames.append({
            "index": i,
            "actor": seat,
            "action": action.to_dict(),
            "events": [e for ev in events if (e := visible_event(ev, None)) is not None
                       and not ev.get("private")],
            "view": masked_state(s, None, reveal_all=True),
            "decision": decisions.get(seq),
        })
    if s.result != meta["result"]:
        raise ReplayError("replay diverged from the stored result")
    return {"meta": {k: v for k, v in meta.items() if k != "actions"}, "frames": frames}
