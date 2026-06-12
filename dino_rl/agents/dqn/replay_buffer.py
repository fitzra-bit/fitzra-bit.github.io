"""Replay buffer (preallocated numpy circular store) + n-step accumulator.

N-step returns are the single biggest win for sparse rewards: instead of
the death signal propagating one step per update, an n=3 transition carries
R = r₀ + γr₁ + γ²r₂ and bootstraps from s₃ with γ³ — so outcome information
reaches earlier decision states 3× faster. Each stored transition carries
its own effective discount (γᵏ) so partial windows at episode end are exact.
"""

from collections import deque
from typing import List, Tuple

import numpy as np


class ReplayBuffer:
    """Fixed-capacity circular buffer over preallocated numpy arrays."""

    def __init__(self, capacity: int, obs_dim: int):
        self.capacity = capacity
        self.s  = np.zeros((capacity, obs_dim), dtype=np.float32)
        self.a  = np.zeros(capacity, dtype=np.int64)
        self.r  = np.zeros(capacity, dtype=np.float32)
        self.ns = np.zeros((capacity, obs_dim), dtype=np.float32)
        self.d  = np.zeros(capacity, dtype=np.float32)
        self.gn = np.zeros(capacity, dtype=np.float32)   # γᵏ for the n-step bootstrap
        self._idx = 0
        self._size = 0

    def push(self, state, action, reward, next_state, done, gamma_n):
        i = self._idx
        self.s[i] = state
        self.a[i] = action
        self.r[i] = reward
        self.ns[i] = next_state
        self.d[i] = float(done)
        self.gn[i] = gamma_n
        self._idx = (i + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)

    def sample(self, batch_size: int) -> Tuple:
        idx = np.random.randint(0, self._size, size=batch_size)
        return self.s[idx], self.a[idx], self.r[idx], self.ns[idx], self.d[idx], self.gn[idx]

    def __len__(self) -> int:
        return self._size


class NStepAccumulator:
    """Converts 1-step transitions into n-step transitions.

    push() returns 0 or more ready n-step transitions; call flush() at
    episode end to emit the remaining partial windows (shorter k, exact γᵏ).
    """

    def __init__(self, n: int, gamma: float):
        self.n = n
        self.gamma = gamma
        self._q: deque = deque()

    def push(self, state, action, reward, next_state, done) -> List[tuple]:
        self._q.append((state, action, reward))
        out = []
        if done:
            # Emit every queued entry with its partial-window return.
            while self._q:
                out.append(self._emit(next_state, done=True))
            return out
        if len(self._q) == self.n:
            out.append(self._emit(next_state, done=False))
        return out

    def _emit(self, bootstrap_state, done: bool) -> tuple:
        s0, a0, _ = self._q[0]
        R, g = 0.0, 1.0
        for (_, _, r) in self._q:
            R += g * r
            g *= self.gamma
        self._q.popleft()
        return (s0, a0, R, bootstrap_state, done, g)   # g = γᵏ

    def reset(self):
        self._q.clear()
