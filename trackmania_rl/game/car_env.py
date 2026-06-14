"""Kinematic bicycle model simulation environment.

Mirrors the control feel of an arcade racer (Trackmania-like) without the
full physics engine. Fast enough to run hundreds of thousands of sim steps
per second; good enough to teach the *shape* of car control (proportional
steering, speed management, smooth inputs) before the agent sees the real game.

Observation (N_OBS = 10 features):
  0  speed_norm          speed / max_speed              [0, 1]
  1  lat_norm            lateral offset / track_width   [-1, 1]
  2  heading_err_norm    heading error / π              [-1, 1]
  3  curv_near           curvature 5 wp ahead           [−, +]
  4  curv_mid            curvature 12 wp ahead
  5  curv_far            curvature 25 wp ahead
  6  progress            fraction of track done         [0, 1]
  7  steer_prev          previous steer action          [-1, 1]
  8  accel_prev          previous accel action          [-1, 1]
  9  wall_dist_norm      nearest wall / track_width     [0, 1]

Action (2 continuous, clipped to [-1, 1]):
  0  steer   −1 = full left,  +1 = full right
  1  accel   −1 = full brake, +1 = full throttle

Reward:
  +Δprogress per step (fraction of track advanced — dense, sensible for driving)
  −1.0 on going off-track (terminal)
  No other shaping — keeps it stationary across curriculum phases.
"""

from __future__ import annotations

import numpy as np
from typing import Optional, Tuple, Dict

from game.track import Track, TRACK_REGISTRY

N_OBS = 10
N_ACT = 2

# ── physics defaults (Trackmania-ish arcade feel) ────────────────────────────
_DEFAULTS: dict = {
    "wheelbase":  2.7,    # m
    "max_steer":  0.50,   # rad  (~29°)
    "max_speed":  55.0,   # m/s  (~200 km/h ceiling)
    "accel_gain": 12.0,   # m/s² at full throttle
    "brake_gain": 20.0,   # m/s² at full brake
    "friction":   0.35,   # m/s² passive drag
    "dt":         1/60,   # s — 60 Hz sim tick
    "action_repeat": 3,   # ticks per agent decision (~20 Hz)
}

# Domain randomisation: ±fraction applied to each parameter
_RAND_FRACS: dict = {
    "wheelbase":  0.15,
    "max_steer":  0.15,
    "max_speed":  0.20,
    "accel_gain": 0.25,
    "brake_gain": 0.25,
    "friction":   0.40,
}

_LOOKAHEADS = (5, 12, 25)   # waypoints ahead for curvature features


class CarEnv:
    """Gym-style continuous-control sim environment."""

    def __init__(
        self,
        track: str = "straight",
        domain_rand: bool = False,
        max_speed: Optional[float] = None,
        max_frames: int = 18_000,
        seed: Optional[int] = None,
    ):
        self.track_name  = track
        self.domain_rand = domain_rand
        self._speed_cap  = max_speed       # overrides physics default when set
        self.max_frames  = max_frames
        self._rng        = np.random.default_rng(seed)
        self._track: Track = TRACK_REGISTRY[track]()
        self._p: dict = {}                 # current episode physics params

        # Mutable state — initialised in reset()
        self.x = self.y = self.theta = self.v = 0.0
        self.steer_prev = self.accel_prev = 0.0
        self.frame = 0
        self._progress_idx = 0             # furthest waypoint idx reached
        self._total_advanced = 0           # cumulative waypoints advanced (for lap count)
        self.laps = 0

    # ── physics ──────────────────────────────────────────────────────────────

    def _sample_physics(self) -> dict:
        p = dict(_DEFAULTS)
        if self._speed_cap is not None:
            p["max_speed"] = self._speed_cap
        if self.domain_rand:
            for k, frac in _RAND_FRACS.items():
                lo, hi = p[k] * (1 - frac), p[k] * (1 + frac)
                p[k] = float(self._rng.uniform(lo, hi))
            if self._speed_cap is not None:
                p["max_speed"] = self._speed_cap  # respect hard cap after rand
        return p

    def _tick(self, steer: float, accel: float):
        p = self._p
        dt = p["dt"]
        delta = float(np.clip(steer, -1, 1)) * p["max_steer"]
        a     = float(np.clip(accel, -1, 1))
        gain  = p["accel_gain"] if a >= 0 else p["brake_gain"]
        dv    = a * gain - p["friction"]
        self.v     = float(np.clip(self.v + dv * dt, 0.0, p["max_speed"]))
        self.theta += self.v * np.tan(delta) / p["wheelbase"] * dt
        self.x     += self.v * np.cos(self.theta) * dt
        self.y     += self.v * np.sin(self.theta) * dt

    # ── observation ──────────────────────────────────────────────────────────

    def _observe(self) -> np.ndarray:
        p = self._p
        t = self._track
        wp_idx, lat_off, tangent, progress = t.nearest_waypoint(self.x, self.y)

        track_angle = np.arctan2(tangent[1], tangent[0])
        heading_err = (self.theta - track_angle + np.pi) % (2 * np.pi) - np.pi

        curvatures = [t.curvature_ahead(wp_idx, lh) for lh in _LOOKAHEADS]

        w = t.width
        wall_dist = float(np.clip((w - abs(lat_off)) / w, 0.0, 1.0))

        return np.array([
            self.v / p["max_speed"],
            lat_off / w,
            heading_err / np.pi,
            *curvatures,
            progress,
            self.steer_prev,
            self.accel_prev,
            wall_dist,
        ], dtype=np.float32)

    # ── gym API ──────────────────────────────────────────────────────────────

    def reset(self, seed: Optional[int] = None) -> np.ndarray:
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        self._p = self._sample_physics()
        t = self._track

        wp0     = t.waypoints[0]
        tangent = t.tangent_at(0)
        noise_pos   = self._rng.uniform(-0.5, 0.5, size=2)
        noise_angle = float(self._rng.uniform(-0.08, 0.08))

        self.x     = float(wp0[0]) + float(noise_pos[0])
        self.y     = float(wp0[1]) + float(noise_pos[1])
        self.theta = float(np.arctan2(tangent[1], tangent[0])) + noise_angle
        self.v     = 0.0
        self.steer_prev = self.accel_prev = 0.0
        self.frame       = 0
        self._progress_idx   = 0
        self._total_advanced = 0
        self.laps = 0
        return self._observe()

    def step(
        self, action: np.ndarray
    ) -> Tuple[np.ndarray, float, bool, Dict]:
        steer = float(action[0])
        accel = float(action[1])

        for _ in range(int(self._p.get("action_repeat", _DEFAULTS["action_repeat"]))):
            self._tick(steer, accel)
            self.frame += 1

        self.steer_prev = steer
        self.accel_prev = accel

        t = self._track
        wp_idx, lat_off, _, progress = t.nearest_waypoint(self.x, self.y)
        n = len(t.waypoints)

        # Progress advance (handles wrap-around for circuits)
        advanced = int((wp_idx - self._progress_idx) % n)
        if advanced > n // 2:   # moved backwards
            advanced = 0
        reward = advanced / n

        if advanced > 0:
            # Lap detection: progress_idx about to wrap past the seam
            if self._progress_idx > n * 0.8 and wp_idx < n * 0.2 and t.closed:
                self.laps += 1
            self._progress_idx    = wp_idx
            self._total_advanced += advanced

        # Off-track terminal
        off_track = abs(lat_off) > t.width
        if off_track:
            reward -= 1.0

        timeout = self.frame >= self.max_frames
        done    = off_track or timeout

        info = {
            "laps":       self.laps,
            "progress":   progress,
            "speed":      self.v,
            "lat_offset": lat_off,
            "off_track":  off_track,
            "timeout":    timeout,
        }
        return self._observe(), float(reward), done, info
