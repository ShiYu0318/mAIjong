"""Shared deals across training seeds must remain a single uncertainty axis."""
import numpy as np
import pytest

from research.reward_analysis import crossed_interval, load_matrix


def test_repeating_same_seed_does_not_fake_more_independent_deals():
    row = np.arange(16, dtype=float)[None]
    assert crossed_interval(row, seed=8) == crossed_interval(np.repeat(row, 3, axis=0), seed=8)


def test_training_seed_variation_survives_identical_deals():
    matrix = np.repeat(np.array([[-100.0], [0.0], [100.0]]), 16, axis=1)
    low, high = crossed_interval(matrix, seed=1)
    assert low < -50 and high > 50
    assert crossed_interval(np.zeros((3, 16))) == (0.0, 0.0)


@pytest.mark.parametrize('matrix', [[], [[float('nan')]], [[1], [float('inf')]]])
def test_invalid_arrays_are_rejected(matrix):
    with pytest.raises(ValueError):
        crossed_interval(np.asarray(matrix))


def test_missing_model_is_not_silently_replaced_with_zero(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_matrix(tmp_path, 'score', pool=0)
