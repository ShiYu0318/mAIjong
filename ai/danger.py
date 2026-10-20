"""Deal-in danger estimates from public information only.

These Taiwanese 16-tile rules have no furiten, so the main hard safety signal comes from declared
ready hands: a declared player can no longer change their hand, so any tile discarded
after their declaration that they did not win on is not one of their waits.
"""

from __future__ import annotations

from engine import tiles
from engine.game import GameState


def safe_against(state: GameState, opponent: int) -> set[int]:
    """Tiles proven safe against a declared opponent."""
    if not state.declared_ting[opponent]:
        return set()
    safe: set[int] = set()
    declared_at: int | None = None
    for ev in state.events:
        if ev["type"] == "TING" and ev["player"] == opponent:
            declared_at = ev["seq"]
        if declared_at is None or ev["seq"] < declared_at:
            continue
        if ev["type"] in ("DISCARD", "TING") and ev["tile"] is not None:
            safe.add(ev["tile"])
    return safe


def visible_counts(state: GameState, seat: int) -> list[int]:
    seen = tiles.to_counts(state.hands[seat])
    for p in range(4):
        for t in state.discards[p]:
            seen[t] += 1
        for m in state.melds[p]:
            for t in m.tiles:
                seen[t] += 1
    return seen


def tile_danger(state: GameState, seat: int, tile: int, seen: list[int] | None = None) -> float:
    """0 (safe) … 1 (very dangerous) for discarding `tile` from `seat`'s view."""
    seen = seen if seen is not None else visible_counts(state, seat)
    threats = [p for p in range(4) if p != seat and state.declared_ting[p]]
    late = state.drawable() < 24
    if not threats and not late:
        return 0.0
    if threats and all(tile in safe_against(state, p) for p in threats):
        return 0.0
    remaining = 4 - seen[tile]
    if remaining <= 0:
        base = 0.0
    elif tiles.is_honor(tile):
        base = 0.15 if remaining <= 1 else 0.35
    else:
        rank = tiles.rank_of(tile)
        base = {1: 0.4, 9: 0.4, 2: 0.55, 8: 0.55}.get(rank, 0.7)
        if remaining <= 1:
            base *= 0.6
    weight = 1.0 if threats else 0.35
    return min(1.0, base * weight * (1 + 0.15 * max(0, len(threats) - 1)))


def suspected_threats(state: GameState, seat: int, melds_min: int, turn_min: int) -> list[int]:
    """Opponents who have not declared but look close to ready from public signs: many
    melds (few concealed tiles left) or a long river. 0 turns a sign off."""
    out = []
    for p in range(4):
        if p == seat or state.declared_ting[p]:
            continue
        if (melds_min and len(state.melds[p]) >= melds_min) or \
                (turn_min and len(state.discards[p]) >= turn_min):
            out.append(p)
    return out


def suspected_danger(state: GameState, tile: int, seen: list[int], threats: list[int]) -> float:
    """Danger against undeclared threats: the tile-type estimate above, raised for a suit a
    threat has melded in (a one-suit hand in the making)."""
    remaining = 4 - seen[tile]
    if remaining <= 0 or not threats:
        return 0.0
    if tiles.is_honor(tile):
        base = 0.15 if remaining <= 1 else 0.35
    else:
        base = {1: 0.4, 9: 0.4, 2: 0.55, 8: 0.55}.get(tiles.rank_of(tile), 0.7)
        if remaining <= 1:
            base *= 0.6
        suit = tiles.suit_of(tile)
        if any(t is not None and not tiles.is_honor(t) and tiles.suit_of(t) == suit
               for p in threats for m in state.melds[p] for t in m.tiles):
            base *= 1.3
    return min(1.0, base * (1 + 0.15 * (len(threats) - 1)))
