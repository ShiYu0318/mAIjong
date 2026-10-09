"""Action types and the 108-way flat action encoding.

ID layout:
    0-33    DISCARD tile
    34-67   KONG tile (concealed, added, or exposed depending on context)
    68      PON
    69-71   CHI_LOW / CHI_MID / CHI_HIGH (discard is the high / middle / low tile)
    72      HU
    73      PASS
    74-107  TING: discard tile and declare ready
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ActionType(StrEnum):
    DISCARD = "DISCARD"
    KONG = "KONG"
    PON = "PON"
    CHI_LOW = "CHI_LOW"
    CHI_MID = "CHI_MID"
    CHI_HIGH = "CHI_HIGH"
    HU = "HU"
    PASS = "PASS"
    TING = "TING"


TILE_ACTIONS = (ActionType.DISCARD, ActionType.KONG, ActionType.TING)
CHI_ACTIONS = (ActionType.CHI_LOW, ActionType.CHI_MID, ActionType.CHI_HIGH)

N_ACTIONS = 108
KONG_OFFSET = 34
PON_ID = 68
CHI_LOW_ID = 69
CHI_MID_ID = 70
CHI_HIGH_ID = 71
HU_ID = 72
PASS_ID = 73
TING_OFFSET = 74

_FIXED_IDS = {
    ActionType.PON: PON_ID,
    ActionType.CHI_LOW: CHI_LOW_ID,
    ActionType.CHI_MID: CHI_MID_ID,
    ActionType.CHI_HIGH: CHI_HIGH_ID,
    ActionType.HU: HU_ID,
    ActionType.PASS: PASS_ID,
}
_FIXED_TYPES = {v: k for k, v in _FIXED_IDS.items()}


@dataclass(frozen=True, slots=True)
class Action:
    type: ActionType
    tile: int | None = None

    def __post_init__(self) -> None:
        needs_tile = self.type in TILE_ACTIONS
        if needs_tile and (self.tile is None or not 0 <= self.tile < 34):
            raise ValueError(f"{self.type} requires a tile id 0-33, got {self.tile}")
        if not needs_tile and self.tile is not None:
            raise ValueError(f"{self.type} takes no tile")

    def to_dict(self) -> dict[str, object]:
        return {"action_type": self.type.value, "tile": self.tile}

    @staticmethod
    def from_dict(d: dict[str, object]) -> Action:
        tile = d.get("tile")
        return Action(ActionType(str(d["action_type"])), None if tile is None else int(str(tile)))


def encode_action(a: Action) -> int:
    if a.type is ActionType.DISCARD:
        assert a.tile is not None
        return a.tile
    if a.type is ActionType.KONG:
        assert a.tile is not None
        return KONG_OFFSET + a.tile
    if a.type is ActionType.TING:
        assert a.tile is not None
        return TING_OFFSET + a.tile
    return _FIXED_IDS[a.type]


def decode_action(i: int) -> Action:
    if 0 <= i < 34:
        return Action(ActionType.DISCARD, i)
    if KONG_OFFSET <= i < KONG_OFFSET + 34:
        return Action(ActionType.KONG, i - KONG_OFFSET)
    if TING_OFFSET <= i < TING_OFFSET + 34:
        return Action(ActionType.TING, i - TING_OFFSET)
    if i in _FIXED_TYPES:
        return Action(_FIXED_TYPES[i])
    raise ValueError(f"action id out of range: {i}")


def legal_mask(actions: list[Action]) -> list[bool]:
    mask = [False] * N_ACTIONS
    for a in actions:
        mask[encode_action(a)] = True
    return mask


DISCARD = ActionType.DISCARD
HU = Action(ActionType.HU)
PASS = Action(ActionType.PASS)
PON = Action(ActionType.PON)
