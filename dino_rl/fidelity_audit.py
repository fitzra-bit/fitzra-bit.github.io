"""Collision-geometry fidelity audit (pure physics, no model).

For each bird height, measure the success window of each action at max speed:
  - run-under (hold noop)
  - duck (hold duck)
  - jump (sweep takeoff timing; report how many timings clear)

Tells us: are run-under/duck robust (wide/total windows), and is jumping a bird
a tiny fragile sliver (faithful — a real but hard exploit) or a wide window
(a sim-leniency bug worth fixing for fidelity)?
"""

import numpy as np
from game.dino_env import DinoEnv, _Obstacle, TREX_X, TREX_W, TREX_GROUND_Y, W

HEIGHTS = {"low": 100.0, "mid": 75.0, "high": 50.0}
SPEED = 13.0


def _fresh():
    env = DinoEnv(birds=True, max_speed=SPEED, action_repeat=1, seed=0)
    env.reset(seed=0)
    env.speed = SPEED
    env.dino_y = TREX_GROUND_Y
    env.jump_vel = 0.0
    env.jumping = False
    env.ducking = False
    return env


def simulate(height_y, plan):
    """Place one bird at the right edge; run frame-by-frame under `plan` until
    the bird passes (clear) or the dino crashes. Also reports whether the dino
    was AIRBORNE while the bird was over it (to tell a real jump-clear from a
    run-under). gap=9999 blocks new spawns."""
    env = _fresh()
    env.obstacles = [_Obstacle("PTERODACTYL", W, height_y, 46.0, 40.0, 9999.0, 0.0)]
    frame = 0
    airborne_during_overlap = False
    while True:
        env.step(plan(frame))     # action_repeat=1 → exactly one frame
        # x-overlap of bird and dino?
        if env.obstacles:
            ob = env.obstacles[0]
            if ob.x < TREX_X + TREX_W and ob.x + ob.w > TREX_X and env.jumping:
                airborne_during_overlap = True
        if env.crashed:
            return "crash", airborne_during_overlap
        if env.cleared >= 1:
            return "clear", airborne_during_overlap
        frame += 1
        if frame > 200:
            return "timeout", airborne_during_overlap


def jump_window(height_y, max_lead=60):
    """Sweep jump-takeoff frame; count only GENUINE jump attempts (dino airborne
    while the bird is over it) — excludes late takeoffs that are really run-unders."""
    clears = attempts = 0
    for t0 in range(max_lead):
        outcome, airborne = simulate(height_y, lambda f, t0=t0: 1 if f == t0 else 0)
        if not airborne:
            continue              # dino wasn't airborne over the bird = not a jump attempt
        attempts += 1
        if outcome == "clear":
            clears += 1
    return clears, attempts


def main():
    print(f"Fidelity audit — single bird at speed {SPEED}\n")
    print(f"{'height':<8}{'run-under':<12}{'duck':<10}{'jump window':<16}")
    print("-" * 46)
    for name, y in HEIGHTS.items():
        run = simulate(y, lambda f: 0)[0]
        duck = simulate(y, lambda f: 2)[0]
        jc, jn = jump_window(y)
        jw = f"{jc}/{jn} ({100*jc//jn if jn else 0}%)"
        print(f"{name:<8}{run:<12}{duck:<10}{jw:<16}")
    print("\nCorrect action per height (real game): low=jump, mid=duck, high=run-under")


if __name__ == "__main__":
    main()
