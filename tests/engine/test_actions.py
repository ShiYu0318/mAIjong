import pytest

from engine.actions import (
    N_ACTIONS,
    Action,
    ActionType,
    decode_action,
    encode_action,
    legal_mask,
)


def test_roundtrip_all_ids():
    seen = set()
    for i in range(N_ACTIONS):
        a = decode_action(i)
        assert encode_action(a) == i
        seen.add(a)
    assert len(seen) == N_ACTIONS == 108


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        (Action(ActionType.DISCARD, 0), 0),
        (Action(ActionType.DISCARD, 33), 33),
        (Action(ActionType.KONG, 0), 34),
        (Action(ActionType.KONG, 33), 67),
        (Action(ActionType.PON), 68),
        (Action(ActionType.CHI_LOW), 69),
        (Action(ActionType.CHI_MID), 70),
        (Action(ActionType.CHI_HIGH), 71),
        (Action(ActionType.HU), 72),
        (Action(ActionType.PASS), 73),
        (Action(ActionType.TING, 0), 74),
        (Action(ActionType.TING, 33), 107),
    ],
)
def test_layout(action, expected):
    assert encode_action(action) == expected


def test_validation_and_mask():
    with pytest.raises(ValueError):
        Action(ActionType.DISCARD)
    with pytest.raises(ValueError):
        Action(ActionType.PON, 3)
    with pytest.raises(ValueError):
        Action(ActionType.DISCARD, 34)
    with pytest.raises(ValueError):
        decode_action(108)
    mask = legal_mask([Action(ActionType.PASS), Action(ActionType.DISCARD, 5)])
    assert sum(mask) == 2 and mask[73] and mask[5]


def test_dict_roundtrip():
    a = Action(ActionType.TING, 12)
    assert Action.from_dict(a.to_dict()) == a
