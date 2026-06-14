"""Entry point.

Two commands you need:
    python main.py --episodes 20000          # start sim curriculum training
    python main.py --auto                    # resume after any stop

Curriculum phases (all in Python sim):
    0-straight      lane-keeping + throttle/brake, slow speed
    1-oval          proportional cornering
    2-slalom        anticipatory steering
    3-domain-rand   randomised physics — bridges to real game

After curriculum: export the actor weights and load into a TMInterface wrapper
(real game phase) for physics calibration. See README.

Other modes:
    python main.py --no-curriculum           # flat training on slalom + rand
    python main.py --demo                    # render a greedy episode (matplotlib)
    python main.py --load runs/sac_X/best_actor.pt   # start from saved weights
"""

import argparse
from datetime import datetime
from pathlib import Path

import torch
# PyTorch defaults to all CPU threads, but inter-thread synchronization
# dominates for tiny batches/networks — single thread is ~170x faster here.
torch.set_num_threads(1)
torch.set_num_interop_threads(1)

from config import SAC_CONFIG
from curriculum import Curriculum
from logger import RunLogger, find_latest_run


def run_training(args):
    from agents.sac.trainer import SACTrainer

    cfg = dict(SAC_CONFIG)
    curriculum = None if args.no_curriculum else Curriculum()

    resume_dir   = None
    start_episode = 0
    load_path    = args.load

    if args.auto:
        latest = find_latest_run()
        if latest is None:
            print("No resumable run found — starting fresh.")
        else:
            resume_dir = str(latest)
            ckpt = latest / "checkpoint.pt"
            if ckpt.exists():
                load_path = str(ckpt)

    if resume_dir is None:
        ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
        resume_dir = f"runs/sac_{ts}"

    print(f"Run dir: {resume_dir}")

    with RunLogger(resume_dir, cfg) as log:
        if args.auto and log.load_state():
            state = log.load_state()
            start_episode = state.get("episode", 0)
            if curriculum is not None and state.get("curriculum"):
                curriculum = Curriculum.from_dict(state["curriculum"])
                print(f"Resuming at episode {start_episode}, "
                      f"phase '{curriculum.phase.name if not curriculum.finished else 'done'}'")

        def on_ep_end(stats):
            log.log(stats)
            ep   = stats["episode"]
            # Print every episode during warm-up, then every 25
            freq = 5 if ep < 200 else 25
            if (ep + 1) % freq == 0 or "eval_avg_laps" in stats:
                line = (
                    f"  ep {ep+1:>6} | "
                    f"reward {stats['reward']:>8.3f} | "
                    f"laps {stats.get('laps', 0):>2} | "
                    f"prog {stats.get('progress', 0):.2f} | "
                    f"α {stats['alpha']:.3f} | "
                    f"steps {stats['total_steps']:>8,} | "
                    f"phase {stats.get('phase', '-')}"
                )
                if "eval_avg_laps" in stats:
                    line += (
                        f"\n  *** EVAL  avg_laps={stats['eval_avg_laps']:.2f} | "
                        f"avg_progress={stats.get('eval_avg_progress', 0):.3f} | "
                        f"avg_speed={stats.get('eval_avg_speed', 0):.1f} m/s ***"
                    )
                print(line)

        trainer = SACTrainer(
            episodes=args.episodes,
            on_episode_end=on_ep_end,
            cfg=cfg,
            logger=log,
            curriculum=curriculum,
            start_episode=start_episode,
        )

        if load_path and not (args.auto and "checkpoint.pt" in str(load_path or "")):
            import torch
            trainer.actor.load_state_dict(torch.load(load_path, weights_only=True))
            print(f"Loaded weights: {load_path}")

        trainer.train()

        print(f"\nTraining complete. Best eval avg_laps: {trainer.best_eval:.2f}")


def run_demo(args):
    """Render one greedy episode using matplotlib."""
    import numpy as np
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
    except ImportError:
        print("matplotlib required for demo: pip install matplotlib")
        return

    from agents.sac.network import Actor
    from game.car_env import CarEnv, N_OBS
    from curriculum import PHASES
    import torch

    phase_name = args.phase or PHASES[-1].name
    phase = next((p for p in PHASES if p.name == phase_name), PHASES[-1])
    env = CarEnv(**phase.env_params)
    track = env._track

    actor = Actor(N_OBS, 2)
    if args.load:
        actor.load_state_dict(torch.load(args.load, weights_only=True))
        print(f"Loaded: {args.load}")
    else:
        print("No --load specified — using random weights (untrained demo)")
    actor.eval()

    obs  = env.reset(seed=42)
    done = False
    xs, ys = [env.x], [env.y]

    while not done:
        action = actor.predict(obs)
        obs, _, done, info = env.step(action)
        xs.append(env.x)
        ys.append(env.y)

    fig, ax = plt.subplots(figsize=(12, 5))
    wp = track.waypoints
    ax.plot(wp[:, 0], wp[:, 1], "--", color="#888", lw=1, label="centreline")
    # Track boundary
    for sign in (+1, -1):
        bx = wp[:, 0] - sign * track.width * np.sin(
            np.arctan2(np.gradient(wp[:, 1]), np.gradient(wp[:, 0]))
        )
        by = wp[:, 1] + sign * track.width * np.cos(
            np.arctan2(np.gradient(wp[:, 1]), np.gradient(wp[:, 0]))
        )
        ax.plot(bx, by, "-", color="#444", lw=1)
    ax.plot(xs, ys, color="#4ea8fe", lw=1.5, label="agent path")
    ax.scatter(xs[0], ys[0], color="#7ee0c0", s=60, zorder=5, label="start")
    ax.scatter(xs[-1], ys[-1], color="#f6c177", s=60, zorder=5, label="end")
    ax.set_title(
        f"Phase: {phase_name} | laps: {info['laps']} | "
        f"progress: {info['progress']:.2%} | off_track: {info['off_track']}"
    )
    ax.legend(); ax.set_aspect("equal"); ax.grid(alpha=0.2)
    plt.tight_layout()
    plt.show()
    print(f"Laps: {info['laps']}  Progress: {info['progress']:.2%}  "
          f"Speed: {info['speed']:.1f} m/s")


def main():
    parser = argparse.ArgumentParser(description="Trackmania SAC trainer (sim phase)")
    parser.add_argument("--episodes",     type=int,  default=20_000)
    parser.add_argument("--no-curriculum",action="store_true")
    parser.add_argument("--auto",         action="store_true",
                        help="Resume the most recent run")
    parser.add_argument("--load",         type=str, default=None, metavar="PATH",
                        help="Load actor weights before training")
    parser.add_argument("--demo",         action="store_true",
                        help="Render one greedy episode (matplotlib)")
    parser.add_argument("--phase",        type=str, default=None,
                        help="Phase to run demo on (default: last sim phase)")
    args = parser.parse_args()

    if args.demo:
        run_demo(args)
    else:
        run_training(args)


if __name__ == "__main__":
    main()
