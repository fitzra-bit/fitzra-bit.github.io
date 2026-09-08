"""Watch your agent play, once, in a visible browser window.

    python play.py                 one episode, window visible
    python play.py --episodes 3    three in a row
    python play.py --quiet         no per-second telemetry

This is for looking at behaviour, not for scoring. Use bench.py for numbers.
Watching is worth more than it sounds: "dies at the first cactus every time"
and "clears cacti but never birds" are different problems, and the score alone
will not tell you which one you have.
"""

import argparse
import time

from agent import Agent
from game.driver import DinoGame, ACTION_NAMES


def play_episode(game, agent, max_seconds: float, quiet: bool) -> dict:
    state = game.reset()
    start = time.time()
    steps = 0
    actions = {0: 0, 1: 0, 2: 0}
    last_report = start
    last_good = state

    while True:
        state = game.get_state()
        if state is None:                 # the browser was busy; try again
            continue
        last_good = state

        if state["crashed"]:
            break
        if time.time() - start > max_seconds:
            break

        action = agent.act(state)
        if action not in ACTION_NAMES:
            raise ValueError(
                f"act() returned {action!r}. It must be NOTHING (0), JUMP (1) "
                f"or DUCK (2) — see game/driver.py."
            )
        game.act(action)
        actions[action] += 1
        steps += 1

        now = time.time()
        if not quiet and now - last_report >= 1.0:
            ob = state["obstacles"][0] if state["obstacles"] else None
            ahead = f"{ob['kind']:<14} x={ob['x']:6.1f}" if ob else "nothing in view"
            print(f"  t={now-start:5.1f}s  score={state['score']:7.0f}  "
                  f"speed={state['speed']:5.2f}  {ahead}")
            last_report = now

    elapsed = time.time() - start
    return {
        "score": last_good["score"],
        "seconds": elapsed,
        "steps": steps,
        "decisions_per_sec": steps / elapsed if elapsed else 0.0,
        "actions": actions,
        "crashed": last_good["crashed"],
    }


def main():
    ap = argparse.ArgumentParser(description="Watch your agent play.")
    ap.add_argument("--episodes", type=int, default=1)
    ap.add_argument("--max-seconds", type=float, default=120.0,
                    help="give up on an episode after this long (default 120)")
    ap.add_argument("--headless", action="store_true", help="hide the window")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    agent = Agent()
    game = DinoGame(headless=args.headless)
    try:
        for ep in range(1, args.episodes + 1):
            print(f"\nEpisode {ep}")
            r = play_episode(game, agent, args.max_seconds, args.quiet)
            mix = "  ".join(f"{ACTION_NAMES[a]}={n}" for a, n in r["actions"].items())
            print(f"  → score {r['score']:.0f} in {r['seconds']:.1f}s  "
                  f"({r['decisions_per_sec']:.0f} decisions/sec)")
            print(f"    {mix}"
                  + ("" if r["crashed"] else "   [stopped on the time limit, not a crash]"))
    finally:
        game.close()


if __name__ == "__main__":
    main()
