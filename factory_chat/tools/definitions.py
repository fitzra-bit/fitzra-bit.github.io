"""Tool definitions passed to the Claude API."""

TOOL_DEFINITIONS = [
    {
        "name": "create_scenario",
        "description": (
            "Create or replace the current manufacturing scenario. "
            "Call this once you have enough information about the process — "
            "step names, approximate capacity, yield, budget. "
            "You should suggest realistic upgrade options for each step based on context "
            "(e.g. second machine, extra shift, process improvement investment)."
        ),
        "input_schema": {
            "type": "object",
            "required": ["name", "steps", "budget"],
            "properties": {
                "name": {"type": "string", "description": "Short name for this operation"},
                "description": {"type": "string"},
                "unit": {"type": "string", "description": "What is being produced (widget, part, board, etc.)"},
                "unit_value": {"type": "number", "description": "Revenue or value per unit produced ($)"},
                "budget": {"type": "number", "description": "Total investment budget available ($)"},
                "hours_per_period": {
                    "type": "number",
                    "description": "Working hours per period (default 176 = standard working month)",
                    "default": 176,
                },
                "periods": {
                    "type": "integer",
                    "description": "Planning horizon in periods for payback analysis (default 24 months)",
                    "default": 24,
                },
                "steps": {
                    "type": "array",
                    "description": "Ordered list of production steps",
                    "items": {
                        "type": "object",
                        "required": ["name", "capacity", "yield_rate"],
                        "properties": {
                            "name": {"type": "string"},
                            "capacity": {"type": "number", "description": "Units the step can process per hour"},
                            "yield_rate": {
                                "type": "number",
                                "description": "Fraction of units that pass quality check (0.0–1.0). 0.95 = 5% scrap.",
                            },
                            "base_opex": {
                                "type": "number",
                                "description": "Recurring cost per period at baseline ($). Include labor, consumables, maintenance.",
                                "default": 0,
                            },
                            "upgrades": {
                                "type": "array",
                                "description": "Investment options available for this step",
                                "items": {
                                    "type": "object",
                                    "required": ["name", "capex"],
                                    "properties": {
                                        "name": {"type": "string"},
                                        "description": {"type": "string"},
                                        "capex": {"type": "number", "description": "One-time capital cost ($)"},
                                        "opex_delta": {
                                            "type": "number",
                                            "description": "Change in recurring cost per period. Positive = more expensive, negative = saves money.",
                                            "default": 0,
                                        },
                                        "capacity_delta": {
                                            "type": "number",
                                            "description": "Additional units per hour this upgrade adds",
                                            "default": 0,
                                        },
                                        "yield_delta": {
                                            "type": "number",
                                            "description": "Improvement to yield rate (e.g. 0.03 = +3 percentage points)",
                                            "default": 0,
                                        },
                                        "max_applications": {
                                            "type": "integer",
                                            "description": "How many times this can be purchased (e.g. 2 machines)",
                                            "default": 1,
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    {
        "name": "run_baseline",
        "description": (
            "Show the current state of the production line with no upgrades applied. "
            "Call this after create_scenario to establish the starting point."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_optimizer",
        "description": (
            "Run an optimization agent to find the best investment strategy within budget. "
            "Use agent='greedy' for an instant result. "
            "Use agent='dqn' for a deeper analysis that may find non-obvious investment sequences "
            "(takes longer but can discover synergies the greedy agent misses)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "enum": ["greedy", "dqn", "random"],
                    "description": "Which optimization method to use. Default: greedy.",
                    "default": "greedy",
                },
                "budget_override": {
                    "type": "number",
                    "description": "Optional: run with a different budget than the scenario default",
                },
                "episodes": {
                    "type": "integer",
                    "description": "For DQN only: number of training episodes (default 200)",
                    "default": 200,
                },
            },
        },
    },
    {
        "name": "compare_agents",
        "description": (
            "Run all three optimization agents (greedy, random, DQN) and show a side-by-side "
            "comparison of their recommendations and outcomes. Use when the executive wants to "
            "understand the range of possible strategies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dqn_episodes": {"type": "integer", "default": 150},
                "random_trials": {"type": "integer", "default": 200},
            },
        },
    },
    {
        "name": "update_scenario",
        "description": (
            "Adjust a parameter of the current scenario and re-run the last optimization. "
            "Use for what-if questions: 'what if budget doubles', 'what if unit value increases'."
        ),
        "input_schema": {
            "type": "object",
            "required": ["parameter", "value"],
            "properties": {
                "parameter": {
                    "type": "string",
                    "enum": ["budget", "unit_value", "hours_per_period"],
                    "description": "Which parameter to change",
                },
                "value": {"type": "number", "description": "New value for the parameter"},
            },
        },
    },
]
