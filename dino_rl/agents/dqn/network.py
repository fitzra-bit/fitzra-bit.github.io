"""PyTorch DQN network with online + target copies."""

from typing import List
import torch
import torch.nn as nn
import numpy as np


class QNetwork(nn.Module):
    def __init__(self, layer_sizes: List[int]):
        super().__init__()
        layers = []
        for i in range(len(layer_sizes) - 1):
            layers.append(nn.Linear(layer_sizes[i], layer_sizes[i + 1]))
            if i < len(layer_sizes) - 2:
                layers.append(nn.ReLU())
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

    def predict(self, state: np.ndarray) -> int:
        with torch.no_grad():
            t = torch.from_numpy(state).unsqueeze(0)
            q = self.forward(t)
            return int(q.argmax(dim=1).item())


def build_networks(layer_sizes: List[int]):
    online = QNetwork(layer_sizes)
    target = QNetwork(layer_sizes)
    target.load_state_dict(online.state_dict())
    target.eval()
    return online, target
