"""Independent reference shanten: classic recursive mentsu/taatsu search.

shanten = 2*M - 2*mentsu - taatsu - pair, with mentsu + taatsu <= M,
maximised over all decompositions (M = melds still needed).
"""

from __future__ import annotations


def ref_shanten(counts: list[int], n_melds: int = 0) -> int:
    need = 5 - n_melds
    c = list(counts)
    best = [2 * need]

    def score(m: int, t: int, p: int) -> int:
        t = min(t, need - m)
        return 2 * need - 2 * m - t - p

    def dfs(i: int, m: int, t: int, p: int) -> None:
        while i < 34 and c[i] == 0:
            i += 1
        if i >= 34:
            best[0] = min(best[0], score(m, t, p))
            return
        if m + t >= need and p:
            best[0] = min(best[0], score(m, t, p))
        suited = i < 27
        r = i % 9
        if c[i] >= 3:
            c[i] -= 3
            dfs(i, m + 1, t, p)
            c[i] += 3
        if suited and r <= 6 and c[i + 1] and c[i + 2]:
            c[i] -= 1; c[i + 1] -= 1; c[i + 2] -= 1  # noqa: E702
            dfs(i, m + 1, t, p)
            c[i] += 1; c[i + 1] += 1; c[i + 2] += 1  # noqa: E702
        if c[i] >= 2:
            c[i] -= 2
            if not p:
                dfs(i, m, t, 1)
            dfs(i, m, t + 1, p)
            c[i] += 2
        if suited and r <= 7 and c[i + 1]:
            c[i] -= 1; c[i + 1] -= 1  # noqa: E702
            dfs(i, m, t + 1, p)
            c[i] += 1; c[i + 1] += 1  # noqa: E702
        if suited and r <= 6 and c[i + 2]:
            c[i] -= 1; c[i + 2] -= 1  # noqa: E702
            dfs(i, m, t + 1, p)
            c[i] += 1; c[i + 2] += 1  # noqa: E702
        c[i] -= 1
        dfs(i, m, t, p)
        c[i] += 1

    dfs(0, 0, 0, 0)
    return best[0]
