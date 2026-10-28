from collections import Counter

from ai.agents import RandomAgent, RuleAgent, create_agent
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game


def play(agents, seed):
    s = new_game(seed=seed)
    while s.phase is not Phase.ENDED:
        p = acting_players(s)[0]
        legal = get_legal_actions(s, p)
        a = agents[p].act(s, p, legal)
        assert a in legal
        s, _ = apply_action(s, p, a)
    return s


def test_rule_agent_beats_random():
    wins: Counter[str] = Counter()
    for seed in range(200):
        agents = [RuleAgent(0.0, seed), RandomAgent(seed), RuleAgent(1.5, seed), RandomAgent(seed)]
        s = play(agents, seed)
        if s.result["kind"] == "HU":
            wins["rule" if s.result["winner"] in (0, 2) else "random"] += 1
    assert wins["rule"] > 5 * max(1, wins["random"])


def test_levels():
    assert isinstance(create_agent(1), RandomAgent)
    assert isinstance(create_agent(3), RuleAgent) and create_agent(3).temperature == 1.5


def test_vote_agent_takes_the_majority_and_breaks_ties_by_order():
    from ai.agents.vote_agent import VoteAgent
    from engine.actions import Action, ActionType

    class Fixed:
        def __init__(self, a):
            self.a = a

        def act(self, state, seat, legal):
            return self.a

    x, y, z = (Action(ActionType.DISCARD, t) for t in (1, 2, 3))
    v = VoteAgent([])
    v.members = [Fixed(x), Fixed(y), Fixed(y)]
    assert v.act(None, 0, [x, y]) == y
    v.members = [Fixed(z), Fixed(x), Fixed(y)]
    assert v.act(None, 0, [x, y, z]) == z  # a three-way tie goes to the first member
