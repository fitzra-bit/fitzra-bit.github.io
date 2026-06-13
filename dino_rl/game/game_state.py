"""Browser game state → the SAME 15-feature vector as game/dino_env.py.

Feature parity between the sim (training) and the browser (eval/demo) is
what lets a sim-trained network play the real game unchanged. Any change
here must be mirrored in DinoEnv._observe() and vice versa.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np

# Must match dino_env.py
_W, _H = 600.0, 150.0
_TREX_X, _TREX_W = 50.0, 44.0
_INITIAL_SPEED = 6.0
_TTC_FRAMES_NORM = 120.0


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
    cleared: int = 0                  # authoritative counter from the game

    def to_array(self) -> np.ndarray:
        """15 features — identical layout to DinoEnv._observe():

          0 obs1 dist (x/600, 1=far/none)     8 gap obs1→obs2 (norm, 1=none)
          1 obs1 top-edge y (/150)            9 speed, (speed−6)/7 → [0,1]
          2 obs1 width (/600)                10 dino y-offset from ground (/150)
          3 obs1 is_bird                     11 dino y-velocity (/20, +down)
          4 obs2 dist                        12 jumping flag
          5 obs2 top-edge y                  13 ducking flag
          6 obs2 width                       14 TTC obs1 (frames-to-impact /120)
          7 obs2 is_bird

        Obstacle y reference (original coordinates): cactus small 0.70,
        large 0.60; bird low 0.67 (jump it), mid 0.50 (duck it),
        high 0.33 (run under).
        """
        def feats(ob: Optional[Obstacle]):
            if ob is None:
                return [1.0, 0.0, 0.0, 0.0]
            return [max(0.0, ob.x / _W), ob.y / _H, ob.width / _W, float(ob.is_bird)]

        # Only obstacles still ahead of the dino (parity with sim's
        # not-counted filter — the browser list includes passed obstacles
        # until they scroll off-screen).
        ahead = [ob for ob in self.obstacles if ob.x + ob.width >= _TREX_X]
        o1 = ahead[0] if len(ahead) > 0 else None
        o2 = ahead[1] if len(ahead) > 1 else None

        f1, f2 = feats(o1), feats(o2)
        gap = (o2.x - (o1.x + o1.width)) / _W if (o1 and o2) else 1.0

        if o1 is not None:
            frames = max(0.0, o1.x - (_TREX_X + _TREX_W)) / max(self.speed, 0.1)
            ttc = min(frames, _TTC_FRAMES_NORM) / _TTC_FRAMES_NORM
        else:
            ttc = 1.0

        return np.array(
            f1 + f2 + [
                gap,
                (self.speed - _INITIAL_SPEED) / 7.0,
                max(0.0, (self.ground_y - self.dino_y)) / _H,
                self.dino_vel_y / 20.0,
                float(self.dino_jumping),
                float(self.dino_ducking),
                ttc,
            ],
            dtype=np.float32,
        )
