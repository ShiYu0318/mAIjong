from ai.explainability.candidate_scorer import score_all_discards
from engine import tiles
from tests.engine.test_game_rules import FILLER, build


def test_ranks_tenpai_discard_first_and_reports_waits():
    # discarding 北 leaves 123m 456m 789m 111p 57s 東東 waiting on 6s
    s = build(["123m 456m 789m 111p 57s 東東 北", FILLER[:16], FILLER[:16], FILLER[:16]])
    cands = score_all_discards(s, 0)
    best = cands[0]
    assert best.tile == tiles.parse("北")[0]
    assert best.shanten_after == 0 and best.waits == tiles.parse("6s")
    assert best.can_declare and best.best_tai is not None and best.best_tai >= 1
    assert all(c.shanten_after >= best.shanten_after for c in cands)


def test_not_my_turn_gives_nothing():
    s = build(["123m 456m 789m 111p 57s 東東 北", FILLER[:16], FILLER[:16], FILLER[:16]])
    assert score_all_discards(s, 1) == []
