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

# ── Phase 1 ──────────────────────────────────────────────────────────────────
# Goal: learn to jump over cacti reliably and reach score 1000+.
# Keep rewards simple — clearing bonus + death penalty + mild spam prevention.
# No jump-accuracy tuning, no duck shaping.  Birds are present (30% from
# obstacle 5) but the model just learns to noop under mid/high birds via the
# death signal.  Once best score is consistently 1000+, load this checkpoint
# and switch to Phase 2 config (accuracy + duck shaping).
DQN_CONFIG = {
    "lr": 1e-4,                      # was 5e-4 — halved to stabilise oscillating loss
    "gamma": 0.99,
    "epsilon_start": 1.0,
    "epsilon_end": 0.02,
    "epsilon_decay": 0.993,         # reaches ~0.02 by ep ~550
    "batch_size": 128,
    "buffer_size": 20_000,          # was 50k — smaller so old random experiences age out faster
    "target_update_freq": 1500,     # was 500 — give targets more time to stabilise before chasing them
    "network_layers": [13, 128, 64, 3],
    "max_steps_per_episode": 20_000,
    "poll_interval": 0.025,

    # ── Core rewards ─────────────────────────────────────────────────────────
    "death_penalty":          -100.0,
    "survival_reward_scale":     0.1,   # score-delta × this per step
    "clearing_bonus":           50.0,   # spike when any obstacle is cleared
    "clearing_close_threshold":  0.25,
    "clearing_far_threshold":    0.55,

    # ── Idle spam prevention ──────────────────────────────────────────────────
    # TTC = obs1_dist / speed (speed-invariant).  Penalise non-noop when
    # the obstacle is far so the model doesn't spam jump/duck all the time.
    "idle_ttc_threshold":  0.60,
    "idle_action_penalty":  8.0,
    "approach_ttc_far":    0.40,    # approach zone: TTC 0.05–0.40
    "approach_ttc_near":   0.05,    # imminent zone: TTC < 0.05

    # ── Approach-zone action shaping (Phase 1: directional, not accuracy) ────
    "wrong_duck_penalty":   30.0,   # duck near cactus → likely death
    "jump_approach_bonus":  30.0,   # raised from 15 — needs ~28+ to make Q(jump)>Q(noop) at current success rate
    "wrong_jump_penalty":   10.0,   # jump near bird   → usually bad
    "airborne_jump_penalty": 20.0,  # double-jump spam → wasteful

    # ── Phase 1 completion trigger ────────────────────────────────────────────
    # Trainer prints a banner and saves "phase1_complete.pt" automatically when
    # the 20-episode rolling average first exceeds this score.
    "phase1_score_threshold": 1000.0,

    # ── Phase 2 additions (not active yet) ───────────────────────────────────
    # Uncomment and load from Phase 1 checkpoint when best score ≥ 1000:
    #
    # Jump accuracy:
    #   "jump_sweet_bonus":          10.0,
    #   "jump_clear_bonus":          30.0,
    #   "jump_outer_penalty":        10.0,
    #   "approach_ttc_jump_max":     0.25,
    #   "airborne_jump_penalty":     30.0,  # raise from 20
    #   "landing_danger_ttc":        0.15,
    #   "landing_danger_penalty":    15.0,
    #
    # Duck / bird shaping:
    #   "duck_approach_bonus":        20.0,
    #   "wrong_noop_low_bird_penalty": 25.0,
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
