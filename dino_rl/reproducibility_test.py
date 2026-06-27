"""Multi-seed reproducibility test for the bird curriculum.

For each seed: train the full curriculum (--jitter --randstart, median eval),
then score the best_model two ways — both FAST (no long rollouts):
  1. Direct-query bird behavior (synthetic states, instant): does it jump low
     birds and NOT jump mid/high (i.e., duck/run-under)?
  2. Capped-episode hazard (max_frames small so cruisers terminate quickly).

Success = most/all seeds independently learn correct per-height bird passing
(not one lucky draw). Run:  python reproducibility_test.py --seeds 1
"""

import argparse
from collections import Counter

import numpy as np

from config import DQN_CONFIG
from curriculum import Curriculum
from logger import RunLogger, load_model
from agents.dqn.network import QNetwork
from agents.dqn.trainer import DQNTrainer
from game.dino_env import DinoEnv, _Obstacle, TREX_X, TREX_W, TREX_GROUND_Y
from visualization.web_dashboard import DashboardServer

HEIGHTS = {"low": 100.0, "mid": 75.0, "high": 50.0}


def bird_jump_pct(net, speed=13.0):
    """Synthetic, instant: fraction of approach states where the net chooses JUMP,
    per bird height. Target: low high%, mid/high low%."""
    env = DinoEnv(birds=True, max_speed=speed, use_dissolved=True, use_cadence=True, seed=0)
    env.reset(seed=0)
    out = {}
    for name, y in HEIGHTS.items():
        jumps = total = 0
        for cad in (2, 4, 6):
            for d in range(5, 160, 5):
                env.speed = speed; env.dino_y = TREX_GROUND_Y; env.jump_vel = 0.0
                env.jumping = False; env.ducking = False; env.last_n_frames = cad
                env.obstacles = [_Obstacle("PTERODACTYL", TREX_X + TREX_W + d, y, 46.0, 40.0, 200.0, 0.0)]
                if int(net.predict(env._observe())) == 1:
                    jumps += 1
                total += 1
        out[name] = 100 * jumps / total
    return out


def bird_behavior_ingame(net, episodes=40, max_frames=20000):
    """In-game (NOT isolated) bird handling. Over real episodes, measures the
    fraction of frames a bird overlaps the dino while it is AIRBORNE (= jumping
    that bird), per height — plus survival/hazard. Robust where the isolated
    direct-query (bird_jump_pct) is out-of-distribution and misleading."""
    air = {100.0: 0, 75.0: 0, 50.0: 0}
    tot = {100.0: 0, 75.0: 0, 50.0: 0}
    deaths = cleared = surv = 0
    causes = Counter()
    for ep in range(episodes):
        env = DinoEnv(birds=True, max_speed=13.0, action_repeat=2,
                      action_repeat_min=2, action_repeat_max=6,
                      max_frames=max_frames, seed=ep)
        obs = env.reset(seed=ep)
        done = False
        info = {}
        while not done:
            obs, _, done, info = env.step(net.predict(obs))
            for ob in env.obstacles:
                if (ob.is_bird and ob.y in tot
                        and ob.x < TREX_X + TREX_W and ob.x + ob.w > TREX_X):
                    tot[ob.y] += 1
                    if env.jumping:
                        air[ob.y] += 1
        cleared += info["cleared"]
        if info.get("death_cause"):
            deaths += 1
            causes[info["death_cause"]] += 1
        else:
            surv += 1
    jp = {k: (100 * air[k] / tot[k] if tot[k] else 0.0) for k in tot}
    return {"low": jp[100.0], "mid": jp[75.0], "high": jp[50.0],
            "survived": surv, "episodes": episodes,
            "hazard": (cleared // deaths) if deaths else None,
            "causes": dict(causes.most_common())}


def hazard(net, episodes=120, max_frames=8000):
    deaths = cleared = survived = 0
    causes = Counter()
    for ep in range(episodes):
        env = DinoEnv(birds=True, max_speed=13.0, action_repeat=2,
                      action_repeat_min=2, action_repeat_max=6,
                      max_frames=max_frames, seed=ep)
        obs = env.reset(seed=ep); done = False; info = {}
        while not done:
            obs, _, done, info = env.step(net.predict(obs))
        cleared += info["cleared"]
        if info.get("death_cause"):
            deaths += 1; causes[info["death_cause"]] += 1
        else:
            survived += 1
    return {"hazard": (cleared // deaths) if deaths else None,
            "survived": survived, "episodes": episodes, "causes": dict(causes.most_common())}


def main(args):
    web = DashboardServer()
    web.start()                       # http://localhost:8765 — watch live
    results = []
    for seed in range(args.seeds):
        cfg = {**DQN_CONFIG, "jitter": True, "randstart": True, "seed": seed}
        print("\n" + "=" * 70 + f"\nSEED {seed}  ({args.episodes} eps)\n" + "=" * 70)
        curriculum = Curriculum()
        with RunLogger(agent="dqn", cfg=cfg, resume_dir=None) as log:
            tr = DQNTrainer(episodes=args.episodes, cfg=cfg, logger=log,
                            curriculum=curriculum, checkpoint_every=10_000_000,
                            on_episode_end=web.push)
            tr.train()
            best = str(log.run_dir / "best_model.pt")
            done = curriculum.finished
        net = QNetwork(cfg["network_layers"]); load_model(net, best); net.eval()
        bb = bird_behavior_ingame(net)   # in-game (robust), not the isolated query
        # correct bird passing: jump low, NOT jump mid/high
        ok = bb["low"] > 70 and bb["mid"] < 30 and bb["high"] < 30
        results.append(dict(seed=seed, completed=done, jump=bb, hz=bb, ok=ok))
        print(f"  seed {seed}: curric {'done' if done else 'INCOMPLETE'} | "
              f"in-game jump% low {bb['low']:.0f} mid {bb['mid']:.0f} high {bb['high']:.0f} | "
              f"hazard 1-in-{bb['hazard']} survived {bb['survived']}/{bb['episodes']} | "
              f"{'LEARNED BIRDS' if ok else 'did NOT learn birds'}")

    print("\n" + "=" * 74)
    print(f"{'seed':<6}{'curric':<10}{'jump low/mid/high':<22}{'hazard':<13}{'learned?':<10}")
    print("-" * 74)
    for r in results:
        j = r["jump"]
        jstr = "%.0f/%.0f/%.0f" % (j["low"], j["mid"], j["high"])
        hzstr = ("1-in-%d" % r["hz"]["hazard"]) if r["hz"]["hazard"] else "0 deaths"
        print(f"{r['seed']:<6}{'done' if r['completed'] else 'INCOMPL':<10}"
              f"{jstr:<22}{hzstr:<13}{'YES' if r['ok'] else 'no':<10}")
    n_ok = sum(r["ok"] for r in results)
    print("-" * 74)
    print(f"RESULT: {n_ok}/{len(results)} seeds independently learned correct bird passing")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--episodes", type=int, default=2500)
    main(ap.parse_args())
