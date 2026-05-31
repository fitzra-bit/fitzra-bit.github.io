from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np


@dataclass
class Obstacle:
    x: float
    y: float
    width: float
    height: float
    type: str  # "CACTUS_SMALL", "CACTUS_LARGE", "PTERODACTYL"

    @property
    def is_bird(self) -> bool:
        return self.type == "PTERODACTYL"


@dataclass
class GameState:
    crashed: bool
    score: float
    speed: float
    dino_y: float
    dino_vel_y: float
    dino_jumping: bool
    dino_ducking: bool
    obstacles: List[Obstacle] = field(default_factory=list)
    ground_y: float = 93.0

    def to_array(
        self,
        speed_norm: float = 20.0,
        dist_norm: float = 600.0,
        y_norm: float = 150.0,
    ) -> np.ndarray:
        """Normalize state into a fixed-length float32 vector for the neural net.

        Features (9 total):
          0  distance to obstacle 1 (norm, 1.0 = far / none)
          1  height of obstacle 1  (norm)
          2  width of obstacle 1   (norm)
          3  obstacle 1 is bird    (0/1)
          4  distance to obstacle 2 (norm)
          5  height of obstacle 2   (norm)
          6  current speed          (norm)
          7  dino y offset from ground (norm, 0=on ground, +up)
          8  dino jumping           (0/1)
        """
        def obs_features(obs: Optional[Obstacle]):
            if obs is None:
                return [1.0, 0.0, 0.0, 0.0]
            return [
                max(0.0, obs.x / dist_norm),
                obs.height / y_norm,
                obs.width / dist_norm,
                float(obs.is_bird),
            ]

        o1 = self.obstacles[0] if len(self.obstacles) > 0 else None
        o2 = self.obstacles[1] if len(self.obstacles) > 1 else None

        dino_offset = max(0.0, (self.ground_y - self.dino_y) / y_norm)

        vec = (
            obs_features(o1)
            + obs_features(o2)[:2]
            + [
                self.speed / speed_norm,
                dino_offset,
                float(self.dino_jumping),
            ]
        )
        return np.array(vec, dtype=np.float32)
