"""Tile ids, names and classification helpers.

Ids 0-33 are playable tiles (may enter a hand); ids 34-41 are flowers, which are
revealed and replaced from the back of the wall as soon as they are drawn.
"""

from __future__ import annotations

SUIT_NAMES = ("萬", "條", "筒")

TILE_NAMES: dict[int, str] = {
    **{i: f"{i + 1}萬" for i in range(9)},
    **{i + 9: f"{i + 1}條" for i in range(9)},
    **{i + 18: f"{i + 1}筒" for i in range(9)},
    27: "東", 28: "南", 29: "西", 30: "北",
    31: "中", 32: "發", 33: "白",
    34: "春", 35: "夏", 36: "秋", 37: "冬",
    38: "梅", 39: "蘭", 40: "菊", 41: "竹",
}

NUMBER_TILES = list(range(27))
HONOR_TILES = list(range(27, 34))
WIND_TILES = list(range(27, 31))
DRAGON_TILES = list(range(31, 34))
PLAYABLE_TILES = list(range(34))
FLOWER_TILES = list(range(34, 42))
SEASON_TILES = list(range(34, 38))
PLANT_TILES = list(range(38, 42))

N_PLAYABLE = 34
N_TILE_KINDS = 42
COPIES_PER_PLAYABLE = 4
WALL_SIZE = N_PLAYABLE * COPIES_PER_PLAYABLE + len(FLOWER_TILES)  # 144

EAST, SOUTH, WEST, NORTH = 0, 1, 2, 3
WIND_NAMES = ("東", "南", "西", "北")


def is_flower(tile: int) -> bool:
    return 34 <= tile <= 41


def is_number(tile: int) -> bool:
    return 0 <= tile <= 26


def is_honor(tile: int) -> bool:
    return 27 <= tile <= 33


def is_wind(tile: int) -> bool:
    return 27 <= tile <= 30


def is_dragon(tile: int) -> bool:
    return 31 <= tile <= 33


def suit_of(tile: int) -> int:
    """0=萬, 1=條, 2=筒; only valid for number tiles."""
    if not is_number(tile):
        raise ValueError(f"tile {tile} is not a number tile")
    return tile // 9


def rank_of(tile: int) -> int:
    """1-9 face value; only valid for number tiles."""
    if not is_number(tile):
        raise ValueError(f"tile {tile} is not a number tile")
    return tile % 9 + 1


def is_terminal(tile: int) -> bool:
    return is_number(tile) and rank_of(tile) in (1, 9)


def wind_tile(wind: int) -> int:
    """Tile id of a wind (0=東 … 3=北)."""
    return 27 + wind


def seat_flowers(seat_wind: int) -> tuple[int, int]:
    """正花 for a seat wind: (春/夏/秋/冬, 梅/蘭/菊/竹)."""
    return (34 + seat_wind, 38 + seat_wind)


def full_wall() -> list[int]:
    """All 144 tiles in canonical order (unshuffled)."""
    return [t for t in PLAYABLE_TILES for _ in range(COPIES_PER_PLAYABLE)] + list(FLOWER_TILES)


def to_counts(tiles: list[int]) -> list[int]:
    """34-length count vector of playable tiles."""
    counts = [0] * N_PLAYABLE
    for t in tiles:
        counts[t] += 1
    return counts


def from_counts(counts: list[int]) -> list[int]:
    return [t for t, c in enumerate(counts) for _ in range(c)]


def name(tile: int) -> str:
    return TILE_NAMES[tile]


def names(tiles: list[int]) -> str:
    return " ".join(TILE_NAMES[t] for t in tiles)


def parse(text: str) -> list[int]:
    """Parse compact notation like "123m 55p 東東 9s" into tile ids.

    m=萬, s=條, p=筒; honors and flowers use their Chinese names.
    """
    suit_offset = {"m": 0, "s": 9, "p": 18}
    by_name = {v: k for k, v in TILE_NAMES.items()}
    out: list[int] = []
    pending: list[int] = []  # digits waiting for their suit letter (may span spaces)
    for ch in text:
        if ch.isspace():
            continue
        if ch.isdigit():
            pending.append(int(ch))
        elif ch in suit_offset:
            if not pending:
                raise ValueError(f"suit {ch!r} without digits in {text!r}")
            out.extend(suit_offset[ch] + d - 1 for d in pending)
            pending = []
        elif ch in by_name:
            out.append(by_name[ch])
        else:
            raise ValueError(f"unknown tile {ch!r} in {text!r}")
    if pending:
        raise ValueError(f"digits without a suit in {text!r}")
    return out
