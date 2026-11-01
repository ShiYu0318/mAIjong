from ai.training.block_evaluate import play_block
from research.confirm_pretrained_baseline import parallel_blocks


def test_parallel_blocks_preserve_seed_order_and_exact_serial_results():
    seeds = [79, 77]
    expected = [play_block('random', 'rule', 'rule', seed) for seed in seeds]
    actual = list(parallel_blocks('random', 'rule', 'rule', seeds, workers=2))
    assert actual == expected
