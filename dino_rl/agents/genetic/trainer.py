"""Runs the genetic training loop: each agent plays one episode, then evolve."""

import time
from typing import Callable, Optional

import numpy as np

from agents.genetic.population import GeneticPopulation
from config import GENETIC_CONFIG, GAME_CONFIG
from game.chrome_driver import DinoDriver


def run_episode(
    driver: DinoDriver,
    predict_fn: Callable[[np.ndarray], int],
    max_steps: int = GENETIC_CONFIG["max_steps_per_episode"],
    poll: float = GAME_CONFIG["poll_interval"],
) -> float:
    """Play one episode; return fitness (= distance score)."""
    for step in range(max_steps):
        state = driver.get_state()
        if state is None:
            break
        if state.crashed:
            return state.score

        action = predict_fn(state.to_array())
        driver.act(action)
        time.sleep(poll)

    state = driver.get_state()
    return state.score if state else 0.0


class GeneticTrainer:
    def __init__(
        self,
        generations: int = 100,
        on_generation_end: Optional[Callable[[dict], None]] = None,
        cfg: dict = GENETIC_CONFIG,
    ):
        self.generations = generations
        self.on_generation_end = on_generation_end
        self.cfg = cfg

    def train(self, driver: DinoDriver) -> GeneticPopulation:
        pop = GeneticPopulation(self.cfg)

        for gen in range(self.generations):
            for idx, agent in enumerate(pop.agents):
                driver.reset()
                time.sleep(0.2)

                score = run_episode(
                    driver,
                    agent.predict,
                    max_steps=self.cfg["max_steps_per_episode"],
                    poll=self.cfg["poll_interval"],
                )
                pop.fitnesses[idx] = score

            stats = pop.stats()
            stats["agent_scores"] = list(pop.fitnesses)

            if self.on_generation_end:
                self.on_generation_end(stats)

            pop.evolve()

        return pop
