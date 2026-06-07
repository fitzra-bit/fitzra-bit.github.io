"""Runs the genetic training loop: each agent plays one episode, then evolve."""

import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional, Union

import numpy as np

from agents.genetic.population import GeneticPopulation
from config import GENETIC_CONFIG, GAME_CONFIG
from game.chrome_driver import DinoDriver


def run_episode(
    driver: DinoDriver,
    predict_fn: Callable[[np.ndarray], int],
    max_steps: int = GENETIC_CONFIG["max_steps_per_episode"],
    poll: float = GAME_CONFIG["poll_interval"],
    stop_event: Optional[threading.Event] = None,
) -> tuple[float, dict]:
    """Play one episode; return (raw_score, action_counts)."""
    action_counts = {0: 0, 1: 0, 2: 0}

    for step in range(max_steps):
        if stop_event and stop_event.is_set():
            return 0.0, action_counts
        state = driver.get_state()
        if state is None:
            break
        if state.crashed:
            return state.score, action_counts

        action = predict_fn(state.to_array())
        action_counts[action] += 1
        driver.act(action)
        time.sleep(poll)

    state = driver.get_state()
    return (state.score if state else 0.0), action_counts


def _apply_spam_penalty(raw: float, action_counts: dict, threshold: float, max_penalty: float) -> float:
    """Discount fitness when jump OR duck dominates (noop is exempt — waiting is healthy).

    At `threshold` rate for the worst offending action: no penalty.
    At 100%: fitness multiplied by (1 - max_penalty).
    """
    total = sum(action_counts.values()) or 1
    # Only penalise active actions; noop at high rate is fine (waiting for obstacles).
    worst_rate = max(action_counts.get(1, 0), action_counts.get(2, 0)) / total
    if worst_rate <= threshold:
        return raw
    t = (worst_rate - threshold) / (1.0 - threshold)
    return raw * (1.0 - max_penalty * t)


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

        # Mutation scale tracked as state so stagnation can reset it.
        self._mutation_scale: float = cfg.get("mutation_scale_start", cfg.get("mutation_scale", 0.10))
        self._mut_scale_end: float  = cfg.get("mutation_scale_end", 0.05)
        self._mut_scale_decay: float = cfg.get("mutation_scale_decay", 1.0)

        # Stagnation tracking.
        self._best_ever: float = 0.0
        self._gens_no_improve: int = 0
        self._stagnation_limit: int = cfg.get("stagnation_limit", 8)
        self._stagnation_inject_pct: float = cfg.get("stagnation_inject_pct", 0.20)

        # Spam penalty (jump or duck).
        self._jump_threshold: float = cfg.get("spam_rate_threshold", 0.50)
        self._jump_penalty_max: float = cfg.get("spam_penalty_max", 0.75)

    def train(self, drivers: Union[DinoDriver, List[DinoDriver]]) -> GeneticPopulation:
        if not isinstance(drivers, list):
            drivers = [drivers]

        pop = GeneticPopulation(self.cfg)

        if len(drivers) == 1:
            self._train_serial(pop, drivers[0])
        else:
            self._train_parallel(pop, drivers)

        return pop

    def _compute_fitness(self, raw: float, action_counts: dict) -> float:
        baseline = self.cfg.get("fitness_baseline", 0.0)
        f = max(0.0, raw - baseline)
        return _apply_spam_penalty(f, action_counts, self._jump_threshold, self._jump_penalty_max)

    def _train_serial(self, pop: GeneticPopulation, driver: DinoDriver):
        stop = threading.Event()
        try:
            for gen in range(self.generations):
                gen_action_counts = {0: 0, 1: 0, 2: 0}
                for idx, agent in enumerate(pop.agents):
                    driver.reset()
                    time.sleep(0.2)
                    raw, action_counts = run_episode(
                        driver,
                        agent.predict,
                        max_steps=self.cfg["max_steps_per_episode"],
                        poll=self.cfg["poll_interval"],
                        stop_event=stop,
                    )
                    pop.fitnesses[idx] = self._compute_fitness(raw, action_counts)
                    for k, v in action_counts.items():
                        gen_action_counts[k] += v
                self._end_generation(pop, gen_action_counts)
        except KeyboardInterrupt:
            stop.set()
            print("\nStopped after generation", pop.generation)

    def _train_parallel(self, pop: GeneticPopulation, drivers: List[DinoDriver]):
        driver_pool: queue.Queue[DinoDriver] = queue.Queue()
        for d in drivers:
            driver_pool.put(d)
        stop = threading.Event()

        def eval_agent(idx: int, agent) -> tuple[int, float, dict]:
            driver = driver_pool.get()
            try:
                if stop.is_set():
                    return idx, 0.0, {0: 0, 1: 0, 2: 0}
                driver.reset()
                time.sleep(0.2)
                raw, action_counts = run_episode(
                    driver,
                    agent.predict,
                    max_steps=self.cfg["max_steps_per_episode"],
                    poll=self.cfg["poll_interval"],
                    stop_event=stop,
                )
                return idx, self._compute_fitness(raw, action_counts), action_counts
            finally:
                driver_pool.put(driver)

        try:
            for gen in range(self.generations):
                gen_action_counts = {0: 0, 1: 0, 2: 0}
                with ThreadPoolExecutor(max_workers=len(drivers)) as executor:
                    futures = {
                        executor.submit(eval_agent, i, agent): i
                        for i, agent in enumerate(pop.agents)
                    }
                    try:
                        for future in as_completed(futures):
                            idx, fitness, action_counts = future.result()
                            pop.fitnesses[idx] = fitness
                            for k, v in action_counts.items():
                                gen_action_counts[k] += v
                    except KeyboardInterrupt:
                        stop.set()
                        executor.shutdown(wait=True, cancel_futures=True)
                        raise
                self._end_generation(pop, gen_action_counts)
        except KeyboardInterrupt:
            print("\nStopped after generation", pop.generation)

    def _decay_mutation_scale(self):
        """Step the mutation scale one tick toward its floor."""
        self._mutation_scale = (
            self._mut_scale_end
            + (self._mutation_scale - self._mut_scale_end) * self._mut_scale_decay
        )

    def _end_generation(self, pop: GeneticPopulation, action_counts: dict = None):
        # --- best_ever: update NOW before stats() so the dashboard is current ---
        current_best = max(pop.fitnesses) if pop.fitnesses else 0.0
        stagnated = False
        if current_best > self._best_ever:
            self._best_ever = current_best
            pop.best_ever = current_best
            self._gens_no_improve = 0
        else:
            self._gens_no_improve += 1
            if self._gens_no_improve >= self._stagnation_limit:
                stagnated = True
                self._gens_no_improve = 0
                # Reset mutation scale back to start to re-enable exploration.
                self._mutation_scale = self.cfg.get("mutation_scale_start",
                                                    self.cfg.get("mutation_scale", 0.10))
                # Inject fresh random agents to break population lock.
                pop.inject_random(self._stagnation_inject_pct)

        stats = pop.stats()
        stats["agent_scores"]   = list(pop.fitnesses)
        stats["mutation_scale"] = round(self._mutation_scale, 4)
        stats["stagnated"]      = stagnated
        if action_counts:
            total = sum(action_counts.values()) or 1
            worst_rate = max(action_counts.get(1, 0), action_counts.get(2, 0)) / total
            stats["action_pct"] = {
                k: round(100 * v / total, 1)
                for k, v in action_counts.items()
            }
            if worst_rate > self._jump_threshold:
                t = (worst_rate - self._jump_threshold) / (1.0 - self._jump_threshold)
                stats["jump_penalty_pct"] = round(self._jump_penalty_max * t * 100, 1)
            else:
                stats["jump_penalty_pct"] = 0.0
        if self.on_generation_end:
            self.on_generation_end(stats)

        self._decay_mutation_scale()
        pop.evolve(mutation_scale=self._mutation_scale)
