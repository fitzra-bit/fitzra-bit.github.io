"""Entry point.

The two commands you actually need:
    python main.py --agent dqn --episodes 5000      # start curriculum training
    python main.py --agent dqn --auto               # resume after ANY stop
                                                    # (crash, Ctrl+C, reboot)

The curriculum advances phases, recovers from stalls, and checkpoints
automatically — see curriculum.py. Progress: http://localhost:8765

Other modes:
    python main.py                                                # genetic, 100 generations
    python main.py --agent dqn --no-curriculum                    # flat training, full game
    python main.py --agent dqn --load runs/dqn_X/best_model.pt    # start from given weights
    python main.py --agent genetic --workers 4                    # parallel Chrome windows
    python main.py --headless                                     # no browser window (faster)
    python main.py --demo --load runs/dqn_X/best_model.pt         # watch best model (no training)
    python main.py --cleanup                                      # kill orphaned Chrome processes
"""

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import GENETIC_CONFIG, DQN_CONFIG, GAME_CONFIG
from game.chrome_driver import DinoDriver
from visualization.dashboard import GeneticDashboard, DQNDashboard

# Headless Chrome ~150-200MB each. Warn if estimated usage exceeds available RAM.
_MB_PER_CHROME = 175
_WARN_RAM_GB = 12


def _open_drivers(n: int, headless: bool) -> list[DinoDriver]:
    """Open N Chrome windows in parallel to avoid sequential startup delay."""
    if n == 1:
        return [DinoDriver(headless=headless)]

    est_gb = (n * _MB_PER_CHROME) / 1024
    if est_gb > _WARN_RAM_GB:
        print(f"  Warning: {n} Chrome windows may use ~{est_gb:.1f}GB RAM.")

    drivers: list[DinoDriver] = [None] * n
    with ThreadPoolExecutor(max_workers=n) as ex:
        futures = {ex.submit(DinoDriver, headless): i for i in range(n)}
        for future in as_completed(futures):
            drivers[futures[future]] = future.result()
    return drivers


def run_genetic(args):
    cfg = {**GENETIC_CONFIG}
    if args.population:
        cfg["population_size"] = args.population

    n_workers = max(1, min(args.workers, cfg["population_size"]))
    print(f"Opening {n_workers} Chrome window(s) in parallel...")
    drivers = _open_drivers(n_workers, args.headless)
    pop = None
    try:
        with GeneticDashboard(cfg["population_size"]) as dash:
            from agents.genetic.trainer import GeneticTrainer

            trainer = GeneticTrainer(
                generations=args.generations,
                on_generation_end=dash.update,
                cfg=cfg,
            )
            pop = trainer.train(drivers)
    except KeyboardInterrupt:
        pass
    finally:
        for d in drivers:
            d.close()

    if pop is not None:
        label = "Training complete" if not pop else "Stopped early"
        print(f"\n{label}. Best score: {pop.best_ever:.1f}")


def run_dqn(args):
    cfg = {**DQN_CONFIG}

    from logger import RunLogger, find_latest_run
    from agents.dqn.trainer import DQNTrainer
    from curriculum import Curriculum
    from visualization.web_dashboard import DashboardServer

    # ── Resume (--auto): newest run with a state.json picks up mid-phase ──
    resume_dir, start_episode, load_path = None, 0, args.load
    curriculum = None if args.no_curriculum else Curriculum()

    if args.auto:
        latest = find_latest_run()
        if latest is None:
            print("No resumable run found — starting fresh.")
        else:
            resume_dir = str(latest)
            checkpoint = latest / "checkpoint.pt"
            if checkpoint.exists():
                load_path = str(checkpoint)

    web = DashboardServer()
    web.start()   # http://localhost:8765  (daemon thread — auto-stops with process)

    # Training is pure simulation — no Chrome, no game server needed.
    with RunLogger(agent="dqn", cfg=cfg, resume_dir=resume_dir) as log:
        # Restore curriculum + counters from state.json after logger exists
        if resume_dir:
            state = log.load_state()
            if state:
                start_episode = state.get("episode", 0)
                if curriculum is not None and state.get("curriculum"):
                    curriculum = Curriculum.from_dict(state["curriculum"])
                    print(f"Resuming at episode {start_episode}, "
                          f"phase '{curriculum.phase.name if not curriculum.finished else 'done'}' "
                          f"({curriculum.evals_in_phase} evals in)")

        with DQNDashboard() as dash:
            def on_ep_end(stats):
                dash.update(stats)   # Rich terminal dashboard
                web.push(stats)      # Web dashboard

            trainer = DQNTrainer(
                episodes=args.episodes,
                on_episode_end=on_ep_end,
                cfg=cfg,
                logger=log,
                checkpoint_every=args.checkpoint,
                load_path=load_path,
                curriculum=curriculum,
                start_episode=start_episode,
            )
            trainer.train()

        print(f"\nTraining complete. Best eval: {trainer.best_eval:.1f} "
              f"(best training score: {trainer.best_score:.1f})")


def run_demo(args):
    """Watch a saved model play with ε=0 — pure exploitation, visible browser, no training."""
    if not args.load:
        print("Error: --demo requires --load PATH")
        print("  Example: python main.py --demo --load runs\\dqn_20260606_113028\\best_model.pt")
        return

    from agents.dqn.network import QNetwork
    from logger import load_model

    cfg = {**DQN_CONFIG}
    net = QNetwork(cfg["network_layers"])
    load_model(net, args.load)
    net.eval()
    print(f"Loaded:  {args.load}")
    print("Mode:    demo (ε=0, no training, no buffer)")
    print("Control: Ctrl+C to stop\n")

    poll       = GAME_CONFIG["poll_interval"]
    dbg_every  = getattr(args, "debug_steps", 0)

    _ACTIONS = {0: "noop", 1: "jump", 2: "duck"}

    driver = DinoDriver(headless=False)   # always visible — that's the point
    ep     = 0
    best   = 0.0

    try:
        while True:
            ep += 1
            driver.reset()
            time.sleep(0.4)              # slightly longer settle so you can see it start

            state = driver.get_state()
            if state is None:
                continue

            obs            = state.to_array()
            ep_score       = 0.0
            ep_steps       = 0
            ep_cleared     = 0
            debug_ep       = (ep == 1 and dbg_every > 0)

            for _ in range(20_000):
                # Debug: show what the network sees and decides
                if debug_ep and ep_steps % dbg_every == 0:
                    import torch as _torch
                    with _torch.no_grad():
                        t  = _torch.from_numpy(obs).unsqueeze(0)
                        qv = net(t).squeeze(0).numpy()
                    feat_names = ["d1","y1","w1","b1","d2","y2","w2","b2",
                                  "gap","spd","dy","vy","jmp","duc","ttc"]
                    feat_str = "  ".join(f"{n}={v:.2f}" for n, v in zip(feat_names, obs))
                    q_str    = "  ".join(f"{_ACTIONS[i]}={qv[i]:.3f}" for i in range(3))
                    chosen   = _ACTIONS[int(qv.argmax())]
                    print(f"  step {ep_steps:3d} | {feat_str}")
                    print(f"           Q: {q_str}  → {chosen}")

                action = net.predict(obs)
                driver.act(action)
                time.sleep(poll)

                next_state = driver.get_state()
                if next_state is None:
                    break

                obs        = next_state.to_array()
                ep_score   = next_state.score
                ep_cleared = next_state.cleared   # authoritative game counter
                ep_steps  += 1

                if next_state.crashed:
                    break

            new_best = ep_score > best
            if new_best:
                best = ep_score

            tag = "  *** NEW BEST ***" if new_best else ""
            print(
                f"  Ep {ep:4d} | "
                f"Score {ep_score:8.1f} | "
                f"Best {best:8.1f} | "
                f"Steps {ep_steps:6d} | "
                f"Cleared {ep_cleared}"
                f"{tag}"
            )

    except KeyboardInterrupt:
        print(f"\nDemo stopped after {ep} episode(s).  Best this session: {best:.1f}")
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
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel Chrome windows for genetic mode (default: 1)",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Kill all orphaned chromedriver/chrome processes and exit",
    )
    parser.add_argument(
        "--load",
        type=str,
        default=None,
        metavar="PATH",
        help="Load DQN weights from a saved .pt file before training",
    )
    parser.add_argument(
        "--checkpoint",
        type=int,
        default=100,
        metavar="N",
        help="Save a checkpoint every N episodes (default: 100)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Resume the most recent DQN run (checkpoint + phase + epsilon) "
             "and continue training. The one command to restart after any stop.",
    )
    parser.add_argument(
        "--no-curriculum",
        action="store_true",
        help="DQN: train on the full game with the base config, no phases.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Watch a saved model play (ε=0, no training). Requires --load PATH.",
    )
    parser.add_argument(
        "--debug-steps",
        type=int,
        default=0,
        metavar="N",
        help="Demo: print obs vector + Q-values every N steps for the first episode (0 = off)",
    )
    args = parser.parse_args()

    if args.cleanup:
        from game.chrome_driver import cleanup_all
        n = cleanup_all()
        print(f"Cleanup: killed {n} process(es).")
        return

    if args.demo:
        run_demo(args)
    elif args.agent == "genetic":
        run_genetic(args)
    else:
        run_dqn(args)


if __name__ == "__main__":
    main()
