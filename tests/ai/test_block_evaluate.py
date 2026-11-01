"""Independent deal blocks and deterministic evaluation contracts."""
from ai.training.block_evaluate import bootstrap_interval, play_block


def test_identical_agents_have_zero_paired_difference():
    row = play_block('random', 'random', 'random', seed=123)
    assert row['differences'] == [0, 0, 0, 0]
    assert row['mean_difference'] == 0
    assert row['hands'] == 8


def test_block_is_independent_of_preceding_calls():
    cache = {}
    first = play_block('random', 'rule', 'random', seed=456, cache=cache)
    play_block('random', 'rule', 'random', seed=789, cache=cache)
    assert play_block('random', 'rule', 'random', seed=456, cache=cache) == first


def test_bootstrap_uses_blocks_and_fixed_seed():
    assert bootstrap_interval([0, 0, 0], seed=1) == (0.0, 0.0)
    assert bootstrap_interval([1, 2, 3], seed=7) == bootstrap_interval([1, 2, 3], seed=7)
