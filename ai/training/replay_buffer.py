"""Prioritized experience replay (SPEC 05.6.5) backed by a sum tree."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


class SumTree:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.tree = np.zeros(2 * capacity, dtype=np.float64)

    def update(self, idx: int, priority: float) -> None:
        i = idx + self.capacity
        self.tree[i] = priority
        i //= 2
        while i >= 1:
            self.tree[i] = self.tree[2 * i] + self.tree[2 * i + 1]
            i //= 2

    @property
    def total(self) -> float:
        return float(self.tree[1])

    def find(self, value: float) -> int:
        """Leaf index whose cumulative range contains value."""
        i = 1
        while i < self.capacity:
            left = 2 * i
            if value <= self.tree[left]:
                i = left
            else:
                value -= self.tree[left]
                i = left + 1
        return i - self.capacity

    def get(self, idx: int) -> float:
        return float(self.tree[idx + self.capacity])


@dataclass
class Batch:
    items: list[Any]
    indices: np.ndarray
    weights: np.ndarray


class PrioritizedReplayBuffer:
    """Samples ∝ priority^alpha with importance weights (N·P)^-beta / max."""

    def __init__(self, capacity: int, alpha: float = 0.6, eps: float = 1e-3) -> None:
        self.capacity = capacity
        self.alpha = alpha
        self.eps = eps
        self.tree = SumTree(capacity)
        self.data: list[Any] = [None] * capacity
        self.pos = 0
        self.size = 0
        self.max_priority = 1.0

    def __len__(self) -> int:
        return self.size

    def add(self, item: Any, priority: float | None = None) -> None:
        p = self.max_priority if priority is None else priority
        self.data[self.pos] = item
        self.tree.update(self.pos, (abs(p) + self.eps) ** self.alpha)
        self.pos = (self.pos + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    def sample(self, n: int, beta: float, rng: np.random.Generator) -> Batch:
        total = self.tree.total
        segment = total / n
        idx = np.empty(n, dtype=np.int64)
        prios = np.empty(n, dtype=np.float64)
        for k in range(n):
            v = rng.uniform(segment * k, segment * (k + 1))
            i = min(self.tree.find(v), self.size - 1)
            idx[k] = i
            prios[k] = self.tree.get(i)
        probs = prios / total
        weights = (self.size * probs) ** (-beta)
        weights /= weights.max()
        return Batch([self.data[i] for i in idx], idx, weights.astype(np.float32))

    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray) -> None:
        for i, e in zip(indices, td_errors, strict=True):
            p = float(abs(e)) + self.eps
            self.max_priority = max(self.max_priority, p)
            self.tree.update(int(i), p ** self.alpha)
