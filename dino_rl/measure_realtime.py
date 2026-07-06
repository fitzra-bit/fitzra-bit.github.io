"""Ground-truth measurement of the REAL wall-clock browser loop.

For a model playing the real browser, per decision we record:
  - cadence: game-frames advanced between successive get_state calls
  - latency: game-frames advanced DURING one decision (get_state -> act applied)
    i.e. how stale the observed state is by the time the action lands
And on death: the speed and cause. Plus cap-reach rate.

This tells us whether the sim-to-real gap is cadence (frame count) or latency
(staleness) — measured, not theorized.

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

MS_PER_FRAME = 1000.0 / 60.0
RT = "return Runner.instance_.runningTime;"


def main(args):
    net = QNetwork(DQN_CONFIG["network_layers"])
    load_model(net, args.load)
    net.eval()
    poll = GAME_CONFIG["poll_interval"]

    d = DinoDriver(headless=args.headless, lockstep=False)
    cadences, latencies, death_speeds = [], [], []
    causes = Counter()
    capped = died = 0
    try:
        for ep in range(args.episodes):
            d.reset(); time.sleep(0.3)
            st = d.get_state()
            if st is None:
                continue
            obs = st.to_array()
            prev_rt = d.driver.execute_script(RT)
            steps = 0
            crashed = False
            for _ in range(args.max_steps):
                rt_obs = d.driver.execute_script(RT)     # game clock at observation
                a = net.predict(obs)
                d.act(a)
                rt_act = d.driver.execute_script(RT)     # game clock when action landed
                if rt_act is not None and rt_obs is not None and rt_act >= rt_obs:
                    latencies.append((rt_act - rt_obs) / MS_PER_FRAME)
                time.sleep(poll)
                ns = d.get_state()
                rt_now = d.driver.execute_script(RT)
                if rt_now is not None and prev_rt is not None and rt_now >= prev_rt:
                    cadences.append((rt_now - prev_rt) / MS_PER_FRAME)
                prev_rt = rt_now
                if ns is None:
                    break
                obs = ns.to_array(); steps += 1
                if ns.crashed:
                    crashed = True
                    death_speeds.append(ns.speed)
                    causes[d.driver.execute_script("return Runner.instance_.deathCause;") or "?"] += 1
                    break
            if crashed:
                died += 1
            else:
                capped += 1
            print(f"  ep {ep}: {'CAPPED' if not crashed else 'died spd %.1f'%ns.speed} steps {steps}")
    finally:
        d.close()

    cad = np.array(cadences); lat = np.array(latencies); ds = np.array(death_speeds)
    print(f"\n== CADENCE (frames/decision): mean {cad.mean():.2f} median {np.median(cad):.1f} "
          f"p5 {np.percentile(cad,5):.1f} p95 {np.percentile(cad,95):.1f} max {cad.max():.1f}")
    print(f"== LATENCY (staleness, frames obs->act): mean {lat.mean():.2f} median {np.median(lat):.2f} "
          f"p95 {np.percentile(lat,95):.2f} max {lat.max():.2f}")
    print(f"== OUTCOMES: capped {capped}/{args.episodes}, died {died}")
    if len(ds):
        print(f"== DEATH speed: mean {ds.mean():.1f} median {np.median(ds):.1f} "
              f"(<9 windup: {(ds<9).sum()}, >=12.5 topspeed: {(ds>=12.5).sum()} of {len(ds)})")
        print(f"== DEATH causes: {dict(causes.most_common())}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", required=True)
    ap.add_argument("--episodes", type=int, default=15)
    ap.add_argument("--max-steps", type=int, default=7000, dest="max_steps")
    ap.add_argument("--headless", action="store_true")
    main(ap.parse_args())
