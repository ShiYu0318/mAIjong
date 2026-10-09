"""Generate the shanten lookup tables used by engine/shanten.py.

For every count pattern of one suit (9 ranks, 0-4 copies each, 5^9 patterns) and of the
honors (7 kinds, 5^7 patterns) we store, for m = 0..5 melds and p = 0/1 pair, the minimum
number of tiles that must be added so the pattern contains m melds (+ a pair if p = 1).

The recursion used:
    cost(h) = 0                                  if h contains such a target
    cost(h) = 1 + min_{i: h_i < 4} cost(h + e_i) otherwise
which is evaluated level by level from the fullest patterns downwards.

Usage:  uv run python scripts/generate_lookup_tables.py
Output: engine/data/shanten_suit.bin.z, engine/data/shanten_honor.bin.z
"""

from __future__ import annotations

import zlib
from pathlib import Path

import numpy as np

MAX_MELDS = 5
BASE = 5
INF = 99
OUT_DIR = Path(__file__).resolve().parent.parent / "engine" / "data"


def build(n_kinds: int, sequences: bool) -> np.ndarray:
    size = BASE**n_kinds
    idx = np.arange(size, dtype=np.int64)
    pow5 = BASE ** np.arange(n_kinds, dtype=np.int64)
    digits = (idx[:, None] // pow5[None, :]) % BASE  # (size, n_kinds)
    total = digits.sum(axis=1)

    groups: list[tuple[int, np.ndarray]] = []  # (code, requirement mask)
    for i in range(n_kinds):
        groups.append((3 * int(pow5[i]), digits[:, i] >= 3))
    if sequences:
        for i in range(n_kinds - 2):
            code = int(pow5[i] + pow5[i + 1] + pow5[i + 2])
            ok = (digits[:, i] >= 1) & (digits[:, i + 1] >= 1) & (digits[:, i + 2] >= 1)
            groups.append((code, ok))
    pairs = [(2 * int(pow5[i]), digits[:, i] >= 2) for i in range(n_kinds)]

    # contains[m][p]: pattern contains m melds (+ pair if p)
    contains = np.zeros((MAX_MELDS + 1, 2, size), dtype=bool)
    contains[0, 0] = True
    for m in range(MAX_MELDS + 1):
        for p in (0, 1):
            if m == 0 and p == 0:
                continue
            acc = np.zeros(size, dtype=bool)
            if m > 0:
                prev = contains[m - 1, p]
                for code, ok in groups:
                    sel = np.flatnonzero(ok)
                    acc[sel] |= prev[sel - code]
            if p == 1:
                prev = contains[m, 0]
                for code, ok in pairs:
                    sel = np.flatnonzero(ok)
                    acc[sel] |= prev[sel - code]
            contains[m, p] = acc

    cost = np.full((size, MAX_MELDS + 1, 2), INF, dtype=np.int16)
    levels = [np.flatnonzero(total == s) for s in range(int(total.max()) + 1)]
    for m in range(MAX_MELDS + 1):
        for p in (0, 1):
            c = np.full(size, INF, dtype=np.int16)
            z = contains[m, p]
            for s in range(len(levels) - 1, -1, -1):
                lv = levels[s]
                best = np.full(lv.size, INF, dtype=np.int16)
                for i in range(n_kinds):
                    can = digits[lv, i] < 4
                    nb = lv[can] + pow5[i]
                    best[can] = np.minimum(best[can], c[nb] + 1)
                c[lv] = np.where(z[lv], 0, np.minimum(best, INF))
            cost[:, m, p] = c
    return np.minimum(cost, 127).astype(np.int8)


def write(name: str, table: np.ndarray) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = table.tobytes(order="C")
    path = OUT_DIR / name
    path.write_bytes(zlib.compress(raw, 9))
    print(f"{path.name}: {table.shape} -> {path.stat().st_size / 1024:.0f} KiB")


def main() -> None:
    write("shanten_suit.bin.z", build(9, sequences=True))
    write("shanten_honor.bin.z", build(7, sequences=False))


if __name__ == "__main__":
    main()
