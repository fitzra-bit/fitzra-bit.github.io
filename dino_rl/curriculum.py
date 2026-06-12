"""Declarative training curriculum — auto-advance, stall detection, auto-recovery.

The goal: a training run should need ZERO human intervention between phases.

Each Phase declares:
  * game_params        — URL query params for dino.html (birds on/off, speed caps).
                         Phase transitions are page navigations, not file edits.
  * reward_overrides   — merged into the trainer cfg when the phase begins.
  * epsilon_start      — exploration reset on phase entry (fresh skills need
                         fresh exploration; converged skills need less).
  * complete_avg       — rolling-average score that completes the phase.
  * stall_window       — episodes without a new best rolling-avg before the
                         curriculum intervenes automatically.

Automatic stall interventions (escalating, all logged):
  1. epsilon boost     — re-explore from current weights.
  2. revert + boost    — reload the phase-best checkpoint, then re-explore.
  3. STALLED flag      — keep training, surface the flag in dashboards/logs
                         so a human knows this phase needs a design change.

State is serialised to runs/<run>/state.json after every episode, so
`python main.py --auto` can resume mid-phase after a crash, reboot, or
Ctrl+C with nothing lost but the in-flight episode.
"""

from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlencode


@dataclass
class Phase:
    name: str
    description: str
    game_params: dict
    reward_overrides: dict
    epsilon_start: float
    complete_avg: float          # rolling-avg score to finish the phase
    complete_window: int = 20
    min_episodes: int = 50       # don't complete off a lucky early streak
    stall_window: int = 150


# ──────────────────────────────────────────────────────────────────────
# The plan. Phase 1A/1B learnings are baked into the base DQN_CONFIG
# (pure outcome + directional nudge); later phases layer on shaping that
# was poison early but is safe once the jump association exists.
# ──────────────────────────────────────────────────────────────────────

PHASES = [
    Phase(
        name="1-jump",
        description="Cacti only. Outcome rewards + directional jump nudge (1A+1B).",
        game_params={"birds": 0},
        reward_overrides={},          # base config IS phase 1
        epsilon_start=1.0,
        complete_avg=200.0,
    ),
    Phase(
        name="2-shaping",
        description="Cacti only. Tighter approach window + mild idle penalty.",
        game_params={"birds": 0},
        reward_overrides={
            "jump_approach_bonus": 10.0,
            "idle_action_penalty": 3.0,
            "idle_ttc_threshold": 0.60,
            "approach_ttc_far": 0.25,
            "approach_ttc_near": 0.05,
        },
        epsilon_start=0.20,
        complete_avg=500.0,
    ),
    Phase(
        name="3-converge",
        description="Cacti only. No new signals — run to convergence.",
        game_params={"birds": 0},
        reward_overrides={},
        epsilon_start=0.10,
        complete_avg=1000.0,
    ),
    Phase(
        name="4-birds",
        description="Full game. Birds spawn at speed ≥ 8.5 (original rule).",
        game_params={"birds": 1},
        reward_overrides={},
        epsilon_start=0.25,           # new obstacle type → re-explore
        complete_avg=2000.0,
        stall_window=250,             # birds are harder; be patient
    ),
]


class Curriculum:
    """Tracks phase progress; tells the trainer when to advance or intervene."""

    def __init__(self, phases: list[Phase] = None):
        self.phases = phases or PHASES
        self.phase_idx = 0
        self.episodes_in_phase = 0
        self.best_avg_in_phase = 0.0
        self.episodes_since_improve = 0
        self.interventions_used = 0
        self.stalled = False
        self._window: list[float] = []

    # ── Accessors ────────────────────────────────────────────────────

    @property
    def phase(self) -> Phase:
        return self.phases[self.phase_idx]

    @property
    def finished(self) -> bool:
        return self.phase_idx >= len(self.phases)

    def game_url(self, base_url: str) -> str:
        """Base game URL + this phase's query params."""
        params = self.phase.game_params
        if not params:
            return base_url
        sep = "&" if "?" in base_url else "?"
        return f"{base_url}{sep}{urlencode(params)}"

    def rolling_avg(self) -> float:
        if not self._window:
            return 0.0
        return sum(self._window) / len(self._window)

    # ── Episode hook ─────────────────────────────────────────────────

    def after_episode(self, score: float) -> dict:
        """Record an episode result. Returns an event dict:

        {"type": None}                    — keep training
        {"type": "advance", ...}          — phase complete, move to next
        {"type": "intervene", "level": n} — stall recovery action needed
        {"type": "stalled"}               — out of automatic options
        """
        ph = self.phase
        self.episodes_in_phase += 1
        self._window.append(score)
        if len(self._window) > ph.complete_window:
            self._window.pop(0)

        avg = self.rolling_avg()

        # Track phase-best rolling average for stall detection
        if avg > self.best_avg_in_phase * 1.02 or self.best_avg_in_phase == 0.0:
            if avg > self.best_avg_in_phase:
                self.best_avg_in_phase = avg
                self.episodes_since_improve = 0
        else:
            self.episodes_since_improve += 1

        # Completion check
        if (
            len(self._window) == ph.complete_window
            and self.episodes_in_phase >= ph.min_episodes
            and avg >= ph.complete_avg
        ):
            completed = ph.name
            self._advance()
            return {
                "type": "advance",
                "completed": completed,
                "avg": avg,
                "next": self.phase.name if not self.finished else None,
            }

        # Stall check
        if self.episodes_since_improve >= ph.stall_window and not self.stalled:
            self.episodes_since_improve = 0
            self.interventions_used += 1
            if self.interventions_used <= 2:
                return {"type": "intervene", "level": self.interventions_used, "avg": avg}
            self.stalled = True
            return {"type": "stalled", "avg": avg}

        return {"type": None}

    def _advance(self):
        self.phase_idx += 1
        self.episodes_in_phase = 0
        self.best_avg_in_phase = 0.0
        self.episodes_since_improve = 0
        self.interventions_used = 0
        self.stalled = False
        self._window = []

    # ── Persistence ──────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "phase_idx": self.phase_idx,
            "episodes_in_phase": self.episodes_in_phase,
            "best_avg_in_phase": self.best_avg_in_phase,
            "episodes_since_improve": self.episodes_since_improve,
            "interventions_used": self.interventions_used,
            "stalled": self.stalled,
            "window": list(self._window),
        }

    @classmethod
    def from_dict(cls, d: dict, phases: list[Phase] = None) -> "Curriculum":
        c = cls(phases)
        c.phase_idx = d.get("phase_idx", 0)
        c.episodes_in_phase = d.get("episodes_in_phase", 0)
        c.best_avg_in_phase = d.get("best_avg_in_phase", 0.0)
        c.episodes_since_improve = d.get("episodes_since_improve", 0)
        c.interventions_used = d.get("interventions_used", 0)
        c.stalled = d.get("stalled", False)
        c._window = list(d.get("window", []))
        return c
