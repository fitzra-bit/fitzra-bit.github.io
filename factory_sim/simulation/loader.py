"""Load a ProductionLine from a YAML scenario file."""

from pathlib import Path
from typing import Any, Dict

import yaml

from simulation.upgrade import UpgradeOption
from simulation.step import ProcessStep
from simulation.line import ProductionLine


def _build_line_from_data(data: dict) -> ProductionLine:
    """Build a ProductionLine from an already-parsed YAML dict."""
    sc = data.get("scenario", data)
    raw_steps = sc.get("steps") or data.get("steps", [])

    steps = []
    for i, raw_step in enumerate(raw_steps):
        upgrades = []
        for j, raw_u in enumerate(raw_step.get("upgrades", [])):
            uid = raw_u.get("id") or (
                raw_u["name"].lower().replace(" ", "_")[:18] + f"_{i}_{j}"
            )
            upgrades.append(
                UpgradeOption(
                    id=uid,
                    name=raw_u["name"],
                    description=raw_u.get("description", ""),
                    capex=float(raw_u.get("capex", 0)),
                    opex_delta=float(raw_u.get("opex_delta", 0)),
                    capacity_delta=float(raw_u.get("capacity_delta", 0)),
                    yield_delta=float(raw_u.get("yield_delta", 0)),
                    max_applications=int(raw_u.get("max_applications", 1)),
                    prerequisites=raw_u.get("prerequisites", []),
                )
            )
        step_id = raw_step.get("id") or (
            raw_step["name"].lower().replace(" ", "_")[:15] + f"_{i}"
        )
        steps.append(
            ProcessStep(
                id=step_id,
                name=raw_step["name"],
                base_capacity=float(raw_step["capacity"]),
                base_yield_rate=float(raw_step["yield_rate"]),
                base_opex=float(raw_step.get("base_opex", 0)),
                upgrades=upgrades,
            )
        )

    return ProductionLine(
        name=sc.get("name", "Unnamed"),
        description=sc.get("description", ""),
        steps=steps,
        unit=sc.get("unit", "unit"),
        unit_value=float(sc.get("unit_value", 1.0)),
        hours_per_period=float(sc.get("hours_per_period", 176.0)),
        budget=float(sc.get("budget", 100_000.0)),
        periods=int(sc.get("periods", 24)),
    )


def load_scenario_from_yaml(yaml_text: str) -> ProductionLine:
    """Build a ProductionLine from a YAML string (e.g. from the browser editor)."""
    data = yaml.safe_load(yaml_text)
    return _build_line_from_data(data)


def load_scenario(path: str | Path) -> ProductionLine:
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return _build_line_from_data(data)
