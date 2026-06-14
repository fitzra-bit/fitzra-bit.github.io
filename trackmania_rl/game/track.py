"""Track definitions as centerline waypoints.

A Track is just a closed (or open) polyline of (x, y) points representing
the road centreline, plus a half-width. All geometry — nearest point, tangent,
signed lateral offset, curvature ahead — is computed from the waypoints so
the same Track object drives both the physics sim and the observation builder.
"""

import numpy as np
from dataclasses import dataclass


@dataclass
class Track:
    name: str
    waypoints: np.ndarray   # (N, 2) float32 centerline points
    width: float            # half-width in meters
    closed: bool = True     # True for circuits, False for straights

    # ── derived geometry ─────────────────────────────────────────────────

    def tangent_at(self, idx: int) -> np.ndarray:
        """Unit tangent vector at waypoint idx."""
        n = len(self.waypoints)
        if self.closed:
            fwd = self.waypoints[(idx + 1) % n] - self.waypoints[(idx - 1) % n]
        else:
            if idx == 0:
                fwd = self.waypoints[1] - self.waypoints[0]
            elif idx == n - 1:
                fwd = self.waypoints[-1] - self.waypoints[-2]
            else:
                fwd = self.waypoints[idx + 1] - self.waypoints[idx - 1]
        norm = np.linalg.norm(fwd)
        return fwd / norm if norm > 1e-6 else np.array([1.0, 0.0], dtype=np.float32)

    def _cum_lengths(self) -> np.ndarray:
        segs = np.linalg.norm(np.diff(self.waypoints, axis=0), axis=1)
        return np.concatenate([[0.0], np.cumsum(segs)])

    @property
    def total_length(self) -> float:
        return float(self._cum_lengths()[-1])

    def nearest_waypoint(self, x: float, y: float):
        """Return (idx, lateral_offset, tangent, progress_frac).

        lateral_offset: signed metres from centreline (+ve = left of direction
        of travel). progress_frac: [0, 1) around the track.
        """
        pos = np.array([x, y], dtype=np.float32)
        dists = np.linalg.norm(self.waypoints - pos, axis=1)
        idx = int(np.argmin(dists))

        tangent = self.tangent_at(idx)
        to_car = pos - self.waypoints[idx]
        lateral = float(np.cross(tangent, to_car))   # signed

        cum = self._cum_lengths()
        progress = cum[idx] / max(self.total_length, 1.0)
        return idx, lateral, tangent, progress

    def curvature_ahead(self, idx: int, lookahead: int) -> float:
        """Mean signed angular change per step over next `lookahead` waypoints."""
        n = len(self.waypoints)
        angles = []
        for k in range(lookahead + 1):
            i = (idx + k) % n if self.closed else min(idx + k, n - 1)
            t = self.tangent_at(i)
            angles.append(np.arctan2(t[1], t[0]))
        if len(angles) < 2:
            return 0.0
        deltas = np.diff(np.unwrap(angles))
        return float(np.mean(deltas))


# ── track generators ─────────────────────────────────────────────────────────

def make_straight(length: float = 250.0, width: float = 9.0, n: int = 60) -> Track:
    """Simple straight road. Agent learns throttle/brake and lane-keeping."""
    x = np.linspace(0.0, length, n, dtype=np.float32)
    y = np.zeros(n, dtype=np.float32)
    return Track("straight", np.stack([x, y], axis=1), width, closed=False)


def make_oval(length: float = 500.0, width: float = 9.0, n: int = 120) -> Track:
    """Smooth oval: two straights joined by semicircles. Teaches cornering."""
    t = np.linspace(0.0, 2 * np.pi, n, endpoint=False, dtype=np.float32)
    a = length / 4.0    # semi-major axis
    b = length / 9.0    # semi-minor axis
    x = (a * np.cos(t)).astype(np.float32)
    y = (b * np.sin(t)).astype(np.float32)
    return Track("oval", np.stack([x, y], axis=1), width, closed=True)


def make_slalom(
    n_gates: int = 10,
    gate_spacing: float = 28.0,
    offset: float = 14.0,
    width: float = 9.0,
    pts_per_gate: int = 12,
) -> Track:
    """S-curve through alternating offset gates. Teaches anticipatory steering."""
    n = n_gates * pts_per_gate
    xs = np.linspace(0.0, n_gates * gate_spacing, n, dtype=np.float32)
    # Smooth sine centreline; half-period per gate spacing × 2
    period = gate_spacing * 2.0
    ys = (offset * np.sin(xs * 2 * np.pi / period)).astype(np.float32)
    return Track("slalom", np.stack([xs, ys], axis=1), width, closed=False)


TRACK_REGISTRY = {
    "straight": make_straight,
    "oval":     make_oval,
    "slalom":   make_slalom,
}
