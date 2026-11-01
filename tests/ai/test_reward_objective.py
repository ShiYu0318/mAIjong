"""Reward-objective regressions independent of the neural-network implementation."""
import pytest

from ai.reward import REWARD_PRESETS, GameResult, StepData, compute_shaped_reward


def test_score_reward_only_pays_terminal_points():
    cfg = REWARD_PRESETS['score']
    improving = StepData(0, 2, 0, 4, 20, own_flowers_gained=2)
    assert compute_shaped_reward(improving, [], None, cfg) == 0
    final = StepData(0, 0, 0, 20, 20, own_flowers_gained=1, is_final=True)
    assert compute_shaped_reward(final, [], GameResult(1, 4, None, 0, False, -300), cfg) == -1.5
    assert compute_shaped_reward(final, [], GameResult(None, 0, None, 0, True, 0), cfg) == 0


@pytest.mark.parametrize('gamma', [0.9, 0.99, 1.0])
def test_discounted_shaping_telescopes_for_different_length_paths(gamma):
    cfg = {**REWARD_PRESETS['discounted'], 'discount_gamma': gamma}
    # Initial potential = -0.05*2 + 0.005*4 = -0.08.
    for qualities in [[(2, 4), (1, 10)], [(2, 4), (3, 2), (2, 4), (1, 10)]]:
        total = 0.0
        for k, (sh, uke) in enumerate(qualities):
            final = k == len(qualities) - 1
            nxt = qualities[k + 1] if not final else (sh, uke)
            step = StepData(0, sh, nxt[0], uke, nxt[1], own_flowers_gained=1, is_final=final)
            result = GameResult(None, 0, None, 0, True, 0) if final else None
            total += gamma ** k * compute_shaped_reward(step, [], result, cfg)
        assert total == pytest.approx(0.08)
