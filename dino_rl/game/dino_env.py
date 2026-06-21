"""DinoEnv — Python mirror of game/dino.html for fast offline training.

Physics, pacing, obstacle rules, and collision boxes are copied constant-
for-constant from the JS game (which itself matches the Chromium original).
The browser game remains the evaluation/demo environment; this sim is where
the millions of training steps happen — ~3 orders of magnitude faster than
the Selenium loop, with zero action-timing jitter.

Gym-style API:
    env = DinoEnv(birds=False, max_speed=8.0, action_repeat=2, seed=0)
    obs = env.reset()
    obs, reward, done, info = env.step(action)   # 0=noop, 1=jump, 2=duck

Rewards are SPARSE and STATIONARY across all curriculum phases:
    +1.0   per obstacle cleared
    -1.0   on death
    +0.001 per frame survived (tie-breaker, negligible vs outcomes)

Curriculum difficulty is environment-shaped (speed caps, birds on/off),
never reward-shaped — so the replay buffer stays consistent across phases.
"""

from typing import Optional

import numpy as np

# ── Original game constants (must match dino.html) ───────────────────
W, H = 600.0, 150.0
MS_PER_FRAME = 1000.0 / 60.0
BOTTOM_PAD = 10.0
GROUND_LINE = H - BOTTOM_PAD            # 140
GRAVITY = 0.6
INITIAL_JUMP_VELOCITY = -10.0           # minus speed/10 at takeoff
DROP_VELOCITY = -5.0
MAX_JUMP_Y = 30.0
SPEED_DROP_COEFFICIENT = 3.0
INITIAL_SPEED = 6.0
GAP_COEFFICIENT = 0.6
MAX_GAP_COEFFICIENT = 1.5
MAX_OBSTACLE_LENGTH = 3
MAX_OBSTACLE_DUPLICATION = 2
CLEAR_TIME_MS = 3000.0

TREX_X, TREX_W, TREX_H = 50.0, 44.0, 47.0
TREX_W_DUCK, TREX_H_DUCK = 59.0, 25.0
TREX_GROUND_Y = GROUND_LINE - TREX_H    # 93

OB_TYPES = {
    "CACTUS_SMALL": {"w": 17.0, "h": 35.0, "y": 105.0, "min_gap": 120.0, "multiple_speed": 4.0},
    "CACTUS_LARGE": {"w": 25.0, "h": 50.0, "y": 90.0,  "min_gap": 120.0, "multiple_speed": 7.0},
    "PTERODACTYL":  {"w": 46.0, "h": 40.0, "ys": [100.0, 75.0, 50.0], "min_gap": 150.0,
                     "speed_offset": 0.8},
}

N_FEATURES = 20           # 15 base + 5 v2 (dissolved time features + cadence)
TTC_FRAMES_NORM = 120.0   # frames-to-impact normaliser for the TTC feature
TRAVERSE_NORM = 20.0      # frames-to-traverse normaliser (obstacle width / speed)


class _Obstacle:
    __slots__ = ("type", "x", "y", "w", "h", "gap", "speed_offset", "counted")

    def __init__(self, type_, x, y, w, h, gap, speed_offset=0.0):
        self.type = type_
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.gap = gap
        self.speed_offset = speed_offset
        self.counted = False    # cleared-counter bookkeeping

    @property
    def is_bird(self) -> bool:
        return self.type == "PTERODACTYL"


class DinoEnv:
    def __init__(
        self,
        birds: bool = True,
        bird_min_speed: float = 8.5,
        max_speed: float = 13.0,
        accel: float = 0.001,
        action_repeat: int = 2,
        action_repeat_min: Optional[int] = None,
        action_repeat_max: Optional[int] = None,
        start_speed_min: Optional[float] = None,
        start_speed_max: Optional[float] = None,
        max_frames: int = 36_000,        # 10 game-minutes cap
        survival_reward: float = 0.001,  # per frame
        clear_reward: float = 1.0,
        death_reward: float = -1.0,
        seed: Optional[int] = None,
    ):
        self.birds = birds
        self.bird_min_speed = bird_min_speed
        self.max_speed = max_speed
        self.accel = accel
        self.action_repeat = action_repeat
        # Timing domain randomization (#2): when both bounds are set, each step
        # advances a random number of frames in [min, max] instead of the fixed
        # action_repeat — bracketing the real browser loop (measured mean 3.8,
        # range 1–5) so the policy learns timing margins, not frame-perfection.
        self.action_repeat_min = action_repeat_min
        self.action_repeat_max = action_repeat_max
        self._jitter = action_repeat_min is not None and action_repeat_max is not None
        # Random start speed (#2, hard-region enrichment): when set, each TRAINING
        # episode begins at a random speed in [min, max] (clamped to max_speed),
        # so the policy gets full-length practice across all speeds — especially
        # the data-light bird band (≥8.5) — instead of a brief fly-through after
        # surviving the easy early game. Eval keeps the canonical start at speed 6.
        self.start_speed_min = start_speed_min
        self.start_speed_max = start_speed_max
        self._randstart = start_speed_min is not None and start_speed_max is not None
        # Independent RNG so the obstacle sequence for a given seed is identical
        # whether or not timing jitter is on (keeps jitter/no-jitter comparable).
        self.timing_rng = np.random.default_rng(None if seed is None else seed + 777)
        self.max_frames = max_frames
        self.survival_reward = survival_reward
        self.clear_reward = clear_reward
        self.death_reward = death_reward
        self.rng = np.random.default_rng(seed)
        self.reset()

    # ── Episode control ───────────────────────────────────────────────

    def reset(self, seed: Optional[int] = None) -> np.ndarray:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
            self.timing_rng = np.random.default_rng(seed + 777)
        self.dino_y = TREX_GROUND_Y
        self.jump_vel = 0.0
        self.jumping = False
        self.ducking = False
        self.speed_drop = False
        self.crashed = False
        self.last_n_frames = self.action_repeat   # cadence feature seed (v2)
        if self._randstart:
            lo = min(self.start_speed_min, self.max_speed)
            hi = min(self.start_speed_max, self.max_speed)
            self.speed = float(self.timing_rng.uniform(lo, hi)) if hi > lo else lo
        else:
            self.speed = INITIAL_SPEED
        self.raw_distance = 0.0
        self.running_time_ms = 0.0
        self.frames = 0
        self.obstacles: list[_Obstacle] = []
        self.history: list[str] = []
        self.cleared = 0
        self.death_cause: Optional[str] = None
        return self._observe()

    @property
    def score(self) -> float:
        """Displayed-score units (original distance-meter coefficient)."""
        return self.raw_distance * 0.025

    # ── Step ──────────────────────────────────────────────────────────

    def step(self, action: int):
        """Apply action, advance action_repeat frames. Returns (obs, r, done, info)."""
        if self.crashed:
            raise RuntimeError("step() called on crashed env — call reset()")

        # Action semantics identical to chrome_driver.act():
        # 1 = startJump, 2 = duck on (fast-fall if airborne), 0 = release duck
        if action == 1:
            if not self.jumping:
                self.jumping = True
                self.ducking = False
                self.speed_drop = False
                self.jump_vel = INITIAL_JUMP_VELOCITY - self.speed / 10.0
        elif action == 2:
            if self.jumping:
                self.speed_drop = True
            else:
                self.ducking = True
        else:
            self.ducking = False
            self.speed_drop = False

        reward = 0.0
        cleared_before = self.cleared
        n_frames = self.action_repeat
        if self._jitter:
            n_frames = int(self.timing_rng.integers(
                self.action_repeat_min, self.action_repeat_max + 1))
        self.last_n_frames = n_frames   # diagnostic: jitter draw on this step
        for _ in range(n_frames):
            self._advance_frame()
            reward += self.survival_reward
            if self.crashed or self.frames >= self.max_frames:
                break

        reward += (self.cleared - cleared_before) * self.clear_reward
        done = self.crashed or self.frames >= self.max_frames
        if self.crashed:
            reward += self.death_reward

        info = {
            "score": self.score,
            "cleared": self.cleared,
            "speed": self.speed,
            "death_cause": self.death_cause,
            "timeout": (not self.crashed) and done,
        }
        return self._observe(), reward, done, info

    # ── Frame physics (mirrors dino.html update(), fe = 1 frame) ─────

    def _advance_frame(self):
        self.frames += 1
        self.running_time_ms += MS_PER_FRAME

        # Jump physics
        if self.jumping:
            mult = SPEED_DROP_COEFFICIENT if self.speed_drop else 1.0
            self.dino_y += self.jump_vel * mult
            self.jump_vel += GRAVITY
            if self.dino_y < MAX_JUMP_Y and self.jump_vel < DROP_VELOCITY:
                self.jump_vel = DROP_VELOCITY
            if self.dino_y >= TREX_GROUND_Y:
                self.dino_y = TREX_GROUND_Y
                self.jump_vel = 0.0
                self.jumping = False
                self.speed_drop = False

        # Obstacles move; count clears when they pass the dino
        for ob in self.obstacles:
            ob.x -= self.speed + ob.speed_offset
            if not ob.counted and ob.x + ob.w < TREX_X:
                ob.counted = True
                self.cleared += 1
        self.obstacles = [ob for ob in self.obstacles if ob.x + ob.w > -10]

        # Spawning (original horizon logic)
        if self.running_time_ms > CLEAR_TIME_MS:
            if not self.obstacles:
                self._spawn()
            else:
                last = self.obstacles[-1]
                if W - (last.x + last.w) > last.gap:
                    self._spawn()

        # Distance & acceleration
        self.raw_distance += self.speed
        if self.speed < self.max_speed:
            self.speed = min(self.max_speed, self.speed + self.accel)

        # Collision
        cause = self._collision()
        if cause is not None:
            self.crashed = True
            self.death_cause = cause

    def _spawn(self):
        names = ["CACTUS_SMALL", "CACTUS_LARGE"]
        if self.birds and self.speed >= self.bird_min_speed:
            names.append("PTERODACTYL")

        name = names[int(self.rng.integers(len(names)))]
        for _ in range(4):   # duplication rule: max 2 identical in a row
            if (len(self.history) >= MAX_OBSTACLE_DUPLICATION
                    and all(h == name for h in self.history[-MAX_OBSTACLE_DUPLICATION:])):
                name = names[int(self.rng.integers(len(names)))]
            else:
                break

        cfg = OB_TYPES[name]
        if name == "PTERODACTYL":
            y = cfg["ys"][int(self.rng.integers(3))]
            w = cfg["w"]
            offset = cfg["speed_offset"] if self.rng.random() > 0.5 else -cfg["speed_offset"]
            gap = self._gap(cfg["min_gap"], w)
            self.obstacles.append(_Obstacle(name, W, y, w, cfg["h"], gap, offset))
        else:
            group = 1
            if self.speed > cfg["multiple_speed"]:
                group = 1 + int(self.rng.integers(MAX_OBSTACLE_LENGTH))
            w = cfg["w"] * group
            gap = self._gap(cfg["min_gap"], w)
            self.obstacles.append(_Obstacle(name, W, cfg["y"], w, cfg["h"], gap))

        self.history.append(name)
        if len(self.history) > 4:
            self.history.pop(0)

    def _gap(self, min_gap_type: float, width: float) -> float:
        min_gap = round(width * self.speed + min_gap_type * GAP_COEFFICIENT)
        max_gap = round(min_gap * MAX_GAP_COEFFICIENT)
        return float(min_gap + self.rng.integers(max(1, max_gap - min_gap)))

    def _collision(self) -> Optional[str]:
        """Effective collision boxes — identical insets to dino.html."""
        if self.ducking:
            dx, dy = TREX_X + 2, GROUND_LINE - TREX_H_DUCK
            dw, dh = TREX_W_DUCK - 8, TREX_H_DUCK
        else:
            dx, dy = TREX_X + 6, self.dino_y + 2
            dw, dh = TREX_W - 14, TREX_H - 4

        for ob in self.obstacles:
            if ob.is_bird:
                ox, oy = ob.x + 12, ob.y + 10
                ow, oh = ob.w - 24, ob.h - 18
            else:
                ox, oy = ob.x + 2, ob.y + 2
                ow, oh = ob.w - 4, ob.h - 2
            if dx < ox + ow and dx + dw > ox and dy < oy + oh and dy + dh > oy:
                if ob.is_bird:
                    height = {100.0: "low", 75.0: "mid", 50.0: "high"}.get(ob.y, "?")
                    return f"bird_{height}"
                return ob.type.lower()
        return None

    # ── Observation (15 features) ─────────────────────────────────────
    #  0 obs1 dist (x/600, 1=far/none)     8 gap obs1→obs2 (norm, 1=none)
    #  1 obs1 top-edge y (/150)            9 speed, (speed-6)/7 → [0,1]
    #  2 obs1 width (/600)                10 dino y-offset from ground (/150)
    #  3 obs1 is_bird                     11 dino y-velocity (/20, +down)
    #  4 obs2 dist                        12 jumping flag
    #  5 obs2 top-edge y                  13 ducking flag
    #  6 obs2 width                       14 TTC obs1 (frames-to-impact /120)
    #  7 obs2 is_bird

    def _observe(self) -> np.ndarray:
        def feats(ob: Optional[_Obstacle]):
            if ob is None:
                return [1.0, 0.0, 0.0, 0.0]
            return [max(0.0, ob.x / W), ob.y / H, ob.w / W, float(ob.is_bird)]

        def ttc_of(ob: Optional[_Obstacle]) -> float:
            """Frames until the obstacle reaches the dino's front (time-to-impact)."""
            if ob is None:
                return 1.0
            f = max(0.0, ob.x - (TREX_X + TREX_W)) / max(self.speed, 0.1)
            return min(f, TTC_FRAMES_NORM) / TTC_FRAMES_NORM

        def traverse_of(ob: Optional[_Obstacle]) -> float:
            """Frames the obstacle blocks the kill x-zone (width / speed) — how long
            the dino must stay clear. Bigger for wide/grouped cacti at low speed."""
            if ob is None:
                return 0.0
            return min(ob.w / max(self.speed, 0.1), TRAVERSE_NORM) / TRAVERSE_NORM

        # First two obstacles not yet passed
        ahead = [ob for ob in self.obstacles if not ob.counted]
        o1 = ahead[0] if len(ahead) > 0 else None
        o2 = ahead[1] if len(ahead) > 1 else None

        f1, f2 = feats(o1), feats(o2)
        gap = (o2.x - (o1.x + o1.w)) / W if (o1 and o2) else 1.0
        ttc1 = ttc_of(o1)

        # ── v2: dissolved (time-based) features + decision cadence ──────────
        # These re-express the physics in TIME units so the policy generalises
        # across speed, and expose the realized decision cadence so the policy
        # can perceive (and adapt to) jitter spikes. See OVERHAUL.md.
        ttc2 = ttc_of(o2)
        trav1 = traverse_of(o1)
        trav2 = traverse_of(o2)
        if o1 is not None and o2 is not None:
            tgap = min(max(0.0, o2.x - (o1.x + o1.w)) / max(self.speed, 0.1),
                       TTC_FRAMES_NORM) / TTC_FRAMES_NORM
        else:
            tgap = 1.0
        cadence = self.last_n_frames / 6.0

        return np.array(
            f1 + f2 + [
                gap,
                (self.speed - INITIAL_SPEED) / 7.0,
                max(0.0, (TREX_GROUND_Y - self.dino_y)) / H,
                self.jump_vel / 20.0,
                float(self.jumping),
                float(self.ducking),
                ttc1,
                # ── appended v2 features (indices 15–19) ──
                ttc2, trav1, trav2, tgap, cadence,
            ],
            dtype=np.float32,
        )
