"""Lightweight numpy-only feedforward network used by the genetic agent."""

from typing import List
import numpy as np


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, x)


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


class NumpyNet:
    """Fully-connected net: ReLU hidden layers, softmax output."""

    def __init__(self, layer_sizes: List[int], weights: List[np.ndarray] = None):
        self.layer_sizes = layer_sizes
        if weights is not None:
            self.weights = [w.copy() for w in weights]
        else:
            self.weights = self._random_weights()

    def _random_weights(self) -> List[np.ndarray]:
        rng = np.random.default_rng()
        params = []
        for i in range(len(self.layer_sizes) - 1):
            fan_in = self.layer_sizes[i]
            fan_out = self.layer_sizes[i + 1]
            # He init
            scale = np.sqrt(2.0 / fan_in)
            W = rng.normal(0, scale, (fan_in, fan_out)).astype(np.float32)
            b = np.zeros(fan_out, dtype=np.float32)
            params.append(np.concatenate([W.ravel(), b]))
        return params

    def _unpack(self, i: int):
        fan_in = self.layer_sizes[i]
        fan_out = self.layer_sizes[i + 1]
        flat = self.weights[i]
        W = flat[: fan_in * fan_out].reshape(fan_in, fan_out)
        b = flat[fan_in * fan_out :]
        return W, b

    def forward(self, x: np.ndarray) -> np.ndarray:
        h = x.astype(np.float32)
        for i in range(len(self.weights) - 1):
            W, b = self._unpack(i)
            h = _relu(h @ W + b)
        W, b = self._unpack(len(self.weights) - 1)
        return _softmax(h @ W + b)

    def predict(self, x: np.ndarray) -> int:
        return int(np.argmax(self.forward(x)))

    def get_flat_weights(self) -> np.ndarray:
        return np.concatenate(self.weights)

    def set_flat_weights(self, flat: np.ndarray):
        idx = 0
        for i, w in enumerate(self.weights):
            n = len(w)
            self.weights[i] = flat[idx : idx + n].copy()
            idx += n

    def clone(self) -> "NumpyNet":
        return NumpyNet(self.layer_sizes, self.weights)
