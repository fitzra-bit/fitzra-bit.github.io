"""The same game, without the browser. Roughly a thousand times faster.

Drop-in replacement for `game.driver.DinoGame`. Same three methods, same raw
state dictionary. If your agent works against the browser, it works against
this — change one import and nothing else:

    # from game.driver import DinoGame
    from fast_game import FastDinoGame as DinoGame

WHAT CHANGED
------------
Nothing about the game. Same physics constants, same obstacle generation, same
speed curve. What changed is that it is no longer waiting for a wall clock, so
you get tens of thousands of decisions per second instead of about thirty.

WHAT DID NOT CHANGE
-------------------
You are still scored in the real browser. `bench.py` has not moved.

This is the trade every applied RL team makes, and it has a cost you should
expect to pay: a policy tuned in here can be worse out there. The simulation
is faithful, but "faithful" and "identical" are different words. Time your
actions against a wall clock in the browser and the same policy will meet
slightly different timing than it did in here.

Finding that gap, and deciding what to do about it, is Round 2.
"""

from __future__ import annotations

from typing import Optional

from dino_env import DinoEnv, TREX_GROUND_Y

# Same action constants as the browser driver.
NOTHING = 0
JUMP = 1
DUCK = 2
ACTIONS = (NOTHING, JUMP, DUCK)
ACTION_NAMES = {NOTHING: "nothing", JUMP: "jump", DUCK: "duck"}


class FastDinoGame:
    """Mirrors game.driver.DinoGame, against the simulation.

    `action_repeat` is how many game frames pass per decision. The browser
    gives you whatever the wall clock allows — usually two or three frames'
    worth. Two is a reasonable default here. It is also a knob: it changes how
    often your agent gets to act, which changes what it can learn.
    """

    def __init__(self, headless: bool = True, action_repeat: int = 2,
                 seed: Optional[int] = None, **env_kwargs):
        self._seed = seed
        self._env = DinoEnv(action_repeat=action_repeat, **env_kwargs)
        self._done = False
        self._last_score = 0.0
        self.reset()

    # ── same three methods as the browser driver ─────────────────────────

    def reset(self, seed: Optional[int] = None) -> dict:
        self._env.reset(seed=seed if seed is not None else self._seed)
        self._done = False
        self._last_score = 0.0
        return self.get_state()

    def get_state(self) -> dict:
        """Identical shape to the browser's get_state(). Never returns None:
        there is no browser here to be busy."""
        e = self._env
        return {
            "crashed": bool(e.crashed),
            "score": float(e.score),
            "speed": float(e.speed),
            "dino_y": float(e.dino_y),
            "dino_vy": float(e.jump_vel),
            "ground_y": float(TREX_GROUND_Y),
            "jumping": bool(e.jumping),
            "ducking": bool(e.ducking),
            "obstacles": [
                {"x": float(ob.x), "y": float(ob.y), "width": float(ob.w),
                 "height": float(ob.h), "kind": ob.type}
                for ob in e.obstacles[:2]
            ],
        }

    def act(self, action: int) -> None:
        """Apply the action and advance the game.

        The browser moves on its own while you think. Here, nothing happens
        until you call this — so a loop that reads the state and never acts
        will spin forever on an unchanging world.
        """
        if self._done or self._env.crashed:
            self._done = True
            return
        _, _, done, info = self._env.step(action)
        self._last_score = info.get("score", self._last_score)
        self._done = bool(done)

    def close(self) -> None:      # nothing to close; kept for interface parity
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


if __name__ == "__main__":
    import time

    g = FastDinoGame()
    n, t0 = 0, time.time()
    episodes, scores = 0, []
    while time.time() - t0 < 5.0:
        s = g.get_state()
        if s["crashed"]:
            scores.append(s["score"])
            episodes += 1
            g.reset()
            continue
        g.act(NOTHING)
        n += 1
    dt = time.time() - t0
    print(f"{n/dt:,.0f} decisions/sec   ({episodes} episodes in {dt:.1f}s "
          f"doing nothing at all)")
    print(f"compare with about 30/sec in the browser — roughly {n/dt/30:,.0f}x")
