from engine import tiles
from engine.ting import is_tenpai, tenpai_discards, waiting_tiles


def c(text: str) -> list[int]:
    return tiles.to_counts(tiles.parse(text))


def test_waiting_tiles():
    assert waiting_tiles(c("123m 456m 789m 111p 57s 東東"), 0) == tiles.parse("6s")
    assert waiting_tiles(c("123m 456m 789m 111p 東東 中中"), 0) == tiles.parse("東中")
    assert waiting_tiles(c("123m 456m 789m 111p 東 中中 9s"), 0) == []


def test_tenpai_discards():
    hand = c("123m 456m 789m 111p 57s 東東 北")
    assert tenpai_discards(hand, 0) == tiles.parse("北")
    assert is_tenpai(c("123m 456m 789m 111p 57s 東東"), 0)
