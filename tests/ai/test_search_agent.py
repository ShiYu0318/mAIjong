"""Search agent (PIMC over the rule agent): sampling and decisions."""

from __future__ import annotations

import random
from collections import Counter

from ai.agents import RuleAgent
from ai.agents.search_agent import SearchAgent, determinize
from engine.actions import ActionType
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game


def _midgame(seed: int, steps: int = 30):
    s = new_game(seed=seed)
    agents = [RuleAgent(0.0, seed + i) for i in range(4)]
    for _ in range(steps):
        if s.phase is Phase.ENDED:
            break
        p = acting_players(s)[0]
        s, _ = apply_action(s, p, agents[p].act(s, p, get_legal_actions(s, p)))
    return s


def test_determinize_keeps_what_the_seat_sees_and_the_tile_multiset():
    for seed in range(8):
        s = _midgame(seed)
        if s.phase is Phase.ENDED:
            continue
        seat = s.turn
        before = (list(s.wall), [list(h) for h in s.hands])
        w = determinize(s, seat, random.Random(seed))
        assert (list(s.wall), [list(h) for h in s.hands]) == before  # input untouched
        assert w.hands[seat] == s.hands[seat]
        assert w.melds == s.melds and w.discards == s.discards and w.flowers == s.flowers
        assert [len(h) for h in w.hands] == [len(h) for h in s.hands]
        assert len(w.wall) == len(s.wall) and w.drawable() == s.drawable()
        def unseen(g, seat=seat):
            return Counter([t for p in range(4) if p != seat for t in g.hands[p]] + list(g.wall))

        assert unseen(w) == unseen(s)
        assert all(t < 34 for p in range(4) for t in w.hands[p])  # flowers stay in the wall


def test_search_agent_plays_legal_moves_to_the_end_and_searches_discards():
    agent = SearchAgent(samples=2, top_k=3, seed=1)
    others = [RuleAgent(0.0, i) for i in range(3)]
    s = new_game(seed=11)
    while s.phase is not Phase.ENDED:
        p = acting_players(s)[0]
        legal = get_legal_actions(s, p)
        a = agent.act(s, p, legal) if p == 0 else others[p - 1].act(s, p, legal)
        assert a in legal
        s, _ = apply_action(s, p, a)
    assert agent.stats["searched"] > 0


def test_search_takes_the_win_and_defers_claims():
    agent = SearchAgent(samples=2, seed=0)
    for seed in range(40):
        s = _midgame(seed, steps=60)
        if s.phase is Phase.ENDED:
            continue
        p = acting_players(s)[0]
        legal = get_legal_actions(s, p)
        hu = [a for a in legal if a.type is ActionType.HU]
        if hu:
            assert agent.act(s, p, legal).type is ActionType.HU
        if s.phase is not Phase.DISCARD:
            assert not agent._should_search(s, p, legal)


def test_ready_hand_is_ready_and_avoids_safe_tiles():
    from ai.agents.search_agent import _ready_hand
    from engine import tiles
    from engine.ting import waiting_tiles

    rng = random.Random(3)
    avail = [4] * 34
    safe = {0, 9, 18}
    built = 0
    for _ in range(30):
        hand = _ready_hand(avail, 16, 0, safe, rng)
        if hand is None:
            continue
        built += 1
        assert len(hand) == 16
        waits = waiting_tiles(tiles.to_counts(hand), 0)
        assert waits and not safe.intersection(waits)
        assert all(tiles.to_counts(hand)[t] <= 4 for t in range(34))
    assert built >= 25


def test_determinize_gives_declared_players_ready_hands():
    from engine import tiles
    from engine.ting import waiting_tiles

    checked = 0
    for seed in range(60):
        s = _midgame(seed, steps=70)
        if s.phase is Phase.ENDED or s.phase is not Phase.DISCARD:
            continue
        seat = s.turn
        declared = [p for p in range(4) if p != seat and s.declared_ting[p]]
        if not declared:
            continue
        w = determinize(s, seat, random.Random(seed), ready=True)

        def unseen(g, seat=seat):
            return Counter([t for p in range(4) if p != seat for t in g.hands[p]] + list(g.wall))

        assert unseen(w) == unseen(s)
        for p in declared:
            assert waiting_tiles(tiles.to_counts(w.hands[p]), len(w.melds[p]))
        checked += 1
    assert checked > 0
