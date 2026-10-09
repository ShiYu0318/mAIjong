"""Tai and settlement tests, many taken from the official Gamesofa tai table examples."""

from __future__ import annotations

from engine import tiles
from engine.hand import Meld, MeldType
from engine.score import (
    FlowerWin,
    ScoringRules,
    WinContext,
    dealer_tai,
    flower_items,
    score_hand,
    settle,
)

P = tiles.parse
EAST, SOUTH, WEST, NORTH = 0, 1, 2, 3


def meld(kind: MeldType, text: str) -> Meld:
    ts = tuple(P(text))
    return Meld(kind, ts, called=ts[0] if kind is not MeldType.AN_KONG else None)


def ctx(
    concealed: str,
    win: str | None,
    *,
    melds: tuple[Meld, ...] = (),
    flowers: str = "",
    seat: int = SOUTH,
    round_wind: int = EAST,
    winner: int = 1,
    dealer: int = 0,
    streak: int = 0,
    **kw,
) -> WinContext:
    hand = P(concealed)
    win_tile = None
    if win is not None:
        win_tile = P(win)[0]
        hand.append(win_tile)
    self_draw = kw.pop("self_draw", False)
    loser = kw.pop("loser", None if self_draw else 2)
    return WinContext(
        winner=winner,
        dealer=dealer,
        dealer_streak=streak,
        seat_wind=seat,
        round_wind=round_wind,
        concealed=tuple(sorted(hand)),
        melds=melds,
        flowers=tuple(P(flowers)) if flowers else (),
        win_tile=win_tile,
        loser=loser,
        self_draw=self_draw,
        tile_from_other=kw.pop("tile_from_other", not self_draw),
        **kw,
    )


def ids(c: WinContext) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in score_hand(c).items:
        out[i.id] = out.get(i.id, 0) + i.tai
    return out


# ---------------------------------------------------------------- official examples


def test_seven_rob_one_case1_official():
    # 南風圈上家開門；手牌 11444555777萬 發發，外露 南南南 +發 → 25 台，不計自摸
    c = ctx(
        "11444555777m 發發", "發",
        melds=(meld(MeldType.PON, "南南南"),),
        flowers="春夏秋冬梅蘭竹菊", seat=SOUTH, round_wind=SOUTH,
        winner=1, dealer=0, loser=3, robbed_from=3,
        flower_win=FlowerWin.ROB_HELD_SEVEN, kong_flower=True, tile_from_other=False,
    )
    got = ids(c)
    assert got == {"T37": 1, "T09": 1, "T07": 1, "T08": 1, "T29": 4, "T25": 4, "T27": 5, "T14": 8}
    assert score_hand(c).tai == 25
    s = settle(c)
    assert s.payers == [3]


def test_seven_rob_one_case2_official():
    # 西風圈對家開門；34567條 88899萬 西西西 白白白 +2條，自摸 → 各家 9 台；
    # 被搶花者另付七搶一 8 台，另兩家另付 秋1 + 花槓2 = 3 台
    c = ctx(
        "34567s 88899m 西西西 白白白", "2s",
        flowers="春秋冬梅蘭菊竹夏", seat=WEST, round_wind=WEST,
        winner=2, dealer=0, self_draw=True, robbed_from=1,
        flower_win=FlowerWin.ROB_DREW_EIGHTH, kong_flower=True,
    )
    hand = {k: v for k, v in ids(c).items() if k != "T14"}
    assert hand == {"T37": 1, "T06": 3, "T09": 1, "T07": 1, "T08": 1, "T28": 2}
    s = settle(c, ScoringRules(100, 50))
    assert sorted(s.payers) == [0, 1, 3]
    assert s.tai_by_payer == {0: 9 + 3 + 1, 1: 9 + 8, 3: 9 + 3}
    assert s.payments[1] == -(100 + 17 * 50)
    assert sum(s.payments) == 0


def test_eight_flowers_without_hand_official():
    # 八仙過海、手牌未胡：各家 1 底 8 台，自摸不計
    c = ctx(
        "123m 456m 789m 111p 東東 中", None,
        flowers="春夏秋冬蘭菊竹梅", self_draw=True, flower_win=FlowerWin.EIGHT,
    )
    assert ids(c) == {"T13": 8}
    s = settle(c)
    assert sorted(s.payers) == [0, 2, 3]
    assert s.tai_by_payer == {0: 8 + 1, 2: 8, 3: 8}


def test_eight_flowers_with_hand():
    # 23444 555777筒 北北 中中中 +1筒（槓上開花）：官方範例列 20 台但漏列門清；
    # 依台數表門清自摸為 3 台，因此為 22 台（見規格 OQ-05）。
    c = ctx(
        "23444555777p 北北 中中中", "1p",
        flowers="春夏秋冬蘭菊竹梅", self_draw=True, kong_flower=True,
        flower_win=FlowerWin.EIGHT,
    )
    assert ids(c) == {"T37": 1, "T06": 3, "T09": 1, "T25": 4, "T27": 5, "T13": 8}


def test_settlement_formula_official_example():
    # 100 底 / 50 台：放槍者付 底 + 台 × 每台
    c = ctx("333567789p 23444s 46m", "5m", winner=1, dealer=0, loser=2)
    s = settle(c, ScoringRules(100, 50))
    tai = s.tai_by_payer[2]
    assert s.payers == [2]
    assert s.payments[2] == -(100 + 50 * tai)
    assert s.payments[1] == 100 + 50 * tai


def test_dealer_tai_six_streak():
    assert dealer_tai(6) == 13
    assert dealer_tai(0) == 1


def test_dealer_tai_only_between_dealer_and_other():
    # non-dealer self-draw: only the dealer pays dealer tai
    c = ctx("123m 456m 789m 111p 東東", "東", self_draw=True, winner=1, dealer=0, streak=2)
    s = settle(c)
    base = score_hand(c).tai
    assert s.tai_by_payer == {0: base + 5, 2: base, 3: base}


def test_single_waits_official():
    assert ids(ctx("333567789p 23444s 46m", "5m")) == {"T05": 1, "T33": 1}
    assert ids(ctx("111p 12 44567s 234678m", "3s")) == {"T05": 1, "T34": 1}
    assert ids(ctx("234456p 667788s 222m 中", "中")) == {"T05": 1, "T35": 1}


# ---------------------------------------------------------------- 平胡


def test_pinghu_basic():
    assert ids(ctx("123m 456m 789p 234s 67s 55p", "8s")) == {"T05": 1, "T30": 2}


def test_pinghu_excluded_cases():
    # 12345 胡 3：不計邊張亦不計平胡
    assert "T30" not in ids(ctx("12345m 789p 234s 567s 88p", "3m"))
    assert "T34" not in ids(ctx("12345m 789p 234s 567s 88p", "3m"))
    # 56789 胡 7
    assert "T30" not in ids(ctx("56789m 789p 234s 567s 88p", "7m"))
    # 聽將眼 4566 胡 6
    assert "T30" not in ids(ctx("4566m 123p 789p 234s 567s", "6m"))
    # 雙邊單吊 2345 胡 5
    assert "T30" not in ids(ctx("2345m 123p 789p 234s 567s", "5m"))
    # 自摸、有花、有字將 皆不計
    assert "T30" not in ids(ctx("123m 456m 789p 234s 67s 55p", "8s", self_draw=True))
    assert "T30" not in ids(ctx("123m 456m 789p 234s 67s 55p", "8s", flowers="春"))
    assert "T30" not in ids(ctx("123m 456m 789p 234s 67s 東東", "8s"))


# ---------------------------------------------------------------- combinations


def test_menzen_tsumo_is_three():
    got = ids(ctx("123m 456m 789p 234s 67s 55p", "8s", self_draw=True))
    assert got == {"T06": 3}


def test_four_concealed_plus_all_pungs_is_nine():
    got = ids(ctx("111m 555p 999s 東東東 中", "中", self_draw=True, seat=SOUTH,
                  melds=(meld(MeldType.PON, "777s"),)))
    assert got["T27"] == 5 and got["T29"] == 4 and "T28" not in got


def test_discard_completing_triplet_is_not_concealed():
    # shanpon wait won on a discard: that triplet is open
    got = ids(ctx("111m 555p 999s 234m 中中 東東", "東"))
    assert got.get("T28") == 2  # 111m 555p 999s only
    assert "T27" not in got


def test_big_dragons_with_half_flush():
    got = ids(ctx("123m 45m 99m 中中中 發發發 白白白", "6m"))
    assert got["T21"] == 8 and got["T25"] == 4 and "T09" not in got


def test_small_dragons_excludes_dragon_triplets():
    got = ids(ctx("456777s 789p 中中中 發發 白白", "白"))
    assert got["T22"] == 4 and "T09" not in got


def test_all_honors_no_all_pungs_but_honor_tai():
    got = ids(ctx("東東東 西西西 中中中 白白白 發發 北北", "北", seat=WEST, round_wind=EAST))
    assert got["T23"] == 8 and "T29" not in got
    # 中中中 白白白 + 發發 is also 小三元, which replaces the dragon triplet tai
    assert got["T07"] == 1 and got["T08"] == 1 and got["T22"] == 4 and "T09" not in got


def test_small_and_big_four_winds():
    small = ids(ctx("77p 444s 東東東 南南 西西西 北北北", "7p", seat=WEST, round_wind=EAST))
    assert small["T20"] == 8 and small["T07"] == 1 and small["T08"] == 1
    big = ids(ctx("678m 33p 東東東 南南南 西西西 北北", "北", seat=WEST))
    assert big["T19"] == 16 and "T07" not in big and "T08" not in big


def test_full_flush_and_seven_waits():
    got = ids(ctx("111 2334456667788s", "9s"))
    assert got["T24"] == 8


def test_all_from_others():
    melds = (
        meld(MeldType.CHI, "123m"), meld(MeldType.CHI, "456m"),
        meld(MeldType.PON, "777p"), meld(MeldType.CHI, "234s"), meld(MeldType.PON, "999s"),
    )
    full = ids(ctx("9m", "9m", melds=melds))
    assert full == {"T31": 2}
    half = ids(ctx("9m", "9m", melds=melds, self_draw=True))
    assert half == {"T04": 1, "T32": 1}


def test_concealed_kong_keeps_menzen_and_counts_concealed():
    melds = (meld(MeldType.AN_KONG, "5555p"),)
    got = ids(ctx("111m 999s 234m 東東 中中", "中", melds=melds, self_draw=True))
    assert got["T06"] == 3 and got["T27"] == 5


def test_earth_ting_self_draw_is_four_plus_two():
    got = ids(ctx("123m 456m 789p 234s 67s 55p", "8s", self_draw=True,
                  declared_ting=True, earth_ting=True))
    assert got == {"T18": 4, "T04": 2}


def test_declared_ting_adds_one():
    got = ids(ctx("123m 456m 789p 234s 67s 55p", "8s", declared_ting=True))
    assert got == {"T03": 1, "T05": 1, "T30": 2}


def test_human_win_excludes_earth_ting():
    got = ids(ctx("123m 456m 789p 234s 67s 55p", "8s", human=True,
                  declared_ting=True, earth_ting=True))
    assert got["T17"] == 8 and "T18" not in got and got["T03"] == 1


def test_heavenly_stacks():
    got = ids(ctx("123m 456m 789p 234s 67s 55p", "8s", heavenly=True, self_draw=True,
                  winner=0, dealer=0))
    assert got == {"T15": 24, "T06": 3}


def test_special_circumstances():
    got = ids(ctx("123m 456m 789p 111s 67s 55p", "8s", rob_kong=True))
    assert got["T36"] == 1
    got = ids(ctx("123m 456m 789p 111s 67s 55p", "8s", self_draw=True, kong_flower=True,
                  last_tile=True))
    assert got["T37"] == 1 and got["T38"] == 1 and got["T06"] == 3


def test_flowers():
    assert [i.id for i in flower_items(tuple(P("春梅")), EAST)] == ["T10", "T10"]
    assert [i.id for i in flower_items(tuple(P("夏")), EAST)] == []
    assert [(i.id, i.tai) for i in flower_items(tuple(P("春夏秋冬梅")), EAST)] == [
        ("T11", 2), ("T10", 1)
    ]


def test_chicken_hand_and_cap():
    melds = (meld(MeldType.CHI, "123m"), meld(MeldType.CHI, "456m"))
    c = ctx("789p 234s 567s 東東", "8p", melds=melds)
    assert ids(c) == {"T00": 0}
    s = settle(c, ScoringRules(100, 50))
    assert s.payments[2] == -100
    big = ctx("東東東 西西西 中中中 白白白 發發 北北", "北", seat=WEST)
    s = settle(big, ScoringRules(100, 50, tai_cap=10))
    assert s.tai_by_payer[2] == 10
