GENETIC_CONFIG = {
    "population_size": 50,
    "elite_fraction": 0.15,
    "mutation_rate": 0.15,
    "mutation_scale_start": 0.30,
    "mutation_scale_end": 0.05,
    "mutation_scale_decay": 0.92,
    "fitness_baseline": 46.0,   # free score from doing nothing (3s obstacle-free
                                # intro + idle survival in the original-pace game)
    "stagnation_limit": 8,
    "stagnation_inject_pct": 0.20,
    "spam_rate_threshold": 0.50,
    "spam_penalty_max": 0.75,
    "crossover_type": "uniform",
    "network_layers": [11, 16, 8, 3],
    "max_steps_per_episode": 20_000,
    "poll_interval": 0.05,
    "parallel_workers": 1,
}

# ── DQN base config = curriculum Phase 1 ─────────────────────────────────────
# Phase 1 learnings (1A/1B experiments) baked in:
#   * Pure outcome rewards first — penalties during exploration bias Q(jump)
#     negative before the model has any timing, converging on noop.
#   * Then directional nudge only (jump_approach_bonus + airborne penalty).
#   * Idle penalties arrive in Phase 2 — see curriculum.py for the full
#     declarative phase plan (thresholds, shaping layers, stall handling).
# Phase transitions, completion detection, stall recovery, and resume are
# automatic: python main.py --agent dqn  /  python main.py --agent dqn --auto
DQN_CONFIG = {
    "lr": 5e-5,                     # was 1e-4 — halved to reduce oscillation from large reward scale
    "gamma": 0.99,
    "epsilon_start": 1.0,
    "epsilon_end": 0.05,            # lower floor — 15% random was injecting too much noise into converged policy
    "epsilon_decay": 0.990,         # reaches ~0.05 by ep ~340
    "batch_size": 128,
    "buffer_size": 20_000,
    "target_update_freq": 4000,     # was 2000 — crashes follow target updates at peaks; slower updates break that cycle
    "network_layers": [13, 128, 64, 3],
    "max_steps_per_episode": 20_000,
    "poll_interval": 0.025,

    # ── Core rewards (the only active signals in Phase 1A) ───────────────────
    "death_penalty":           -50.0,   # halved — same 3:2 ratio vs clearing, half the Q-value variance
    "survival_reward_scale":     0.1,
    "clearing_bonus":           75.0,   # halved from 150 — loss was flat at 430-500 all run; reward scale too large
    "clearing_close_threshold":  0.25,
    "clearing_far_threshold":    0.55,

    # ── Phase 1B directional shaping (no idle punishment) ────────────────────
    # Pure outcome (1A) plateaued at ~1.5 clears/ep after 750 eps — policy
    # couldn't self-stabilise.  These two signals give directional labels
    # without poisoning exploration the way the idle penalty did.
    "approach_ttc_far":      0.35,   # approach zone upper bound (tighter than old 0.40)
    "approach_ttc_near":     0.05,   # approach zone lower bound
    "jump_approach_bonus":   10.0,   # +10 for jumping near cactus (not near bird)
    "airborne_jump_penalty":  5.0,   # -5 for double-jump while already airborne

    # Phase 2+ shaping (idle penalty, tighter windows) and all completion
    # thresholds live in curriculum.py — applied automatically per phase.
}

GAME_CONFIG = {
    "headless": False,
    "game_url": "http://localhost:8766/game/dino.html",  # self-hosted game
    "poll_interval": 0.05,
    "canvas_width": 600,
    "canvas_height": 150,
    "speed_norm": 20.0,
    "dist_norm": 600.0,
    "y_norm": 150.0,
}

ACTIONS = {
    0: "noop",
    1: "jump",
    2: "duck",
}
