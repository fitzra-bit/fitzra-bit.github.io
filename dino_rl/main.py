"""Entry point.

Usage:
    python main.py                         # genetic, 100 generations, 50 agents
    python main.py --agent dqn             # DQN, 500 episodes
    python main.py --agent genetic --generations 200 --population 30
    python main.py --agent dqn --episodes 1000
    python main.py --headless              # no browser window (faster)
"""

import argparse
import sys

from config import GENETIC_CONFIG, DQN_CONFIG, GAME_CONFIG
from game.chrome_driver import DinoDriver
from visualization.dashboard import GeneticDashboard, DQNDashboard


def run_genetic(args):
    cfg = {**GENETIC_CONFIG}
    if args.population:
        cfg["population_size"] = args.population

    driver = DinoDriver(headless=args.headless)
    try:
        with GeneticDashboard(cfg["population_size"]) as dash:
            from agents.genetic.trainer import GeneticTrainer

            trainer = GeneticTrainer(
                generations=args.generations,
                on_generation_end=dash.update,
                cfg=cfg,
            )
            pop = trainer.train(driver)

        print(f"\nTraining complete. Best score: {pop.best_ever:.1f}")
    finally:
        driver.close()


def run_dqn(args):
    cfg = {**DQN_CONFIG}

    driver = DinoDriver(headless=args.headless)
    try:
        with DQNDashboard() as dash:
            from agents.dqn.trainer import DQNTrainer

            trainer = DQNTrainer(
                episodes=args.episodes,
                on_episode_end=dash.update,
                cfg=cfg,
            )
            network = trainer.train(driver)

        print(f"\nTraining complete. Best score: {trainer.best_score:.1f}")
    finally:
        driver.close()


def main():
    parser = argparse.ArgumentParser(description="Chrome Dino RL trainer")
    parser.add_argument(
        "--agent",
        choices=["genetic", "dqn"],
        default="genetic",
        help="Learning algorithm (default: genetic)",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=100,
        help="Generations to run (genetic mode)",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=500,
        help="Episodes to run (DQN mode)",
    )
    parser.add_argument(
        "--population",
        type=int,
        default=None,
        help="Override population size (genetic mode)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome headlessly (no visible window)",
    )
    args = parser.parse_args()

    if args.agent == "genetic":
        run_genetic(args)
    else:
        run_dqn(args)


if __name__ == "__main__":
    main()
