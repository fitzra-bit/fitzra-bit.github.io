"""Hyperparameters for the Trackmania SAC trainer."""

SAC_CONFIG: dict = {
    # Network
    "hidden":          [128, 128],  # shared hidden sizes for actor and critics

    # Optimiser
    "lr":              3e-4,
    "gamma":           0.99,
    "tau":             0.005,       # soft target update coefficient
    "target_entropy":  -1.0,        # H* target; -1 keeps moderate entropy (was -2 → α→0)

    # Replay
    "buffer_size":     500_000,
    "min_buffer":      2_000,       # warm-up: random actions until this full
    "batch_size":      256,

    # Episode / eval
    "max_episode_frames": 18_000,   # ~5 game-minutes at 60 Hz (not the eval cap)
    "eval_every":      50,          # episodes between greedy eval runs
    "eval_episodes":   5,           # fixed-seed greedy episodes per eval
    "update_every":    8,           # env steps between SAC updates (CPU throughput)
    "explore_std_start":  0.5,     # action noise σ at step 0 (decays to end)
    "explore_std_end":    0.05,    # action noise σ floor
    "explore_decay_steps": 500_000, # steps to decay explore noise (was 100k → collapsed too fast)
}
