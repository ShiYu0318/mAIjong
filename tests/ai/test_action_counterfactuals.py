import random

import numpy as np

from ai.agents import LEVEL5_PARAMS, RuleAgent
from engine.actions import Action, ActionType, encode_action
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game
from research.action_counterfactuals import action_candidates, label_actions


def ting_decision():
    state = new_game(seed=0)
    agents = [RuleAgent(0.0, p, params=LEVEL5_PARAMS) for p in range(4)]
    while state.phase is not Phase.ENDED:
        seat = acting_players(state)[0]
        legal = get_legal_actions(state, seat)
        teacher = agents[seat].act(state, seat, legal)
        if teacher.type is ActionType.TING:
            return state, seat, legal, teacher, agents[seat]
        state, _ = apply_action(state, seat, teacher)
    raise AssertionError('Seeded fixture should reach a TING decision')


def test_candidates_keep_teacher_and_same_tile_discard_as_distinct_actions():
    state, seat, legal, teacher, agent = ting_decision()
    actions = action_candidates(agent, state, seat, legal, teacher)
    assert actions[0] == teacher
    assert Action(ActionType.DISCARD, teacher.tile) in actions
    assert len({encode_action(a) for a in actions}) == len(actions)
    assert all(a in legal for a in actions)


def test_labels_apply_exact_action_and_share_pre_action_worlds(monkeypatch):
    import research.action_counterfactuals as module

    state, seat, legal, teacher, agent = ting_decision()
    actions = [teacher, Action(ActionType.DISCARD, teacher.tile)]
    original_wall = list(state.wall)
    seen = []
    def apply(world, player, action):
        seen.append(tuple(world.wall))
        return apply_action(world, player, action)
    monkeypatch.setattr(module, 'apply_action', apply)
    def value(after, player, seed):
        return float(after.declared_ting[player])
    random_state = random.getstate()
    q, se, samples = label_actions(state, seat, actions, seed=7, worlds=3, rollout=value)
    assert q[encode_action(teacher)] == 1
    assert q[encode_action(actions[1])] == 0
    assert samples.shape == (3, 108)
    assert all(seen[k] == seen[k + 1] for k in [0, 2, 4])
    assert seen[0] != seen[2]
    assert state.wall == original_wall and not state.declared_ting[seat]
    assert se[encode_action(teacher)] == 0
    assert np.isnan(q).sum() == 106
    assert random.getstate() == random_state


def test_collected_samples_replay_to_exact_teacher_decisions_and_visible_inputs():
    from ai.features import encode
    from ai.history import encode_public_history
    from ai.simulate import replay_states
    from research.generate_action_counterfactuals import collect

    result = collect((7, 1.0, 1, 2, 8))
    data = result['arrays']
    assert result['rows'] > 0
    replay = list(replay_states(7, result['record']['actions']))
    assert np.all(data['candidate_mask'] <= data['legal_mask'])
    assert np.isnan(data['paired_wall_se']).all()  # One world does not estimate uncertainty.
    for row in range(result['rows']):
        state, seat, aid = replay[int(data['action_index'][row])]
        assert seat == data['seat'][row] and aid == data['teacher_action'][row]
        tiles, scalars = encode(state, seat)
        history, mask = encode_public_history(state, seat, 8)
        np.testing.assert_array_equal(data['tiles'][row], tiles.astype(np.float16))
        np.testing.assert_array_equal(data['scalars'][row], scalars.astype(np.float16))
        np.testing.assert_array_equal(data['history'][row], history)
        np.testing.assert_array_equal(data['history_mask'][row], mask)
