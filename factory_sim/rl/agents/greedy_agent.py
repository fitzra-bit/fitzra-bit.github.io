"""Greedy ROI agent: always picks the upgrade with highest marginal ROI.

ROI score = (delta_gross_profit_per_period × periods - capex) / capex

This mimics how most operations managers reason. It can get stuck
optimizing the wrong bottleneck or miss synergistic upgrade pairs.
"""

from typing import Optional
from rl.environment import FactoryEnv


class GreedyROIAgent:
    name = "Greedy ROI"

    def choose_action(self, env: FactoryEnv) -> int:
        stop_idx = next(
            i for i, a in enumerate(env._action_map) if a is None
        )
        best_idx = stop_idx
        best_score = -float("inf")

        for idx in env.valid_actions():
            action = env._action_map[idx]
            if action is None:
                continue
            step_idx, upgrade_id = action
            step = env.line.steps[step_idx]
            upgrade = next(u for u in step.upgrades if u.id == upgrade_id)

            profit_before = env.line.gross_profit_per_period
            # Simulate the upgrade on a clone to measure marginal impact
            clone = env.line.clone()
            clone.apply_upgrade(step_idx, upgrade_id)
            profit_after = clone.gross_profit_per_period

            delta_profit = profit_after - profit_before
            capex = upgrade.capex

            if capex <= 0:
                score = delta_profit * env.line.periods
            else:
                score = (delta_profit * env.line.periods - capex) / capex

            if score > best_score:
                best_score = score
                best_idx = idx

        return best_idx
