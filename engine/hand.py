"""Melds and small helpers for manipulating sorted hands."""

from __future__ import annotations

from bisect import insort
from dataclasses import dataclass
from enum import StrEnum


class MeldType(StrEnum):
    CHI = "CHI"
    PON = "PON"
    MING_KONG = "MING_KONG"  # exposed kong on a discard (明槓)
    ADD_KONG = "ADD_KONG"  # pon upgraded with a self-drawn 4th tile (加槓／補槓)
    AN_KONG = "AN_KONG"  # concealed kong (暗槓)


KONG_TYPES = (MeldType.MING_KONG, MeldType.ADD_KONG, MeldType.AN_KONG)
EXPOSED_TYPES = (MeldType.CHI, MeldType.PON, MeldType.MING_KONG, MeldType.ADD_KONG)


@dataclass(frozen=True, slots=True)
class Meld:
    type: MeldType
    tiles: tuple[int, ...]
    called: int | None = None  # tile taken from another player
    from_player: int | None = None

    @property
    def is_kong(self) -> bool:
        return self.type in KONG_TYPES

    @property
    def is_triplet(self) -> bool:
        """Pon or any kong (counts as a 刻子 for scoring)."""
        return self.type is not MeldType.CHI

    @property
    def is_exposed(self) -> bool:
        """Breaks 門清 (concealed kongs do not)."""
        return self.type in EXPOSED_TYPES

    @property
    def base_tile(self) -> int:
        return self.tiles[0]

    def to_dict(self) -> dict[str, object]:
        return {
            "type": self.type.value,
            "tiles": list(self.tiles),
            "called": self.called,
            "from_player": self.from_player,
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> Meld:
        tiles = d["tiles"]
        assert isinstance(tiles, list)
        called = d.get("called")
        from_player = d.get("from_player")
        return Meld(
            MeldType(str(d["type"])),
            tuple(int(t) for t in tiles),
            None if called is None else int(str(called)),
            None if from_player is None else int(str(from_player)),
        )


def add_tile(hand: list[int], tile: int) -> list[int]:
    out = list(hand)
    insort(out, tile)
    return out


def remove_tiles(hand: list[int], *remove: int) -> list[int]:
    out = list(hand)
    for t in remove:
        out.remove(t)
    return out
