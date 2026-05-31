"""Load a ProductionLine from a YAML scenario file."""

from pathlib import Path
from typing import Any, Dict

import yaml

from simulation.upgrade import UpgradeOption
from simulation.step import ProcessStep
from simulation.line import ProductionLine


def load_scenario(path: str | Path) -> ProductionLine:
    with open(path, "r") as f:
        data = yaml.safe_load(f)

    sc = data.get("scenario", data)
    # steps may live directly in sc or at the top-level alongside "scenario:"
    raw_steps = sc.get("steps") or data.get("steps", [])

    steps = []
    for raw_step in raw_steps:
        upgrades = []
        for raw_u in raw_step.get("upgrades", []):
            upgrades.append(
                UpgradeOption(
                    id=raw_u["id"],
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
        steps.append(
            ProcessStep(
                id=raw_step["id"],
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
