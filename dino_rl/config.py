GENETIC_CONFIG = {
    # Legacy browser-based mode — kept as a demo of evolution vs. gradient
    # learning. Serious training happens in the sim via the DQN path.
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
    "network_layers": [15, 16, 8, 3],
    "max_steps_per_episode": 20_000,
    "poll_interval": 0.05,
    "parallel_workers": 1,
}

# ── DQN — sim-trained, sparse rewards, env-shaped curriculum ─────────────────
# Training runs against game/dino_env.py (~35k steps/sec, deterministic).
# Rewards are sparse and IDENTICAL across all curriculum phases; difficulty
# ramps through environment knobs (speed caps, birds) — see curriculum.py.
# The browser game is the eval/demo surface (python main.py --demo).
DQN_CONFIG = {
    # Network: dueling trunk (V/A heads appended internally)
    # Input is 26 (15 base + 5 v2 + 6 explicit obstacle-class one-hots;
    # see game/dino_env.py). Earlier checkpoints are incompatible.
    "network_layers": [26, 128, 64],

    # Optimisation
    "lr": 1e-4,
    "gamma": 0.99,
    "n_step": 3,                    # n-step returns — outcome signal reaches
                                    # earlier decisions 3× faster
    "batch_size": 128,
    "buffer_size": 200_000,
    "min_buffer": 5_000,
    "tau": 0.005,                   # soft target update per step

    # Exploration — step-based linear decay + noop-biased random actions
    "epsilon_start": 1.0,
    "epsilon_end": 0.05,
    "epsilon_decay_steps": 150_000,
    "explore_action_probs": [0.70, 0.15, 0.15],   # noop, jump, duck

    # Environment
    "action_repeat": 2,             # frames per decision (~30 decisions/sec)
    "max_episode_frames": 36_000,   # 10 game-minutes → episode timeout

    # Timing domain randomization (#2) — sim→real robustness, opt-in via --jitter.
    # The real wall-clock browser loop advances ~3.8 frames/decision (range 1–5,
    # see measure_timing.py); a policy trained at a fixed 2 frames can't survive
    # that jittery cadence. With --jitter, TRAINING steps sample frames uniformly
    # in [min, max]; EVAL stays fixed at eval_action_repeat (the real-loop median)
    # so the gating signal is deterministic and deployment-representative.
    "jitter": False,
    "action_repeat_min": 2,
    "action_repeat_max": 6,
    "eval_action_repeat": 4,

    # Random start speed (#2) — opt-in via --randstart. Each TRAINING episode
    # starts at a uniform speed in [start_speed_min, start_speed_max] (clamped to
    # the phase's max_speed), giving full-length practice in the data-light bird
    # band (≥8.5) where "good" trajectories are otherwise sparse. Eval unaffected.
    "randstart": False,
    "start_speed_min": 6.0,
    "start_speed_max": 12.0,

    # Ablation knobs (for crediting each change). Defaults = full v2 setup.
    "use_dissolved": True,      # dissolved time features (TTC2, traverse, time-gap)
    "use_cadence": True,        # decision-cadence feature
    "eval_metric": "median",    # gate/checkpoint on "median" (robust) or "mean"
    "seed": None,               # training seed — set for reproducible ablations

    # Rewards (constant across ALL phases — never tune these per phase)
    "survival_reward": 0.001,       # per frame, tie-breaker only
    "clear_reward": 1.0,
    "death_reward": -1.0,

    # Evaluation protocol — drives gates, checkpoints, stall detection
    "eval_every": 50,               # episodes between greedy eval rounds
    "eval_episodes": 16,            # fixed-seed episodes per round (raised from 5:
                                    # 5 seeds let a jump-all-birds policy pass by luck)
    # Eval under jitter (deterministically seeded) when training has jitter, so the
    # exam reflects DEPLOYMENT reality. A fixed-cadence eval rewards timing-fragile
    # tricks (e.g. jumping high birds) that collapse under real jitter — making the
    # checkpoint/gate signal non-representative. Still repeatable (fixed seeds).
    "eval_jitter": True,
    # best_model is selected on a FIXED deployment eval (full game + birds,
    # jittered), NOT the per-phase eval — otherwise the easy cacti phases hit
    # the score ceiling and lock best_model to a pre-bird checkpoint, discarding
    # all the bird learning. Bird-heavy so mid-jumping compounds to failure.
    "deploy_eval_params": {"birds": True, "max_speed": 13.0, "bird_weight": 0.5},
    # Full timeout, NOT a short cap: a jumper survives ~12k frames (its bird
    # failures haven't compounded yet) and hits a short cap identical to a
    # ducker, saturating selection. At 36k the jumper dies (compounds) while a
    # ducker reaches the ceiling — so best_model can finally tell them apart.
    "deploy_eval_max_frames": 36_000,

    # Phase-entry exploration (new env ⇒ re-explore briefly)
    "phase_entry_epsilon": 0.25,
    "phase_entry_explore_steps": 20_000,
}

GAME_CONFIG = {
    # Browser game — used for eval/demo only (training is in the sim).
    "headless": False,
    "game_url": "http://localhost:8766/game/dino.html",
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
