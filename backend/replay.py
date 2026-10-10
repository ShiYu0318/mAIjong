"""Rebuild replay frames from a stored hand (seed + action sequence)."""

from __future__ import annotations

from typing import Any

from backend.ws.view import masked_state, visible_event
from engine.actions import decode_action
from engine.game import apply_action, new_game
from engine.score import ScoringRules


class ReplayError(ValueError):
    pass


def build_frames(records: list[dict[str, Any]]) -> dict[str, Any]:
    """records: lines of a stored .jsonl replay (META first, then events)."""
    if not records or records[0].get("type") != "META":
        raise ReplayError("missing replay header")
    meta = records[0]
    actions = meta.get("actions") or []
    if not actions:
        raise ReplayError("this replay has no action log")
    decisions = {ev["seq"]: ev["ai_decision"] for ev in records[1:] if "ai_decision" in ev}
    rules = ScoringRules(**meta["rules"]) if meta.get("rules") else ScoringRules()
    s = new_game(
        int(meta["seed"]), dealer=meta["dealer"], round_wind=meta["round_wind"],
        dealer_streak=meta["dealer_streak"], scores=meta.get("scores_before"), rules=rules,
        game_id=meta["game_id"],
    )
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
