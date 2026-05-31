from dataclasses import dataclass, field
from typing import List


@dataclass
class UpgradeOption:
    """One purchasable upgrade that can be applied to a process step."""

    id: str
    name: str
    description: str = ""
    capex: float = 0.0           # one-time capital cost
    opex_delta: float = 0.0      # recurring cost change per period (+ = more expensive)
    capacity_delta: float = 0.0  # additive units/hour gain
    yield_delta: float = 0.0     # additive yield rate gain (e.g. 0.02 = +2 pp)
    max_applications: int = 1    # how many times this upgrade can be stacked
    prerequisites: List[str] = field(default_factory=list)  # upgrade ids required first

    # Runtime state (not in YAML — tracked during simulation)
    times_applied: int = field(default=0, compare=False, repr=False)

    @property
    def available(self) -> bool:
        return self.times_applied < self.max_applications

    def clone(self) -> "UpgradeOption":
        return UpgradeOption(
            id=self.id,
            name=self.name,
            description=self.description,
            capex=self.capex,
            opex_delta=self.opex_delta,
            capacity_delta=self.capacity_delta,
            yield_delta=self.yield_delta,
            max_applications=self.max_applications,
            prerequisites=list(self.prerequisites),
            times_applied=self.times_applied,
        )
