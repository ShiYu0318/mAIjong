import numpy as np

from research.audit_observations import decision_groups


def test_forced_and_response_choices_are_distinguished_from_discard_choices():
    tiles = np.zeros((3, 34, 14), dtype=np.float32)
    scalars = np.zeros((3, 13), dtype=np.float32)
    masks = np.zeros((3, 108), dtype=bool)
    masks[0, 107] = True
    masks[1, [0, 1]] = True
    masks[2, [102, 107]] = True
    scalars[2, 10] = 1.0
    groups = decision_groups(tiles, scalars, masks)
    assert groups['forced'].tolist() == [True, False, False]
    assert groups['discard_choice'].tolist() == [False, True, False]
    assert groups['response_choice'].tolist() == [False, False, True]
    assert groups['threatened_choice'].tolist() == [False, False, True]
