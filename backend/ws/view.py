"""Per-seat masked views of the game state (only what that seat may see)."""

from __future__ import annotations

from typing import Any

from engine import tiles
from engine.actions import ActionType
from engine.game import GameState, Phase, acting_players, get_legal_actions
from engine.hand import MeldType
from engine.shanten import shanten_after_discards
from engine.ting import waiting_tiles


def masked_state(s: GameState, seat: int | None, reveal_all: bool = False) -> dict[str, Any]:
    """seat=None gives a spectator view (no concealed tiles at all); reveal_all shows every
    hand (replays)."""
    players = []
    flags = discard_flags(s)
    for p in range(4):
        own = seat == p
        melds = []
        for m in s.melds[p]:
            hidden = (m.type is MeldType.AN_KONG and not own and not reveal_all
                      and s.phase is not Phase.ENDED)
            melds.append({
                "type": m.type.value,
                "tiles": [None] * 4 if hidden else list(m.tiles),
                "called": None if hidden else m.called,
                "from_player": m.from_player,
            })
        reveal = own or reveal_all or s.phase is Phase.ENDED
        players.append({
            "seat": p,
            "seat_wind": s.seat_wind(p),
            "hand": list(s.hands[p]) if reveal else None,
            "hand_count": len(s.hands[p]),
            "melds": melds,
            "flowers": list(s.flowers[p]),
            "discards": list(s.discards[p]),
            "tsumogiri": flags[p],
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


def discard_flags(s: GameState) -> list[list[bool]]:
    """Per player, whether each tile still in the river was discarded straight after being
    drawn (tsumogiri), so the table can grey those out. Claimed discards leave the river."""
    rivers: list[list[tuple[int, bool]]] = [[] for _ in range(4)]
    drawn: list[int | None] = [None] * 4
    for ev in s.events:
        p, kind = ev.get("player"), ev.get("type")
        if p is None:
            continue
        if kind == "DRAW":
            drawn[p] = ev.get("tile")
        elif kind in ("DISCARD", "TING"):
            rivers[p].append((ev["tile"], drawn[p] == ev["tile"]))
            drawn[p] = None
        elif kind in ("PON", "CHI") or (kind == "KONG" and ev.get("kind") == "MING_KONG"):
            src = ev.get("from")
            if src is not None and rivers[src]:
                rivers[src].pop()
            drawn[p] = None
    out = []
    for p in range(4):
        if [t for t, _ in rivers[p]] == list(s.discards[p]):
            out.append([f for _, f in rivers[p]])
        else:  # defensive: never mislabel, fall back to "hand discard"
            out.append([False] * len(s.discards[p]))
    return out


def discard_waits(s: GameState, seat: int) -> dict[str, list[list[int]]]:
    """For each legal discard that leaves the hand ready: [wait tile, copies not yet seen].
    Seen = own hand after the discard, every river, exposed melds and the discard itself."""
    if s.phase is not Phase.DISCARD or s.turn != seat:
        return {}
    legal = {a.tile for a in get_legal_actions(s, seat)
             if a.type in (ActionType.DISCARD, ActionType.TING) and a.tile is not None}
    counts = tiles.to_counts(s.hands[seat])
    n_melds = len(s.melds[seat])
    after = shanten_after_discards(counts, n_melds)
    seen = [0] * 34
    for p in range(4):
        for t in s.discards[p]:
            if t < 34:
                seen[t] += 1
        for m in s.melds[p]:
            hidden = m.type is MeldType.AN_KONG and p != seat
            if not hidden:
                for t in m.tiles:
                    if t is not None and t < 34:
                        seen[t] += 1
    out: dict[str, list[list[int]]] = {}
    for t in sorted(legal):
        if t >= 34 or after.get(t) != 0:
            continue
        rest = list(counts)
        rest[t] -= 1
        waits = waiting_tiles(rest, n_melds)
        out[str(t)] = [[w, max(0, 4 - rest[w] - seen[w] - (1 if w == t else 0))] for w in waits]
    return out
