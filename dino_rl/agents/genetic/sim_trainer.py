"""Genetic algorithm on the sim — evolution at 35k steps/sec.

The browser-based GA evaluated one agent per live episode (~30s each, load-
sensitive). On the sim a full 50-agent generation takes seconds, which turns
evolution from a slow demo into a serious optimizer.

Applies the same measurement discipline as the overhauled DQN, plus one
GA-specific fix:

* COMMON RANDOM NUMBERS: within a generation every genome is evaluated on
  the SAME episode seeds. Without this, selection compares "agent A on an
  easy obstacle draw" against "agent B on a hard one" — fitness noise that
  the old browser GA had no answer to (it was a big part of the score
  regressions across generations). Seeds rotate each generation so the
  population can't overfit one sequence.

* CHAMPION EVAL ON FIXED SEEDS (10000+i — identical to the DQN's eval
  protocol), so `eval_avg` is directly comparable across the two learners:
  same sim, same exam.

* SHARED CURRICULUM: the same env-shaped phases (curriculum.py) gate on
  champion eval. Rewards aren't a concept here — fitness is just score —
  so the env-knob curriculum is the only kind that even applies.

Resume: population weights + RNG-free state saved every generation;
`python main.py --agent genetic --auto` continues mid-phase.
"""

import json
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from agents.genetic.population import GeneticPopulation
from agents.genetic.trainer import _apply_spam_penalty
from agents.neural_net import NumpyNet
from config import GENETIC_CONFIG
from game.dino_env import DinoEnv


# Fitness episodes start with a short frame cap so early generations are
# fast, and the cap DOUBLES whenever the generation champion times out —
# i.e. the measuring stick grows exactly when the population outgrows it.
# (A fixed cap silently saturates fitness: once several genomes survive
# the whole window, selection can't tell them apart and evolution random-
# walks. We hit exactly this — best fitness pinned at the cap score of
# ~1,727 for 60+ generations while real skill differences lived beyond it.)
FITNESS_FRAME_CAP_START = 7_200    # 2 game-minutes
EVAL_FRAME_CAP          = 36_000   # 10 game-minutes (same as DQN)


def run_sim_episode(env: DinoEnv, net: NumpyNet, seed: int) -> tuple[float, dict, bool]:
    """One episode; returns (score, action_counts, timed_out)."""
    obs = env.reset(seed=seed)
    counts = {0: 0, 1: 0, 2: 0}
    done = False
    while not done:
        a = net.predict(obs)
        counts[a] += 1
        obs, _, done, info = env.step(a)
    return info["score"], counts, info["timeout"]


class SimGeneticTrainer:
    def __init__(
        self,
        generations: int = 1000,
        on_generation_end: Optional[Callable[[dict], None]] = None,
        cfg: dict = GENETIC_CONFIG,
        curriculum=None,
        run_dir: Optional[str] = None,
        episodes_per_agent: int = 3,
        eval_every: int = 5,            # generations between champion evals
        eval_episodes: int = 5,
        start_generation: int = 0,
    ):
        self.generations = generations
        self.on_generation_end = on_generation_end
        self.cfg = cfg
        self.curriculum = curriculum
        self.episodes_per_agent = episodes_per_agent
        self.eval_every = eval_every
        self.eval_episodes = eval_episodes
        self.start_generation = start_generation

        self.run_dir = Path(run_dir) if run_dir else None
        if self.run_dir:
            self.run_dir.mkdir(parents=True, exist_ok=True)

        self.pop = GeneticPopulation(cfg)
        self.best_eval = 0.0
        self.last_eval = 0.0
        self._fitness_cap = FITNESS_FRAME_CAP_START
        self._rng = np.random.default_rng()

        # Evolution control state (mirrors browser GeneticTrainer)
        self._mutation_scale = cfg.get("mutation_scale_start", 0.30)
        self._mut_scale_end = cfg.get("mutation_scale_end", 0.05)
        self._mut_scale_decay = cfg.get("mutation_scale_decay", 0.92)
        self._best_fitness_ever = 0.0
        self._gens_no_improve = 0

    # ── Environments (curriculum-aware, parity with DQN trainer) ─────

    def _env_params(self) -> dict:
        if self.curriculum is not None:
            return self.curriculum.env_params()
        return {"birds": True, "max_speed": 13.0}

    def _make_env(self, frame_cap: int) -> DinoEnv:
        return DinoEnv(action_repeat=2, max_frames=frame_cap, **self._env_params())

    # ── Fitness: common random numbers across the population ─────────

    def _evaluate_generation(self, gen_seeds: list[int]) -> dict:
        env = self._make_env(self._fitness_cap)
        gen_counts = {0: 0, 1: 0, 2: 0}
        timeouts = [0] * len(self.pop.agents)
        for idx, agent in enumerate(self.pop.agents):
            scores = []
            counts = {0: 0, 1: 0, 2: 0}
            for seed in gen_seeds:        # SAME seeds for every agent
                s, c, timed_out = run_sim_episode(env, agent, seed)
                scores.append(s)
                timeouts[idx] += int(timed_out)
                for k, v in c.items():
                    counts[k] += v
            raw = float(np.mean(scores))
            self.pop.fitnesses[idx] = _apply_spam_penalty(
                raw, counts,
                self.cfg.get("spam_rate_threshold", 0.50),
                self.cfg.get("spam_penalty_max", 0.75),
            )
            for k, v in counts.items():
                gen_counts[k] += v

        # Adaptive fitness window: if the champion survives most of its
        # episodes to the cap, fitness has saturated — double the window
        # so selection can see the skill differences that live beyond it.
        best_idx = int(np.argmax(self.pop.fitnesses))
        if (timeouts[best_idx] >= max(2, len(gen_seeds) - 1)
                and self._fitness_cap < EVAL_FRAME_CAP):
            self._fitness_cap = min(self._fitness_cap * 2, EVAL_FRAME_CAP)
            print(f"  ▲ fitness window saturated — raised to "
                  f"{self._fitness_cap} frames ({self._fitness_cap/60/60:.1f} game-min)")
        return gen_counts

    # ── Champion eval — fixed seeds, identical to DQN protocol ──────

    def evaluate_champion(self) -> dict:
        champion = self.pop.agents[
            int(np.argmax(self.pop.fitnesses))
        ]
        env = self._make_env(EVAL_FRAME_CAP)
        scores, clears, causes = [], [], {}
        for i in range(self.eval_episodes):
            obs = env.reset(seed=10_000 + i)
            done = False
            while not done:
                obs, _, done, info = env.step(champion.predict(obs))
            scores.append(info["score"])
            clears.append(info["cleared"])
            if info["death_cause"]:
                causes[info["death_cause"]] = causes.get(info["death_cause"], 0) + 1
        return {
            "avg": float(np.mean(scores)),
            "clears": float(np.mean(clears)),
            "death_causes": causes,
            "champion": champion,
        }

    # ── Persistence ───────────────────────────────────────────────────

    def save_state(self, generation: int):
        if not self.run_dir:
            return
        np.savez_compressed(
            self.run_dir / "population.npz",
            weights=np.stack([a.get_flat_weights() for a in self.pop.agents]),
            fitnesses=np.array(self.pop.fitnesses),
        )
        state = {
            "generation": generation + 1,
            "best_eval": self.best_eval,
            "mutation_scale": self._mutation_scale,
            "best_fitness_ever": self._best_fitness_ever,
            "gens_no_improve": self._gens_no_improve,
            "fitness_cap": self._fitness_cap,
            "curriculum": self.curriculum.to_dict() if self.curriculum else None,
        }
        tmp = self.run_dir / "state.json.tmp"
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(self.run_dir / "state.json")

    def load_state(self) -> int:
        """Restore population + counters. Returns the generation to resume at."""
        if not self.run_dir:
            return 0
        pop_file = self.run_dir / "population.npz"
        state_file = self.run_dir / "state.json"
        if not (pop_file.exists() and state_file.exists()):
            return 0
        data = np.load(pop_file)
        for agent, flat in zip(self.pop.agents, data["weights"]):
            agent.set_flat_weights(flat.astype(np.float32))
        self.pop.fitnesses = list(data["fitnesses"])
        state = json.loads(state_file.read_text())
        self.best_eval = state.get("best_eval", 0.0)
        self._mutation_scale = state.get("mutation_scale", self._mutation_scale)
        self._best_fitness_ever = state.get("best_fitness_ever", 0.0)
        self._gens_no_improve = state.get("gens_no_improve", 0)
        self._fitness_cap = state.get("fitness_cap", FITNESS_FRAME_CAP_START)
        if self.curriculum is not None and state.get("curriculum"):
            from curriculum import Curriculum
            self.curriculum = Curriculum.from_dict(state["curriculum"])
        return state.get("generation", 0)

    def _save_champion(self, label: str):
        if not self.run_dir:
            return
        champion = self.pop.agents[int(np.argmax(self.pop.fitnesses))]
        np.savez_compressed(
            self.run_dir / f"{label}.npz",
            weights=champion.get_flat_weights(),
            layers=np.array(self.cfg["network_layers"]),
        )

    # ── Training loop ─────────────────────────────────────────────────

    def train(self):
        cur = self.curriculum
        if cur is not None and not cur.finished:
            ph = cur.phase
            print(f"\n──  PHASE {cur.phase_idx + 1}/{len(cur.phases)}: {ph.name}  ──")
            print(f"    {ph.description}")
            print(f"    gate: champion eval ≥ {ph.complete_eval_avg:.0f}\n")

        try:
            for gen in range(self.start_generation, self.start_generation + self.generations):
                t0 = time.time()
                # Rotating common seeds: same for all agents this generation
                gen_seeds = [int(self._rng.integers(1 << 30))
                             for _ in range(self.episodes_per_agent)]
                gen_counts = self._evaluate_generation(gen_seeds)
                gen_time = time.time() - t0

                # Stagnation / mutation-scale control (as browser trainer)
                current_best = max(self.pop.fitnesses)
                stagnated = False
                if current_best > self._best_fitness_ever:
                    self._best_fitness_ever = current_best
                    self.pop.best_ever = current_best
                    self._gens_no_improve = 0
                else:
                    self._gens_no_improve += 1
                    if self._gens_no_improve >= self.cfg.get("stagnation_limit", 8):
                        stagnated = True
                        self._gens_no_improve = 0
                        self._mutation_scale = self.cfg.get("mutation_scale_start", 0.30)
                        self.pop.inject_random(self.cfg.get("stagnation_inject_pct", 0.20))

                # Champion eval + curriculum
                eval_info = None
                if (gen + 1) % self.eval_every == 0:
                    eval_info = self.evaluate_champion()
                    self.last_eval = eval_info["avg"]
                    if self.last_eval > self.best_eval:
                        self.best_eval = self.last_eval
                        self._save_champion("best_genome")
                    if cur is not None and not cur.finished:
                        event = cur.after_eval(self.last_eval)
                        if event["type"] == "advance":
                            self._save_champion(f"phase_{event['completed']}_complete")
                            print(f"\n{'═'*70}")
                            print(f"  ✔  PHASE '{event['completed']}' COMPLETE — "
                                  f"champion eval {event['eval_avg']:.0f}")
                            if cur.finished:
                                print("  ✔  CURRICULUM COMPLETE — continuing on the full game.")
                            else:
                                print(f"  →  advancing to '{event['next']}'")
                            print("═"*70 + "\n")
                            # New phase ⇒ re-explore: reset mutation scale
                            self._mutation_scale = self.cfg.get("mutation_scale_start", 0.30)
                        elif event["type"] == "intervene":
                            self._mutation_scale = self.cfg.get("mutation_scale_start", 0.30)
                            self.pop.inject_random(0.3)
                            print(f"\n  ⚠  STALL (eval {event['eval_avg']:.0f}) — "
                                  f"mutation reset + 30% fresh genomes\n")
                        elif event["type"] == "stalled":
                            print(f"\n  ✖  STALLED (eval {event['eval_avg']:.0f}) — "
                                  f"phase design needs a human look.\n")

                # Stats
                total_a = sum(gen_counts.values()) or 1
                stats = {
                    "episode": gen,                       # CSV column parity with DQN
                    "generation": gen,
                    "score": round(current_best, 1),      # best fitness this gen
                    "best": round(self._best_fitness_ever, 1),
                    "eval_avg": round(self.last_eval, 1),
                    "eval_best": round(self.best_eval, 1),
                    "avg_fitness": round(float(np.mean(self.pop.fitnesses)), 1),
                    "mutation_scale": round(self._mutation_scale, 4),
                    "stagnated": stagnated,
                    "gen_seconds": round(gen_time, 1),
                    "fitness_cap": self._fitness_cap,
                    "phase": (cur.phase.name if cur and not cur.finished
                              else ("done" if cur else "")),
                    "phase_status": ("stalled" if cur and not cur.finished and cur.stalled
                                     else "ok"),
                    "action_pct": {
                        "noop": round(gen_counts[0] / total_a * 100, 1),
                        "jump": round(gen_counts[1] / total_a * 100, 1),
                        "duck": round(gen_counts[2] / total_a * 100, 1),
                    },
                }
                if eval_info:
                    stats["eval_clears"] = round(eval_info["clears"], 1)
                    stats["eval_death_causes"] = eval_info["death_causes"]

                if self.on_generation_end:
                    self.on_generation_end(stats)

                self.save_state(gen)

                # Evolve
                self._mutation_scale = (
                    self._mut_scale_end
                    + (self._mutation_scale - self._mut_scale_end) * self._mut_scale_decay
                )
                self.pop.evolve(mutation_scale=self._mutation_scale)

        except KeyboardInterrupt:
            print(f"\nStopped at generation {gen} — best eval: {self.best_eval:.1f}")
            self.save_state(gen)

        return self.pop


def load_genome(path: str) -> NumpyNet:
    """Load a saved champion genome (.npz) into a NumpyNet for demo/eval."""
    data = np.load(path)
    net = NumpyNet([int(x) for x in data["layers"]])
    net.set_flat_weights(data["weights"].astype(np.float32))
    return net
