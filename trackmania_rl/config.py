"""Hyperparameters for the Trackmania SAC trainer."""

SAC_CONFIG: dict = {
    # Network
    "hidden":          [256, 256],  # shared hidden sizes for actor and critics

    # Optimiser
    "lr":              3e-4,
    "gamma":           0.99,
    "tau":             0.005,       # soft target update coefficient
    "target_entropy":  -2.0,        # H* = −n_actions; auto-tuned α targets this

    # Replay
    "buffer_size":     1_000_000,
    "min_buffer":      5_000,       # warm-up: random actions until this full
    "batch_size":      256,

    # Episode / eval
    "max_episode_frames": 18_000,   # ~5 game-minutes at 60 Hz (not the eval cap)
    "eval_every":      50,          # episodes between greedy eval runs
    "eval_episodes":   5,           # fixed-seed greedy episodes per eval
}
