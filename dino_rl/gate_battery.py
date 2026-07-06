"""E0b — The gate battery: P(pass the windup gate) from a canonical start.

PASS = reach --threshold score (default 2,500) from the canonical speed-6
start. FAIL = die first. Deaths take ~30s, passes ~2min, so 20 visible
episodes run in ~30-40 min — the cheap primary metric for every experiment
arm. Full 20k-step runs (clean_realtime.py) remain the champion-crowning
instrument only.

Two modes, same protocol:
  browser (default): the deployment loop, visible unless --headless.
                     Requires: python -m http.server 8766
  --sim:             DinoEnv with the deployment-eval params (birds, jitter
                     2-6, canonical start). Hundreds of episodes in seconds.
                     Only trust it for ranking once E1 validates sim-vs-
                     visible fidelity at the gate.

Usage:
  python gate_battery.py --load runs/<run>/best_model.pt --episodes 20
  python gate_battery.py --load runs/<run>/best_model.pt --sim --episodes 200
"""
import argparse
import math
import time
from collections import Counter

import numpy as np

from config import DQN_CONFIG, GAME_CONFIG
from agents.dqn.network import QNetwork
from logger import load_model


def wilson_ci(k, n, z=1.96):
    """95% Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def summarize(results, threshold):
    """results: list of (passed, score, death_speed, death_cause)."""
    n = len(results)
    k = sum(1 for r in results if r[0])
    lo, hi = wilson_ci(k, n)
    print(f"\n== GATE (score >= {threshold:.0f}): {k}/{n} pass = {100 * k / n:.0f}%  "
          f"(95% CI {100 * lo:.0f}-{100 * hi:.0f}%)")
    s = np.array([r[1] for r in results])
    print(f"== SCORE: median {np.median(s):.0f}  p10 {np.percentile(s, 10):.0f}  "
          f"p90 {np.percentile(s, 90):.0f}  max {s.max():.0f}")
    deaths = [r for r in results if not r[0]]
    if deaths:
        ds = np.array([r[2] for r in deaths])
        causes = Counter(r[3] or "?" for r in deaths)
        print(f"== deaths {len(deaths)}: speed mean {ds.mean():.1f} "
              f"range {ds.min():.1f}-{ds.max():.1f}  causes {dict(causes.most_common())}")


def run_browser(args, net, n_in):
    from game.chrome_driver import DinoDriver
    poll = GAME_CONFIG["poll_interval"]
    d = DinoDriver(headless=args.headless, lockstep=args.lockstep)
    if args.maxspeed or args.no_birds or args.fixedstep:
        # Speed-capped / cacti-only game via dino.html URL params — e.g. cap at
        # 7.5 to hold the game inside the windup death band indefinitely
        # (discriminates speed-band effects from early-episode warmup effects).
        params = []
        if args.maxspeed:
            params.append(f"maxspeed={args.maxspeed}")
        if args.no_birds:
            params.append("birds=0")
        if args.fixedstep:
            params.append("fixedstep=1")
        d.load_url(GAME_CONFIG["game_url"] + "?" + "&".join(params))
    results = []
    try:
        for ep in range(args.episodes):
            d.reset()
            time.sleep(0.3)
            st = d.get_state()
            if st is None:
                continue
            obs = st.to_array()[:n_in]
            last = st
            passed = False
            for _ in range(args.max_steps):
                a = net.predict(obs)
                if args.lockstep:
                    # deterministic frame-stepping: same game, timing removed
                    ns = d.step(a, n_frames=args.lockstep_frames)
                else:
                    d.act(a)
                    time.sleep(poll)
                    ns = d.get_state()
                if ns is None:
                    break
                obs, last = ns.to_array()[:n_in], ns
                if ns.score >= args.threshold:
                    passed = True
                    break
                if ns.crashed:
                    break
            cause = None
            if not passed and last.crashed:
                cause = d.driver.execute_script(
                    "return Runner.instance_.deathCause;") or "?"
            results.append((passed, last.score, last.speed, cause))
            print(f"  ep {ep:2d}: {'PASS' if passed else 'FAIL'}  score {last.score:7.0f}"
                  f"{'' if passed else '  (died spd %.1f, %s)' % (last.speed, cause)}")
    finally:
        d.close()
    return results


def run_sim(args, net, n_in):
    from game.dino_env import DinoEnv
    cfg = DQN_CONFIG
    p = cfg.get("deploy_eval_params", {"birds": True, "max_speed": 13.0})
    results = []
    for ep in range(args.episodes):
        seed = args.seed + ep
        kwargs = dict(
            action_repeat=cfg.get("eval_action_repeat") or cfg["action_repeat"],
            use_dissolved=cfg.get("use_dissolved", True),
            use_cadence=cfg.get("use_cadence", True),
            max_frames=args.sim_max_frames,
            seed=seed,
            **p,
        )
        if args.maxspeed:
            kwargs["max_speed"] = args.maxspeed
        if args.no_birds:
            kwargs["birds"] = False
        if not args.no_jitter:
            kwargs["action_repeat_min"] = cfg["action_repeat_min"]
            kwargs["action_repeat_max"] = cfg["action_repeat_max"]
        if args.spike_prob > 0.0:
            kwargs["spike_prob"] = args.spike_prob
        if args.fe != 1.0:
            kwargs["fe"] = args.fe
        if args.cadence_file:
            kwargs["cadence_samples"] = np.load(args.cadence_file)
        if args.act_latency > 0.0:
            kwargs["act_latency_frames"] = args.act_latency
        env = DinoEnv(**kwargs)
        obs = env.reset(seed=seed)[:n_in]
        passed = False
        info = {"score": 0.0, "speed": 0.0, "death_cause": None}
        done = False
        while not done:
            obs, _, done, info = env.step(net.predict(obs))
            obs = obs[:n_in]
            if info["score"] >= args.threshold:
                passed = True
                break
        results.append((passed, info["score"], info["speed"], info["death_cause"]))
        if args.episodes <= 40 or (ep + 1) % 25 == 0:
            print(f"  ep {ep:3d}: {'PASS' if passed else 'FAIL'}  score {info['score']:7.0f}")
    return results


def main(args):
    layers = ([int(x) for x in args.layers.split(",")] if args.layers
              else DQN_CONFIG["network_layers"])
    n_in = layers[0]
    net = QNetwork(layers)
    load_model(net, args.load)
    net.eval()

    results = run_sim(args, net, n_in) if args.sim else run_browser(args, net, n_in)
    summarize(results, args.threshold)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", required=True)
    ap.add_argument("--episodes", type=int, default=20)
    ap.add_argument("--threshold", type=float, default=2500.0)
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--sim-max-frames", type=int, default=36_000, dest="sim_max_frames",
                    help="sim episode frame cap; raise (with a huge --threshold) "
                         "for ENDURANCE runs — where does the model really die?")
    ap.add_argument("--no-jitter", action="store_true", dest="no_jitter",
                    help="sim only: fixed eval_action_repeat instead of jitter")
    ap.add_argument("--seed", type=int, default=50_000, help="sim base seed")
    ap.add_argument("--spike-prob", type=float, default=0.0, dest="spike_prob",
                    help="sim only: P(7-9 frame cadence spike) per decision below "
                         "speed 8, per the measured visible distribution (E0a: ~0.01)")
    ap.add_argument("--fe", type=float, default=1.0,
                    help="sim only: physics quantum in frames — 0.414 matches the "
                         "visible game on the 145Hz display (E1 root cause)")
    ap.add_argument("--cadence-file", default=None, dest="cadence_file",
                    help="sim only: .npy of measured frames/decision samples — "
                         "eval clock resampled from the REAL loop instead of "
                         "uniform 2-6 jitter")
    ap.add_argument("--act-latency", type=float, default=0.0, dest="act_latency",
                    help="sim only: observe->act delay in frames (measured "
                         "visible ~0.25); action lands after the first substep(s)")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--maxspeed", type=float, default=None,
                    help="cap game speed (both modes), e.g. 7.5 = live in the windup band")
    ap.add_argument("--no-birds", action="store_true", dest="no_birds")
    ap.add_argument("--fixedstep", action="store_true",
                    help="browser only: fixed-timestep game physics (fe=1 "
                         "accumulator) — the 144Hz jump-arc fidelity fix")
    ap.add_argument("--lockstep", action="store_true",
                    help="browser only: deterministic frame-stepping (isolates "
                         "timing from physics/geometry)")
    ap.add_argument("--lockstep-frames", type=int, default=4, dest="lockstep_frames",
                    help="frames/decision in lockstep (4 = deployment median)")
    ap.add_argument("--max-steps", type=int, default=5000, dest="max_steps",
                    help="browser safety cap (threshold normally hit long before)")
    ap.add_argument("--layers", default=None,
                    help="comma-separated network layers for older checkpoints, e.g. 20,128,64")
    main(ap.parse_args())
