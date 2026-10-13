"""Head-to-head benchmark (SPEC 05.7 B) on a few matches."""

from __future__ import annotations

from ai.agents import RuleAgent
from ai.training.benchmark import benchmark, play_match, table


def test_play_match_is_zero_sum_and_ends():
    scores, hands = play_match([RuleAgent(0.0, i) for i in range(4)], seed=3, rounds=1)
    assert sum(scores) == 0 and len(hands) >= 4


def test_benchmark_rates_add_up_and_rotate_seats():
    out = benchmark(["random", "rule", "rule", "random"], matches=8, workers=1)
    assert set(out) == {"random", "rule"}
    for s in out.values():
        assert s["matches"] == 16  # two slots each, eight matches
        assert abs(sum(s[f"place_{i}"] for i in range(1, 5)) - 1) < 1e-9
        assert 1 <= s["avg_place"] <= 4
    assert out["rule"]["avg_place"] < out["random"]["avg_place"]
    assert out["random"]["win_rate"] < out["rule"]["win_rate"]
    assert "| rule |" in table("mix", out)


def test_same_agent_four_times_is_even():
    out = benchmark(["rule"] * 4, matches=4, workers=1)
    assert out["rule"]["matches"] == 16 and out["rule"]["avg_final_score"] == 0
