"""Test the robustness/peak trade-off hypothesis.

Claim: the sim-only model, ONCE it reaches cruise (max speed), is flawless;
the jitter-trained model traded some of that peak cruise quality for windup
survival. To test it without the windup confound, start episodes directly at
max speed (the cruise regime) and measure per-obstacle hazard there, under
the real-browser timing jitter.

Usage:
    python cruise_robustness.py \
        --old models/validated_20260612/best_model.pt \
        --new models/validated_jitter_20260620/best_model.pt \
        --episodes 200
"""

import argparse

import numpy as np

from config import DQN_CONFIG
from game.dino_env import DinoEnv
from agents.dqn.network import QNetwork
from logger import load_model


def load(path):
    net = QNetwork(DQN_CONFIG["network_layers"])
    load_model(net, path)
    net.eval()
    return net


def evaluate(net, episodes, jmin, jmax, max_frames):
    """Start every episode at speed 13 (cruise), apply jitter, measure hazard."""
    deaths = cleared_total = survived = 0
    death_speeds = []
    for ep in range(episodes):
        kw = dict(birds=True, max_speed=13.0, action_repeat=2,
                  start_speed_min=13.0, start_speed_max=13.0,
                  max_frames=max_frames, seed=ep)
        if jmax > jmin:
            kw["action_repeat_min"] = jmin
            kw["action_repeat_max"] = jmax
        env = DinoEnv(**kw)
        obs = env.reset(seed=ep)
        done = False
        info = {}
        while not done:
            obs, _, done, info = env.step(net.predict(obs))
        cleared_total += info["cleared"]
        if info.get("death_cause"):
            deaths += 1
            death_speeds.append(info["speed"])
        else:
            survived += 1
    hazard = f"1 in {cleared_total // deaths}" if deaths else "none (flawless)"
    return dict(deaths=deaths, survived=survived, cleared=cleared_total,
                hazard=hazard, episodes=episodes)


def main(args):
    conditions = [("fixed 2 (train cadence)", 2, 2),
                  ("fixed 4 (real median)", 4, 4),
                  ("jitter 2-6 (deployment)", 2, 6)]
    models = [("OLD  sim-only ", args.old), ("NEW  jitter  ", args.new)]
    nets = {name: load(p) for name, p in models}

    for label, jmin, jmax in conditions:
        print(f"\n══ cruise regime (start@13), {label} — {args.episodes} eps ══")
        for name, _ in models:
            r = evaluate(nets[name], args.episodes, jmin, jmax, args.max_frames)
            print(f"  {name}: survived {r['survived']:3d}/{r['episodes']}  "
                  f"deaths {r['deaths']:3d}  cleared {r['cleared']:6d}  "
                  f"hazard {r['hazard']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--episodes", type=int, default=200)
    ap.add_argument("--max-frames", type=int, default=36_000, dest="max_frames")
    main(ap.parse_args())
