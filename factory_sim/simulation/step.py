from dataclasses import dataclass, field
from typing import List, Set
import copy

from simulation.upgrade import UpgradeOption


@dataclass
class ProcessStep:
    """One station in a production line."""

    id: str
    name: str
    base_capacity: float     # units/hour at baseline
    base_yield_rate: float   # fraction passing quality check (0–1)
    base_opex: float         # recurring cost per period at baseline

    upgrades: List[UpgradeOption] = field(default_factory=list)

    # Runtime state — computed from applied upgrades
    _capacity: float = field(init=False)
    _yield_rate: float = field(init=False)
    _opex: float = field(init=False)

    def __post_init__(self):
        self._capacity = self.base_capacity
        self._yield_rate = self.base_yield_rate
        self._opex = self.base_opex

    # ------------------------------------------------------------------
    # Live state
    # ------------------------------------------------------------------

    @property
    def capacity(self) -> float:
        return self._capacity

    @property
    def yield_rate(self) -> float:
        return self._yield_rate

    @property
    def opex(self) -> float:
        return self._opex

    @property
    def applied_upgrade_ids(self) -> Set[str]:
        return {u.id for u in self.upgrades if u.times_applied > 0}

    # ------------------------------------------------------------------
    # Upgrade mechanics
    # ------------------------------------------------------------------

    def can_apply(self, upgrade: UpgradeOption, remaining_budget: float) -> bool:
        if not upgrade.available:
            return False
        if upgrade.capex > remaining_budget:
            return False
        for req in upgrade.prerequisites:
            if req not in self.applied_upgrade_ids:
                return False
        return True

    def apply_upgrade(self, upgrade_id: str) -> UpgradeOption:
        """Apply one instance of the given upgrade; returns the upgrade applied."""
        for u in self.upgrades:
            if u.id == upgrade_id and u.available:
                u.times_applied += 1
                self._capacity += u.capacity_delta
                self._yield_rate = min(1.0, self._yield_rate + u.yield_delta)
                self._opex += u.opex_delta
                return u
        raise ValueError(f"Upgrade '{upgrade_id}' not available on step '{self.id}'")

    def recompute(self):
        """Recompute live state from scratch (useful after cloning)."""
        self._capacity = self.base_capacity
        self._yield_rate = self.base_yield_rate
        self._opex = self.base_opex
        for u in self.upgrades:
            for _ in range(u.times_applied):
                self._capacity += u.capacity_delta
                self._yield_rate = min(1.0, self._yield_rate + u.yield_delta)
                self._opex += u.opex_delta

    def clone(self) -> "ProcessStep":
        s = ProcessStep(
            id=self.id,
            name=self.name,
            base_capacity=self.base_capacity,
            base_yield_rate=self.base_yield_rate,
            base_opex=self.base_opex,
            upgrades=[u.clone() for u in self.upgrades],
        )
        s.recompute()
        return s
