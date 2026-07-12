"""E12 pre-visible check — browser-side closing-velocity mechanics (headless OK).

The driver measures closing_v from consecutive reads (game/chrome_driver.py);
game_state.to_array() turns it into the residual features 26-27. This script
verifies, against the REAL game, that:
  - bird residuals split by hidden speed_offset sign (~±0.4 after /2 norm)
  - cactus residuals are ~zero-mean and small
  - coverage: residual is non-zero on most post-first-sighting reads
Headless is fine: this validates MECHANICS (matching, sign, scale), not
performance — the visible 145Hz display remains deployment truth.

Requires: python -m http.server 8766
Usage:    python closing_v_check.py --load runs/<run>/best_model.pt --poll 0.02
"""
import argparse
import time

import numpy as np

from config import DQN_CONFIG, GAME_CONFIG
from game.chrome_driver import DinoDriver
from agents.dqn.network import QNetwork
from logger import load_model


def main(args):
    layers = ([int(x) for x in args.layers.split(",")] if args.layers
              else DQN_CONFIG["network_layers"])
    n_in = layers[0]
    net = QNetwork(layers)
    load_model(net, args.load)
    net.eval()

    d = DinoDriver(headless=not args.visible, lockstep=False)
    bird_res, cactus_res, zero_reads, covered_reads = [], [], 0, 0
    try:
        for ep in range(args.episodes):
            d.reset()
            time.sleep(0.3)
            st = d.get_state()
            if st is None:
                continue
            obs = st.to_array()[:n_in]
            for _ in range(args.max_steps):
                a = net.predict(obs)
                d.act(a)
                time.sleep(args.poll)
                ns = d.get_state()
                if ns is None:
                    break
                obs = ns.to_array()[:n_in]
                full = ns.to_array()
                ahead = [ob for ob in ns.obstacles if ob.x + ob.width >= 50.0]
                if ahead:
                    r = full[26]
                    if r == 0.0:
                        zero_reads += 1
                    else:
                        covered_reads += 1
                        (bird_res if ahead[0].is_bird else cactus_res).append(r)
                if ns.crashed:
                    break
            print(f"  ep {ep}: score {ns.score if ns else 0:.0f}  "
                  f"bird_n={len(bird_res)} cactus_n={len(cactus_res)}")
    finally:
        d.close()

    b, c = np.array(bird_res), np.array(cactus_res)
    tot = zero_reads + covered_reads
    print(f"\n== closing_v coverage: {covered_reads}/{tot} obs1-present reads "
          f"non-zero ({100 * covered_reads / max(tot, 1):.0f}%)")
    if len(c):
        print(f"== cactus residuals: n={len(c)} mean {c.mean():+.3f} "
              f"std {c.std():.3f} |max| {np.abs(c).max():.3f}  (want ~0)")
    if len(b):
        fast, slow = b[b > 0.05], b[b < -0.05]
        print(f"== bird residuals: n={len(b)} mean {b.mean():+.3f} std {b.std():.3f}")
        print(f"   fast cluster n={len(fast)} mean {fast.mean() if len(fast) else 0:+.3f} "
              f"(want ~+0.4) | slow cluster n={len(slow)} "
              f"mean {slow.mean() if len(slow) else 0:+.3f} (want ~-0.4)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", required=True)
    ap.add_argument("--layers", default=None)
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--max-steps", type=int, default=6000, dest="max_steps")
    ap.add_argument("--poll", type=float, default=0.02)
    ap.add_argument("--visible", action="store_true",
                    help="use a visible window (default headless — mechanics only)")
    main(ap.parse_args())
