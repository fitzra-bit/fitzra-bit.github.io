"""Baseline agent: picks a random valid upgrade each step."""

import random
from rl.environment import FactoryEnv


class RandomAgent:
    name = "Random"

    def choose_action(self, env: FactoryEnv) -> int:
        valid = env.valid_actions()
        return random.choice(valid)
