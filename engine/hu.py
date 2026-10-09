"""Win detection and decomposition of complete hands.

A complete concealed part splits into (5 - n_melds) groups plus one pair. Scoring needs
every decomposition and every role the winning tile can play in it, because tai depend on
the interpretation (e.g. 平胡 needs a two-sided wait, 中洞 a closed wait).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from engine.shanten import is_complete

SEQ = "S"
TRI = "T"


@dataclass(frozen=True, slots=True)
class Group:
    kind: str  # SEQ or TRI
    tile: int  # first tile of a sequence, or the triplet tile

    def tiles(self) -> tuple[int, int, int]:
        if self.kind == SEQ:
            return (self.tile, self.tile + 1, self.tile + 2)
        return (self.tile, self.tile, self.tile)


@dataclass(frozen=True, slots=True)
class Decomposition:
    groups: tuple[Group, ...]
    pair: int


class WaitShape(StrEnum):
    RYANMEN = "RYANMEN"  # two-sided (兩面)
    KANCHAN = "KANCHAN"  # closed middle (中洞)
    PENCHAN = "PENCHAN"  # edge (邊張)
    TANKI = "TANKI"  # pair wait (單釣)
    SHANPON = "SHANPON"  # dual pon wait (雙碰)


@dataclass(frozen=True, slots=True)
class Placement:
    """Where the winning tile sits inside a decomposition."""

    group_index: int | None  # None = in the pair
    shape: WaitShape


def is_win(hand_34: list[int], n_melds: int) -> bool:
    return is_complete(hand_34, n_melds)


def decompositions(hand_34: list[int], n_melds: int) -> list[Decomposition]:
    """All distinct ways to split a complete concealed part into groups + pair."""
    need = 5 - n_melds
    counts = list(hand_34)
    if sum(counts) != 3 * need + 2:
        return []
    out: set[Decomposition] = set()

    def split(i: int, acc: list[Group]) -> list[tuple[Group, ...]]:
        while i < 34 and counts[i] == 0:
            i += 1
        if i == 34:
            return [tuple(acc)]
        results: list[tuple[Group, ...]] = []
        if counts[i] >= 3:
            counts[i] -= 3
            acc.append(Group(TRI, i))
            results += split(i, acc)
            acc.pop()
            counts[i] += 3
        if i < 27 and i % 9 <= 6 and counts[i + 1] and counts[i + 2]:
            for j in (i, i + 1, i + 2):
                counts[j] -= 1
            acc.append(Group(SEQ, i))
            results += split(i, acc)
            acc.pop()
            for j in (i, i + 1, i + 2):
                counts[j] += 1
        return results

    for p in range(34):
        if counts[p] >= 2:
            counts[p] -= 2
            for groups in split(0, []):
                if len(groups) == need:
                    out.add(Decomposition(tuple(sorted(groups, key=lambda g: (g.tile, g.kind))), p))
            counts[p] += 2
    return sorted(out, key=lambda d: (d.pair, [(g.tile, g.kind) for g in d.groups]))


def placements(d: Decomposition, win_tile: int) -> list[Placement]:
    """Every role the winning tile can play in decomposition d."""
    out: list[Placement] = []
    if d.pair == win_tile:
        out.append(Placement(None, WaitShape.TANKI))
    for idx, g in enumerate(d.groups):
        if win_tile not in g.tiles():
            continue
        if g.kind == TRI:
            out.append(Placement(idx, WaitShape.SHANPON))
            continue
        pos = win_tile - g.tile
        rank = g.tile % 9 + 1  # rank of the first tile
        if pos == 1:
            shape = WaitShape.KANCHAN
        elif pos == 0:
            shape = WaitShape.PENCHAN if rank == 7 else WaitShape.RYANMEN
        else:
            shape = WaitShape.PENCHAN if rank == 1 else WaitShape.RYANMEN
        out.append(Placement(idx, shape))
    return out
