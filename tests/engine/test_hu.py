from engine import tiles
from engine.hu import SEQ, TRI, WaitShape, decompositions, is_win, placements


def c(text: str) -> list[int]:
    return tiles.to_counts(tiles.parse(text))


def test_simple_win_and_decomposition():
    hand = c("123m 456m 789m 111p 東東東 中中")
    assert is_win(hand, 0)
    ds = decompositions(hand, 0)
    assert len(ds) == 1
    assert ds[0].pair == tiles.parse("中")[0]
    kinds = sorted(g.kind for g in ds[0].groups)
    assert kinds == [SEQ, SEQ, SEQ, TRI, TRI]


def test_multiple_decompositions():
    # 111222333m can be three triplets or three sequences
    hand = c("111222333m 456p 99s")
    assert is_win(hand, 1)
    ds = decompositions(hand, 1)
    assert len(ds) == 2


def test_with_melds_and_not_win():
    assert is_win(c("456s 99p"), 4)
    assert not is_win(c("123m 456m 789m 111p 東東東 中發"), 0)
    assert decompositions(c("123m 456m 789m 111p 東東東 中發"), 0) == []


def test_placements_shapes():
    (d,) = decompositions(c("123m 456m 789m 111p 東東東 中中"), 0)
    shapes = {p.shape for p in placements(d, tiles.parse("3m")[0])}
    assert shapes == {WaitShape.PENCHAN}
    shapes = {p.shape for p in placements(d, tiles.parse("5m")[0])}
    assert shapes == {WaitShape.KANCHAN}
    shapes = {p.shape for p in placements(d, tiles.parse("4m")[0])}
    assert shapes == {WaitShape.RYANMEN}
    shapes = {p.shape for p in placements(d, tiles.parse("7m")[0])}
    assert shapes == {WaitShape.PENCHAN}
    shapes = {p.shape for p in placements(d, tiles.parse("中")[0])}
    assert shapes == {WaitShape.TANKI}
    shapes = {p.shape for p in placements(d, tiles.parse("東")[0])}
    assert shapes == {WaitShape.SHANPON}


def test_ambiguous_placement_12345_plus_3():
    # 12345m + 3m: the 3 can complete 12 (edge) or 45 (two-sided)
    hand = c("123345m 789p 111s 東東東 中中")
    ds = decompositions(hand, 0)
    shapes = {p.shape for d in ds for p in placements(d, tiles.parse("3m")[0])}
    assert shapes == {WaitShape.PENCHAN, WaitShape.RYANMEN}
