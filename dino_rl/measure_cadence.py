"""E0a/E1 — Measure the real-time browser loop's timing, binned by speed band.

Zero observer effect: cadence_frames is computed inside the driver's single
get_state() script call (runningTime delta), and act latency uses Python-side
timestamps only — this loop is EXACTLY the deployment loop with no extra
browser reads. (measure_timing.py adds an extra execute_script per decision;
do not use it for deployment-faithful numbers.)

Measures, per decision:
  cadence  — game-frames elapsed between state reads (read-to-read)
  act_ms   — wall ms from state-read return to act() return: the OBSERVE->ACT
             delay. Sim and lockstep apply actions atomically at the observed
             state; the real-time loop does not. This is the timing dimension
             uniform jitter training never modeled (E1 finding).

Reports distributions overall / per speed band, plus a death-context section
comparing the final decisions before each death against the baseline.

Requires: python -m http.server 8766
Usage:    python measure_cadence.py --load runs/<run>/best_model.pt --decisions 1500
          python measure_cadence.py --load ... --maxspeed 7.5 --no-birds   (death farm)
"""
import argparse
import time

import numpy as np

from config import DQN_CONFIG, GAME_CONFIG
from game.chrome_driver import DinoDriver
from agents.dqn.network import QNetwork
from logger import load_model

BANDS = [("windup <8", 0.0, 8.0), ("mid 8-11", 8.0, 11.0), ("cruise >=11", 11.0, 99.0)]
DEATH_WINDOW = 20   # decisions before each death to profile separately


def report(name, cad, act):
    if not len(cad):
        print(f"  {name:14s}  (no samples)")
        return
    c, a = np.array(cad), np.array(act)
    print(f"  {name:14s}  n={len(c):5d}  cadence: mean {c.mean():.2f} p95 "
          f"{np.percentile(c, 95):.1f} p99 {np.percentile(c, 99):.1f} max {c.max():.1f} "
          f">6fr {100 * (c > 6).mean():.1f}%  |  act_ms: mean {a.mean():.1f} p95 "
          f"{np.percentile(a, 95):.1f} p99 {np.percentile(a, 99):.1f} max {a.max():.0f}")


def main(args):
    layers = ([int(x) for x in args.layers.split(",")] if args.layers
              else DQN_CONFIG["network_layers"])
    n_in = layers[0]
    net = QNetwork(layers)
    load_model(net, args.load)
    net.eval()
    poll = GAME_CONFIG["poll_interval"] if args.poll is None else args.poll

    d = DinoDriver(headless=args.headless, lockstep=False)
    if args.maxspeed or args.no_birds:
        params = []
        if args.maxspeed:
            params.append(f"maxspeed={args.maxspeed}")
        if args.no_birds:
            params.append("birds=0")
        d.load_url(GAME_CONFIG["game_url"] + "?" + "&".join(params))

    samples = []            # (cadence, speed, act_ms)
    death_idxs = []         # index into samples at each death
    try:
        d.reset()
        time.sleep(0.3)
        st = d.get_state()
        obs = st.to_array()[:n_in]
        first = True        # first cadence after reset is a nominal placeholder
        while len(samples) < args.decisions:
            a = net.predict(obs)
            t0 = time.perf_counter()
            d.act(a)
            act_ms = (time.perf_counter() - t0) * 1000.0
            time.sleep(poll)
            ns = d.get_state()
            if ns is None:
                break
            if not first:
                samples.append((ns.cadence_frames, ns.speed, act_ms))
            first = False
            obs = ns.to_array()[:n_in]
            if ns.crashed:
                death_idxs.append(len(samples) - 1)
                d.reset()
                time.sleep(0.3)
                st = d.get_state()
                if st is None:
                    break
                obs = st.to_array()[:n_in]
                first = True
    finally:
        d.close()

    cad = np.array([s[0] for s in samples])
    spd = np.array([s[1] for s in samples])
    act = np.array([s[2] for s in samples])
    if args.dump:
        np.save(args.dump, cad)
        print(f"[dumped {len(cad)} cadence samples -> {args.dump}]")
    print(f"\n{'VISIBLE' if not args.headless else 'HEADLESS'} loop timing — "
          f"{len(samples)} decisions, {len(death_idxs)} death(s). "
          f"Trained jitter: {DQN_CONFIG.get('action_repeat_min')}-"
          f"{DQN_CONFIG.get('action_repeat_max')} frames/decision.")
    report("ALL", cad, act)
    for name, lo, hi in BANDS:
        m = (spd >= lo) & (spd < hi)
        report(name, cad[m], act[m])

    if death_idxs:
        # death context vs baseline: is timing worse right before deaths?
        pre = np.zeros(len(samples), dtype=bool)
        for di in death_idxs:
            pre[max(0, di - DEATH_WINDOW):di + 1] = True
        print(f"\n  death context (last {DEATH_WINDOW} decisions before each death) "
              f"vs baseline:")
        report("pre-death", cad[pre], act[pre])
        report("baseline", cad[~pre], act[~pre])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", required=True)
    ap.add_argument("--decisions", type=int, default=1500)
    ap.add_argument("--poll", type=float, default=None,
                    help="override GAME_CONFIG poll_interval (s) — E12 poll-rate "
                         "sweep; the realized cadence floor is what matters, "
                         "not the requested rate")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--maxspeed", type=float, default=None)
    ap.add_argument("--no-birds", action="store_true", dest="no_birds")
    ap.add_argument("--dump", default=None,
                    help="save raw cadence samples to this .npy (for DinoEnv cadence_samples)")
    ap.add_argument("--layers", default=None,
                    help="comma-separated network layers for older checkpoints, e.g. 20,128,64")
    main(ap.parse_args())
