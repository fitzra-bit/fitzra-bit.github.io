from abc import ABC, abstractmethod
import numpy as np


class BaseAgent(ABC):
    @abstractmethod
    def choose_action(self, state: np.ndarray) -> int:
        """Return action index given a normalized state vector."""

    def on_episode_end(self, score: float):
        """Hook called after each episode (optional for stateless agents)."""
