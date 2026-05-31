"""Load a ProductionLine from the plant model YAML + scenario change overrides."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "factory_sim"))

import yaml

from simulation.upgrade import UpgradeOption
from simulation.step import ProcessStep
from simulation.line import ProductionLine

PLANT_FILE = Path(__file__).parent / "default_plant.yaml"


def load_plant_data() -> dict:
    with open(PLANT_FILE) as f:
        return yaml.safe_load(f)


def plant_to_line(plant_data: dict, changes: dict = None) -> ProductionLine:
    """
    Build a ProductionLine from the plant model, applying scenario-level overrides.

    changes dict (all optional):
        unit_value: float
        budget: float
        hours_per_period: float
        upgrade_cost_overrides: {upgrade_id: new_capex}
    """
    changes = changes or {}
    plant   = plant_data.get("plant", {})
    market  = plant_data.get("market_assumptions", {})
    catalog = {u["id"]: u for u in plant_data.get("upgrade_catalog", [])}

    # Resolve market values with scenario overrides
    unit_value        = changes.get("unit_value")        or market.get("unit_value", 1.0)
    budget            = changes.get("budget")            or market.get("budget_available", 100_000.0)
    hours_per_period  = changes.get("hours_per_period")  or market.get("hours_per_period", 176.0)
    periods           = market.get("periods", 24)
    cost_overrides    = changes.get("upgrade_cost_overrides", {})

    steps = []
    for raw_step in plant_data.get("steps", []):
        step_id = raw_step["id"]

        # Find all catalog upgrades that apply to this step
        step_upgrades = []
        for uid, u in catalog.items():
            targets = u.get("applies_to_steps", [])
            single  = u.get("applies_to")
            if single == step_id or step_id in targets:
                capex = float(cost_overrides.get(uid, u.get("capex", 0)))
                step_upgrades.append(
                    UpgradeOption(
                        id=uid,
                        name=u["name"],
                        description=u.get("description", ""),
                        capex=capex,
                        opex_delta=float(u.get("opex_delta", 0)),
                        capacity_delta=float(u.get("capacity_delta", 0)),
                        yield_delta=float(u.get("yield_delta", 0)),
                        max_applications=int(u.get("max_applications", 1)),
                    )
                )

        steps.append(
            ProcessStep(
                id=step_id,
                name=raw_step["name"],
                base_capacity=float(raw_step["capacity"]),
                base_yield_rate=float(raw_step["yield_rate"]),
                base_opex=float(raw_step.get("base_opex", 0)),
                upgrades=step_upgrades,
            )
        )

    return ProductionLine(
        name=plant.get("name", "Plant"),
        description=plant.get("description", ""),
        steps=steps,
        unit=market.get("unit", "unit"),
        unit_value=float(unit_value),
        hours_per_period=float(hours_per_period),
        budget=float(budget),
        periods=int(periods),
    )


def apply_in_flight(line: ProductionLine, in_flight: list) -> ProductionLine:
    """Return a clone of line with all in-flight investments applied."""
    result = line.reset()
    result.remaining_budget = line.budget  # in-flight doesn't consume scenario budget
    for inv in in_flight:
        step_id    = inv.get("step_id") or inv.get("step")
        upgrade_id = inv.get("upgrade_id") or inv.get("upgrade")
        count      = int(inv.get("count", 1))
        step_idx   = next(
            (i for i, s in enumerate(result.steps) if s.id == step_id), None
        )
        if step_idx is None:
            continue
        for _ in range(count):
            try:
                result.apply_upgrade(step_idx, upgrade_id)
            except Exception:
                pass
    result.capex_log = []  # in-flight doesn't show in investment log
    return result
