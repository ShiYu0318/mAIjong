import numpy as np

from ai.elo import INITIAL_ELO, games_coeff, update_elo
from ai.training.replay_buffer import PrioritizedReplayBuffer, SumTree


def test_sum_tree_find():
    t = SumTree(4)
    for i, p in enumerate([1.0, 2.0, 3.0, 4.0]):
        t.update(i, p)
    assert t.total == 10
    assert t.find(0.5) == 0 and t.find(2.5) == 1 and t.find(5.5) == 2 and t.find(9.9) == 3


def test_prioritized_sampling_prefers_high_priority():
    buf = PrioritizedReplayBuffer(64, alpha=1.0)
    for i in range(64):
        buf.add(i, priority=100.0 if i == 7 else 0.01)
    rng = np.random.default_rng(0)
    batch = buf.sample(32, beta=0.4, rng=rng)
    assert sum(1 for x in batch.items if x == 7) > 16
    assert batch.weights.max() == 1.0
    buf.update_priorities(batch.indices, np.zeros(32))
    assert len(buf) == 64


def test_elo_update_zero_sum_for_equal_newcomers():
    new = update_elo([INITIAL_ELO] * 4, [1, 2, 3, 4], [0, 0, 0, 0])
    assert new == [1530, 1510, 1490, 1470]
    assert games_coeff(1000) == 0.2
    stronger_win = update_elo([1800, 1500, 1500, 1500], [1, 2, 3, 4], [400] * 4)
    assert stronger_win[0] - 1800 < 30 * 0.2  # beating weaker tables earns less
