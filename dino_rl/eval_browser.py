"""Evaluate a saved model in the REAL browser game.

Unlike the sim eval (deterministic Python mirror), this drives the actual
dino.html through Selenium. Two loop modes:

    --lockstep   advance exactly action_repeat frames per decision, no
                 wall-clock polling (deterministic, jitter-free) — this is
                 the apples-to-apples comparison with the sim.
    (default)    real-time wall-clock polling (poll_interval) — what a human
                 watching --demo sees; subject to Selenium round-trip jitter.

Requires the game server running:  python -m http.server 8766
Usage:
    python eval_browser.py --load models/validated_20260612/best_model.pt --lockstep --episodes 5
"""

import argparse
import time

import numpy as np

from config import DQN_CONFIG, GAME_CONFIG
from game.chrome_driver import DinoDriver


def load_net(path):
    if path.endswith(".npz"):
        from agents.genetic.sim_trainer import load_genome
        return load_genome(path)
    from agents.dqn.network import QNetwork
    from logger import load_model
    net = QNetwork(DQN_CONFIG["network_layers"])
    load_model(net, path)
    net.eval()
    return net


def run(args):
    net = load_net(args.load)
    n_frames = DQN_CONFIG["action_repeat"]
    poll = GAME_CONFIG["poll_interval"]
    max_steps = args.max_steps

    driver = DinoDriver(headless=args.headless, lockstep=args.lockstep)
    mode = (f"lockstep ({n_frames} frames/decision)" if args.lockstep
            else f"real-time (poll {poll*1000:.0f}ms)")
    print(f"Model: {args.load}")
    print(f"Loop:  {mode}\n")

    scores = []
    try:
        for ep in range(args.episodes):
            driver.reset()
            if not args.lockstep:
                time.sleep(0.4)
            state = driver.get_state()
            if state is None:
                print(f"  ep {ep}: no state — is the server running?")
                continue
            obs = state.to_array()
            score = cleared = steps = 0
            crashed = False
            for _ in range(max_steps):
                a = net.predict(obs)
                if args.lockstep:
                    ns = driver.step(a, n_frames=n_frames)
                else:
                    driver.act(a)
                    time.sleep(poll)
                    ns = driver.get_state()
                if ns is None:
                    break
                obs, score, cleared = ns.to_array(), ns.score, ns.cleared
                steps += 1
                if ns.crashed:
                    crashed = True
                    break
            scores.append(score)
            tag = "" if crashed else "  (survived to step cap)"
            print(f"  ep {ep}: score {score:9.1f}  cleared {cleared:4d}  steps {steps:5d}{tag}")
    finally:
        driver.close()

    if scores:
        print(f"\n  mean {np.mean(scores):8.1f}   min {min(scores):8.1f}   max {max(scores):8.1f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Evaluate a model in the real browser game")
    p.add_argument("--load", required=True, help="path to .pt (DQN) or .npz (genetic)")
    p.add_argument("--episodes", type=int, default=5)
    p.add_argument("--lockstep", action="store_true",
                   help="deterministic frame-stepping (no wall-clock jitter)")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--max-steps", type=int, default=20_000, dest="max_steps")
    run(p.parse_args())
