"""Clean real-time eval — the RC-B metric.

NO per-step instrumentation (the observer effect that corrupted the earlier
measurements). Exactly the deployment loop: get_state -> predict -> act ->
sleep -> get_state. The only extra read is deathCause, ONCE, after a crash —
so it cannot affect timing during play.

Reports the goal metric (SCORE: median/mean/best) + a trustworthy death profile.
Requires: python -m http.server 8766
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
    layers = ([int(x) for x in args.layers.split(",")] if args.layers
              else DQN_CONFIG["network_layers"])
    n_in = layers[0]                   # older models use a prefix of the
    net = QNetwork(layers)             # 26-feature vector (one-hots are last)
    load_model(net, args.load)
    net.eval()
    poll = GAME_CONFIG["poll_interval"] if args.poll is None else args.poll

    d = DinoDriver(headless=args.headless, lockstep=False)
    scores, death_speeds = [], []
    causes = Counter()
    try:
        for ep in range(args.episodes):
            d.reset()
            time.sleep(0.3)
            st = d.get_state()
            if st is None:
                continue
            obs = st.to_array()[:n_in]
            steps = 0
            crashed = False
            last = st
            for _ in range(args.max_steps):
                a = net.predict(obs)
                d.act(a)
                time.sleep(poll)               # the ONLY thing between decisions
                ns = d.get_state()
                if ns is None:
                    break
                obs, last = ns.to_array()[:n_in], ns
                steps += 1
                if ns.crashed:
                    crashed = True
                    break
            scores.append(last.score)          # SCORE is the metric
            if crashed:
                death_speeds.append(last.speed)
                causes[d.driver.execute_script(
                    "return Runner.instance_.deathCause;") or "?"] += 1
            print(f"  ep {ep:2d}: SCORE {last.score:8.0f}  ({'survived cap' if not crashed else 'died spd %.1f' % last.speed})")
    finally:
        d.close()

    s = np.array(scores)
    print(f"\n== SCORE — median {np.median(s):.0f}  mean {s.mean():.0f}  best {s.max():.0f}  worst {s.min():.0f}")
    print(f"== all scores: {sorted([int(x) for x in scores], reverse=True)}")
    if len(death_speeds):
        ds = np.array(death_speeds)
        print(f"== deaths {len(death_speeds)}/{args.episodes}: death-speed mean {ds.mean():.1f}"
              f"  causes {dict(causes.most_common())}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", required=True)
    ap.add_argument("--episodes", type=int, default=15)
    ap.add_argument("--max-steps", type=int, default=4000, dest="max_steps")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--poll", type=float, default=None,
                    help="override GAME_CONFIG poll_interval (s) — E12 recipe "
                         "deploys at 0.02")
    ap.add_argument("--layers", default=None,
                    help="comma-separated network layers for older checkpoints, e.g. 20,128,64")
    main(ap.parse_args())
