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

DQN_CONFIG = {
    "lr": 5e-4,
    "gamma": 0.99,
    "epsilon_start": 1.0,
    "epsilon_end": 0.02,
    "epsilon_decay": 0.993,         # reaches ~0.02 by ep ~900
    "batch_size": 128,
    "buffer_size": 50_000,
    "target_update_freq": 500,
    "network_layers": [13, 128, 64, 3],
    "max_steps_per_episode": 20_000,
    "poll_interval": 0.025,         # 25ms — doubles control resolution for jump timing
    "death_penalty": -100.0,
    "survival_reward_scale": 0.1,   # score-delta × this per step
    "clearing_bonus": 50.0,         # reward spike when an obstacle is cleared
    "clearing_close_threshold": 0.25,  # obs1_dist must have been this close (normalised)
    "clearing_far_threshold": 0.55,    # obs1_dist must jump to at least this far after
    # Action-type shaping — all zones now use TTC (time-to-collision = obs1_dist/speed)
    # so thresholds are speed-invariant.  At 2× speed the same TTC fires at 2× dist.
    #
    # TTC zones (obs[12], already in [0,1] with clip=2):
    #   idle     : TTC > idle_ttc           obstacle far/off-screen → stand still
    #   approach : approach_ttc_near < TTC < approach_ttc_far  → teach correct action
    #   imminent : TTC < approach_ttc_near  → death/clearing reward takes over
    "idle_ttc_threshold":   0.60,      # TTC above this → penalise non-noop
    "idle_action_penalty":   8.0,      # per-step penalty for jump/duck while idle
    "approach_ttc_far":     0.40,      # enter approach zone at this TTC
    "approach_ttc_near":    0.05,      # leave approach zone (imminent) at this TTC
    "wrong_duck_penalty":   30.0,      # duck near cactus (b1=0) → subtract this
    "wrong_jump_penalty":   10.0,      # jump near bird  (b1=1) → subtract this
    # Jump accuracy shaping — rewards outcome, not just the action:
    #   jump_clear_bonus  : fires on the CLEARING step if dino was airborne (good jump)
    #   jump_outer_penalty: fires when jumping too early in approach zone (TTC > jump sweet spot)
    #   approach_ttc_jump_max: upper bound of sweet-spot window; above this → too early penalty
    "jump_sweet_bonus":         10.0,  # directional nudge: jump in sweet spot (TTC≤jump_max) near cactus
    "jump_clear_bonus":         30.0,  # outcome bonus: fires on clearing step if dino was airborne
    "jump_outer_penalty":       10.0,  # too early: jumping in outer approach zone (TTC 0.25-0.40) near cactus
    "approach_ttc_jump_max":    0.25,  # upper bound of sweet spot — TTC 0.05-0.25 = good timing window
    # Low-bird duck shaping (symmetric to jump shaping for cacti):
    #   LOW bird = PTERODACTYL with y1_norm > 0.95 (y≈160/150=1.067, must duck to survive)
    #   MID/HIGH birds = y1_norm ≤ 0.95 — noop clears them; duck/noop both fine
    "duck_approach_bonus":        20.0,  # duck near LOW bird (b1=1, y1>0.95) → add this
    "wrong_noop_low_bird_penalty": 25.0, # noop near LOW bird → subtract this
    # Airborne spam: reduced from 60 — 60 suppressed all jump exploration in early training
    "airborne_jump_penalty":    30.0,  # painful but not fatal; 60 was too heavy for exploration phase
    # Landing danger: reduced from 35 — secondary learning signal, not primary
    "landing_danger_ttc":       0.15,  # obstacle TTC threshold that triggers landing penalty
    "landing_danger_penalty":   15.0,  # learning signal for jumped-too-early (was 35, too heavy)
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
