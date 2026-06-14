"""Preallocated numpy replay buffer for SAC.

Pre-allocates all arrays up-front to avoid repeated GC pressure.
No n-step accumulation needed for SAC (off-policy, standard Bellman targets).
"""

from __future__ import annotations
import numpy as np
import torch


class ReplayBuffer:
    def __init__(self, state_dim: int, action_dim: int, capacity: int = 1_000_000):
        self.cap  = capacity
        self.ptr  = 0
        self.size = 0

        self.s  = np.zeros((capacity, state_dim),  dtype=np.float32)
        self.a  = np.zeros((capacity, action_dim),  dtype=np.float32)
        self.r  = np.zeros((capacity, 1),           dtype=np.float32)
        self.ns = np.zeros((capacity, state_dim),  dtype=np.float32)
        self.d  = np.zeros((capacity, 1),           dtype=np.float32)

    def push(
        self,
        s:    np.ndarray,
        a:    np.ndarray,
        r:    float,
        ns:   np.ndarray,
        done: float,
    ):
        self.s [self.ptr] = s
        self.a [self.ptr] = a
        self.r [self.ptr] = r
        self.ns[self.ptr] = ns
        self.d [self.ptr] = done
        self.ptr  = (self.ptr + 1) % self.cap
        self.size = min(self.size + 1, self.cap)

    def sample(self, batch_size: int):
        idx = np.random.randint(0, self.size, size=batch_size)
        def _t(arr): return torch.from_numpy(arr[idx])
        return _t(self.s), _t(self.a), _t(self.r), _t(self.ns), _t(self.d)
