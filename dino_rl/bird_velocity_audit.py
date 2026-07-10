"""Bird closing-velocity observability audit (POMDP hypothesis test).

Birds move at speed +/- BIRD_SPEED_OFFSET (0.8), but a single state snapshot
cannot reveal the sign: the TTC feature is computed as x/speed, which is WRONG
for birds by up to ~12%. Hypothesis: residual bird deaths skew toward
fast-approaching (+offset) birds vs the ~50/50 encounter base rate. If
confirmed, frame stacking (which reveals per-frame displacement -> true
closing velocity) has a specific, mechanistic justification.

Probe env (diagnostic, NOT a comparability instrument): calibrated timing
(fe + empirical cadence + act latency) with high-speed starts to farm
top-speed bird encounters at maximum rate.

Usage:
  python bird_velocity_audit.py --load runs/<run>/best_model.pt \
      --layers 26,256,128 --episodes 100
"""
import argparse
from collections import defaultdict

import numpy as np

from config import DQN_CONFIG
from game.dino_env import DinoEnv
from agents.dqn.network import QNetwork
from logger import load_model

HNAME = {100.0: "low", 75.0: "mid", 50.0: "high"}


def main(args):
    layers = [int(x) for x in args.layers.split(",")]
    n_in = layers[0]
    net = QNetwork(layers)
    load_model(net, args.load)
    net.eval()

    cadence = np.load("measurements/cadence_visible_20260705.npy")

    # encounters[height][sign] / deaths[height][sign], sign in {+1, -1}
    encounters = defaultdict(lambda: defaultdict(int))
    deaths = defaultdict(lambda: defaultdict(int))
    nonbird_deaths = 0

    for ep in range(args.episodes):
        env = DinoEnv(
            birds=True, max_speed=13.0, bird_weight=0.5,
            start_speed_min=11.0, start_speed_max=13.0,   # farm top-speed birds
            max_frames=args.max_frames,
            action_repeat=DQN_CONFIG.get("eval_action_repeat", 4),
            action_repeat_min=DQN_CONFIG["action_repeat_min"],
            action_repeat_max=DQN_CONFIG["action_repeat_max"],
            fe=0.4138, cadence_samples=cadence, act_latency_frames=0.25,
            seed=70_000 + ep,
        )
        obs = env.reset(seed=70_000 + ep)[:n_in]
        seen = set()          # ids of birds already recorded as cleared
        done = False
        info = {"death_cause": None}
        while not done:
            obs, _, done, info = env.step(net.predict(obs))
            obs = obs[:n_in]
            # record newly-cleared birds (counted, still on the list)
            for ob in env.obstacles:
                if ob.is_bird and ob.counted and id(ob) not in seen:
                    seen.add(id(ob))
                    sign = 1 if ob.speed_offset > 0 else -1
                    encounters[ob.y][sign] += 1

        cause = info.get("death_cause")
        if cause and cause.startswith("bird_"):
            # the killer: first uncounted bird whose height matches the cause
            for ob in env.obstacles:
                if ob.is_bird and not ob.counted and HNAME.get(ob.y) == cause[5:]:
                    sign = 1 if ob.speed_offset > 0 else -1
                    deaths[ob.y][sign] += 1
                    break
        elif cause:
            nonbird_deaths += 1

        if (ep + 1) % 20 == 0:
            d = sum(sum(v.values()) for v in deaths.values())
            e = sum(sum(v.values()) for v in encounters.values())
            print(f"  ep {ep + 1}: {e} bird encounters, {d} bird deaths, "
                  f"{nonbird_deaths} non-bird deaths")

    print(f"\n== BIRD VELOCITY AUDIT — {args.episodes} eps, probe env "
          f"(start 11-13, calibrated timing) ==")
    tot_d = {s: 0 for s in (1, -1)}
    tot_e = {s: 0 for s in (1, -1)}
    for y in (100.0, 75.0, 50.0):
        e, d = encounters[y], deaths[y]
        for s in (1, -1):
            tot_e[s] += e[s]
            tot_d[s] += d[s]
        rp = d[1] / e[1] if e[1] else 0.0
        rm = d[-1] / e[-1] if e[-1] else 0.0
        print(f"  {HNAME[y]:>4} bird: encounters +{e[1]}/-{e[-1]}  "
              f"deaths +{d[1]}/-{d[-1]}  "
              f"death-rate fast {100 * rp:.2f}% vs slow {100 * rm:.2f}%")
    rp = tot_d[1] / tot_e[1] if tot_e[1] else 0.0
    rm = tot_d[-1] / tot_e[-1] if tot_e[-1] else 0.0
    print(f"\n  TOTAL: encounters +{tot_e[1]}/-{tot_e[-1]}  "
          f"deaths +{tot_d[1]}/-{tot_d[-1]}")
    print(f"  death rate per encounter: FAST(+0.8) {100 * rp:.2f}%  "
          f"SLOW(-0.8) {100 * rm:.2f}%  "
          f"ratio {rp / rm:.1f}x" if rm > 0 else
          f"  death rate per encounter: FAST {100 * rp:.2f}%  SLOW 0 deaths")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", required=True)
    ap.add_argument("--layers", default="26,256,128")
    ap.add_argument("--episodes", type=int, default=100)
    ap.add_argument("--max-frames", type=int, default=20_000, dest="max_frames")
    main(ap.parse_args())
