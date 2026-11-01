from collections import Counter

import pytest
from maijong_sdk.types import observe

from ai.agents import LEVEL5_PARAMS, RuleAgent
from ai.agents.rule_agent import _visible_counts
from ai.danger import suspected_danger, visible_counts
from engine.game import get_legal_actions, new_game
from engine.hand import Meld, MeldType


def hidden_kong_worlds():
    state = new_game(seed=17)
    unknown = [t for t in range(34) if t not in state.hands[0]]
    first = unknown[0]
    second = next(t for t in unknown if t < 27 and t // 9 != first // 9)
    pool = [t for hand in state.hands[1:] for t in hand] + list(state.wall)
    playable = [t for t in pool if t < 34]
    flowers = [t for t in pool if t >= 34]
    for _ in range(4):
        playable.remove(first)
    state.melds[1] = [Meld(MeldType.AN_KONG, (first,) * 4)]
    offset = 0
    for seat, size in [(1, 13), (2, 16), (3, 16)]:
        state.hands[seat] = sorted(playable[offset:offset + size])
        offset += size
    state.wall = playable[offset:] + flowers
    state.reserve += 1
    state.events = []
    changed = state.clone()
    def swap(tile):
        return second if tile == first else first if tile == second else tile
    for seat in range(1, 4):
        changed.hands[seat] = sorted(swap(t) for t in changed.hands[seat])
    changed.wall = [swap(t) for t in changed.wall]
    changed.melds[1] = [Meld(MeldType.AN_KONG, (second,) * 4)]
    def all_tiles(game):
        return Counter([t for hand in game.hands for t in hand] + game.wall
                       + [t for melds in game.melds for meld in melds for t in meld.tiles])
    assert all_tiles(state) == all_tiles(changed)
    assert observe(state, 0) == observe(changed, 0)
    return state, changed, first, second


@pytest.mark.parametrize('count', [visible_counts, _visible_counts])
def test_opponent_hidden_kong_identity_cannot_change_visible_counts(count):
    state, changed, first, second = hidden_kong_worlds()
    assert count(state, 0) == count(changed, 0)
    assert count(state, 0)[first] == 0
    assert count(state, 0)[second] == 0


@pytest.mark.parametrize('count', [visible_counts, _visible_counts])
def test_own_concealed_kong_still_counts_as_known_tiles(count):
    state, _, first, _ = hidden_kong_worlds()
    assert count(state, 1)[first] == 4


def test_rule_scores_do_not_depend_on_opponents_concealed_kong_tiles():
    state, changed, _, _ = hidden_kong_worlds()
    legal = get_legal_actions(state, 0)
    assert legal == get_legal_actions(changed, 0)
    agent = RuleAgent(0.0, 7, params=LEVEL5_PARAMS)
    assert agent.scores(state, 0, legal) == agent.scores(changed, 0, legal)


def test_suspected_danger_cannot_infer_suit_from_an_opponents_concealed_kong():
    state, changed, first, _ = hidden_kong_worlds()
    seen = visible_counts(state, 0)
    assert suspected_danger(state, first, seen, [1]) == suspected_danger(changed, first, seen, [1])


def test_threat_model_rule_scores_remain_invariant_to_concealed_kong_suit():
    state, changed, _, _ = hidden_kong_worlds()
    legal = get_legal_actions(state, 0)
    agent = RuleAgent(0.0, 7, params=LEVEL5_PARAMS, threat_melds=1)
    assert agent.scores(state, 0, legal) == agent.scores(changed, 0, legal)
