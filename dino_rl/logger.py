"""Training run logger — CSV episode log + model checkpoints in a timestamped directory."""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn


class RunLogger:
    """Creates a runs/<agent>_<timestamp>/ directory and writes to it throughout training.

    Directory layout:
        runs/dqn_20260604_143022/
            config.json      — config snapshot at run start
            log.csv          — one row per episode
            best_model.pt    — weights at the all-time best score
            checkpoint.pt    — latest periodic checkpoint
    """

    _CSV_FIELDS = [
        "episode", "score", "best", "cleared", "steps",
        "epsilon", "buffer", "loss", "timestamp",
    ]

    def __init__(self, agent: str, cfg: dict, base_dir: str = "runs"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = Path(base_dir) / f"{agent}_{ts}"
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Config snapshot.
        (self.run_dir / "config.json").write_text(
            json.dumps(cfg, indent=2, default=str), encoding="utf-8"
        )

        # CSV — open and keep the writer alive for the run.
        self._csv_path = self.run_dir / "log.csv"
        self._csv_file = open(self._csv_path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._csv_file, fieldnames=self._CSV_FIELDS, extrasaction="ignore")
        self._writer.writeheader()
        self._csv_file.flush()

        print(f"Run dir: {self.run_dir}")

    # ------------------------------------------------------------------

    def log(self, stats: dict):
        row = {**stats, "timestamp": datetime.now().isoformat(timespec="seconds")}
        self._writer.writerow(row)
        self._csv_file.flush()

    def save_model(self, network: nn.Module, label: str = "checkpoint"):
        path = self.run_dir / f"{label}.pt"
        torch.save(network.state_dict(), path)

    def close(self):
        self._csv_file.close()

    # Support use as a context manager.
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def load_model(network: nn.Module, path: str) -> nn.Module:
    """Load saved weights into a network (in-place). Returns the network."""
    state = torch.load(path, map_location="cpu", weights_only=True)
    network.load_state_dict(state)
    return network
