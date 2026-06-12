"""Training run logger — CSV episode log, checkpoints, and resumable run state."""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn


class RunLogger:
    """Creates (or resumes) a runs/<agent>_<timestamp>/ directory.

    Directory layout:
        runs/dqn_20260604_143022/
            config.json          — config snapshot at run start
            log.csv              — one row per episode (append-safe on resume)
            state.json           — resume state: epsilon, phase, steps, episode
            best_model.pt        — weights-only, at the all-time best score
            checkpoint.pt        — full training state (model+target+optimizer)
            phaseN_complete.pt   — weights at each curriculum phase completion
            phase_best.pt        — weights at the current phase's best rolling avg
    """

    _CSV_FIELDS = [
        "episode", "score", "best", "cleared", "steps",
        "epsilon", "buffer", "loss", "phase", "avg20", "timestamp",
    ]

    def __init__(self, agent: str, cfg: dict, base_dir: str = "runs",
                 resume_dir: Optional[str] = None):
        if resume_dir:
            self.run_dir = Path(resume_dir)
            if not self.run_dir.exists():
                raise FileNotFoundError(f"Resume dir not found: {resume_dir}")
            self.resumed = True
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.run_dir = Path(base_dir) / f"{agent}_{ts}"
            self.run_dir.mkdir(parents=True, exist_ok=True)
            self.resumed = False

        # Config snapshot (kept fresh — overrides may differ on resume).
        (self.run_dir / "config.json").write_text(
            json.dumps(cfg, indent=2, default=str), encoding="utf-8"
        )

        # CSV — append on resume so history is continuous.
        self._csv_path = self.run_dir / "log.csv"
        write_header = not (self.resumed and self._csv_path.exists())
        mode = "a" if self.resumed else "w"
        self._csv_file = open(self._csv_path, mode, newline="", encoding="utf-8")
        self._writer = csv.DictWriter(
            self._csv_file, fieldnames=self._CSV_FIELDS, extrasaction="ignore"
        )
        if write_header:
            self._writer.writeheader()
        self._csv_file.flush()

        label = "Resumed" if self.resumed else "Run dir"
        print(f"{label}: {self.run_dir}")

    # ── Episode logging ───────────────────────────────────────────────

    def log(self, stats: dict):
        row = {**stats, "timestamp": datetime.now().isoformat(timespec="seconds")}
        self._writer.writerow(row)
        self._csv_file.flush()

    # ── Run state (resume support) ────────────────────────────────────

    def save_state(self, state: dict):
        """Atomic-ish write of resume state — called every episode."""
        tmp = self.run_dir / "state.json.tmp"
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(self.run_dir / "state.json")

    def load_state(self) -> Optional[dict]:
        p = self.run_dir / "state.json"
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    # ── Checkpoints ───────────────────────────────────────────────────

    def save_model(self, network: nn.Module, label: str = "checkpoint"):
        """Weights-only save (for --demo and --load compatibility)."""
        torch.save(network.state_dict(), self.run_dir / f"{label}.pt")

    def save_full_checkpoint(self, trainer, label: str = "checkpoint"):
        """Full training state: model + target + optimizer + counters."""
        torch.save({
            "format": "full_v1",
            "model": trainer.online.state_dict(),
            "target": trainer.target.state_dict(),
            "optimizer": trainer.optimizer.state_dict(),
            "epsilon": trainer.epsilon,
            "total_steps": trainer.total_steps,
            "best_score": trainer.best_score,
        }, self.run_dir / f"{label}.pt")

    def close(self):
        self._csv_file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ──────────────────────────────────────────────────────────────────────
# Loading helpers
# ──────────────────────────────────────────────────────────────────────

def load_model(network: nn.Module, path: str) -> nn.Module:
    """Load weights into a network. Accepts weights-only or full checkpoints."""
    state = torch.load(path, map_location="cpu", weights_only=True)
    if isinstance(state, dict) and state.get("format") == "full_v1":
        network.load_state_dict(state["model"])
    else:
        network.load_state_dict(state)
    return network


def load_full_checkpoint(trainer, path: str) -> bool:
    """Restore full training state into a trainer. Returns True if it was a
    full checkpoint, False if weights-only (still loads the weights)."""
    state = torch.load(path, map_location="cpu", weights_only=True)
    if isinstance(state, dict) and state.get("format") == "full_v1":
        trainer.online.load_state_dict(state["model"])
        trainer.target.load_state_dict(state["target"])
        trainer.optimizer.load_state_dict(state["optimizer"])
        trainer.epsilon = state["epsilon"]
        trainer.total_steps = state["total_steps"]
        trainer.best_score = state["best_score"]
        return True
    trainer.online.load_state_dict(state)
    trainer.target.load_state_dict(state)
    return False


def find_latest_run(base_dir: str = "runs", agent: str = "dqn") -> Optional[Path]:
    """Most recently modified runs/<agent>_*/ that has a state.json."""
    base = Path(base_dir)
    if not base.exists():
        return None
    candidates = [
        d for d in base.glob(f"{agent}_*")
        if d.is_dir() and (d / "state.json").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda d: (d / "state.json").stat().st_mtime)
