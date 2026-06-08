GENETIC_CONFIG = {
    "population_size": 50,
    "elite_fraction": 0.15,
    "mutation_rate": 0.15,
    "mutation_scale_start": 0.30,
    "mutation_scale_end": 0.05,
    "mutation_scale_decay": 0.92,
    "fitness_baseline": 30.5,
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

# ── Phase 1A — Pure outcome learning ─────────────────────────────────────────
# Goal: model discovers that jumping near obstacles prevents death.
# NO intermediate penalties — only death and clearing bonus.
# Penalties during exploration bias Q(jump) negative before the model
# has any sense of timing, causing it to converge on noop.
# Add shaping layers in later phases once basic jumping is solid.
#
# Completion: 20-ep avg ≥ 200, clearing rate ≥ 0.5/ep  →  save checkpoint
#             then move to Phase 1B (add airborne penalty only)
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

    # ── Phase 1A completion trigger ───────────────────────────────────────────
    "phase1_score_threshold": 200.0,   # 20-ep avg ≥ 200 → banner + checkpoint

    # ── Phase 1B (add after 1A checkpoint) ───────────────────────────────────
    # Load 1A checkpoint, set epsilon_start: 0.3, then add only:
    #   "airborne_jump_penalty": 10.0   # prevent double-jump waste
    #
    # ── Phase 2 (add after 1B checkpoint, score ≥ 500) ───────────────────────
    # Load 1B checkpoint, set epsilon_start: 0.2, then add:
    #   "jump_approach_bonus":  10.0    # gentle nudge toward obstacle
    #   "idle_action_penalty":   3.0    # very mild — obstacle far
    #   "idle_ttc_threshold":    0.60
    #   "approach_ttc_far":      0.25   # tighter window than before
    #   "approach_ttc_near":     0.05
    #
    # ── Phase 3 (convergence, score ≥ 1000) ──────────────────────────────────
    # No new signals — run to convergence, epsilon_start: 0.1
    #
    # ── Phase 4+ (birds) — see curriculum plan ───────────────────────────────
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
