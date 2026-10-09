from collections import Counter

import pytest

from engine import tiles


def test_wall_has_144_tiles_with_correct_copies():
    wall = tiles.full_wall()
    assert len(wall) == tiles.WALL_SIZE == 144
    counts = Counter(wall)
    assert all(counts[t] == 4 for t in tiles.PLAYABLE_TILES)
    assert all(counts[t] == 1 for t in tiles.FLOWER_TILES)


def test_classification():
    assert tiles.is_number(0) and tiles.is_number(26) and not tiles.is_number(27)
    assert tiles.is_wind(27) and tiles.is_wind(30) and not tiles.is_wind(31)
    assert tiles.is_dragon(31) and tiles.is_dragon(33)
    assert tiles.is_flower(34) and tiles.is_flower(41) and not tiles.is_flower(33)
    assert tiles.suit_of(10) == 1 and tiles.rank_of(10) == 2
    assert tiles.is_terminal(0) and tiles.is_terminal(8) and not tiles.is_terminal(27)
    with pytest.raises(ValueError):
        tiles.rank_of(27)


@pytest.mark.parametrize(
    ("seat_wind", "expected"),
    [(0, ("春", "梅")), (1, ("夏", "蘭")), (2, ("秋", "菊")), (3, ("冬", "竹"))],
)
def test_seat_flowers(seat_wind, expected):
    a, b = tiles.seat_flowers(seat_wind)
    assert (tiles.name(a), tiles.name(b)) == expected


def test_parse_and_counts_roundtrip():
    hand = tiles.parse("123m 55p 東東 9s 中")
    assert tiles.names(hand) == "1萬 2萬 3萬 5筒 5筒 東 東 9條 中"
    assert tiles.from_counts(tiles.to_counts(hand)) == sorted(hand)
    with pytest.raises(ValueError):
        tiles.parse("X")
