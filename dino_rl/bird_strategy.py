"""Does the model actually use the right action per bird height?

Birds: low (y=100) → jump, mid (y=75) → duck, high (y=50) → run under (noop).
Hypothesis: the model never learned to duck/run-under — it just jumps everything,
which is fatal for high birds. Runs at FIXED cadence (no jitter confound) and
records the action the model commits as each bird enters the decision window.

Usage: python bird_strategy.py --load models/validated_jitter_20260620/best_model.pt --layers 20
"""

import argparse
from collections import Counter, defaultdict

import numpy as np

from game.dino_env import DinoEnv, TREX_X, TREX_W
from agents.dqn.network import QNetwork
from logger import load_model

ACT = {0: "noop/run-under", 1: "jump", 2: "duck"}
CORRECT = {100.0: "jump", 75.0: "duck", 50.0: "noop/run-under"}
HNAME = {100.0: "low", 75.0: "mid", 50.0: "high"}


def main(args):
    net = QNetwork([args.layers, 128, 64])
    load_model(net, args.load)
    net.eval()

    # action histogram per bird height, sampled in the commit window (TTC small)
    per_height = defaultdict(Counter)
    global_actions = Counter()

    for ep in range(args.episodes):
        kwargs = dict(birds=True, max_speed=13.0, action_repeat=4, seed=ep,
                      max_frames=args.max_frames)
        if args.calibrated:
            # E1b deployment timing: true arc, empirical clock, act latency
            kwargs.update(fe=0.4138, act_latency_frames=0.25,
                          cadence_samples=np.load(
                              "measurements/cadence_visible_20260705.npy"))
        env = DinoEnv(**kwargs)
        obs = env.reset(seed=ep)
        done = False
        while not done:
            a = int(net.predict(obs[:args.layers]))
            global_actions[a] += 1
            # If a bird is the imminent front obstacle, log the action
            ahead = [o for o in env.obstacles if not o.counted]
            if ahead:
                o1 = ahead[0]
                ttc_px = o1.x - (TREX_X + TREX_W)
                if o1.is_bird and 0 < ttc_px < 90:      # decision window
                    per_height[o1.y][a] += 1
            obs, _, done, _ = env.step(a)

    tot = sum(global_actions.values()) or 1
    print(f"\nGlobal action mix: "
          f"noop {100*global_actions[0]/tot:.1f}%  "
          f"jump {100*global_actions[1]/tot:.1f}%  "
          f"duck {100*global_actions[2]/tot:.1f}%")
    print("\nAction taken as each bird approaches (in commit window):")
    for y in (100.0, 75.0, 50.0):
        c = per_height[y]
        n = sum(c.values()) or 1
        print(f"  {HNAME[y]:>4} bird (correct = {CORRECT[y]:>14}): "
              f"jump {100*c[1]/n:4.0f}%  duck {100*c[2]/n:4.0f}%  "
              f"noop {100*c[0]/n:4.0f}%   (n={sum(c.values())})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", required=True)
    ap.add_argument("--layers", type=int, default=26, help="input dim (15/20/26)")
    ap.add_argument("--episodes", type=int, default=150)
    ap.add_argument("--max-frames", type=int, default=36_000, dest="max_frames")
    ap.add_argument("--calibrated", action="store_true",
                    help="run under the E1b deployment timing model")
    main(ap.parse_args())
