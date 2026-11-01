import pytest

from backend.ws.view import visible_event
from engine.actions import Action, ActionType, encode_action


@pytest.mark.parametrize('seat', [None, 0, 2, 3])
def test_concealed_kong_hides_tile_and_encoded_action_from_other_views(seat):
    event = {'type': 'KONG', 'player': 1, 'kind': 'AN_KONG', 'tile': 7,
             'action_id': encode_action(Action(ActionType.KONG, 7))}
    result = visible_event(event, seat)
    assert result['tile'] is None
    assert result['action_id'] is None
    assert event['tile'] == 7 and event['action_id'] is not None


def test_owner_keeps_concealed_kong_action_and_public_kongs_remain_visible():
    event = {'type': 'KONG', 'player': 1, 'kind': 'AN_KONG', 'tile': 7,
             'action_id': encode_action(Action(ActionType.KONG, 7))}
    assert visible_event(event, 1) == event
    event['kind'] = 'MING_KONG'
    assert visible_event(event, 0) == event


def test_other_players_private_events_do_not_expose_action_ids():
    event = {'type': 'DRAW', 'player': 1, 'private': True, 'tile': 7, 'action_id': 7}
    assert visible_event(event, 0)['action_id'] is None
    assert visible_event(event, 1) == event
