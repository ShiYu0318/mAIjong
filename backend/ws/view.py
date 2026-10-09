"""Per-seat masked views of the game state (only what that seat may see)."""

from __future__ import annotations

from typing import Any

from engine.game import GameState, Phase, acting_players, get_legal_actions
from engine.hand import MeldType


def masked_state(s: GameState, seat: int | None) -> dict[str, Any]:
    """seat=None gives a spectator view (no concealed tiles at all)."""
    players = []
    for p in range(4):
        own = seat == p
        melds = []
        for m in s.melds[p]:
            hidden = m.type is MeldType.AN_KONG and not own and s.phase is not Phase.ENDED
            melds.append({
                "type": m.type.value,
                "tiles": [None] * 4 if hidden else list(m.tiles),
                "called": None if hidden else m.called,
                "from_player": m.from_player,
            })
        reveal = own or s.phase is Phase.ENDED
        players.append({
            "seat": p,
            "seat_wind": s.seat_wind(p),
            "hand": list(s.hands[p]) if reveal else None,
            "hand_count": len(s.hands[p]),
            "melds": melds,
            "flowers": list(s.flowers[p]),
            "discards": list(s.discards[p]),
            "score": s.scores[p],
            "declared_ting": s.declared_ting[p],
        })
    return {
        "game_id": s.game_id,
        "phase": s.phase.value,
        "turn": s.turn,
        "dealer": s.dealer,
        "dealer_streak": s.dealer_streak,
        "round_wind": s.round_wind,
        "drawable": s.drawable(),
        "last_discard": list(s.last_discard) if s.last_discard else None,
        "last_draw": s.last_draw if seat == s.turn else None,
        "acting": acting_players(s),
        "players": players,
        "you": seat,
        "result": s.result,
    }


def legal_actions_payload(s: GameState, seat: int) -> list[dict[str, Any]]:
    return [a.to_dict() for a in get_legal_actions(s, seat)]


def visible_event(ev: dict[str, Any], seat: int | None) -> dict[str, Any] | None:
    """Hide private events (other players' draws)."""
    if ev.get("private") and ev.get("player") != seat:
        return {**ev, "tile": None}
    if ev.get("type") == "DEAL":
        return None
    if ev.get("type") == "KONG" and ev.get("kind") == "AN_KONG" and ev.get("player") != seat:
        return {**ev, "tile": None}
    return ev
