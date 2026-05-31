# Factory Simulation RL

A process simulation framework for multi-step manufacturing lines. Define your line in YAML, then run reinforcement learning agents to find the optimal investment strategy within a budget.

## What it models

Each step in a production line has:
- **Capacity** (units/hour) — the raw processing rate
- **Yield rate** — fraction of units that pass quality (scrap loss)
- **OPEX** — recurring cost per period

The system throughput is constrained by the **bottleneck step** (lowest capacity). The effective yield is the product of all step yields. Net revenue = throughput × yield × unit value × hours per period.

Each step has a menu of upgrades with:
- **CAPEX** — one-time investment
- **OPEX delta** — recurring cost change
- **Capacity delta** — throughput increase
- **Yield delta** — quality improvement

## Three agents compete

| Agent | Strategy | Strength | Weakness |
|-------|----------|----------|----------|
| **Greedy ROI** | Always picks highest immediate ROI upgrade | Fast, transparent, often very good | Misses synergies; can optimize the wrong bottleneck |
| **Random Search** | Monte Carlo over random upgrade sequences | Finds unusual combinations | Needs many trials to be reliable |
| **DQN** | Learns long-horizon Q-values via experience replay | Can discover non-obvious investment ordering | Needs training time; small action space helps |

## Setup

```bash
cd factory_sim
pip install -r requirements.txt
```

## Run

```bash
# Full run: inspect baseline, then all three agents
python main.py

# Specific scenario
python main.py --scenario scenarios/widget_factory.yaml

# Just inspect the baseline (generates HTML, no training)
python main.py --inspect-only

# Single agent
python main.py --agent dqn --episodes 400
python main.py --agent greedy
python main.py --agent random --trials 500
```

Each run generates HTML reports:
- `widget_factory_baseline.html` — pipeline flow + economics at baseline
- `widget_factory_greedy.html` — before/after comparison after greedy optimization
- `widget_factory_dqn.html` — before/after for DQN result

## Define your own scenario

Create a new YAML file (copy `scenarios/widget_factory.yaml` as a template):

```yaml
scenario:
  name: "My Process"
  unit: "part"
  unit_value: 120.0        # revenue per unit ($)
  hours_per_period: 176.0  # working hours per month
  budget: 200000.0
  periods: 24

steps:
  - id: step_a
    name: "Step A"
    capacity: 100           # units/hour
    yield_rate: 0.95
    base_opex: 3000

    upgrades:
      - id: step_a_machine2
        name: "Second Machine"
        capex: 80000
        opex_delta: 3500
        capacity_delta: 100
        yield_delta: 0
        max_applications: 1

      - id: step_a_process_imp
        name: "Process Improvement"
        capex: 15000
        opex_delta: 200
        capacity_delta: 0
        yield_delta: 0.03
        max_applications: 1
```

## Architecture

```
factory_sim/
├── main.py                          # Entry point + CLI
├── requirements.txt
├── scenarios/
│   └── widget_factory.yaml          # Example 5-step line
├── simulation/
│   ├── upgrade.py                   # UpgradeOption dataclass
│   ├── step.py                      # ProcessStep (capacity, yield, opex)
│   ├── line.py                      # ProductionLine (bottleneck, metrics, apply_upgrade)
│   ├── loader.py                    # YAML → ProductionLine
│   └── metrics.py                   # KPI dataclass + calculations
├── rl/
│   ├── environment.py               # FactoryEnv (state, action space, reward)
│   └── agents/
│       ├── random_agent.py          # Random baseline
│       ├── greedy_agent.py          # Marginal ROI greedy
│       └── dqn_agent.py             # DQN with action masking
├── visualization/
│   ├── dashboard.py                 # Rich terminal live dashboards
│   └── html_export.py               # Static HTML report generator
```

## Key design decisions

**State vector**: for each step — [capacity_frac, yield_rate, opex_frac, upgrade_count_per_upgrade...] plus remaining_budget_frac. Fixed size regardless of what upgrades have been applied.

**Action space**: one discrete action per (step, upgrade) pair, plus a "stop" action. Invalid actions (budget exceeded, max_applications reached) are masked to -∞ before DQN selects.

**Reward**: `(delta_profit_per_period × periods - capex) / budget` — captures the full value of an upgrade over the planning horizon, normalized by budget so it's dimensionless.

**Bottleneck insight**: The widget factory scenario is designed so the non-obvious optimal strategy is to first fix CNC yield (via tooling + SPC), *then* add a second CNC machine. A greedy agent often adds the machine first (big immediate capacity gain) but wastes money running a high-scrap process at higher throughput.
