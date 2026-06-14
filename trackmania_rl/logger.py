"""Run logging: CSV, checkpoints, state.json for resume."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Optional

import torch


class RunLogger:
    def __init__(self, run_dir: str, cfg: dict):
        self.dir = Path(run_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._csv_path   = self.dir / "log.csv"
        self._state_path = self.dir / "state.json"
        self._csv_writer: Optional[csv.DictWriter] = None
        self._csv_file   = None
        self._headers_written = False

        (self.dir / "config.json").write_text(json.dumps(cfg, indent=2))

    def __enter__(self):
        self._csv_file = open(self._csv_path, "a", newline="")
        return self

    def __exit__(self, *_):
        if self._csv_file:
            self._csv_file.close()

    def log(self, stats: dict):
        if self._csv_file is None:
            return
        if not self._headers_written:
            self._csv_writer = csv.DictWriter(
                self._csv_file, fieldnames=list(stats.keys()), extrasaction="ignore"
            )
            if self._csv_path.stat().st_size == 0:
                self._csv_writer.writeheader()
            self._headers_written = True
        self._csv_writer.writerow(stats)
        self._csv_file.flush()

    def save_state(self, state: dict):
        tmp = self.dir / "state.json.tmp"
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(self._state_path)

    def load_state(self) -> Optional[dict]:
        if self._state_path.exists():
            return json.loads(self._state_path.read_text())
        return None

    def save_best(self, actor, critic=None):
        torch.save(actor.state_dict(), self.dir / "best_actor.pt")
        if critic:
            torch.save(critic.state_dict(), self.dir / "best_critic.pt")

    def save_phase_checkpoint(self, actor, critic, phase_name: str):
        torch.save(actor.state_dict(),  self.dir / f"phase_{phase_name}_actor.pt")
        torch.save(critic.state_dict(), self.dir / f"phase_{phase_name}_critic.pt")

    def save_checkpoint(self, actor, critic, opt_actor, opt_critic, log_alpha, opt_alpha, episode: int):
        torch.save({
            "actor":      actor.state_dict(),
            "critic":     critic.state_dict(),
            "opt_actor":  opt_actor.state_dict(),
            "opt_critic": opt_critic.state_dict(),
            "log_alpha":  log_alpha,
            "opt_alpha":  opt_alpha.state_dict(),
            "episode":    episode,
        }, self.dir / "checkpoint.pt")


def find_latest_run(base: str = "runs") -> Optional[Path]:
    p = Path(base)
    if not p.exists():
        return None
    candidates = [d for d in p.glob("sac_*") if (d / "state.json").exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda d: (d / "state.json").stat().st_mtime)
