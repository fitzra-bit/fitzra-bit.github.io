# Chrome Dino RL

Reinforcement learning agents that teach themselves to play the Chrome offline dinosaur game, driven live via Selenium + JS injection.

Two learning modes:
- **Genetic** (default) — a population of agents evolves across generations; the fittest survive, reproduce, and mutate
- **DQN** — a single agent learns via Deep Q-Network with experience replay

## How it works

```
Game state (9 features)
  ├─ distance / height / width / type → obstacle 1
  ├─ distance / height          → obstacle 2
  ├─ current speed
  ├─ dino y-offset from ground
  └─ is dino jumping

Neural net (9 → 16 → 8 → 3)
  └─ output: noop | jump | duck

Genetic loop
  for each generation:
    run every agent in the live Chrome game, record score
    keep elite top-20%, breed+mutate the rest
    repeat

DQN loop
  for each episode:
    ε-greedy action selection
    store (s, a, r, s') in replay buffer
    sample minibatch → MSE loss on Q-values
    soft-sync target network every 200 steps
```

## Setup

```bash
cd dino_rl
pip install -r requirements.txt
```

Requires Chrome installed. ChromeDriver is downloaded automatically via `webdriver-manager`.

## Run

```bash
# Genetic algorithm — 100 generations, 50 agents per gen (default)
python main.py

# More generations, smaller population
python main.py --agent genetic --generations 200 --population 20

# DQN — 500 episodes
python main.py --agent dqn --episodes 500

# Headless (no browser window, faster)
python main.py --headless
```

A live dashboard renders in the terminal as training runs.

## Architecture

```
dino_rl/
├── main.py                     # Entry point + CLI
├── config.py                   # All hyperparameters
├── requirements.txt
├── game/
│   ├── chrome_driver.py        # Selenium wrapper + JS injection
│   └── game_state.py           # State dataclass + normalization
├── agents/
│   ├── base_agent.py
│   ├── neural_net.py           # numpy-only feedforward net (genetic)
│   ├── genetic/
│   │   ├── population.py       # Selection, crossover, mutation
│   │   └── trainer.py          # Episode runner + evolution loop
│   └── dqn/
│       ├── network.py          # PyTorch online + target networks
│       ├── replay_buffer.py    # Circular experience buffer
│       └── trainer.py          # ε-greedy + Q-learning update
└── visualization/
    └── dashboard.py            # Rich live terminal dashboard
```

## Tuning

All hyperparameters live in `config.py`:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `population_size` | 50 | More agents → broader search, slower per-gen |
| `elite_fraction` | 0.20 | % kept unchanged per generation |
| `mutation_rate` | 0.15 | Fraction of weights perturbed |
| `mutation_scale` | 0.10 | Gaussian noise magnitude |
| `poll_interval` | 0.05s | How often state is read (lower = more decisions) |
| DQN `epsilon_decay` | 0.995 | How fast random exploration drops off |
| DQN `gamma` | 0.99 | Future reward discount |
