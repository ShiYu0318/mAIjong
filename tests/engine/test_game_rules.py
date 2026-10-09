"""Scenario tests for rule edge cases (SPEC 02.9 E01-E24) on hand-crafted states."""

from __future__ import annotations

from engine import tiles
from engine.actions import Action, ActionType
from engine.game import (
    GameState,
    Phase,
    Source,
    acting_players,
    apply_action,
    get_legal_actions,
    new_game,
)
from engine.hand import Meld, MeldType

P = tiles.parse
A = ActionType
FILLER = "東南西北中發白東南西北中發白"  # junk drawable tiles


def build(
    hands: list[str],
    wall: str = FILLER,
    *,
    turn: int = 0,
    dealer: int = 0,
    melds: list[list[Meld]] | None = None,
    flowers: list[str] | None = None,
    last_draw: str | None = None,
    **kw,
) -> GameState:
    s = GameState(
        game_id="t",
        round_wind=0,
        dealer=dealer,
        dealer_streak=0,
        turn=turn,
        phase=Phase.DISCARD,
        hands=[sorted(P(h)) for h in hands],
        melds=melds or [[] for _ in range(4)],
        flowers=[P(f) for f in flowers] if flowers else [[] for _ in range(4)],
        discards=[[] for _ in range(4)],
        scores=[0, 0, 0, 0],
        declared_ting=[False] * 4,
        pass_lock=[False] * 4,
        pon_lock=[False] * 4,
        wall=P(wall),
        reserve=0,
        n_discards=[1, 1, 1, 1],
        n_draws=[1, 1, 1, 1],
        last_draw=P(last_draw)[0] if last_draw else None,
        draw_source=Source.WALL,
        **kw,
    )
    return s


def act(s: GameState, p: int, t: ActionType, tile: str | None = None) -> GameState:
    a = Action(t, P(tile)[0] if tile else None)
    s, _ = apply_action(s, p, a)
    return s


def legal_types(s: GameState, p: int) -> set[ActionType]:
    return {a.type for a in get_legal_actions(s, p)}


# tenpai 16-tile hand waiting on 6s (kanchan)
TENPAI_6S = "123m 456m 789m 111p 57s 東東"
# tenpai hand waiting on 東 / 中 (shanpon)
SHANPON = "123m 456m 789m 111p 東東 中中"


def test_new_game_deal_sizes_and_flowers_replaced():
    s = new_game(seed=1)
    assert len(s.hands[0]) == 17 and all(len(s.hands[p]) == 16 for p in (1, 2, 3))
    assert not any(tiles.is_flower(t) for h in s.hands for t in h)
    assert s.reserve == 16 and s.turn == 0


def test_closest_player_wins_when_several_can_hu():  # E08 攔胡
    s = build(["123m 456m 789m 111p 東東 9s 6s", TENPAI_6S, TENPAI_6S, TENPAI_6S], last_draw="6s")
    s = act(s, 0, A.DISCARD, "6s")
    assert s.phase is Phase.RESPONSE and set(s.pending_responses) == {1, 2, 3}
    s = act(s, 3, A.HU)
    s = act(s, 2, A.HU)
    s = act(s, 1, A.PASS)
    assert s.result and s.result["winner"] == 2  # seat 2 is nearer to the discarder than 3


def test_no_exposed_kong_from_left_player_and_chi_only_for_next():  # E03, 2.3
    s = build(["5s 123m 456m 789m 111p 東東 中", "555s 1m 2m 3m 4m 5m 6m 7m 8m 9m 9p 9p 9p",
               "555s 12345678m 9p 9p", "46s 123m 456m 789m 9p 9p 1p 1p"])
    s = act(s, 0, A.DISCARD, "5s")
    opts1 = {a.type for a in s.pending_responses[1]}
    assert A.PON in opts1 and A.KONG not in opts1  # seat 1's left player is seat 0
    opts2 = {a.type for a in s.pending_responses[2]}
    assert A.KONG in opts2 and A.CHI_LOW not in opts2
    assert 3 not in s.pending_responses  # 46s could chi, but only the next seat may


def test_chi_and_kuikae_restriction():  # E11
    s = build(["3s 123m 456m 789m 111p 東東 中", "45s 6s 12m 345m 789m 99p 1p 2p 中",
               FILLER[:16], FILLER[:16]])
    s = act(s, 0, A.DISCARD, "3s")
    s = act(s, 1, A.CHI_HIGH)  # 4-5 takes 3
    discards = {a.tile for a in get_legal_actions(s, 1) if a.type is A.DISCARD}
    assert P("3s")[0] not in discards and P("6s")[0] not in discards
    assert A.HU not in legal_types(s, 1) and A.KONG not in legal_types(s, 1)


def test_pass_on_win_locks_until_own_discard():  # E09 過水
    s = build(["6s 123m 456m 789m 111p 東東 中", TENPAI_6S, "123456789p 1s1s 2s2s 中中 發",
               "1p 2p 3p 4p 5p 7p 8p 9p 1m 1m 2m 2m 3m 3m 中 白"],
              wall="6s 東南西北中發白東南西北")
    s = act(s, 0, A.DISCARD, "6s")
    s = act(s, 1, A.PASS)
    assert s.pass_lock[1] and s.passed_win[1]
    # seat 1 draws the other 6s next: still locked, cannot self-draw
    assert s.turn == 1 and s.last_draw == P("6s")[0]
    assert A.HU not in legal_types(s, 1)
    s = act(s, 1, A.DISCARD, "6s")
    assert not s.pass_lock[1]


def test_pon_pass_lock_same_go_around():  # E10 過水碰
    s = build(["9s 123m 456m 789m 111p 東東 中", "123p 456p 789p 1m 1m 2m 2m 3m 3m 中 白",
               "99s 12m 345m 789m 1p 2p 3p 中 白 發", FILLER[:16]],
              wall="9s 東西北中發白東南西北中發白")
    s = act(s, 0, A.DISCARD, "9s")
    s = act(s, 2, A.PASS)
    assert s.pon_lock[2]
    # seat 1 draws the other 9s and discards it: seat 2 may not pon in the same go-around
    assert s.turn == 1 and s.last_draw == P("9s")[0]
    s = act(s, 1, A.DISCARD, "9s")
    assert 2 not in s.pending_responses


def test_exposed_kong_replacement_cannot_win():  # E04
    hand = "777p 123m 456m 789m 東東 6s 5s"  # after kong: 123 456 789 東東 5s6s... wait 4s/7s
    s = build(["7p 123m 456m 789m 111s 東東 中", FILLER[:16], hand, FILLER[:16]],
              wall="東南西北中發白 4s", turn=0)
    s = act(s, 0, A.DISCARD, "7p")
    s = act(s, 2, A.KONG, "7p")
    assert s.turn == 2 and s.last_draw == P("4s")[0]
    assert A.HU not in legal_types(s, 2)


def test_added_kong_can_be_robbed():  # E06 搶槓
    melds = [[], [Meld(MeldType.PON, tuple(P("5555s")[:3]), P("5s")[0], 0)], [], []]
    s = build(["123m 456m 789m 111p 46s 東東", "5s 123m 456m 789m 中 白 發 北",
               FILLER[:16], FILLER[:16]],
              melds=melds, turn=1, last_draw="5s")
    s = act(s, 1, A.KONG, "5s")
    assert s.phase is Phase.ROB_KONG and 0 in s.pending_responses
    s = act(s, 0, A.HU)
    assert s.result and s.result["winner"] == 0
    ids = {i["id"] for i in s.result["tai_breakdown"]}
    assert "T36" in ids and s.result["payers"] == [1]


def test_concealed_kong_replacement_win_is_kong_flower():  # E05 / T37
    s = build(["4444s 123m 456m 789m 東東 67s", FILLER[:16], FILLER[:16], FILLER[:16]],
              wall="東南西北中發白 8s", last_draw="6s")
    s = act(s, 0, A.KONG, "4s")
    assert s.last_draw == P("8s")[0] and A.HU in legal_types(s, 0)
    s = act(s, 0, A.HU)
    ids = {i["id"] for i in s.result["tai_breakdown"]}
    assert {"T37", "T06"} <= ids


def test_declared_ting_only_discards_drawn_tile():  # E15
    s = build([TENPAI_6S + " 北", FILLER[:16], FILLER[:16], FILLER[:16]], wall="南西北中發白")
    s = act(s, 0, A.TING, "北")
    assert s.declared_ting[0] and s.earth_ting[0] is False  # not first discard
    # everyone passes / draws until seat 0 again
    while s.turn != 0 or s.phase is not Phase.DISCARD:
        p = acting_players(s)[0]
        s = act(s, p, A.DISCARD, tiles.name(s.last_draw)) if s.phase is Phase.DISCARD else act(
            s, p, A.PASS)
    legal = get_legal_actions(s, 0)
    assert legal == [Action(A.DISCARD, s.last_draw)]


def test_no_calls_near_wall_end():  # E12
    s = build(["9s 123m 456m 789m 111p 東東 中", "99s 12m 345m 789m 1p 2p 3p 中 白 發",
               FILLER[:16], FILLER[:16]], wall="東南西")
    s = act(s, 0, A.DISCARD, "9s")
    assert s.phase is Phase.DISCARD  # no response offered; next player drew


def test_exhaustive_draw_when_wall_runs_out():  # E13
    s = build(["9s 123m 456m 789m 111p 東東 中", FILLER[:16], FILLER[:16], FILLER[:16]], wall="")
    s = act(s, 0, A.DISCARD, "9s")
    assert s.phase is Phase.ENDED and s.result == {
        "kind": "DRAW", "reason": "WALL_EXHAUSTED", "payments": [0, 0, 0, 0]}


def test_last_tile_flower_cannot_be_replaced():  # E14 / OQ-03
    s = build(["9s 123m 456m 789m 111p 東東 中", FILLER[:16], FILLER[:16], FILLER[:16]],
              wall="春 東")
    s.reserve = 1
    s = act(s, 0, A.DISCARD, "9s")
    assert s.result and s.result["kind"] == "DRAW"


def test_haidi_self_draw_scores_last_tile():  # T38
    s = build(["9s 123m 456m 789m 111p 東東 中", TENPAI_6S, FILLER[:16], FILLER[:16]],
              wall="6s")
    s = act(s, 0, A.DISCARD, "9s")
    s = act(s, 1, A.HU)
    ids = {i["id"] for i in s.result["tai_breakdown"]}
    assert "T38" in ids and "T06" in ids


def test_eight_flowers_during_play():  # E19
    flowers = ["春夏秋冬梅蘭菊", "", "", ""]
    s = build(["9s 123m 456m 789m 111p 東東 中", FILLER[:16], FILLER[:16], FILLER[:16]],
              wall="竹 東 北", flowers=flowers, turn=3)
    s.hands[3] = sorted(P("1s 123m 456m 789m 111p 東東 中"))
    s = act(s, 3, A.DISCARD, "1s")
    # seat 0 draws 竹 as the 8th flower → 八仙過海, three players pay
    assert s.result and s.result["winner"] == 0 and s.result["flower_win"] == "EIGHT"
    assert sorted(s.result["payers"]) == [1, 2, 3]
    ids = {i["id"]: i["tai"] for i in s.result["tai_breakdown"]}
    assert ids["T13"] == 8 and "T04" not in ids and "T10" not in ids


def test_seven_rob_one_when_other_draws_eighth():  # E20 (1)
    flowers = ["春夏秋冬梅蘭菊", "", "", ""]
    s = build(["123m 456m 789m 111p 57s 東東", "9s 123m 456m 789m 111p 東 中",
               FILLER[:16], FILLER[:16]], wall="竹 北 6s", flowers=flowers, turn=1,
              last_draw="9s")
    s = act(s, 1, A.DISCARD, "9s")
    # seat 2 draws 竹 (8th flower) → seat 0 robs it and draws replacement 6s → wins hand too
    assert s.result and s.result["winner"] == 0 and s.result["flower_win"] == "ROB_HELD_SEVEN"
    assert s.result["payers"] == [2]
    ids = {i["id"] for i in s.result["tai_breakdown"]}
    assert {"T14", "T37"} <= ids and "T04" not in ids and "T06" not in ids


def test_deal_flower_win_for_dealer():  # E18 配牌花胡
    s = new_game(seed=1)
    s.flowers[0] = P("春夏秋冬梅蘭菊竹")
    from engine.game import _check_deal_flower_win, _resolve_deferred_flower

    _check_deal_flower_win(s)
    _resolve_deferred_flower(s, [])
    ids = {i["id"]: i["tai"] for i in s.result["tai_breakdown"]}
    assert ids["T13"] == 8 and ids["T12"] == 4


def test_heavenly_hand():
    s = build(["123m 456m 789m 111p 東東東 中中", FILLER[:16], FILLER[:16], FILLER[:16]])
    s.n_discards = [0, 0, 0, 0]
    s.last_draw = None
    s.draw_source = Source.DEAL
    s = act(s, 0, A.HU)
    ids = {i["id"] for i in s.result["tai_breakdown"]}
    assert "T15" in ids
