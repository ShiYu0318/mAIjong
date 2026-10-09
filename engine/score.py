"""Tai (台) detection and settlement, following the Gamesofa (神來也) tai table.

`score_hand` finds the best-scoring interpretation of a win; `settle` turns it into
per-player payments: payment = BASE_POINTS + tai × TAI_POINTS, where the dealer tai
(1 + 2 × dealer_streak) only applies between the dealer and the other party.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from engine import tiles
from engine.hand import Meld, MeldType
from engine.hu import SEQ, TRI, Decomposition, WaitShape, decompositions, placements
from engine.ting import waiting_tiles

TAI_NAMES: dict[str, str] = {
    "T00": "屁胡", "T01": "莊家", "T02": "連莊拉莊", "T03": "宣告聽牌", "T04": "自摸",
    "T05": "門清", "T06": "門清自摸", "T07": "圈風刻", "T08": "門風刻", "T09": "三元刻",
    "T10": "正花", "T11": "花槓", "T12": "配牌花胡", "T13": "八仙過海", "T14": "七搶一",
    "T15": "天胡", "T16": "地胡", "T17": "人胡", "T18": "地聽", "T19": "大四喜",
    "T20": "小四喜", "T21": "大三元", "T22": "小三元", "T23": "字一色", "T24": "清一色",
    "T25": "湊一色", "T26": "五暗刻", "T27": "四暗刻", "T28": "三暗刻", "T29": "碰碰胡",
    "T30": "平胡", "T31": "全求人", "T32": "半求人", "T33": "中洞", "T34": "邊張",
    "T35": "單釣", "T36": "搶槓", "T37": "槓上開花", "T38": "海底撈月",
}


@dataclass(frozen=True, slots=True)
class TaiItem:
    id: str
    tai: int

    @property
    def name(self) -> str:
        return TAI_NAMES[self.id]

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "name": self.name, "tai": self.tai}


def item(tai_id: str, tai: int) -> TaiItem:
    return TaiItem(tai_id, tai)


class FlowerWin(StrEnum):
    EIGHT = "EIGHT"  # 八仙過海：winner holds all 8 flowers; three players pay
    ROB_HELD_SEVEN = "ROB_HELD_SEVEN"  # 七搶一(1)：winner held 7, another drew the 8th
    ROB_DREW_EIGHTH = "ROB_DREW_EIGHTH"  # 七搶一(2)：winner held 6, drew the 8th, robbed 1


@dataclass(frozen=True, slots=True)
class ScoringRules:
    base_points: int = 100
    tai_points: int = 50
    tai_cap: int | None = None


@dataclass(frozen=True)
class WinContext:
    winner: int
    dealer: int
    dealer_streak: int
    seat_wind: int
    round_wind: int
    concealed: tuple[int, ...]  # concealed tiles incl. the winning tile
    melds: tuple[Meld, ...]
    flowers: tuple[int, ...]
    win_tile: int | None  # None when only flowers win (hand incomplete)
    loser: int | None = None  # player who pays alone (discarder / robbed player)
    self_draw: bool = False  # earns 自摸 tai
    tile_from_other: bool = False  # winning tile was a discard / robbed kong (breaks 暗刻)
    declared_ting: bool = False
    earth_ting: bool = False  # 地聽 still valid (not voided by passing a win)
    rob_kong: bool = False
    kong_flower: bool = False  # 槓上開花
    last_tile: bool = False  # 海底撈月
    heavenly: bool = False
    earthly: bool = False
    human: bool = False
    flower_win: FlowerWin | None = None
    deal_flower_win: bool = False  # 配牌花胡
    robbed_from: int | None = None  # 七搶一: owner of the robbed flower


@dataclass
class HandScore:
    items: list[TaiItem]
    hand_complete: bool

    @property
    def tai(self) -> int:
        return sum(i.tai for i in self.items)


@dataclass
class Settlement:
    winner: int
    payers: list[int]
    hand_items: list[TaiItem]
    dealer_tai: int
    tai_by_payer: dict[int, int]
    payments: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    extra_by_payer: dict[int, list[TaiItem]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "winner": self.winner,
            "payers": self.payers,
            "tai_breakdown": [i.to_dict() for i in self.hand_items],
            "dealer_tai": self.dealer_tai,
            "tai_by_payer": {str(k): v for k, v in self.tai_by_payer.items()},
            "payments": self.payments,
        }


def flower_items(flowers: tuple[int, ...] | list[int], seat_wind: int) -> list[TaiItem]:
    """T10 正花 / T11 花槓 for one player's flowers."""
    out: list[TaiItem] = []
    owned = set(flowers)
    season, plant = tiles.seat_flowers(seat_wind)
    for group, mine in ((tiles.SEASON_TILES, season), (tiles.PLANT_TILES, plant)):
        if all(f in owned for f in group):
            out.append(item("T11", 2))
        elif mine in owned:
            out.append(item("T10", 1))
    return out


def dealer_tai(dealer_streak: int) -> int:
    return 1 + 2 * dealer_streak


def _suit_profile(all_tiles: list[int]) -> tuple[set[int], bool]:
    suits = {tiles.suit_of(t) for t in all_tiles if tiles.is_number(t)}
    has_honor = any(tiles.is_honor(t) for t in all_tiles)
    return suits, has_honor


def _score_decomposition(
    ctx: WinContext, d: Decomposition, single_wait: bool
) -> list[TaiItem]:
    assert ctx.win_tile is not None
    win = ctx.win_tile
    melds = ctx.melds
    by_discard = ctx.tile_from_other
    exposed = [m for m in melds if m.is_exposed]
    menzen = not exposed

    all_tiles = list(ctx.concealed) + [t for m in melds for t in m.tiles]
    suits, has_honor = _suit_profile(all_tiles)

    triplet_tiles = [g.tile for g in d.groups if g.kind == TRI] + [
        m.base_tile for m in melds if m.is_triplet
    ]
    seq_count = sum(1 for g in d.groups if g.kind == SEQ) + sum(
        1 for m in melds if m.type is MeldType.CHI
    )
    winds = [t for t in triplet_tiles if tiles.is_wind(t)]
    dragons = [t for t in triplet_tiles if tiles.is_dragon(t)]

    best: list[TaiItem] | None = None
    for pl in placements(d, win):
        items: list[TaiItem] = []

        # --- special timing
        if ctx.heavenly:
            items.append(item("T15", 24))
        if ctx.earthly:
            items.append(item("T16", 16))
        if ctx.human:
            items.append(item("T17", 8))
        earth = ctx.earth_ting and not ctx.human

        # --- ready declaration, menzen, self-draw
        if earth:
            items.append(item("T18", 4))
            if ctx.self_draw:
                items.append(item("T04", 2))
        else:
            if ctx.declared_ting:
                items.append(item("T03", 1))
            if menzen and ctx.self_draw:
                items.append(item("T06", 3))
            elif menzen:
                items.append(item("T05", 1))
            elif ctx.self_draw:
                items.append(item("T04", 1))

        # --- winds and dragons
        wind_pair = tiles.is_wind(d.pair)
        dragon_pair = tiles.is_dragon(d.pair)
        big_winds = len(winds) == 4
        small_winds = len(winds) == 3 and wind_pair
        if big_winds:
            items.append(item("T19", 16))
        else:
            if small_winds:
                items.append(item("T20", 8))
            if tiles.wind_tile(ctx.round_wind) in winds:
                items.append(item("T07", 1))
            if tiles.wind_tile(ctx.seat_wind) in winds:
                items.append(item("T08", 1))
        if len(dragons) == 3:
            items.append(item("T21", 8))
        elif len(dragons) == 2 and dragon_pair:
            items.append(item("T22", 4))
        else:
            items.extend(item("T09", 1) for _ in dragons)

        # --- suits
        all_honor = not suits
        if all_honor:
            items.append(item("T23", 8))
        elif len(suits) == 1 and not has_honor:
            items.append(item("T24", 8))
        elif len(suits) == 1 and has_honor:
            items.append(item("T25", 4))

        # --- concealed triplets and all-pungs
        concealed_tri = sum(1 for g in d.groups if g.kind == TRI)
        if by_discard and pl.group_index is not None and d.groups[pl.group_index].kind == TRI:
            concealed_tri -= 1
        concealed_tri += sum(1 for m in melds if m.type is MeldType.AN_KONG)
        if concealed_tri >= 5:
            items.append(item("T26", 8))
        elif concealed_tri == 4:
            items.append(item("T27", 5))
        elif concealed_tri == 3:
            items.append(item("T28", 2))
        if seq_count == 0 and not all_honor:
            items.append(item("T29", 4))

        # --- hand shape
        all_exposed = len(exposed) == 5
        if all_exposed:
            items.append(item("T32" if ctx.self_draw else "T31", 1 if ctx.self_draw else 2))
        shapes = {p.shape for p in placements(d, win)}
        if (
            seq_count == 5
            and tiles.is_number(d.pair)
            and not ctx.flowers
            and not ctx.self_draw
            and shapes == {WaitShape.RYANMEN}
        ):
            items.append(item("T30", 2))
        if single_wait:
            if pl.shape is WaitShape.KANCHAN:
                items.append(item("T33", 1))
            elif pl.shape is WaitShape.PENCHAN:
                items.append(item("T34", 1))
            elif pl.shape is WaitShape.TANKI and not all_exposed:
                items.append(item("T35", 1))

        # --- winning circumstances
        if ctx.rob_kong:
            items.append(item("T36", 1))
        if ctx.kong_flower:
            items.append(item("T37", 1))
        if ctx.last_tile:
            items.append(item("T38", 1))

        if best is None or sum(i.tai for i in items) > sum(i.tai for i in best):
            best = items
    assert best is not None
    return best


def score_hand(ctx: WinContext) -> HandScore:
    """Best tai interpretation of the winning hand (dealer tai excluded)."""
    items: list[TaiItem] = []
    complete = False
    if ctx.win_tile is not None:
        counts = tiles.to_counts(list(ctx.concealed))
        n_melds = len(ctx.melds)
        ds = decompositions(counts, n_melds)
        if ds:
            complete = True
            before = list(counts)
            before[ctx.win_tile] -= 1
            single = waiting_tiles(before, n_melds) == [ctx.win_tile]
            candidates = [_score_decomposition(ctx, d, single) for d in ds]
            items = max(candidates, key=lambda its: sum(i.tai for i in its))

    if ctx.flower_win is None:
        items += flower_items(ctx.flowers, ctx.seat_wind)
    elif ctx.flower_win is FlowerWin.EIGHT:
        items.append(item("T13", 8))
    else:
        items.append(item("T14", 8))
    if ctx.flower_win is not None and ctx.deal_flower_win:
        items.append(item("T12", 4))
    if not items or sum(i.tai for i in items) == 0:
        items.append(item("T00", 0))
    return HandScore(items, complete)


def _apply_cap(tai: int, rules: ScoringRules) -> int:
    return tai if rules.tai_cap is None else min(tai, rules.tai_cap)


def settle(ctx: WinContext, rules: ScoringRules | None = None) -> Settlement:
    """Score a win and compute everyone's payment (positive = receives)."""
    rules = rules or ScoringRules()
    score = score_hand(ctx)
    d_tai = dealer_tai(ctx.dealer_streak)
    others = [p for p in range(4) if p != ctx.winner]
    hand_tai = score.tai
    extras: dict[int, list[TaiItem]] = {}

    fw = ctx.flower_win
    if fw is FlowerWin.EIGHT:
        payers = others
    elif fw is FlowerWin.ROB_HELD_SEVEN:
        assert ctx.robbed_from is not None
        payers = [ctx.robbed_from]
    elif fw is FlowerWin.ROB_DREW_EIGHTH:
        assert ctx.robbed_from is not None
        if score.hand_complete:
            # treated as self-draw: everyone pays the hand; flower part paid separately
            payers = others
            flower_part = [i for i in score.items if i.id in ("T14", "T12")]
            hand_tai = sum(i.tai for i in score.items if i.id not in ("T14", "T12"))
            own_flowers = tuple(f for f in ctx.flowers if f not in _robbed_flower(ctx))
            for p in others:
                extras[p] = (
                    flower_part
                    if p == ctx.robbed_from
                    else flower_items(own_flowers, ctx.seat_wind)
                )
        else:
            payers = [ctx.robbed_from]
    elif ctx.self_draw:
        payers = others
    else:
        assert ctx.loser is not None
        payers = [ctx.loser]

    tai_by_payer: dict[int, int] = {}
    payments = [0, 0, 0, 0]
    for p in payers:
        tai_p = hand_tai + sum(i.tai for i in extras.get(p, []))
        if ctx.dealer in (ctx.winner, p):
            tai_p += d_tai
        tai_p = _apply_cap(tai_p, rules)
        tai_by_payer[p] = tai_p
        amount = rules.base_points + tai_p * rules.tai_points
        payments[p] -= amount
        payments[ctx.winner] += amount

    return Settlement(
        winner=ctx.winner,
        payers=payers,
        hand_items=score.items,
        dealer_tai=d_tai if ctx.dealer == ctx.winner or ctx.dealer in payers else 0,
        tai_by_payer=tai_by_payer,
        payments=payments,
        extra_by_payer=extras,
    )


def _robbed_flower(ctx: WinContext) -> tuple[int, ...]:
    """The flower taken in 七搶一 is recorded as the last flower of the winner."""
    return ctx.flowers[-1:] if ctx.flowers else ()
