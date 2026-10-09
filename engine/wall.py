"""Wall construction, dealing and draw bookkeeping.

Normal draws take wall[0]; flower and kong replacements take wall[-1]. The last
WALL_RESERVE tiles (+1 per kong) may never be drawn.
"""

from __future__ import annotations

import random

from engine.tiles import full_wall

WALL_RESERVE = 16
HAND_SIZE = 16


def shuffled_wall(rng: random.Random) -> list[int]:
    wall = full_wall()
    rng.shuffle(wall)
    return wall


def deal(wall: list[int], dealer: int) -> tuple[list[list[int]], list[int]]:
    """16 tiles each in seat order starting from the dealer; the dealer takes a 17th."""
    wall = list(wall)
    hands: list[list[int]] = [[] for _ in range(4)]
    for _ in range(HAND_SIZE // 4):
        for k in range(4):
            seat = (dealer + k) % 4
            hands[seat].extend(wall[:4])
            del wall[:4]
    hands[dealer].append(wall.pop(0))
    return [sorted(h) for h in hands], wall


def drawable(wall: list[int], reserve: int) -> int:
    return len(wall) - reserve
