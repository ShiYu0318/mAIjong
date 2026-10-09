import random

import pytest

from engine import tiles
from engine.shanten import is_complete, shanten, uke_ire
from tests.engine.shanten_reference import ref_shanten


def c(text: str) -> list[int]:
    return tiles.to_counts(tiles.parse(text))


@pytest.mark.parametrize(
    ("hand", "n_melds", "expected"),
    [
        # complete 17-tile hand: 5 melds + pair
        ("123m 456m 789m 111p 東東東 中中", 0, -1),
        # tenpai 16 tiles waiting on 中 or 東 (shanpon)
        ("123m 456m 789m 111p 東東 中中", 0, 0),
        # tenpai with two declared melds
        ("123m 456s 99p 55p", 2, 0),
        # one melded set: 2 melds + 79p + 11s pair → 2-shanten
        ("123m 456m 79p 11s 2s 5s 東", 1, 2),
        # all honors scattered: far away
        ("東南西北中發白 19m 19s 19p 東南", 0, 8),
    ],
)
def test_known_values(hand, n_melds, expected):
    assert shanten(c(hand), n_melds) == expected


def test_is_complete():
    assert is_complete(c("123m 456m 789m 111p 東東東 中中"))
    assert not is_complete(c("123m 456m 789m 111p 東東東 中發"))


def test_uke_ire_tenpai_equals_waits():
    # 4 melds + 東東 pair + 57s → kanchan wait on 6s only
    hand = c("123m 456m 789m 111p 57s 東東")
    assert shanten(hand) == 0
    assert uke_ire(hand) == tiles.parse("6s")


def test_uke_ire_shanpon():
    hand = c("123m 456m 789m 111p 東東 中中")
    assert uke_ire(hand) == tiles.parse("東中")


def test_fifth_tile_wait_is_not_tenpai():
    # 4 copies of 北 held: "waiting" on a 5th 北 is impossible
    hand = c("111s 234s 223344p 北北北北")
    assert shanten(hand) == 1
    assert ref_shanten(hand) == 0  # the naive reference ignores the 4-copy limit


def _complete(rng: random.Random, n_melds: int) -> list[int]:
    while True:
        cnt = [0] * 34
        for _ in range(5 - n_melds):
            if rng.random() < 0.6:
                s, r = rng.randrange(3), rng.randrange(7)
                group = [9 * s + r, 9 * s + r + 1, 9 * s + r + 2]
            else:
                group = [rng.randrange(34)] * 3
            for t in group:
                cnt[t] += 1
        cnt[rng.randrange(34)] += 2
        if max(cnt) <= 4:
            return cnt


def test_matches_reference_on_random_and_near_complete_hands():
    rng = random.Random(20261010)
    wall = [t for t in range(34) for _ in range(4)]
    hands: list[tuple[list[int], int]] = []
    for _ in range(1500):
        n_melds = rng.choice([0, 0, 1, 2, 3])
        size = 16 - 3 * n_melds + rng.choice([0, 1])
        hands.append((tiles.to_counts(rng.sample(wall, size)), n_melds))
    for _ in range(1500):
        n_melds = rng.choice([0, 0, 1, 2])
        cnt = _complete(rng, n_melds)
        for _ in range(rng.choice([1, 1, 2, 3])):
            cnt[rng.choice([t for t in range(34) if cnt[t]])] -= 1
            free = [t for t in range(34) if cnt[t] < 4]
            cnt[rng.choice(free)] += 1
        if rng.random() < 0.5:
            cnt[rng.choice([t for t in range(34) if cnt[t]])] -= 1
        hands.append((cnt, n_melds))

    for cnt, n_melds in hands:
        a, b = shanten(cnt, n_melds), ref_shanten(cnt, n_melds)
        if a != b:
            # only allowed difference: the reference counts an impossible 5th-tile wait
            assert a == b + 1 and 4 in cnt, (a, b, tiles.names(tiles.from_counts(cnt)))
