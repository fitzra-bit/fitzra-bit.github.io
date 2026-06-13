"""Declarative training curriculum — environment-shaped, eval-gated, self-driving.

Design principles (see OVERHAUL.md for the full rationale):

1. REWARDS NEVER CHANGE. Every phase uses the same sparse rewards
   (+1 clear, −1 death, tiny survival). Changing rewards between phases
   poisons the replay buffer — transitions recorded under old rewards
   become wrong under new ones. Difficulty ramps through the ENVIRONMENT:
   speed caps and bird availability, via DinoEnv constructor params.

2. ALL CONTROL DECISIONS USE GREEDY EVAL, NOT TRAINING SCORES.
   Training episodes are ε-contaminated: a single random jump at the
   wrong moment kills, so training scores systematically understate the
   policy and add variance. Phase gates, best-checkpoint selection, and
   stall detection all key off periodic ε=0 evaluation runs on fixed
   seeds — the same exam every time.

3. STALLS RECOVER AUTOMATICALLY: (1) ε boost re-explores; (2) revert to
   phase-best weights + boost; (3) STALLED flag — the only point where a
   human is needed, and it means the phase needs a design change, not a
   restart.

State serialises to runs/<run>/state.json after every episode;
`python main.py --agent dqn --auto` resumes mid-phase.
"""

from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlencode


@dataclass
class Phase:
    name: str
    description: str
    env_params: dict             # DinoEnv kwargs: birds, max_speed, accel...
    complete_eval_avg: float     # greedy-eval mean score to finish the phase
    min_evals: int = 3           # don't complete off a single lucky eval
    stall_evals: int = 25        # eval rounds without a new best → intervene


# Reference points (cacti-only, max_speed 8): random policy ≈ 45,
# perfectly-timed scripted jumper ≈ 6,700 (10-min timeout cap).
# Gates are "solid competence", not perfection.

PHASES = [
    Phase(
        name="1-slow",
        description="Cacti only, speed capped at 8. Learn jump timing.",
        env_params={"birds": False, "max_speed": 8.0},
        complete_eval_avg=600.0,
    ),
    Phase(
        name="2-mid",
        description="Cacti only, speed capped at 10. Tighter timing windows.",
        env_params={"birds": False, "max_speed": 10.0},
        complete_eval_avg=800.0,
    ),
    Phase(
        name="3-full-speed",
        description="Cacti only, full speed 13. Master the hardest timing.",
        env_params={"birds": False, "max_speed": 13.0},
        complete_eval_avg=1000.0,
    ),
    Phase(
        name="4-birds",
        description="Full game. Birds at speed ≥ 8.5: low=jump, mid=duck, high=run.",
        env_params={"birds": True, "max_speed": 13.0},
        complete_eval_avg=1500.0,
        stall_evals=40,          # new skill (ducking) — be patient
    ),
]


class Curriculum:
    """Tracks phase progress from eval results; emits advance/intervene events."""

    def __init__(self, phases: Optional[list] = None):
        self.phases = phases or PHASES
        self.phase_idx = 0
        self.evals_in_phase = 0
        self.best_eval_in_phase = 0.0
        self.evals_since_improve = 0
        self.interventions_used = 0
        self.stalled = False

    # ── Accessors ────────────────────────────────────────────────────

    @property
    def phase(self) -> Phase:
        return self.phases[self.phase_idx]

    @property
    def finished(self) -> bool:
        return self.phase_idx >= len(self.phases)

    def env_params(self) -> dict:
        """DinoEnv kwargs for the current phase (full game once finished)."""
        if self.finished:
            return {"birds": True, "max_speed": 13.0}
        return dict(self.phase.env_params)

    def game_url(self, base_url: str) -> str:
        """Equivalent dino.html URL — for browser eval/demo parity."""
        p = self.env_params()
        params = {"birds": int(p.get("birds", True))}
        if p.get("max_speed"):
            params["maxspeed"] = p["max_speed"]
        sep = "&" if "?" in base_url else "?"
        return f"{base_url}{sep}{urlencode(params)}"

    # ── Eval hook (called after each greedy evaluation round) ────────

    def after_eval(self, eval_avg: float) -> dict:
        """Returns {"type": None|"advance"|"intervene"|"stalled", ...}."""
        if self.finished:
            return {"type": None}

        ph = self.phase
        self.evals_in_phase += 1

        if eval_avg > self.best_eval_in_phase:
            self.best_eval_in_phase = eval_avg
            self.evals_since_improve = 0
        else:
            self.evals_since_improve += 1

        if self.evals_in_phase >= ph.min_evals and eval_avg >= ph.complete_eval_avg:
            completed = ph.name
            self._advance()
            return {
                "type": "advance",
                "completed": completed,
                "eval_avg": eval_avg,
                "next": self.phase.name if not self.finished else None,
            }

        if self.evals_since_improve >= ph.stall_evals and not self.stalled:
            self.evals_since_improve = 0
            self.interventions_used += 1
            if self.interventions_used <= 2:
                return {"type": "intervene", "level": self.interventions_used,
                        "eval_avg": eval_avg}
            self.stalled = True
            return {"type": "stalled", "eval_avg": eval_avg}

        return {"type": None}

    def _advance(self):
        self.phase_idx += 1
        self.evals_in_phase = 0
        self.best_eval_in_phase = 0.0
        self.evals_since_improve = 0
        self.interventions_used = 0
        self.stalled = False

    # ── Persistence ──────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "phase_idx": self.phase_idx,
            "evals_in_phase": self.evals_in_phase,
            "best_eval_in_phase": self.best_eval_in_phase,
            "evals_since_improve": self.evals_since_improve,
            "interventions_used": self.interventions_used,
            "stalled": self.stalled,
        }

    @classmethod
    def from_dict(cls, d: dict, phases: Optional[list] = None) -> "Curriculum":
        c = cls(phases)
        c.phase_idx = d.get("phase_idx", 0)
        c.evals_in_phase = d.get("evals_in_phase", 0)
        c.best_eval_in_phase = d.get("best_eval_in_phase", 0.0)
        c.evals_since_improve = d.get("evals_since_improve", 0)
        c.interventions_used = d.get("interventions_used", 0)
        c.stalled = d.get("stalled", False)
        return c
