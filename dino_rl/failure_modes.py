"""Characterize the RESIDUAL failure modes of a jitter-robust model.

The windup wall is solved; what kills the model now? Runs many ε=0 episodes in
the sim under timing jitter (validated to match the real browser) and records,
for each death: cause, speed, the jitter draw on the fatal step, whether the
killer cactus was grouped, the bird height, and the gap to the next obstacle.

Usage:
    python failure_modes.py --load models/validated_jitter_20260620/best_model.pt \
        --episodes 400 --jmin 2 --jmax 6
"""

import argparse
from collections import Counter

import numpy as np

from config import DQN_CONFIG
from game.dino_env import DinoEnv, OB_TYPES, TREX_X, TREX_W
from agents.dqn.network import QNetwork
from logger import load_model

BASE_W = {"CACTUS_SMALL": OB_TYPES["CACTUS_SMALL"]["w"],
          "CACTUS_LARGE": OB_TYPES["CACTUS_LARGE"]["w"]}


def front_obstacle(env):
    """The obstacle the dino is colliding with / about to: frontmost not-passed."""
    ahead = [o for o in env.obstacles if o.x + o.w >= TREX_X - 5]
    return ahead[0] if ahead else None, (ahead[1] if len(ahead) > 1 else None)


def main(args):
    net = QNetwork(DQN_CONFIG["network_layers"])
    load_model(net, args.load)
    net.eval()

    causes = Counter()
    death_speeds, fatal_jitter, all_jitter = [], [], Counter()
    cactus_group_sizes = Counter()
    bird_heights = Counter()
    gaps_at_death = []
    n_deaths = n_survived = 0
    total_cleared = 0

    for ep in range(args.episodes):
        env = DinoEnv(birds=True, max_speed=13.0,
                      action_repeat=2, action_repeat_min=args.jmin,
                      action_repeat_max=args.jmax, seed=ep)
        obs = env.reset(seed=ep)
        done = False
        info = {}
        while not done:
            obs, _, done, info = env.step(net.predict(obs))
            all_jitter[env.last_n_frames] += 1
        total_cleared += info["cleared"]
        if info.get("death_cause"):
            n_deaths += 1
            cause = info["death_cause"]
            causes[cause] += 1
            death_speeds.append(info["speed"])
            fatal_jitter.append(env.last_n_frames)
            o1, o2 = front_obstacle(env)
            if o1 is not None:
                if o1.is_bird:
                    bird_heights[{100.0: "low(jump)", 75.0: "mid(duck)",
                                  50.0: "high(run)"}.get(o1.y, "?")] += 1
                elif o1.type in BASE_W:
                    cactus_group_sizes[max(1, round(o1.w / BASE_W[o1.type]))] += 1
                if o2 is not None:
                    gaps_at_death.append((o2.x - (o1.x + o1.w)))
        else:
            n_survived += 1

    s = np.array(death_speeds)
    print(f"\n══ {args.episodes} episodes, jitter [{args.jmin},{args.jmax}] ══")
    print(f"deaths {n_deaths} | survived-to-timeout {n_survived} | "
          f"obstacles cleared total {total_cleared}")
    if n_deaths:
        print(f"per-obstacle hazard ≈ 1 in {total_cleared // n_deaths}")
        print(f"\ndeath causes: {dict(causes.most_common())}")
        print(f"\ndeath speed: mean {s.mean():.1f}  median {np.median(s):.1f}  "
              f"min {s.min():.1f}  max {s.max():.1f}")
        for lo, hi in [(6, 9), (9, 11), (11, 12.5), (12.5, 13.1)]:
            n = ((s >= lo) & (s < hi)).sum()
            print(f"   speed [{lo:>4}, {hi:>4}): {n:3d} ({100*n/n_deaths:.0f}%)")
        # Jitter-spike correlation: is the fatal step's frame-count skewed high?
        fj = np.array(fatal_jitter)
        tot = sum(all_jitter.values())
        print(f"\njitter on fatal step: mean {fj.mean():.2f}  "
              f"(overall mean {sum(k*v for k,v in all_jitter.items())/tot:.2f})")
        print(f"   fatal-step frame counts: {dict(sorted(Counter(fatal_jitter).items()))}")
        print(f"   overall frame counts:    {dict(sorted(all_jitter.items()))}")
        if cactus_group_sizes:
            print(f"\ncactus deaths by group size (1=single): "
                  f"{dict(sorted(cactus_group_sizes.items()))}")
        if bird_heights:
            print(f"bird deaths by height: {dict(bird_heights.most_common())}")
        if gaps_at_death:
            g = np.array(gaps_at_death)
            print(f"\ngap to NEXT obstacle at death: mean {g.mean():.0f}px  "
                  f"median {np.median(g):.0f}px  min {g.min():.0f}px "
                  f"(tight gap = landed-into-next)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", required=True)
    ap.add_argument("--episodes", type=int, default=400)
    ap.add_argument("--jmin", type=int, default=2)
    ap.add_argument("--jmax", type=int, default=6)
    main(ap.parse_args())
