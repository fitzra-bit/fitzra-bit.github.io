"""Dueling Q-network: shared trunk → separate value and advantage heads.

Q(s,a) = V(s) + A(s,a) − mean_a' A(s,a')

The dueling split matches this game's structure: most states are
"nothing nearby — every action has the same value" (V dominates), and the
rare near-obstacle states are where the action choice matters (A dominates).
"""

from typing import List

import numpy as np
import torch
import torch.nn as nn


class QNetwork(nn.Module):
    def __init__(self, trunk_layers: List[int], n_actions: int = 3):
        super().__init__()
        blocks = []
        for in_d, out_d in zip(trunk_layers, trunk_layers[1:]):
            blocks += [nn.Linear(in_d, out_d), nn.ReLU()]
        self.trunk = nn.Sequential(*blocks)
        self.value = nn.Linear(trunk_layers[-1], 1)
        self.advantage = nn.Linear(trunk_layers[-1], n_actions)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        f = self.trunk(x)
        a = self.advantage(f)
        return self.value(f) + a - a.mean(dim=1, keepdim=True)

    @torch.no_grad()
    def predict(self, obs: np.ndarray) -> int:
        t = torch.from_numpy(obs).unsqueeze(0)
        return int(self(t).argmax(dim=1).item())


def build_networks(trunk_layers: List[int], n_actions: int = 3):
    online = QNetwork(trunk_layers, n_actions)
    target = QNetwork(trunk_layers, n_actions)
    target.load_state_dict(online.state_dict())
    target.eval()
    return online, target
