"""Gym-style environment wrapping a ProductionLine.

State  : normalized vector encoding each step's capacity, yield, opex,
         and applied-upgrade counts, plus remaining budget fraction.
Actions: discrete — one per (step, upgrade) pair, plus a "stop" action.
Reward : change in gross profit per period minus capex amortized over
         the planning horizon. Shaped to discourage trivial non-actions.
Done   : no valid upgrades remain, budget exhausted, or agent stops.
"""

from typing import List, Optional, Tuple
import numpy as np

from simulation.line import ProductionLine
from simulation.upgrade import UpgradeOption


class FactoryEnv:
    def __init__(self, line: ProductionLine):
        self._template = line          # never mutated; used as reset source
        self.line: ProductionLine = line.reset()
        self.baseline_profit = self.line.gross_profit_per_period

        # Build a stable action index: [(step_idx, upgrade_id), ...]
        # Order is fixed so action IDs are consistent across episodes.
        self._action_map: List[Optional[Tuple[int, str]]] = []
        for i, step in enumerate(line.steps):
            for u in step.upgrades:
                self._action_map.append((i, u.id))
        self._action_map.append(None)  # "stop" / do-nothing action

        self.n_actions = len(self._action_map)
        self.state_size = self._compute_state_size()
        self._done = False
        self._steps_taken = 0

    def _compute_state_size(self) -> int:
        # Per step: [capacity_frac, yield_rate, opex_frac, upgrade_count_i...]
        per_step = 3 + max((len(s.upgrades) for s in self._template.steps), default=0)
        return per_step * len(self._template.steps) + 1  # +1 for budget_frac

    # ------------------------------------------------------------------
    # Gym interface
    # ------------------------------------------------------------------

    def reset(self) -> np.ndarray:
        self.line = self._template.reset()
        self._done = False
        self._steps_taken = 0
        return self._observe()

    def step(self, action_idx: int) -> Tuple[np.ndarray, float, bool, dict]:
        if self._done:
            raise RuntimeError("Environment is done. Call reset().")

        action = self._action_map[action_idx]
        reward = 0.0
        info: dict = {}

        if action is None:
            # Agent chose to stop
            self._done = True
            info["reason"] = "agent_stop"
        else:
            step_idx, upgrade_id = action
            step = self.line.steps[step_idx]
            upgrade = next((u for u in step.upgrades if u.id == upgrade_id), None)

            if upgrade is None or not step.can_apply(upgrade, self.line.remaining_budget):
                # Invalid action: small penalty
                reward = -0.01
                info["reason"] = "invalid_action"
            else:
                profit_before = self.line.gross_profit_per_period
                capex = self.line.apply_upgrade(step_idx, upgrade_id)
                profit_after = self.line.gross_profit_per_period

                delta_annual = (profit_after - profit_before) * self.line.periods
                reward = (delta_annual - capex) / max(self.line.budget, 1.0)
                info["upgrade"] = upgrade_id
                info["step"] = step.name
                info["capex"] = capex
                info["profit_delta_per_period"] = profit_after - profit_before

        self._steps_taken += 1
        if not self.valid_actions():
            self._done = True
            info["reason"] = info.get("reason", "no_valid_actions")

        return self._observe(), reward, self._done, info

    def valid_actions(self) -> List[int]:
        """Return list of currently valid action indices."""
        valid = []
        for idx, action in enumerate(self._action_map):
            if action is None:
                valid.append(idx)  # stop is always valid
                continue
            step_idx, upgrade_id = action
            step = self.line.steps[step_idx]
            upgrade = next((u for u in step.upgrades if u.id == upgrade_id), None)
            if upgrade and step.can_apply(upgrade, self.line.remaining_budget):
                valid.append(idx)
        return valid

    def action_mask(self) -> np.ndarray:
        mask = np.zeros(self.n_actions, dtype=bool)
        for idx in self.valid_actions():
            mask[idx] = True
        return mask

    # ------------------------------------------------------------------
    # State encoding
    # ------------------------------------------------------------------

    def _observe(self) -> np.ndarray:
        template_steps = self._template.steps
        max_upgrades = max((len(s.upgrades) for s in template_steps), default=0)

        # Normalization references from template (baseline maximums)
        max_cap = max(s.base_capacity for s in template_steps) * 4  # headroom
        max_opex = max(s.base_opex for s in template_steps) * 4

        parts = []
        for i, step in enumerate(self.line.steps):
            parts.append(step.capacity / max_cap)
            parts.append(step.yield_rate)
            parts.append(step.opex / max(max_opex, 1.0))
            for u in step.upgrades:
                parts.append(u.times_applied / max(u.max_applications, 1))
            # Pad to max_upgrades
            for _ in range(max_upgrades - len(step.upgrades)):
                parts.append(0.0)

        parts.append(self.line.remaining_budget / max(self.line.budget, 1.0))
        return np.array(parts, dtype=np.float32)
