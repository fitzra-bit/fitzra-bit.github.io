"""DQN agent with action masking and experience replay."""

import random
from collections import deque
from typing import List, Optional
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from rl.environment import FactoryEnv


class _QNet(nn.Module):
    def __init__(self, state_size: int, n_actions: int, hidden: List[int]):
        super().__init__()
        layers = []
        in_dim = state_size
        for h in hidden:
            layers += [nn.Linear(in_dim, h), nn.ReLU()]
            in_dim = h
        layers.append(nn.Linear(in_dim, n_actions))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class DQNAgent:
    name = "DQN"

    def __init__(
        self,
        state_size: int,
        n_actions: int,
        hidden: List[int] = (128, 128),
        lr: float = 1e-3,
        gamma: float = 0.99,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.05,
        epsilon_decay: float = 0.98,
        buffer_size: int = 5_000,
        batch_size: int = 64,
        target_update_freq: int = 20,
    ):
        self.n_actions = n_actions
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_update_freq = target_update_freq
        self._train_steps = 0

        self.online = _QNet(state_size, n_actions, list(hidden))
        self.target = _QNet(state_size, n_actions, list(hidden))
        self.target.load_state_dict(self.online.state_dict())
        self.target.eval()

        self.optimizer = optim.Adam(self.online.parameters(), lr=lr)
        self.buffer: deque = deque(maxlen=buffer_size)

    def choose_action(self, env: FactoryEnv) -> int:
        valid = env.valid_actions()
        if random.random() < self.epsilon:
            return random.choice(valid)

        obs = torch.from_numpy(env._observe()).unsqueeze(0)
        mask = torch.from_numpy(env.action_mask())
        with torch.no_grad():
            q = self.online(obs).squeeze(0)
        q[~mask] = -float("inf")
        return int(q.argmax().item())

    def store(self, s, a, r, ns, done, mask):
        self.buffer.append((s, a, r, ns, done, mask))

    def train_step(self):
        if len(self.buffer) < self.batch_size:
            return

        batch = random.sample(self.buffer, self.batch_size)
        s, a, r, ns, d, m = zip(*batch)

        S = torch.from_numpy(np.array(s, dtype=np.float32))
        A = torch.tensor(a, dtype=torch.long)
        R = torch.tensor(r, dtype=torch.float32)
        NS = torch.from_numpy(np.array(ns, dtype=np.float32))
        D = torch.tensor(d, dtype=torch.float32)
        M = torch.from_numpy(np.array(m, dtype=bool))

        q_vals = self.online(S).gather(1, A.unsqueeze(1)).squeeze(1)

        with torch.no_grad():
            next_q = self.target(NS)
            next_q[~M] = -float("inf")
            next_q_max = next_q.max(1).values
            target_q = R + self.gamma * next_q_max * (1 - D)

        loss = nn.functional.smooth_l1_loss(q_vals, target_q)
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), 1.0)
        self.optimizer.step()

        self._train_steps += 1
        if self._train_steps % self.target_update_freq == 0:
            self.target.load_state_dict(self.online.state_dict())

    def decay_epsilon(self):
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
