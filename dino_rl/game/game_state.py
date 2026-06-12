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
        vel_norm: float = 20.0,
        ttc_clip: float = 2.0,
    ) -> np.ndarray:
        """Normalize state into a fixed-length float32 vector for the neural net.

        Features (13 total):
          0  distance to obstacle 1    (norm, 1.0 = far / none)
          1  y-position of obstacle 1  (norm) ← top edge of sprite, NOT size
               (original 600×150 coordinate space, y_norm=150)
               cactus small: 0.70   cactus large: 0.60
               bird low:  0.67  (must JUMP — hits standing and ducking)
               bird mid:  0.50  (must DUCK — hits standing, clears duck)
               bird high: 0.33  (run under — clears standing)
          2  width of obstacle 1       (norm)
          3  obstacle 1 is bird        (0/1)
          4  distance to obstacle 2    (norm)
          5  y-position of obstacle 2  (norm)
          6  obstacle 2 is bird        (0/1)
          7  current speed             (norm)
          8  dino y offset from ground (norm, 0=on ground, +up)
          9  dino vertical velocity    (norm, +up)
         10  dino jumping              (0/1)
         11  dino ducking              (0/1)  ← new: dino's own crouch state
         12  time-to-collision obs1    (norm)  ← new: obs1_dist/speed, clipped
                                                  speed-invariant approach timing
        """
        def obs_features(obs: Optional[Obstacle]):
            if obs is None:
                return [1.0, 0.0, 0.0, 0.0]
            return [
                max(0.0, obs.x / dist_norm),
                obs.y / y_norm,           # vertical position of top edge (not size)
                obs.width / dist_norm,
                float(obs.is_bird),
            ]

        o1 = self.obstacles[0] if len(self.obstacles) > 0 else None
        o2 = self.obstacles[1] if len(self.obstacles) > 1 else None

        o1_feats = obs_features(o1)
        o2_feats = obs_features(o2)

        speed_n     = self.speed / speed_norm
        dino_offset = max(0.0, (self.ground_y - self.dino_y) / y_norm)

        # Time-to-collision: how many "speed-lengths" until obs1 reaches the dino.
        # Using normalised dist / normalised speed gives a ratio that is large when
        # the obstacle is far or the game is slow, and small when it's close or fast.
        # Clipped to [0, ttc_clip] then divided back so the feature sits in [0, 1].
        ttc = min(o1_feats[0] / (speed_n + 0.01), ttc_clip) / ttc_clip

        vec = (
            o1_feats
            + [o2_feats[0], o2_feats[1], o2_feats[3]]   # dist, height, is_bird
            + [
                speed_n,
                dino_offset,
                self.dino_vel_y / vel_norm,
                float(self.dino_jumping),
                float(self.dino_ducking),                # feature 11
                ttc,                                     # feature 12
            ]
        )
        return np.array(vec, dtype=np.float32)
