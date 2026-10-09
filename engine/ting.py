"""Tenpai detection, waiting tiles, and discards that leave the hand tenpai."""

from __future__ import annotations

from engine.shanten import shanten, uke_ire


def is_tenpai(hand_34: list[int], n_melds: int) -> bool:
    """For a 3n+1 concealed part."""
    return shanten(hand_34, n_melds) == 0


def waiting_tiles(hand_34: list[int], n_melds: int) -> list[int]:
    """Winning tiles of a tenpai 3n+1 hand ([] if not tenpai)."""
    if shanten(hand_34, n_melds) != 0:
        return []
    return uke_ire(hand_34, n_melds)


def tenpai_discards(hand_34: list[int], n_melds: int) -> list[int]:
    """Tiles of a 3n+2 hand whose discard leaves the hand tenpai."""
    counts = list(hand_34)
    out: list[int] = []
    for t in range(34):
        if not counts[t]:
            continue
        counts[t] -= 1
        if shanten(counts, n_melds) == 0:
            out.append(t)
        counts[t] += 1
    return out
