"""The nightly simulation script's checks run in every CI too (on a small sample)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "nightly_sim", Path(__file__).resolve().parents[2] / "scripts" / "nightly_sim.py")
assert _spec and _spec.loader
nightly = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nightly)


def test_soak_sample_is_clean():
    assert nightly.soak(40) == []


def test_expected_ranges():
    assert nightly.expected("random", "rule", 0.0, 0.42) is None
    assert nightly.expected("rule", "random", 0.42, 0.0) is None
    assert nightly.expected("random", "rule", 0.10, 0.30) is not None  # random winning too much
    assert nightly.expected("random", "lv5", 0.0, 0.15) is not None  # real agent too weak
    assert nightly.expected("rule", "lv5", 0.22, 0.26) is None
    assert nightly.expected("rule", "lv5", 0.05, 0.45) is not None
