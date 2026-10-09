from engine.game import Phase
from engine.match import finish_hand, new_match, ranks, start_hand


class _G:
    """Minimal finished-hand stand-in."""

    def __init__(self, result, scores=None):
        self.phase = Phase.ENDED
        self.result = result
        self.scores = scores or [0, 0, 0, 0]


def test_dealer_win_and_draw_keep_dealer():
    m = new_match()
    m = finish_hand(m, _G({"kind": "HU", "winner": 0}))
    assert (m.dealer, m.dealer_streak) == (0, 1)
    m = finish_hand(m, _G({"kind": "DRAW"}))
    assert (m.dealer, m.dealer_streak) == (0, 2)


def test_non_dealer_win_rotates_and_round_advances():
    m = new_match()
    for expected_dealer in (1, 2, 3):
        m = finish_hand(m, _G({"kind": "HU", "winner": (m.dealer + 1) % 4}))
        assert m.dealer == expected_dealer and m.round_wind == 0
    m = finish_hand(m, _G({"kind": "HU", "winner": 1}))
    assert m.dealer == 0 and m.round_wind == 1 and not m.finished


def test_streak_capped_at_nine():
    m = new_match()
    for _ in range(9):
        m = finish_hand(m, _G({"kind": "DRAW"}))
    assert m.dealer_streak == 9
    m = finish_hand(m, _G({"kind": "HU", "winner": 0}))
    assert m.dealer == 1 and m.dealer_streak == 0


def test_one_round_match_finishes():
    m = new_match(rounds=1)
    for _ in range(4):
        m = finish_hand(m, _G({"kind": "HU", "winner": (m.dealer + 1) % 4}))
    assert m.finished


def test_start_hand_uses_match_state():
    m = new_match(first_dealer=2)
    g = start_hand(m, seed=3)
    assert g.dealer == 2 and len(g.hands[2]) == 17


def test_ranks():
    assert ranks([100, -50, 100, -150]) == [1, 3, 2, 4]
