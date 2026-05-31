GENETIC_CONFIG = {
    "population_size": 50,
    "elite_fraction": 0.20,
    "mutation_rate": 0.15,
    "mutation_scale": 0.10,
    "crossover_type": "uniform",
    "network_layers": [9, 16, 8, 3],
    "max_steps_per_episode": 20_000,
    "poll_interval": 0.05,
    "parallel_workers": 1,
}

DQN_CONFIG = {
    "lr": 1e-3,
    "gamma": 0.99,
    "epsilon_start": 1.0,
    "epsilon_end": 0.02,
    "epsilon_decay": 0.995,
    "batch_size": 64,
    "buffer_size": 10_000,
    "target_update_freq": 200,
    "network_layers": [9, 64, 64, 3],
    "max_steps_per_episode": 20_000,
    "poll_interval": 0.05,
}

GAME_CONFIG = {
    "headless": False,
    "game_url": "chrome://dino",
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
