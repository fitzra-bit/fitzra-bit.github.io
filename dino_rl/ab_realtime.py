"""Interleaved A/B visible crowning — EXPERIMENTS.md amendment 8.

Alternates two artifacts episode-by-episode (A,B,A,B,...) within ONE session
so platform/day effects cancel by construction. Basis: E8's P(reach 22.2k)
swung 9/10 -> 5/10 across 12 days (n=10 sampling noise + measured cadence
drift 3.56->3.72 f/dec); cross-era comparisons are unreliable in both
directions.

One driver (one visible browser) alive at a time — an idle second browser
would still run its rAF loop and contaminate timing. Per-episode browser
startup (~5s) is the price of clean interleaving.

Each side gets its own poll + step cap so the SCORE ceiling matches across
clocks (amendment 7): cap_frames ~= max_steps * realized_f_per_step.

Requires: python -m http.server 8766
Usage:
  python ab_realtime.py \
    --a-load models/validated_capacity_20260707/best_model.pt --a-layers 26,256,128 --a-max-steps 30000 \
    --b-load models/validated_pollrate_20260710/best_model.pt --b-layers 28,256,128 --b-poll 0.02 --b-max-steps 62000 \
    --episodes 10
"""
import argparse
import time
from collections import Counter

import numpy as np

from config import DQN_CONFIG, GAME_CONFIG
from game.chrome_driver import DinoDriver
from agents.dqn.network import QNetwork
from logger import load_model


def load_net(path, layers_str):
    layers = ([int(x) for x in layers_str.split(",")] if layers_str
              else DQN_CONFIG["network_layers"])
    net = QNetwork(layers)
    load_model(net, path)
    net.eval()
    return net, layers[0]


def run_episode(net, n_in, poll, max_steps):
    """One clean-realtime episode in a fresh browser. Returns
    (score, speed, crashed, cause) or None on a failed start."""
    d = DinoDriver(headless=False, lockstep=False)
    try:
        d.reset()
        time.sleep(0.3)
        st = d.get_state()
        if st is None:
            return None
        obs = st.to_array()[:n_in]
        last, crashed = st, False
        for _ in range(max_steps):
            a = net.predict(obs)
            d.act(a)
            time.sleep(poll)
            ns = d.get_state()
            if ns is None:
                break
            obs, last = ns.to_array()[:n_in], ns
            if ns.crashed:
                crashed = True
                break
        cause = None
        if crashed:
            cause = d.driver.execute_script(
                "return Runner.instance_.deathCause;") or "?"
        return last.score, last.speed, crashed, cause
    finally:
        d.close()


def summarize(name, results):
    scores = np.array([r[0] for r in results])
    deaths = [r for r in results if r[2]]
    capped = len(results) - len(deaths)
    exposure = scores.sum()
    msbd = exposure / len(deaths) if deaths else float("inf")
    print(f"\n== {name}: median {np.median(scores):.0f}  mean {scores.mean():.0f}"
          f"  best {scores.max():.0f}  worst {scores.min():.0f}")
    print(f"   cap-outs {capped}/{len(results)}  deaths {len(deaths)}"
          f"  MSBD {msbd:.0f}" + ("" if not deaths else
          f"  causes {dict(Counter(r[3] or '?' for r in deaths))}"))
    return scores.mean(), msbd


def main(args):
    net_a, nin_a = load_net(args.a_load, args.a_layers)
    net_b, nin_b = load_net(args.b_load, args.b_layers)
    poll_a = GAME_CONFIG["poll_interval"] if args.a_poll is None else args.a_poll
    poll_b = GAME_CONFIG["poll_interval"] if args.b_poll is None else args.b_poll

    res_a, res_b = [], []
    for ep in range(args.episodes):
        for tag, net, nin, poll, cap, res in (
            ("A", net_a, nin_a, poll_a, args.a_max_steps, res_a),
            ("B", net_b, nin_b, poll_b, args.b_max_steps, res_b),
        ):
            r = run_episode(net, nin, poll, cap)
            if r is None:
                print(f"  ep {ep:2d} {tag}: START FAILED — skipped")
                continue
            res.append(r)
            score, speed, crashed, cause = r
            state = f"died spd {speed:.1f}, {cause}" if crashed else "survived cap"
            print(f"  ep {ep:2d} {tag}: SCORE {score:8.0f}  ({state})", flush=True)

    mean_a, msbd_a = summarize(f"A ({args.a_load})", res_a)
    mean_b, msbd_b = summarize(f"B ({args.b_load})", res_b)
    lead = "A" if mean_a > mean_b else "B"
    print(f"\n== INTERLEAVED VERDICT: mean/game {mean_a:.0f} (A) vs {mean_b:.0f} (B)"
          f" — {lead} leads; MSBD {msbd_a:.0f} vs {msbd_b:.0f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--a-load", required=True, dest="a_load")
    ap.add_argument("--a-layers", default=None, dest="a_layers")
    ap.add_argument("--a-poll", type=float, default=None, dest="a_poll")
    ap.add_argument("--a-max-steps", type=int, required=True, dest="a_max_steps")
    ap.add_argument("--b-load", required=True, dest="b_load")
    ap.add_argument("--b-layers", default=None, dest="b_layers")
    ap.add_argument("--b-poll", type=float, default=None, dest="b_poll")
    ap.add_argument("--b-max-steps", type=int, required=True, dest="b_max_steps")
    ap.add_argument("--episodes", type=int, default=10,
                    help="episodes PER SIDE (total = 2x this)")
    main(ap.parse_args())
