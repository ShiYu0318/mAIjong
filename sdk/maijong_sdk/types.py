"""Public types shared by agents and the platform (stable v1 interface).

An Observation contains only what the acting seat may see: its own concealed tiles,
every player's exposed melds, flowers and discards, declared-ready flags and scores.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from engine.actions import Action, ActionType, decode_action, encode_action
from engine.game import GameState
from engine.hand import MeldType


@dataclass(frozen=True)
class MeldView:
    type: str  # CHI | PON | MING_KONG | ADD_KONG | AN_KONG
    tiles: tuple[int | None, ...]  # opponents' concealed kongs are None
    from_player: int | None


@dataclass(frozen=True)
class Observation:
    seat: int
    phase: str  # DISCARD | RESPONSE | ROB_KONG
    hand: tuple[int, ...]  # own concealed tiles, sorted
    last_draw: int | None  # own freshly drawn tile (DISCARD phase only)
    last_discard: tuple[int, int] | None  # (player, tile) awaiting responses
    melds: tuple[tuple[MeldView, ...], ...]  # per seat
    flowers: tuple[tuple[int, ...], ...]
    discards: tuple[tuple[int, ...], ...]
    declared_ting: tuple[bool, ...]
    scores: tuple[int, ...]
    seat_winds: tuple[int, ...]
    round_wind: int
    dealer: int
    dealer_streak: int
    drawable: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Observation:
        melds = tuple(tuple(MeldView(m["type"], tuple(m["tiles"]), m["from_player"]) for m in ms)
                      for ms in d["melds"])
        ld = d.get("last_discard")
        return Observation(
            seat=d["seat"], phase=d["phase"], hand=tuple(d["hand"]), last_draw=d["last_draw"],
            last_discard=(int(ld[0]), int(ld[1])) if ld else None,
            melds=melds, flowers=tuple(tuple(x) for x in d["flowers"]),
            discards=tuple(tuple(x) for x in d["discards"]),
            declared_ting=tuple(d["declared_ting"]), scores=tuple(d["scores"]),
            seat_winds=tuple(d["seat_winds"]), round_wind=d["round_wind"],
            dealer=d["dealer"], dealer_streak=d["dealer_streak"], drawable=d["drawable"],
        )


@dataclass(frozen=True)
class GameInfo:
    seat: int
    seat_wind: int
    round_wind: int
    dealer: int
    rules: dict[str, Any] = field(default_factory=dict)


def observe(state: GameState, seat: int) -> Observation:
    """Masked view of an engine state for `seat`."""
    melds = []
    for p in range(4):
        row = []
        for m in state.melds[p]:
            hidden = m.type is MeldType.AN_KONG and p != seat
            row.append(MeldView(m.type.value, (None,) * 4 if hidden else tuple(m.tiles),
                                m.from_player))
        melds.append(tuple(row))
    return Observation(
        seat=seat,
        phase=state.phase.value,
        hand=tuple(state.hands[seat]),
        last_draw=state.last_draw if state.turn == seat else None,
        last_discard=state.last_discard,
        melds=tuple(melds),
        flowers=tuple(tuple(f) for f in state.flowers),
        discards=tuple(tuple(d) for d in state.discards),
        declared_ting=tuple(state.declared_ting),
        scores=tuple(state.scores),
        seat_winds=tuple(state.seat_wind(p) for p in range(4)),
        round_wind=state.round_wind,
        dealer=state.dealer,
        dealer_streak=state.dealer_streak,
        drawable=state.drawable(),
    )


__all__ = ["Action", "ActionType", "GameInfo", "MeldView", "Observation", "decode_action",
           "encode_action", "observe"]
