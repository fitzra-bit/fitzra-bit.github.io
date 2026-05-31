"""ProductionLine: a chain of ProcessSteps with global economics."""

from dataclasses import dataclass, field
from typing import List, Tuple
import copy

from simulation.step import ProcessStep
from simulation.upgrade import UpgradeOption
from simulation.metrics import LineMetrics, compute_metrics


@dataclass
class ProductionLine:
    name: str
    description: str
    steps: List[ProcessStep]
    unit: str = "unit"
    unit_value: float = 1.0       # revenue per unit
    hours_per_period: float = 176.0  # working hours per period (default: 1 month)
    budget: float = 100_000.0     # total investment budget
    periods: int = 24             # planning horizon for ROI

    remaining_budget: float = field(init=False)
    capex_log: List[Tuple[str, str, float]] = field(default_factory=list)

    def __post_init__(self):
        self.remaining_budget = self.budget

    # ------------------------------------------------------------------
    # Core properties
    # ------------------------------------------------------------------

    @property
    def bottleneck_step(self) -> ProcessStep:
        return min(self.steps, key=lambda s: s.capacity)

    @property
    def effective_yield(self) -> float:
        y = 1.0
        for s in self.steps:
            y *= s.yield_rate
        return y

    @property
    def system_throughput(self) -> float:
        return self.bottleneck_step.capacity

    @property
    def net_output_per_hour(self) -> float:
        return self.system_throughput * self.effective_yield

    @property
    def net_output_per_period(self) -> float:
        return self.net_output_per_hour * self.hours_per_period

    @property
    def revenue_per_period(self) -> float:
        return self.net_output_per_period * self.unit_value

    @property
    def total_opex_per_period(self) -> float:
        return sum(s.opex for s in self.steps)

    @property
    def gross_profit_per_period(self) -> float:
        return self.revenue_per_period - self.total_opex_per_period

    @property
    def total_capex_spent(self) -> float:
        return self.budget - self.remaining_budget

    # ------------------------------------------------------------------
    # Upgrade mechanics
    # ------------------------------------------------------------------

    def all_valid_actions(self) -> List[Tuple[int, UpgradeOption]]:
        """Returns (step_index, upgrade) pairs that can be applied right now."""
        actions = []
        for i, step in enumerate(self.steps):
            for u in step.upgrades:
                if step.can_apply(u, self.remaining_budget):
                    actions.append((i, u))
        return actions

    def apply_upgrade(self, step_index: int, upgrade_id: str) -> float:
        """Apply upgrade; return capex spent. Raises if invalid."""
        step = self.steps[step_index]
        upgrade = next((u for u in step.upgrades if u.id == upgrade_id), None)
        if upgrade is None:
            raise ValueError(f"Upgrade {upgrade_id} not found on step {step.id}")
        if not step.can_apply(upgrade, self.remaining_budget):
            raise ValueError(f"Cannot apply {upgrade_id}: budget or max_applications exceeded")
        step.apply_upgrade(upgrade_id)
        self.remaining_budget -= upgrade.capex
        self.capex_log.append((step.name, upgrade.name, upgrade.capex))
        return upgrade.capex

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def metrics(self, baseline_profit: float = 0.0) -> LineMetrics:
        return compute_metrics(self, baseline_profit)

    # ------------------------------------------------------------------
    # Clone
    # ------------------------------------------------------------------

    def clone(self) -> "ProductionLine":
        new = ProductionLine(
            name=self.name,
            description=self.description,
            steps=[s.clone() for s in self.steps],
            unit=self.unit,
            unit_value=self.unit_value,
            hours_per_period=self.hours_per_period,
            budget=self.budget,
            periods=self.periods,
        )
        new.remaining_budget = self.remaining_budget
        new.capex_log = list(self.capex_log)
        return new

    def reset(self) -> "ProductionLine":
        """Return a fresh copy at baseline with all upgrades reset to times_applied=0."""
        fresh = self.clone()
        fresh.remaining_budget = self.budget
        fresh.capex_log = []
        for step in fresh.steps:
            for u in step.upgrades:
                u.times_applied = 0
            step.recompute()
        return fresh
