"""SAC actor and twin-critic networks.

Actor  — Gaussian policy with tanh squashing (bounded actions in [-1, 1]).
Critic — Twin Q-networks; caller uses min(Q1, Q2) to reduce overestimation.

The actor exposes:
  .sample(state)   → (action, log_prob, deterministic_action)
  .predict(obs)    → numpy action  (deterministic, for eval / demo)
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from torch.distributions import Normal

LOG_STD_MIN = -5
LOG_STD_MAX = 2


def _mlp(sizes: list, activation=nn.ReLU) -> nn.Sequential:
    """MLP with activations between every pair of layers except the last."""
    layers: list = []
    for i in range(len(sizes) - 1):
        layers.append(nn.Linear(sizes[i], sizes[i + 1]))
        if i < len(sizes) - 2:
            layers.append(activation())
    return nn.Sequential(*layers)


class Actor(nn.Module):
    """Gaussian policy; outputs squashed samples in [-1, 1]^n_act."""

    def __init__(self, state_dim: int, action_dim: int, hidden=(256, 256)):
        super().__init__()
        # Trunk ends with ReLU so mean / log_std heads receive activated features
        layers: list = []
        sizes = [state_dim, *hidden]
        for i in range(len(sizes) - 1):
            layers += [nn.Linear(sizes[i], sizes[i + 1]), nn.ReLU()]
        self.trunk   = nn.Sequential(*layers)
        self.mean    = nn.Linear(hidden[-1], action_dim)
        self.log_std = nn.Linear(hidden[-1], action_dim)

    def forward(self, state: torch.Tensor):
        h       = self.trunk(state)
        mean    = self.mean(h)
        log_std = self.log_std(h).clamp(LOG_STD_MIN, LOG_STD_MAX)
        return mean, log_std

    def sample(self, state: torch.Tensor):
        """Reparameterised sample + log-prob with change-of-variables."""
        mean, log_std = self(state)
        dist   = Normal(mean, log_std.exp())
        x_t    = dist.rsample()
        action = torch.tanh(x_t)
        # Correction for tanh squashing
        log_prob = (dist.log_prob(x_t) - torch.log(1 - action.pow(2) + 1e-6)).sum(-1, keepdim=True)
        return action, log_prob, torch.tanh(mean)   # (action, logp, det_action)

    def predict(self, obs: np.ndarray) -> np.ndarray:
        """Deterministic inference — equivalent to ε=0 for continuous control."""
        with torch.no_grad():
            t = torch.from_numpy(obs.astype(np.float32)).unsqueeze(0)
            mean, _ = self(t)
            return torch.tanh(mean).squeeze(0).numpy()

    # ── fast numpy inference ──────────────────────────────────────────────────

    def build_numpy_cache(self):
        """Extract weights into numpy arrays for fast single-step inference.

        Call after each parameter update. Avoids PyTorch dispatch overhead
        (~20ms/call on CPU) during the training step loop.
        """
        self._np_cache: list[tuple] = []
        with torch.no_grad():
            for layer in self.trunk:
                if isinstance(layer, torch.nn.Linear):
                    self._np_cache.append((
                        layer.weight.numpy().T.copy(),  # (in, out)
                        layer.bias.numpy().copy(),
                    ))
            self._np_mean_W  = self.mean.weight.numpy().T.copy()
            self._np_mean_b  = self.mean.bias.numpy().copy()
            self._np_lstd_W  = self.log_std.weight.numpy().T.copy()
            self._np_lstd_b  = self.log_std.bias.numpy().copy()

    def predict_numpy(self, obs: np.ndarray) -> np.ndarray:
        """Stochastic action via cached numpy weights (~0.1ms vs 20ms torch).

        Mirrors actor.sample() exactly: samples from N(mean, exp(log_std)) in
        pre-tanh space, then applies tanh. This keeps buffer experiences
        consistent with the policy distribution the SAC updates assume.
        explore_std acts as a temperature multiplier (decays from start to end).
        """
        x = obs.astype(np.float32)
        for W, b in self._np_cache:
            x = np.maximum(0.0, x @ W + b)          # ReLU hidden
        mean    = x @ self._np_mean_W + self._np_mean_b
        log_std = np.clip(x @ self._np_lstd_W + self._np_lstd_b,
                          LOG_STD_MIN, LOG_STD_MAX)
        std = np.exp(log_std)
        # Temperature multiplier: explore_std decays 0.5→0.05, giving 1.5x→1.05x variance
        if hasattr(self, '_explore_std') and self._explore_std > 0:
            std = std * (1.0 + self._explore_std)
        x_t = mean + std * np.random.randn(*mean.shape)
        return np.tanh(x_t).astype(np.float32)


class Critic(nn.Module):
    """Twin Q-networks Q1, Q2.  Input: concat(state, action)."""

    def __init__(self, state_dim: int, action_dim: int, hidden=(256, 256)):
        super().__init__()
        in_dim  = state_dim + action_dim
        self.q1 = _mlp([in_dim, *hidden, 1])
        self.q2 = _mlp([in_dim, *hidden, 1])

    def forward(self, state: torch.Tensor, action: torch.Tensor):
        sa = torch.cat([state, action], dim=-1)
        return self.q1(sa), self.q2(sa)

    def q_min(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        q1, q2 = self(state, action)
        return torch.min(q1, q2)
