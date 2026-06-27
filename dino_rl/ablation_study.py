"""Ablation study — credit each v2 change.

All runs share: --jitter --randstart, jittered 16-seed eval, seed=0, 20-input net.
One knob flipped per run. Each resulting best_model is scored by a 300-episode
failure-mode hazard (jitter 2-6), the low-variance robust metric.

Comparisons:
  full(median) vs full(mean)        -> median gating impact
  full(median) vs no-cadence        -> cadence feature impact
  no-cadence   vs no-diss+no-cadence -> dissolved features impact
  full(median) vs no-diss+no-cadence -> all v2 features vs none (under good eval)

Run:  python ablation_study.py   (≈1 hr; writes a table at the end)
"""

from collections import Counter

import numpy as np

from config import DQN_CONFIG
from curriculum import Curriculum
from logger import RunLogger, load_model
from agents.dqn.network import QNetwork
from agents.dqn.trainer import DQNTrainer
from game.dino_env import DinoEnv

SEED = 0
TRAIN_EPISODES = 1000
EVAL_EPISODES = 300

CONFIGS = [
    ("full (median)",          {}),
    ("full (mean gate)",       {"eval_metric": "mean"}),
    ("no cadence",             {"use_cadence": False}),
    ("no dissolved+cadence",   {"use_cadence": False, "use_dissolved": False}),
]


def eval_hazard(net, use_dissolved, use_cadence, episodes=EVAL_EPISODES):
    deaths = cleared = survived = 0
    causes = Counter()
    for ep in range(episodes):
        env = DinoEnv(birds=True, max_speed=13.0, action_repeat=2,
                      action_repeat_min=2, action_repeat_max=6,
                      use_dissolved=use_dissolved, use_cadence=use_cadence, seed=ep)
        obs = env.reset(seed=ep)
        done = False
        info = {}
        while not done:
            obs, _, done, info = env.step(net.predict(obs))
        cleared += info["cleared"]
        if info.get("death_cause"):
            deaths += 1
            causes[info["death_cause"]] += 1
        else:
            survived += 1
    return {
        "deaths": deaths, "survived": survived, "episodes": episodes,
        "hazard": (cleared // deaths) if deaths else None,
        "causes": dict(causes.most_common()),
    }


def main():
    results = []
    for name, override in CONFIGS:
        cfg = {**DQN_CONFIG, "jitter": True, "randstart": True, "seed": SEED, **override}
        print("\n" + "=" * 70)
        print(f"ABLATION: {name}   (seed {SEED}, {TRAIN_EPISODES} eps)")
        print("=" * 70)
        curriculum = Curriculum()
        with RunLogger(agent="dqn", cfg=cfg, resume_dir=None) as log:
            tr = DQNTrainer(episodes=TRAIN_EPISODES, cfg=cfg, logger=log,
                            curriculum=curriculum, checkpoint_every=10_000_000)
            tr.train()
            best_path = str(log.run_dir / "best_model.pt")
            best_eval = tr.best_eval
        net = QNetwork(cfg["network_layers"])
        load_model(net, best_path)
        net.eval()
        r = eval_hazard(net, cfg["use_dissolved"], cfg["use_cadence"])
        r.update(name=name, best_eval=best_eval, completed=curriculum.finished)
        results.append(r)
        print(f"  -> best_eval {best_eval:.0f} | curriculum {'DONE' if curriculum.finished else 'incomplete'}"
              f" | hazard 1-in-{r['hazard']} | survived {r['survived']}/{r['episodes']}")

    # summary table
    print("\n" + "=" * 78)
    print(f"{'config':<24}{'curric':<10}{'best_eval':<11}{'hazard':<13}{'survived':<11}")
    print("-" * 78)
    for r in results:
        hz = f"1-in-{r['hazard']}" if r['hazard'] else "0 deaths"
        print(f"{r['name']:<24}{'done' if r['completed'] else 'INCOMPL':<10}"
              f"{r['best_eval']:<11.0f}{hz:<13}{str(r['survived'])+'/'+str(r['episodes']):<11}")
    print("-" * 78)
    print("death causes per config:")
    for r in results:
        print(f"  {r['name']:<24} {r['causes']}")


if __name__ == "__main__":
    main()
