"""Where does the frame-perfect model die in the real (wall-clock) browser?

Plays the un-throttled demo loop for N episodes and records, per death, the
speed and cause at the moment of death — to test the hypothesis that the
vulnerability is concentrated in the speed-ramp / bird-introduction band
(speed ~8.5) rather than at top speed.

Requires:  python -m http.server 8766
Usage:     python death_analysis.py --load models/validated_20260612/best_model.pt --episodes 50
"""

import argparse
import time
from collections import Counter

import numpy as np

from config import DQN_CONFIG, GAME_CONFIG
from game.chrome_driver import DinoDriver
from agents.dqn.network import QNetwork
from logger import load_model


def main(args):
    net = QNetwork(DQN_CONFIG["network_layers"])
    load_model(net, args.load)
    net.eval()
    poll = GAME_CONFIG["poll_interval"]

    driver = DinoDriver(headless=args.headless, lockstep=False)
    death_speeds, death_causes = [], Counter()
    reached_max, survived = 0, 0
    reached_max_and_died = 0

    try:
        for ep in range(args.episodes):
            driver.reset()
            time.sleep(0.3)
            state = driver.get_state()
            if state is None:
                continue
            obs = state.to_array()
            hit_max = False
            crashed = False
            for _ in range(args.max_steps):
                a = net.predict(obs)
                driver.act(a)
                time.sleep(poll)
                ns = driver.get_state()
                if ns is None:
                    break
                if ns.speed >= 12.5:
                    hit_max = True
                obs = ns.to_array()
                if ns.crashed:
                    crashed = True
                    cause = driver.driver.execute_script(
                        "return Runner.instance_.deathCause;")
                    death_speeds.append(ns.speed)
                    death_causes[cause or "?"] += 1
                    if hit_max:
                        reached_max_and_died += 1
                    break
            if hit_max:
                reached_max += 1
            if not crashed:
                survived += 1
            print(f"  ep {ep:3d}: {'SURVIVED cap' if not crashed else f'died @ speed {ns.speed:.1f} ({cause})'}"
                  f"{'  [reached max speed]' if hit_max else ''}")
    finally:
        driver.close()

    s = np.array(death_speeds)
    print(f"\n── {len(s)} deaths, {survived} survived to step cap ──")
    if len(s):
        print(f"death speed: mean {s.mean():.1f}  median {np.median(s):.1f}  "
              f"min {s.min():.1f}  max {s.max():.1f}")
        for lo, hi in [(6, 8.5), (8.5, 10), (10, 12.5), (12.5, 13.1)]:
            n = ((s >= lo) & (s < hi)) .sum()
            print(f"   speed [{lo:>4}, {hi:>4}): {n:3d} deaths ({100*n/len(s):.0f}%)")
        print(f"death causes: {dict(death_causes)}")
    print(f"\nReached max speed (≥12.5): {reached_max} episodes; "
          f"of those, {reached_max_and_died} still died, "
          f"{reached_max - reached_max_and_died} cruised to cap.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", required=True)
    ap.add_argument("--episodes", type=int, default=50)
    ap.add_argument("--max-steps", type=int, default=8000, dest="max_steps")
    ap.add_argument("--headless", action="store_true")
    main(ap.parse_args())
