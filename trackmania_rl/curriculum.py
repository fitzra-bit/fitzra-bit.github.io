"""Curriculum for sim-based car-control training.

Same design as the dino curriculum:
  - Difficulty ramps via the ENVIRONMENT (track shape + physics caps), not the reward
  - Gates on greedy eval (avg_laps from fixed-seed deterministic rollouts)
  - Auto-advances; flags STALLED after stall_evals rounds without improvement

Phases 0–3 are pure Python sim; the real-game TMInterface phases (4+) come
after the policy has learned basic car control and just needs physics
calibration — domain randomisation in Phase 3 bridges the gap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Phase:
    name:          str
    env_params:    dict
    complete_eval: float        # avg_laps threshold to advance
    stall_evals:   int = 25     # eval rounds without improvement before flagging
    description:   str = ""


PHASES: List[Phase] = [
    Phase(
        name="0-straight",
        env_params={
            "track": "straight", "domain_rand": False,
            "max_speed": 22.0, "max_frames": 3_600,   # 1 game-minute cap — keep episodes short
            "speed_init_frac": 0.55,                   # start at 55% max speed for early signal
        },
        complete_eval=0.85,
        description="Straight road, slow. Learn throttle/brake and lane-keeping.",
    ),
    Phase(
        name="1-oval",
        env_params={
            "track": "oval", "domain_rand": False,
            "max_speed": 38.0, "max_frames": 9_000,   # 2.5 game-minutes
        },
        complete_eval=3.0,
        description="Oval circuit. Learn proportional cornering.",
    ),
    Phase(
        name="2-slalom",
        env_params={
            "track": "slalom", "domain_rand": False,
            "max_speed": 48.0, "max_frames": 9_000,
        },
        complete_eval=2.0,
        description="S-curve track. Learn anticipatory steering.",
    ),
    Phase(
        name="3-domain-rand",
        env_params={
            "track": "slalom", "domain_rand": True,
            "max_frames": 12_000,
        },
        complete_eval=2.0,
        stall_evals=35,
        description=(
            "Randomised physics (friction, wheelbase, speed). "
            "Build robustness for real-game physics transfer."
        ),
    ),
    # Phase 4+ will be TMInterface (real game) — stubs below for documentation.
    # Uncomment and populate env_params with TMInterface kwargs when the
    # real-game wrapper is ready.
    #
    # Phase(
    #     name="4-real-simple",
    #     env_params={"interface": "tminterface", "track_id": "Stadium_A1"},
    #     complete_eval=1.0,
    #     description="Real game, wide simple track. Calibrate to actual physics.",
    # ),
]


class Curriculum:
    def __init__(self):
        self.phases    = PHASES
        self.phase_idx = 0

        # Per-phase counters
        self.evals_in_phase       = 0
        self.best_eval_in_phase   = 0.0
        self.evals_since_improve  = 0
        self.stalled              = False

    @property
    def phase(self) -> Phase:
        return self.phases[self.phase_idx]

    @property
    def finished(self) -> bool:
        return self.phase_idx >= len(self.phases)

    def env_params(self) -> dict:
        return dict(self.phase.env_params)

    def after_eval(self, avg_laps: float) -> dict:
        self.evals_in_phase += 1

        if avg_laps > self.best_eval_in_phase:
            self.best_eval_in_phase  = avg_laps
            self.evals_since_improve = 0
        else:
            self.evals_since_improve += 1

        # Advance
        if avg_laps >= self.phase.complete_eval:
            completed = self.phase.name
            self.phase_idx          += 1
            self.evals_in_phase      = 0
            self.best_eval_in_phase  = 0.0
            self.evals_since_improve = 0
            self.stalled             = False
            next_name = (
                self.phases[self.phase_idx].name
                if not self.finished else "done"
            )
            return {"type": "advance", "completed": completed,
                    "next": next_name, "eval": avg_laps}

        # Stall
        if self.evals_since_improve >= self.phase.stall_evals:
            self.stalled = True
            return {"type": "stalled", "eval": avg_laps}

        return {"type": None, "eval": avg_laps}

    def to_dict(self) -> dict:
        return {
            "phase_idx":           self.phase_idx,
            "evals_in_phase":      self.evals_in_phase,
            "best_eval_in_phase":  self.best_eval_in_phase,
            "evals_since_improve": self.evals_since_improve,
            "stalled":             self.stalled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Curriculum":
        c = cls()
        c.phase_idx           = d["phase_idx"]
        c.evals_in_phase      = d["evals_in_phase"]
        c.best_eval_in_phase  = d["best_eval_in_phase"]
        c.evals_since_improve = d["evals_since_improve"]
        c.stalled             = d.get("stalled", False)
        return c
