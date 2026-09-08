"""The official scoreboard run. This is what your entry is judged on.

    python bench.py              Round 1  (5 episodes, 60s cap)   ~5 min
    python bench.py --round 2    Round 2  (10 episodes, 90s cap)  ~15 min

Read the whole run out to the facilitator, or screenshot it. The fingerprint
line identifies the exact agent.py that produced the score.

WHY MEDIAN, NOT BEST
--------------------
Your ranked number is the MEDIAN score across episodes, not the best one. The
game's obstacles are randomly generated, so any single run is part skill and
part luck. An agent that scores 200, 220, 240, 260, 4000 is not better than one
that scores 900 every time — it got one good roll. Median asks the fairer
question: what does this agent do on a typical run?

Best and worst are printed too, because the spread tells you something. A big
gap between them usually means one specific situation kills you.
"""

import argparse
import hashlib
import statistics
import time
from pathlib import Path

from agent import Agent
from game.driver import DinoGame

# Fixed per round so that everyone's number means the same thing.
ROUNDS = {
    1: {"episodes": 5,  "max_seconds": 60.0,  "label": "Round 1 — real time"},
    2: {"episodes": 10, "max_seconds": 90.0,  "label": "Round 2 — after the reveal"},
}


def fingerprint() -> str:
    """Short hash of agent.py, so a score can be tied to the code that made it."""
    return hashlib.sha256(Path("agent.py").read_bytes()).hexdigest()[:12]


def run_episode(game, agent, max_seconds: float) -> tuple[float, bool]:
    game.reset()
    start = time.time()
    last = game.get_state()
    while True:
        state = game.get_state()
        if state is None:
            continue
        last = state
        if state["crashed"]:
            return state["score"], True
        if time.time() - start > max_seconds:
            return state["score"], False
        game.act(agent.act(state))


def main():
    ap = argparse.ArgumentParser(description="Official benchmark run.")
    ap.add_argument("--round", type=int, choices=(1, 2), default=1)
    ap.add_argument("--show", action="store_true",
                    help="watch it (slower, and the window can steal focus)")
    args = ap.parse_args()

    cfg = ROUNDS[args.round]
    n, cap = cfg["episodes"], cfg["max_seconds"]

    print(f"\n  {cfg['label']}")
    print(f"  {n} episodes, {cap:.0f}s cap each — up to {n * cap / 60:.0f} minutes")
    print(f"  agent.py fingerprint: {fingerprint()}")
    print("  " + "-" * 52)

    agent = Agent()
    game = DinoGame(headless=not args.show)
    scores, timeouts = [], 0
    try:
        for ep in range(1, n + 1):
            t0 = time.time()
            score, crashed = run_episode(game, agent, cap)
            scores.append(score)
            if not crashed:
                timeouts += 1
            print(f"  episode {ep:>2}/{n}   score {score:>8.0f}   "
                  f"{time.time() - t0:5.1f}s" + ("" if crashed else "   [hit the time cap]"))
    finally:
        game.close()

    scores.sort()
    print("  " + "-" * 52)
    print(f"  MEDIAN   {statistics.median(scores):>8.0f}   <- your ranked score")
    print(f"  mean     {statistics.mean(scores):>8.0f}")
    print(f"  best     {max(scores):>8.0f}")
    print(f"  worst    {min(scores):>8.0f}")
    if timeouts:
        print(f"\n  {timeouts} episode(s) hit the {cap:.0f}s cap without crashing.")
        print("  That is a good problem to have — your real score is higher than this.")
    print()


if __name__ == "__main__":
    main()
