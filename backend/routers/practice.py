"""Single-player practice modes (SPEC 04.5, P11-1..P11-3).

Every mode is stateless on the server: a signed token carries the seed and the
player's choices so far, and each request replays them deterministically.
"""

from __future__ import annotations

import json
import random
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ai.agents.rule_agent import RuleAgent
from ai.explainability.analysis import _replay_to
from backend.security import TokenError, _encode, create_ws_token, decode_token
from backend.ws.hub import RoomConfig, RoomManager
from engine import tiles
from engine.actions import Action, ActionType
from engine.game import GameState, Phase, acting_players, apply_action, get_legal_actions
from engine.shanten import shanten
from engine.wall import WALL_RESERVE

router = APIRouter(prefix="/practice", tags=["practice"])
TOKEN_TTL = timedelta(hours=3)
SCENARIOS_PATH = Path(__file__).resolve().parent.parent / "data" / "scenarios.json"
DEFENSE_TURNS = 5


def _token(payload: dict[str, Any]) -> str:
    return _encode({"kind": "practice", **payload}, TOKEN_TTL)


def _claims(token: str, mode: str) -> dict[str, Any]:
    try:
        c = decode_token(token, "practice")
    except TokenError as e:
        raise HTTPException(400, "練習已過期，請重新開始") from e
    if c.get("mode") != mode:
        raise HTTPException(400, "token 不屬於這個練習")
    return c


# ---------------------------------------------------------------- speed challenge


def _speed_state(seed: int, discards: list[int]) -> dict[str, Any]:
    wall = [t for t in range(34) for _ in range(4)]
    random.Random(seed).shuffle(wall)
    hand = sorted(wall[:16])
    pos = 16
    drawn: int | None = None
    for d in [*discards, None]:
        drawn = wall[pos]
        pos += 1
        hand = sorted([*hand, drawn])
        if d is None:
            break
        if d not in hand:
            raise HTTPException(422, "這張牌不在手上")
        hand.remove(d)
        if shanten(tiles.to_counts(hand)) == 0:
            remaining = len(wall) - pos - WALL_RESERVE
            return {"hand": hand, "drawn": None, "drawable": remaining, "done": True,
                    "tenpai": True, "score": max(0, remaining), "shanten": 0}
    remaining = len(wall) - pos - WALL_RESERVE
    done = remaining <= 0
    return {"hand": hand, "drawn": drawn, "drawable": remaining, "done": done, "tenpai": False,
            "score": 0 if done else None, "shanten": shanten(tiles.to_counts(hand))}


@router.post("/speed/start")
def speed_start() -> dict[str, Any]:
    seed = random.randrange(2**31)
    return {"token": _token({"mode": "speed", "seed": seed, "discards": []}),
            **_speed_state(seed, [])}


class DiscardIn(BaseModel):
    token: str
    tile: int = Field(ge=0, le=33)


@router.post("/speed/discard")
def speed_discard(body: DiscardIn) -> dict[str, Any]:
    c = _claims(body.token, "speed")
    discards = [*c["discards"], body.tile]
    state = _speed_state(int(c["seed"]), discards)
    return {"token": _token({"mode": "speed", "seed": c["seed"], "discards": discards}),
            **state}


# ---------------------------------------------------------------- defense drill


def _find_defense(rng: random.Random) -> tuple[int, int, int]:
    """(seed, step, seat): an opponent has declared ready, the seat is not tenpai and
    must discard, with enough wall left for several turns."""
    from engine.game import new_game

    for _ in range(300):
        seed = rng.randrange(2**31)
        agents = [RuleAgent(0.0, seed * 4 + i) for i in range(4)]
        s = new_game(seed=seed)
        step = 0
        while s.phase is not Phase.ENDED and step < 500:
            p = acting_players(s)[0]
            if (s.phase is Phase.DISCARD and not s.declared_ting[p]
                    and any(s.declared_ting[q] for q in range(4) if q != p)
                    and s.drawable() > 20
                    and shanten(tiles.to_counts(s.hands[p]), len(s.melds[p])) >= 1):
                return seed, step, p
            s, _ = apply_action(s, p, agents[p].act(s, p, get_legal_actions(s, p)))
            step += 1
    raise HTTPException(503, "暫時找不到合適的防守局面，請再試一次")


def _advance_others(s: GameState, seat: int, agents: list[RuleAgent]) -> GameState:
    """Bots act; the player auto-passes on calls; stop at the player's next discard."""
    while s.phase is not Phase.ENDED:
        acting = acting_players(s)
        if seat in acting and s.phase is Phase.DISCARD:
            return s
        p = acting[0]
        legal = get_legal_actions(s, p)
        a = Action(ActionType.PASS) if p == seat else agents[p].act(s, p, legal)
        s, _ = apply_action(s, p, a)
    return s


def _defense_state(seed: int, step: int, seat: int, discards: list[int]) -> dict[str, Any]:
    s = _replay_to(seed, step)
    agents = [RuleAgent(0.0, seed * 4 + i + 1000) for i in range(4)]
    survived = 0
    for d in discards:
        if s.phase is Phase.ENDED or s.turn != seat:
            break
        if Action(ActionType.DISCARD, d) not in get_legal_actions(s, seat):
            raise HTTPException(422, "這張牌現在不能打")
        s, _ = apply_action(s, seat, Action(ActionType.DISCARD, d))
        s = _advance_others(s, seat, agents)
        survived += 1
        if s.phase is Phase.ENDED:
            break
    r = s.result
    dealt_in = bool(r and r.get("kind") == "HU" and r.get("loser") == seat
                    and not r.get("self_draw"))
    done = dealt_in or survived >= DEFENSE_TURNS or s.phase is Phase.ENDED
    declared = [q for q in range(4) if s.declared_ting[q] and q != seat]
    out: dict[str, Any] = {
        "seat": seat, "hand": list(s.hands[seat]), "drawn": s.last_draw if s.turn == seat else None,
        "discards": [list(x) for x in s.discards], "declared": declared,
        "melds": [[m.to_dict() for m in s.melds[q]] for q in range(4)],
        "survived": survived, "turns": DEFENSE_TURNS, "done": done, "dealt_in": dealt_in,
        "success": done and not dealt_in,
    }
    if done:
        out["result"] = r
        out["waits"] = {str(q): _waits(s, q) for q in declared}
    return out


def _waits(s: GameState, q: int) -> list[int]:
    from engine.ting import waiting_tiles

    counts = tiles.to_counts(s.hands[q])
    if sum(counts) % 3 == 2:  # winner's hand already includes the winning tile
        return []
    return waiting_tiles(counts, len(s.melds[q]))


@router.post("/defense/start")
def defense_start() -> dict[str, Any]:
    seed, step, seat = _find_defense(random.Random())
    payload = {"mode": "defense", "seed": seed, "step": step, "seat": seat, "discards": []}
    return {"token": _token(payload), **_defense_state(seed, step, seat, [])}


@router.post("/defense/discard")
def defense_discard(body: DiscardIn) -> dict[str, Any]:
    c = _claims(body.token, "defense")
    discards = [*c["discards"], body.tile]
    state = _defense_state(int(c["seed"]), int(c["step"]), int(c["seat"]), discards)
    payload = {"mode": "defense", "seed": c["seed"], "step": c["step"], "seat": c["seat"],
               "discards": discards}
    return {"token": _token(payload), **state}


# ---------------------------------------------------------------- scenarios


def load_scenarios() -> list[dict[str, Any]]:
    if not SCENARIOS_PATH.exists():
        return []
    data: list[dict[str, Any]] = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    return data


@router.get("/scenarios")
def scenarios() -> list[dict[str, Any]]:
    return [{k: v for k, v in sc.items() if k not in ("seed", "step")} for sc in load_scenarios()]


@router.post("/scenarios/{scenario_id}/play")
async def play_scenario(scenario_id: str, request: Request) -> dict[str, Any]:
    sc = next((x for x in load_scenarios() if x["id"] == scenario_id), None)
    if sc is None:
        raise HTTPException(404, "scenario not found")
    manager: RoomManager = request.app.state.rooms
    seat = int(sc["seat"])
    bots: list[int | None] = [3, 3, 3, 3]
    bots[seat] = None
    cfg = RoomConfig(time_limit=None, rounds=1, bot_levels=bots, next_hand_delay=0)
    from backend.models import new_id

    room = manager.create(new_id(), "PRACTICE", cfg, None)
    room.scenario = {"seed": int(sc["seed"]), "step": int(sc["step"])}
    name = "練習者"
    room.join(None, name, seat)
    await room.start()
    return {"room": room.public(), "seat": seat,
            "ws_token": create_ws_token(room.id, seat, None, name)}
