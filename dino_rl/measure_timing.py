"""Measure the real timing jitter of the wall-clock browser loop.

For each agent decision in the un-throttled --demo loop, record how much game
time actually elapsed (Runner.runningTime delta) and convert to game-frames.
The sim trains at a FIXED 2 frames/decision; this tells us the real
distribution we need to domain-randomize over for jitter-robust training.

Requires the game server:  python -m http.server 8766
Usage:  python measure_timing.py --load models/validated_20260612/best_model.pt --decisions 800
"""

import argparse
import time

import numpy as np

from config import DQN_CONFIG, GAME_CONFIG
from game.chrome_driver import DinoDriver
from agents.dqn.network import QNetwork
from logger import load_model

MS_PER_FRAME = 1000.0 / 60.0


def main(args):
    net = QNetwork(DQN_CONFIG["network_layers"])
    load_model(net, args.load)
    net.eval()
    poll = GAME_CONFIG["poll_interval"]

    driver = DinoDriver(headless=args.headless, lockstep=False)
    frames_per_decision = []
    deaths = 0
    try:
        driver.reset()
        time.sleep(0.4)
        prev_rt = driver.driver.execute_script("return Runner.instance_.runningTime;")
        state = driver.get_state()
        obs = state.to_array()
        for _ in range(args.decisions):
            a = net.predict(obs)
            driver.act(a)
            time.sleep(poll)
            ns = driver.get_state()
            rt = driver.driver.execute_script("return Runner.instance_.runningTime;")
            if ns is None:
                break
            if rt is not None and prev_rt is not None and rt >= prev_rt:
                frames_per_decision.append((rt - prev_rt) / MS_PER_FRAME)
            prev_rt = rt
            obs = ns.to_array()
            if ns.crashed:
                deaths += 1
                driver.reset()
                time.sleep(0.4)
                prev_rt = driver.driver.execute_script("return Runner.instance_.runningTime;")
                s = driver.get_state()
                if s is not None:
                    obs = s.to_array()
    finally:
        driver.close()

    f = np.array(frames_per_decision)
    print(f"\nSampled {len(f)} decisions over {deaths} death(s).")
    print(f"Sim trains at:  2.00 frames/decision (fixed)")
    print(f"Real loop:      mean {f.mean():.2f}  std {f.std():.2f}  "
          f"min {f.min():.2f}  max {f.max():.2f}")
    for p in (5, 25, 50, 75, 95, 99):
        print(f"   p{p:<2d} = {np.percentile(f, p):.2f} frames")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", required=True)
    ap.add_argument("--decisions", type=int, default=800)
    ap.add_argument("--headless", action="store_true")
    main(ap.parse_args())
