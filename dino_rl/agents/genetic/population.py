"""Genetic population: selection, crossover, mutation of NumpyNet weights."""

from typing import List, Tuple
import numpy as np

from agents.neural_net import NumpyNet
from config import GENETIC_CONFIG


class GeneticPopulation:
    def __init__(self, cfg: dict = GENETIC_CONFIG):
        self.cfg = cfg
        self.size = cfg["population_size"]
        self.elite_n = max(1, int(self.size * cfg["elite_fraction"]))
        self.mutation_rate = cfg["mutation_rate"]
        # Support both legacy single value and new start/end/decay schedule.
        self.mutation_scale = cfg.get("mutation_scale_start", cfg.get("mutation_scale", 0.10))
        self.layers = cfg["network_layers"]

        self.agents: List[NumpyNet] = [
            NumpyNet(self.layers) for _ in range(self.size)
        ]
        self.fitnesses: List[float] = [0.0] * self.size
        self.generation = 0
        self.best_ever: float = 0.0

    # ------------------------------------------------------------------
    # Evolution
    # ------------------------------------------------------------------

    def evolve(self, mutation_scale: float = None):
        ranked = sorted(
            range(self.size), key=lambda i: self.fitnesses[i], reverse=True
        )
        elites = [self.agents[i].clone() for i in ranked[: self.elite_n]]

        new_agents: List[NumpyNet] = list(elites)
        rng = np.random.default_rng()

        while len(new_agents) < self.size:
            p1, p2 = self._tournament_select(rng, ranked)
            child_weights = self._crossover(
                self.agents[p1].get_flat_weights(),
                self.agents[p2].get_flat_weights(),
                rng,
            )
            child_weights = self._mutate(child_weights, rng, mutation_scale)
            child = NumpyNet(self.layers)
            child.set_flat_weights(child_weights)
            new_agents.append(child)

        self.agents = new_agents[: self.size]
        self.fitnesses = [0.0] * self.size
        self.generation += 1

    def _tournament_select(
        self, rng: np.random.Generator, ranked: List[int], k: int = 5
    ) -> Tuple[int, int]:
        pool = ranked[: max(self.elite_n * 3, k + 1)]
        k = min(k, len(pool))
        candidates = rng.choice(pool, k, replace=False)
        candidates = sorted(candidates, key=lambda i: self.fitnesses[i], reverse=True)
        return candidates[0], candidates[1]

    def _crossover(
        self, w1: np.ndarray, w2: np.ndarray, rng: np.random.Generator
    ) -> np.ndarray:
        if self.cfg["crossover_type"] == "uniform":
            mask = rng.random(len(w1)) < 0.5
            child = np.where(mask, w1, w2)
        else:
            point = rng.integers(1, len(w1))
            child = np.concatenate([w1[:point], w2[point:]])
        return child.astype(np.float32)

    def _mutate(self, weights: np.ndarray, rng: np.random.Generator, scale: float = None) -> np.ndarray:
        mask = rng.random(len(weights)) < self.mutation_rate
        noise = rng.normal(0, scale or self.mutation_scale, len(weights)).astype(np.float32)
        weights[mask] += noise[mask]
        return weights

    def inject_random(self, fraction: float):
        """Replace the bottom `fraction` of agents with fresh random networks."""
        n = max(1, int(self.size * fraction))
        ranked = sorted(range(self.size), key=lambda i: self.fitnesses[i])
        for i in ranked[:n]:
            self.agents[i] = NumpyNet(self.layers)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        scored = [f for f in self.fitnesses if f > 0]
        return {
            "generation": self.generation,
            "best_this_gen": max(self.fitnesses) if scored else 0.0,
            "avg_this_gen": float(np.mean(scored)) if scored else 0.0,
            "best_ever": self.best_ever,
            "alive": len(scored),
        }
