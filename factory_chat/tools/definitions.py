"""Tool definitions passed to the Claude API."""

TOOL_DEFINITIONS = [
    # ── Plant & scenario management ────────────────────────────────
    {
        "name": "load_plant",
        "description": (
            "Load the pre-configured plant model. Call this at the start of any session "
            "so you know the current facility layout, step capacities, yields, and upgrade catalog "
            "with real vendor quotes. Returns the baseline metrics."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "include_in_flight": {
                    "type": "boolean",
                    "description": "If true, show projected metrics with in-flight investments applied",
                    "default": True,
                }
            },
        },
    },
    {
        "name": "create_scenario",
        "description": (
            "Create a named scenario that captures a specific set of assumption changes and "
            "saves it with a rationale. Use when the user mentions a new vendor quote, price change, "
            "budget shift, new goal, or any 'what if' question worth preserving. "
            "The scenario is saved and appears in the Scenarios tab. "
            "After creating, call run_optimizer to find the optimal strategy under these assumptions."
        ),
        "input_schema": {
            "type": "object",
            "required": ["name", "rationale"],
            "properties": {
                "name": {"type": "string", "description": "Short descriptive name (e.g. 'Haas Q1 Discount')"},
                "rationale": {
                    "type": "string",
                    "description": "Why this scenario matters — what changed and what question it answers. This will appear in the saved record.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels like 'vendor-deal', 'market-change', 'budget', 'in-flight'",
                },
                "changes": {
                    "type": "object",
                    "description": "What changes from the base plant assumptions",
                    "properties": {
                        "unit_value": {"type": "number", "description": "New revenue per unit ($)"},
                        "budget": {"type": "number", "description": "New capital budget ($)"},
                        "hours_per_period": {"type": "number", "description": "New working hours per period"},
                        "upgrade_cost_overrides": {
                            "type": "object",
                            "description": "Map of upgrade_id → new_capex. Use for vendor price changes.",
                            "additionalProperties": {"type": "number"},
                        },
                    },
                },
                "in_flight": {
                    "type": "array",
                    "description": "Investments already approved/in-progress but not yet operational",
                    "items": {
                        "type": "object",
                        "required": ["upgrade_id", "step_id"],
                        "properties": {
                            "upgrade_id": {"type": "string"},
                            "step_id": {"type": "string"},
                            "count": {"type": "integer", "default": 1},
                            "status": {
                                "type": "string",
                                "enum": ["approved", "ordered", "installing"],
                                "default": "approved",
                            },
                            "expected_operational": {"type": "string", "description": "Expected date (YYYY-MM-DD)"},
                            "notes": {"type": "string"},
                        },
                    },
                },
            },
        },
    },
    {
        "name": "save_current_as_scenario",
        "description": (
            "Save the current session state (scenario + any optimization result) as a named scenario. "
            "Call this after a successful optimization when the user wants to preserve the analysis."
        ),
        "input_schema": {
            "type": "object",
            "required": ["name", "rationale"],
            "properties": {
                "name": {"type": "string"},
                "rationale": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "list_scenarios",
        "description": "List all saved scenarios with their names, rationales, and key metrics.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "load_saved_scenario",
        "description": "Load a previously saved scenario into the current session for further analysis.",
        "input_schema": {
            "type": "object",
            "required": ["scenario_id"],
            "properties": {
                "scenario_id": {"type": "string", "description": "The ID of the saved scenario"},
            },
        },
    },
    {
        "name": "compare_scenarios",
        "description": "Compare two or more saved scenarios side by side — investments, costs, outcomes, rationale.",
        "input_schema": {
            "type": "object",
            "required": ["scenario_ids"],
            "properties": {
                "scenario_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "IDs of scenarios to compare (2-4)",
                },
            },
        },
    },

    # ── Simulation ─────────────────────────────────────────────────
    {
        "name": "run_baseline",
        "description": (
            "Show the current state of the production line with no upgrades applied. "
            "Use after load_plant or create_scenario to establish the starting point."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_optimizer",
        "description": (
            "Run an optimization agent to find the best investment strategy within budget. "
            "Use agent='greedy' for an instant result. "
            "Use agent='dqn' for a deeper analysis that may find non-obvious investment sequences."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "enum": ["greedy", "dqn", "random"],
                    "default": "greedy",
                },
                "budget_override": {"type": "number", "description": "Override scenario budget"},
                "episodes": {"type": "integer", "default": 200},
            },
        },
    },
    {
        "name": "compare_agents",
        "description": "Run all three agents and compare their recommendations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dqn_episodes": {"type": "integer", "default": 150},
                "random_trials": {"type": "integer", "default": 200},
            },
        },
    },

    # ── Ad-hoc scenario building (kept for custom processes) ────────
    {
        "name": "build_custom_scenario",
        "description": (
            "Build a scenario from scratch when the user describes a completely custom process "
            "not covered by the plant model. Use create_scenario for variations on the known plant."
        ),
        "input_schema": {
            "type": "object",
            "required": ["name", "steps", "budget"],
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "unit": {"type": "string"},
                "unit_value": {"type": "number"},
                "budget": {"type": "number"},
                "hours_per_period": {"type": "number", "default": 176},
                "periods": {"type": "integer", "default": 24},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "capacity", "yield_rate"],
                        "properties": {
                            "name": {"type": "string"},
                            "capacity": {"type": "number"},
                            "yield_rate": {"type": "number"},
                            "base_opex": {"type": "number", "default": 0},
                            "upgrades": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["name", "capex"],
                                    "properties": {
                                        "name": {"type": "string"},
                                        "description": {"type": "string"},
                                        "capex": {"type": "number"},
                                        "opex_delta": {"type": "number", "default": 0},
                                        "capacity_delta": {"type": "number", "default": 0},
                                        "yield_delta": {"type": "number", "default": 0},
                                        "max_applications": {"type": "integer", "default": 1},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
]
