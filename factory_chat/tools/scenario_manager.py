"""Persist, load, and compare named scenarios."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCENARIOS_DIR = Path(__file__).parent.parent / "saved_scenarios"
SCENARIOS_DIR.mkdir(exist_ok=True)


# ------------------------------------------------------------------
# Serialization helpers
# ------------------------------------------------------------------

def _scenario_path(sid: str) -> Path:
    return SCENARIOS_DIR / f"{sid}.json"


def save_scenario(
    name: str,
    rationale: str,
    changes: dict,
    in_flight: list,
    pre_committed: list,
    optimization: Optional[dict] = None,
    tags: list = None,
    scenario_id: Optional[str] = None,
) -> dict:
    sid = scenario_id or _slug(name)
    # Avoid collisions
    base = sid
    counter = 1
    while _scenario_path(sid).exists() and scenario_id is None:
        sid = f"{base}_{counter}"
        counter += 1

    record = {
        "id": sid,
        "name": name,
        "rationale": rationale,
        "tags": tags or [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "changes": changes or {},
        "in_flight": in_flight or [],
        "pre_committed": pre_committed or [],
        "optimization": optimization,
    }
    _scenario_path(sid).write_text(json.dumps(record, indent=2))
    return record


def load_scenario(scenario_id: str) -> Optional[dict]:
    p = _scenario_path(scenario_id)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def list_scenarios() -> list:
    records = []
    for p in sorted(SCENARIOS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            records.append(json.loads(p.read_text()))
        except Exception:
            pass
    return records


def delete_scenario(scenario_id: str) -> bool:
    p = _scenario_path(scenario_id)
    if p.exists():
        p.unlink()
        return True
    return False


def update_optimization(scenario_id: str, optimization: dict) -> bool:
    record = load_scenario(scenario_id)
    if record is None:
        return False
    record["optimization"] = optimization
    _scenario_path(scenario_id).write_text(json.dumps(record, indent=2))
    return True


# ------------------------------------------------------------------
# Comparison helper
# ------------------------------------------------------------------

def compare_scenarios(ids: list) -> list:
    """Return list of scenario dicts for the given IDs (in order)."""
    results = []
    for sid in ids:
        rec = load_scenario(sid)
        if rec:
            results.append(rec)
    return results


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------

def _slug(name: str) -> str:
    import re
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")[:40]
    return s or uuid.uuid4().hex[:8]
