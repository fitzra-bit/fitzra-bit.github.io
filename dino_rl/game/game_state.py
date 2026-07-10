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
_TRAVERSE_NORM = 20.0       # must match dino_env.TRAVERSE_NORM


@dataclass
class Obstacle:
    x: float
    y: float
    width: float
    height: float
    type: str  # "CACTUS_SMALL", "CACTUS_LARGE", "PTERODACTYL"
    closing_v: Optional[float] = None   # measured px/frame toward the dino
                                        # (set by the driver from consecutive
                                        # reads; None = no previous observation)

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
    cadence_frames: float = 2.0       # frames elapsed since last decision (set by driver)

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

        def ttc_of(ob: Optional[Obstacle]) -> float:
            if ob is None:
                return 1.0
            f = max(0.0, ob.x - (_TREX_X + _TREX_W)) / max(self.speed, 0.1)
            return min(f, _TTC_FRAMES_NORM) / _TTC_FRAMES_NORM

        def traverse_of(ob: Optional[Obstacle]) -> float:
            if ob is None:
                return 0.0
            return min(ob.width / max(self.speed, 0.1), _TRAVERSE_NORM) / _TRAVERSE_NORM

        # Only obstacles still ahead of the dino (parity with sim's
        # not-counted filter — the browser list includes passed obstacles
        # until they scroll off-screen).
        ahead = [ob for ob in self.obstacles if ob.x + ob.width >= _TREX_X]
        o1 = ahead[0] if len(ahead) > 0 else None
        o2 = ahead[1] if len(ahead) > 1 else None

        f1, f2 = feats(o1), feats(o2)
        gap = (o2.x - (o1.x + o1.width)) / _W if (o1 and o2) else 1.0
        ttc1 = ttc_of(o1)

        # ── v2: dissolved (time-based) features + decision cadence ──────────
        # MUST mirror dino_env.DinoEnv._observe() exactly (transfer depends on it).
        ttc2 = ttc_of(o2)
        trav1 = traverse_of(o1)
        trav2 = traverse_of(o2)
        if o1 is not None and o2 is not None:
            tgap = min(max(0.0, o2.x - (o1.x + o1.width)) / max(self.speed, 0.1),
                       _TTC_FRAMES_NORM) / _TTC_FRAMES_NORM
        else:
            tgap = 1.0
        cadence = self.cadence_frames / 6.0

        # Explicit obstacle-class one-hots — MUST mirror dino_env.bird_class().
        def bird_class(ob: Optional[Obstacle]):
            if ob is None or not ob.is_bird:
                return [0.0, 0.0, 0.0]
            return [float(ob.y == 100.0), float(ob.y == 75.0), float(ob.y == 50.0)]

        # E11: closing-velocity residual — MUST mirror dino_env.closing_res().
        # closing_v is measured by the driver from consecutive reads (Δx over
        # the cadence interval); the residual vs game speed exposes the birds'
        # hidden ±0.8 speed_offset that a single snapshot cannot reveal.
        def closing_res(ob: Optional[Obstacle]) -> float:
            if ob is None or ob.closing_v is None:
                return 0.0
            if abs(ob.closing_v - self.speed) > 1.5:   # mismatch artifact guard
                return 0.0
            return max(-1.0, min(1.0, (ob.closing_v - self.speed) / 2.0))

        return np.array(
            f1 + f2 + [
                gap,
                (self.speed - _INITIAL_SPEED) / 7.0,
                max(0.0, (self.ground_y - self.dino_y)) / _H,
                self.dino_vel_y / 20.0,
                float(self.dino_jumping),
                float(self.dino_ducking),
                ttc1,
                # ── appended v2 features (indices 15–19) ──
                ttc2, trav1, trav2, tgap, cadence,
            ] + bird_class(o1) + bird_class(o2)     # indices 20–25
              + [closing_res(o1), closing_res(o2)],  # indices 26–27 (E11)
            dtype=np.float32,
        )
