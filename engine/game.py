"""Hand (一手) state machine.

`apply_action(state, player, action)` is pure: it returns a new state plus the events
that happened, and never mutates its input. Drawing, flower replacement and
exhaustive draws happen automatically between player decisions.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field, fields
from enum import StrEnum
from typing import Any

from engine import tiles
from engine.actions import CHI_ACTIONS, Action, ActionType, encode_action
from engine.hand import Meld, MeldType, add_tile, remove_tiles
from engine.score import FlowerWin, ScoringRules, Settlement, WinContext, settle
from engine.shanten import is_complete
from engine.ting import tenpai_discards
from engine.wall import WALL_RESERVE, deal, drawable, shuffled_wall


class Phase(StrEnum):
    DISCARD = "DISCARD"  # `turn` acts after drawing / calling
    RESPONSE = "RESPONSE"  # others react to the last discard
    ROB_KONG = "ROB_KONG"  # others may rob an added kong
    ENDED = "ENDED"


class Source(StrEnum):
    DEAL = "DEAL"
    WALL = "WALL"
    FLOWER = "FLOWER"  # replacement after a flower
    KONG = "KONG"  # replacement after a concealed / added kong
    MING_KONG = "MING_KONG"  # replacement after an exposed kong (cannot win on it)


class IllegalAction(ValueError):
    pass


LOW_SEQ = 2  # chi variants: offsets of the two hand tiles relative to the discard
_CHI_OFFSETS = {
    ActionType.CHI_LOW: (-2, -1),
    ActionType.CHI_MID: (-1, 1),
    ActionType.CHI_HIGH: (1, 2),
}


@dataclass
class GameState:
    game_id: str
    round_wind: int
    dealer: int
    dealer_streak: int
    turn: int
    phase: Phase
    hands: list[list[int]]
    melds: list[list[Meld]]
    flowers: list[list[int]]
    discards: list[list[int]]
    scores: list[int]
    declared_ting: list[bool]
    pass_lock: list[bool]
    pon_lock: list[bool]
    wall: list[int]
    reserve: int
    last_discard: tuple[int, int] | None = None
    pending_responses: dict[int, list[Action]] = field(default_factory=dict)
    responses: dict[int, Action] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    seed: int | None = None
    rules: ScoringRules = field(default_factory=ScoringRules)
    # --- bookkeeping for rules and scoring
    last_draw: int | None = None
    draw_source: Source = Source.DEAL
    no_self_win: bool = False  # after an exposed kong until the next discard (E04)
    after_call: tuple[str, int] | None = None  # (call type, called tile) restricting discards
    n_draws: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    n_discards: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    any_call: bool = False
    earth_ting: list[bool] = field(default_factory=lambda: [False] * 4)
    passed_win: list[bool] = field(default_factory=lambda: [False] * 4)
    last_draw_is_haidi: bool = False
    last_discard_is_haidi: bool = False
    rob_kong: tuple[int, int] | None = None  # (kong player, tile)
    deferred_flower: tuple[int, str, int | None] | None = None  # (winner, kind, robbed)
    result: dict[str, Any] | None = None

    # ------------------------------------------------------------------ helpers
    def seat_wind(self, player: int) -> int:
        return (player - self.dealer) % 4

    def drawable(self) -> int:
        return drawable(self.wall, self.reserve)

    def clone(self) -> GameState:
        values = {f.name: _copy(getattr(self, f.name)) for f in fields(self) if f.name != "events"}
        return GameState(events=list(self.events), **values)  # events are never mutated

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in fields(self):
            out[f.name] = _jsonable(getattr(self, f.name))
        return out


def _copy(v: Any) -> Any:
    if isinstance(v, list):
        return [_copy(x) for x in v]
    if isinstance(v, dict):
        return {k: _copy(x) for k, x in v.items()}
    return v


def _jsonable(v: Any) -> Any:
    if isinstance(v, Meld | Action):
        return v.to_dict()
    if isinstance(v, ScoringRules):
        return {"base_points": v.base_points, "tai_points": v.tai_points, "tai_cap": v.tai_cap}
    if isinstance(v, StrEnum):
        return v.value
    if isinstance(v, list | tuple):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return v


# ====================================================================== setup


def new_game(
    seed: int | None = None,
    *,
    dealer: int = 0,
    round_wind: int = 0,
    dealer_streak: int = 0,
    scores: list[int] | None = None,
    rules: ScoringRules | None = None,
    game_id: str | None = None,
) -> GameState:
    """Shuffle, deal, replace initial flowers and hand the dealer their first turn."""
    if seed is None:
        seed = random.randrange(2**63)
    rng = random.Random(seed)
    hands, wall = deal(shuffled_wall(rng), dealer)
    s = GameState(
        game_id=game_id or uuid.uuid4().hex,
        round_wind=round_wind,
        dealer=dealer,
        dealer_streak=dealer_streak,
        turn=dealer,
        phase=Phase.DISCARD,
        hands=hands,
        melds=[[] for _ in range(4)],
        flowers=[[] for _ in range(4)],
        discards=[[] for _ in range(4)],
        scores=list(scores) if scores else [0, 0, 0, 0],
        declared_ting=[False] * 4,
        pass_lock=[False] * 4,
        pon_lock=[False] * 4,
        wall=wall,
        reserve=WALL_RESERVE,
        seed=seed,
        rules=rules or ScoringRules(),
    )
    events: list[dict[str, Any]] = []
    _emit(s, events, "DEAL", dealer, extra={"hands": [list(h) for h in hands]})
    _initial_flowers(s, events)
    _check_deal_flower_win(s)
    if s.deferred_flower and s.deferred_flower[0] == dealer:
        _resolve_deferred_flower(s, events)
    return s


def _initial_flowers(s: GameState, events: list[dict[str, Any]]) -> None:
    """E01: replace flowers round by round starting from the dealer."""
    while True:
        replaced = False
        for k in range(4):
            p = (s.dealer + k) % 4
            fl = [t for t in s.hands[p] if tiles.is_flower(t)]
            if not fl:
                continue
            replaced = True
            for f in fl:
                s.hands[p].remove(f)
                s.flowers[p].append(f)
                _emit(s, events, "FLOWER", p, f)
            for _ in fl:
                t = s.wall.pop()
                s.hands[p] = add_tile(s.hands[p], t)
        if not replaced:
            return


def _check_deal_flower_win(s: GameState) -> None:
    """配牌花胡: 8 flowers, or 7 with another player holding the 8th, after the deal."""
    for p in range(4):
        n = len(s.flowers[p])
        if n == 8:
            s.deferred_flower = (p, FlowerWin.EIGHT.value, None)
            return
        if n == 7:
            other = next((q for q in range(4) if q != p and s.flowers[q]), None)
            if other is not None:
                s.deferred_flower = (p, FlowerWin.ROB_HELD_SEVEN.value, other)
                return


# ====================================================================== queries


def get_legal_actions(s: GameState, player: int) -> list[Action]:
    if s.phase is Phase.ENDED:
        return []
    if s.phase is Phase.DISCARD:
        return _turn_actions(s, player) if player == s.turn else []
    if player in s.pending_responses and player not in s.responses:
        return list(s.pending_responses[player])
    return []


def acting_players(s: GameState) -> list[int]:
    """Players who currently owe a decision."""
    if s.phase is Phase.DISCARD:
        return [s.turn]
    if s.phase in (Phase.RESPONSE, Phase.ROB_KONG):
        return [p for p in sorted(s.pending_responses) if p not in s.responses]
    return []


def _counts(s: GameState, p: int) -> list[int]:
    return tiles.to_counts(s.hands[p])


def _forbidden_discards(s: GameState) -> set[int]:
    """E11: no discarding the called tile (or its 同絡 tile after chi)."""
    if s.after_call is None:
        return set()
    kind, t = s.after_call
    out = {t}
    if kind == ActionType.CHI_LOW.value and tiles.is_number(t) and tiles.rank_of(t) >= 4:
        out.add(t - 3)
    if kind == ActionType.CHI_HIGH.value and tiles.is_number(t) and tiles.rank_of(t) <= 6:
        out.add(t + 3)
    return out


def _can_self_win(s: GameState, p: int) -> bool:
    return (
        s.after_call is None
        and not s.no_self_win
        and not s.pass_lock[p]
        and is_complete(_counts(s, p), len(s.melds[p]))
    )


def _turn_actions(s: GameState, p: int) -> list[Action]:
    counts = _counts(s, p)
    n_melds = len(s.melds[p])
    acts: list[Action] = []
    if _can_self_win(s, p):
        acts.append(Action(ActionType.HU))
    can_kong = s.after_call is None and s.drawable() >= 2
    if s.declared_ting[p]:
        if s.last_draw is not None:
            acts.append(Action(ActionType.DISCARD, s.last_draw))
        if can_kong:
            acts.extend(Action(ActionType.KONG, t) for t in range(34) if counts[t] == 4)
        return acts

    forbidden = _forbidden_discards(s)
    options = [t for t in range(34) if counts[t] and t not in forbidden]
    if not options:  # degenerate: everything forbidden
        options = [t for t in range(34) if counts[t]]
    acts.extend(Action(ActionType.DISCARD, t) for t in options)
    ready = set(tenpai_discards(counts, n_melds))
    acts.extend(Action(ActionType.TING, t) for t in options if t in ready)
    if can_kong:
        pons = {m.base_tile for m in s.melds[p] if m.type is MeldType.PON}
        for t in range(34):
            if counts[t] == 4 or (counts[t] >= 1 and t in pons):
                acts.append(Action(ActionType.KONG, t))
    return acts


# ====================================================================== transitions


def apply_action(
    state: GameState, player: int, action: Action
) -> tuple[GameState, list[dict[str, Any]]]:
    if action not in get_legal_actions(state, player):
        raise IllegalAction(f"player {player} cannot {action} in phase {state.phase}")
    s = state.clone()
    events: list[dict[str, Any]] = []
    if s.phase is Phase.DISCARD:
        _apply_turn(s, player, action, events)
    else:
        s.responses[player] = action
        if action.type is ActionType.PASS:
            _emit(s, events, "PASS", player, action=action)
        if not acting_players(s):
            if s.phase is Phase.RESPONSE:
                _resolve_responses(s, events)
            else:
                _resolve_rob_kong(s, events)
    return s, events


def _apply_turn(s: GameState, p: int, a: Action, events: list[dict[str, Any]]) -> None:
    could_win = _can_self_win(s, p)
    if a.type is ActionType.HU:
        _win_self_draw(s, p, events)
        return
    if could_win:  # passing on a self-drawn win (過水)
        s.pass_lock[p] = True
        s.passed_win[p] = True
    if a.type in (ActionType.DISCARD, ActionType.TING):
        assert a.tile is not None
        _discard(s, p, a.tile, a.type is ActionType.TING, events)
    elif a.type is ActionType.KONG:
        assert a.tile is not None
        if _counts(s, p)[a.tile] == 4:
            _concealed_kong(s, p, a.tile, events)
        else:
            _start_added_kong(s, p, a.tile, events)


def _discard(
    s: GameState, p: int, t: int, declare: bool, events: list[dict[str, Any]]
) -> None:
    s.hands[p] = remove_tiles(s.hands[p], t)
    s.discards[p].append(t)
    s.n_discards[p] += 1
    if declare:
        s.declared_ting[p] = True
        s.earth_ting[p] = s.n_discards[p] == 1 and not s.melds[p]
    s.pass_lock[p] = False  # 過水 lifts once the player discards (OQ-01)
    s.after_call = None
    s.no_self_win = False
    s.last_draw = None
    s.last_discard = (p, t)
    s.last_discard_is_haidi = s.drawable() <= 0
    _emit(s, events, "TING" if declare else "DISCARD", p, t,
          action=Action(ActionType.TING if declare else ActionType.DISCARD, t))

    pending: dict[int, list[Action]] = {}
    last = s.drawable() <= 0
    late = s.drawable() <= 3  # E12
    for k in range(1, 4):
        q = (p + k) % 4
        counts = _counts(s, q)
        opts: list[Action] = []
        win_counts = list(counts)
        win_counts[t] += 1
        if not s.pass_lock[q] and is_complete(win_counts, len(s.melds[q])):
            opts.append(Action(ActionType.HU))
        if not last and not late and not s.declared_ting[q]:
            if counts[t] >= 2 and not s.pon_lock[q]:
                opts.append(Action(ActionType.PON))
            if counts[t] == 3 and k != 1 and s.drawable() >= 2:
                opts.append(Action(ActionType.KONG, t))
            if k == 1 and tiles.is_number(t):
                for ct, (o1, o2) in _CHI_OFFSETS.items():
                    a, b = t + o1, t + o2
                    if _same_suit(t, a) and _same_suit(t, b) and counts[a] and counts[b]:
                        opts.append(Action(ct))
        if opts:
            pending[q] = [*opts, Action(ActionType.PASS)]
    if pending:
        s.phase = Phase.RESPONSE
        s.pending_responses = pending
        s.responses = {}
    else:
        _next_turn(s, (p + 1) % 4, events)


def _same_suit(a: int, b: int) -> bool:
    return 0 <= b < 27 and tiles.is_number(a) and a // 9 == b // 9


def _closest(order_from: int, players: list[int]) -> int:
    return min(players, key=lambda q: (q - order_from) % 4)


def _resolve_responses(s: GameState, events: list[dict[str, Any]]) -> None:
    assert s.last_discard is not None
    d, t = s.last_discard
    resp = dict(s.responses)
    pending = dict(s.pending_responses)
    s.pending_responses, s.responses = {}, {}

    hu = [q for q, a in resp.items() if a.type is ActionType.HU]
    if hu:
        _win_on_discard(s, _closest(d, hu), d, t, events)
        return
    for q, opts in pending.items():
        chosen = resp[q]
        if Action(ActionType.HU) in opts:
            s.pass_lock[q] = True
            s.passed_win[q] = True
        if Action(ActionType.PON) in opts and chosen.type is ActionType.PASS:
            s.pon_lock[q] = True

    claim = next(
        (q for q, a in resp.items() if a.type in (ActionType.PON, ActionType.KONG)), None
    )
    if claim is None:
        claim = next((q for q, a in resp.items() if a.type in CHI_ACTIONS), None)
    if claim is None:
        _next_turn(s, (d + 1) % 4, events)
        return

    a = resp[claim]
    s.discards[d].pop()
    s.any_call = True
    s.turn = claim
    s.phase = Phase.DISCARD
    s.last_draw = None
    if a.type is ActionType.PON:
        s.hands[claim] = remove_tiles(s.hands[claim], t, t)
        s.melds[claim].append(Meld(MeldType.PON, (t, t, t), t, d))
        s.after_call = (ActionType.PON.value, t)
        _emit(s, events, "PON", claim, t, action=a, extra={"from": d})
    elif a.type is ActionType.KONG:
        s.hands[claim] = remove_tiles(s.hands[claim], t, t, t)
        s.melds[claim].append(Meld(MeldType.MING_KONG, (t, t, t, t), t, d))
        s.after_call = None
        _emit(s, events, "KONG", claim, t, action=a, extra={"from": d, "kind": "MING_KONG"})
        s.reserve += 1
        s.no_self_win = True
        _draw(s, claim, Source.MING_KONG, events)
    else:
        o1, o2 = _CHI_OFFSETS[a.type]
        s.hands[claim] = remove_tiles(s.hands[claim], t + o1, t + o2)
        seq = tuple(sorted((t, t + o1, t + o2)))
        s.melds[claim].append(Meld(MeldType.CHI, seq, t, d))
        s.after_call = (a.type.value, t)
        _emit(s, events, "CHI", claim, t, action=a, extra={"from": d, "tiles": list(seq)})


def _concealed_kong(s: GameState, p: int, t: int, events: list[dict[str, Any]]) -> None:
    s.hands[p] = remove_tiles(s.hands[p], t, t, t, t)
    s.melds[p].append(Meld(MeldType.AN_KONG, (t, t, t, t)))
    _emit(s, events, "KONG", p, t, action=Action(ActionType.KONG, t), extra={"kind": "AN_KONG"})
    s.reserve += 1
    _draw(s, p, Source.KONG, events)


def _start_added_kong(s: GameState, p: int, t: int, events: list[dict[str, Any]]) -> None:
    """Announce an added kong; others may rob it (E06)."""
    pending: dict[int, list[Action]] = {}
    for k in range(1, 4):
        q = (p + k) % 4
        counts = _counts(s, q)
        counts[t] += 1
        if not s.pass_lock[q] and is_complete(counts, len(s.melds[q])):
            pending[q] = [Action(ActionType.HU), Action(ActionType.PASS)]
    _emit(s, events, "KONG", p, t, action=Action(ActionType.KONG, t),
          extra={"kind": "ADD_KONG", "announced": True})
    if pending:
        s.phase = Phase.ROB_KONG
        s.rob_kong = (p, t)
        s.pending_responses = pending
        s.responses = {}
    else:
        _finish_added_kong(s, p, t, events)


def _finish_added_kong(s: GameState, p: int, t: int, events: list[dict[str, Any]]) -> None:
    s.hands[p] = remove_tiles(s.hands[p], t)
    s.melds[p] = [
        Meld(MeldType.ADD_KONG, (t, t, t, t), m.called, m.from_player)
        if m.type is MeldType.PON and m.base_tile == t
        else m
        for m in s.melds[p]
    ]
    s.phase = Phase.DISCARD
    s.turn = p
    s.reserve += 1
    _draw(s, p, Source.KONG, events)


def _resolve_rob_kong(s: GameState, events: list[dict[str, Any]]) -> None:
    assert s.rob_kong is not None
    p, t = s.rob_kong
    resp = dict(s.responses)
    pending = dict(s.pending_responses)
    s.pending_responses, s.responses, s.rob_kong = {}, {}, None
    hu = [q for q, a in resp.items() if a.type is ActionType.HU]
    if hu:
        winner = _closest(p, hu)
        s.hands[p] = remove_tiles(s.hands[p], t)
        _win_on_discard(s, winner, p, t, events, rob_kong=True)
        return
    for q in pending:
        s.pass_lock[q] = True
        s.passed_win[q] = True
    _finish_added_kong(s, p, t, events)


def _next_turn(s: GameState, p: int, events: list[dict[str, Any]]) -> None:
    s.pon_lock[p] = False  # 過水碰 lasts until the player's next turn
    s.turn = p
    s.phase = Phase.DISCARD
    _draw(s, p, Source.WALL, events)


def _draw(s: GameState, p: int, source: Source, events: list[dict[str, Any]]) -> None:
    """Draw for p, replacing flowers; may end the hand."""
    while True:
        if s.drawable() <= 0:
            _exhaustive_draw(s, events)
            return
        t = s.wall.pop(0) if source is Source.WALL else s.wall.pop()
        is_last = s.drawable() == 0
        if source is Source.WALL:
            s.n_draws[p] += 1
        if tiles.is_flower(t):
            s.flowers[p].append(t)
            _emit(s, events, "FLOWER", p, t)
            if _flower_win_during_play(s, p, events):
                return
            if is_last:  # the last drawable tile was a flower: no replacement (OQ-03)
                _exhaustive_draw(s, events)
                return
            if source is not Source.MING_KONG:
                source = Source.FLOWER
            continue
        s.hands[p] = add_tile(s.hands[p], t)
        s.last_draw = t
        s.draw_source = source
        s.last_draw_is_haidi = is_last
        s.turn = p
        s.phase = Phase.DISCARD
        _emit(s, events, "DRAW", p, t, extra={"source": source.value}, private=True)
        if s.deferred_flower and s.deferred_flower[0] == p:
            _resolve_deferred_flower(s, events)
            return
        _auto_added_kong(s, p, t, events)
        return


def _auto_added_kong(s: GameState, p: int, t: int, events: list[dict[str, Any]]) -> None:
    """Declared players automatically upgrade a pon with the drawn 4th tile."""
    if not s.declared_ting[p] or s.drawable() < 2 or _can_self_win(s, p):
        return
    if any(m.type is MeldType.PON and m.base_tile == t for m in s.melds[p]):
        _start_added_kong(s, p, t, events)


# ====================================================================== flowers


def _flower_win_during_play(s: GameState, p: int, events: list[dict[str, Any]]) -> bool:
    n = len(s.flowers[p])
    if n == 8:
        _flower_win(s, p, FlowerWin.EIGHT, None, events)
        return True
    if n == 7:
        holder = next((q for q in range(4) if q != p and s.flowers[q]), None)
        if holder is not None:
            _flower_win(s, p, FlowerWin.ROB_DREW_EIGHTH, holder, events)
            return True
    if n == 1:
        robber = next((q for q in range(4) if q != p and len(s.flowers[q]) == 7), None)
        if robber is not None:
            _flower_win(s, robber, FlowerWin.ROB_HELD_SEVEN, p, events)
            return True
    return False


def _flower_win(
    s: GameState,
    winner: int,
    kind: FlowerWin,
    robbed: int | None,
    events: list[dict[str, Any]],
    *,
    deal_bonus: bool = False,
    replace: bool = True,
) -> None:
    """Resolve 八仙過海 / 七搶一; the winner draws a replacement that may also win the hand."""
    if robbed is not None:
        f = s.flowers[robbed].pop()
        s.flowers[winner].append(f)
        _emit(s, events, "FLOWER_ROB", winner, f, extra={"from": robbed})
    win_tile: int | None = None
    if replace and s.drawable() > 0:
        t = s.wall.pop()
        s.hands[winner] = add_tile(s.hands[winner], t)
        _emit(s, events, "DRAW", winner, t, extra={"source": Source.FLOWER.value}, private=True)
        win_tile = t
    elif not replace:
        win_tile = s.last_draw
    hand_ok = win_tile is not None and is_complete(
        _counts(s, winner), len(s.melds[winner])
    )
    held_seven = kind is FlowerWin.ROB_HELD_SEVEN
    ctx = _context(
        s, winner,
        win_tile=win_tile if hand_ok else None,
        self_draw=hand_ok and not held_seven,
        loser=robbed if held_seven else None,
        kong_flower=hand_ok and replace,
        flower_win=kind,
        deal_flower_win=deal_bonus,
        robbed_from=robbed,
    )
    _finish_win(s, ctx, events)


def _resolve_deferred_flower(s: GameState, events: list[dict[str, Any]]) -> None:
    assert s.deferred_flower is not None
    winner, kind, robbed = s.deferred_flower
    s.deferred_flower = None
    _flower_win(s, winner, FlowerWin(kind), robbed, events, deal_bonus=True, replace=False)


# ====================================================================== wins


def _context(s: GameState, winner: int, **kw: Any) -> WinContext:
    base: dict[str, Any] = {
        "winner": winner,
        "dealer": s.dealer,
        "dealer_streak": s.dealer_streak,
        "seat_wind": s.seat_wind(winner),
        "round_wind": s.round_wind,
        "concealed": tuple(s.hands[winner]),
        "melds": tuple(s.melds[winner]),
        "flowers": tuple(s.flowers[winner]),
        "declared_ting": s.declared_ting[winner],
        "earth_ting": s.earth_ting[winner] and not s.passed_win[winner],
    }
    base.update(kw)
    return WinContext(**base)


def _win_self_draw(s: GameState, p: int, events: list[dict[str, Any]]) -> None:
    flags: dict[str, Any] = {
        "self_draw": True,
        "kong_flower": s.draw_source in (Source.FLOWER, Source.KONG),
        "last_tile": s.last_draw_is_haidi,
        "heavenly": p == s.dealer and s.n_discards[p] == 0 and not s.melds[p],
        "earthly": p != s.dealer and s.n_draws[p] == 1 and s.n_discards[p] == 0,
    }
    if s.last_draw is not None:
        ctx = _context(s, p, win_tile=s.last_draw, **flags)
    else:  # dealer's opening hand: pick the most favourable winning tile
        candidates = [_context(s, p, win_tile=t, **flags) for t in sorted(set(s.hands[p]))]
        ctx = max(candidates, key=lambda c: settle(c, s.rules).tai_by_payer.get((p + 1) % 4, 0))
    _finish_win(s, ctx, events)


def _win_on_discard(
    s: GameState,
    winner: int,
    loser: int,
    t: int,
    events: list[dict[str, Any]],
    *,
    rob_kong: bool = False,
) -> None:
    if not rob_kong:
        s.discards[loser].pop()
    s.hands[winner] = add_tile(s.hands[winner], t)
    ctx = _context(
        s, winner,
        win_tile=t,
        loser=loser,
        tile_from_other=True,
        rob_kong=rob_kong,
        last_tile=not rob_kong and s.last_discard_is_haidi,
        human=not rob_kong and s.n_discards[loser] == 1 and not s.any_call,
    )
    _finish_win(s, ctx, events)


def _finish_win(s: GameState, ctx: WinContext, events: list[dict[str, Any]]) -> None:
    st: Settlement = settle(ctx, s.rules)
    for i in range(4):
        s.scores[i] += st.payments[i]
    s.phase = Phase.ENDED
    s.pending_responses, s.responses = {}, {}
    s.result = {
        "kind": "HU",
        "winner": ctx.winner,
        "loser": ctx.loser if not ctx.self_draw else None,
        "self_draw": ctx.self_draw,
        "win_tile": ctx.win_tile,
        "hand": list(ctx.concealed) if ctx.win_tile is None else list(s.hands[ctx.winner]),
        "melds": [m.to_dict() for m in s.melds[ctx.winner]],
        "flowers": list(s.flowers[ctx.winner]),
        "flower_win": ctx.flower_win.value if ctx.flower_win else None,
        **st.to_dict(),
    }
    _emit(s, events, "HU", ctx.winner, ctx.win_tile, extra={"result": s.result})


def _exhaustive_draw(s: GameState, events: list[dict[str, Any]]) -> None:
    s.phase = Phase.ENDED
    s.pending_responses, s.responses = {}, {}
    s.result = {"kind": "DRAW", "reason": "WALL_EXHAUSTED", "payments": [0, 0, 0, 0]}
    _emit(s, events, "ROUND_DRAW", None, extra={"reason": "WALL_EXHAUSTED"})


# ====================================================================== events


def _emit(
    s: GameState,
    events: list[dict[str, Any]],
    kind: str,
    player: int | None,
    tile: int | None = None,
    *,
    action: Action | None = None,
    extra: dict[str, Any] | None = None,
    private: bool = False,
) -> None:
    ev: dict[str, Any] = {
        "seq": len(s.events),
        "type": kind,
        "player": player,
        "tile": tile,
        "action_id": encode_action(action) if action else None,
    }
    if private:
        ev["private"] = True
    if extra:
        ev.update(extra)
    s.events.append(ev)
    events.append(ev)
