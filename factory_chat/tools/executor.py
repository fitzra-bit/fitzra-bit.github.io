"""Execute tool calls from Claude and return (text_for_claude, html_for_panel) pairs."""

import sys
from pathlib import Path

# Allow importing from factory_sim alongside this package
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "factory_sim"))

from simulation.upgrade import UpgradeOption
from simulation.step import ProcessStep
from simulation.line import ProductionLine


# ------------------------------------------------------------------
# HTML rendering (inline fragment, not a full page)
# ------------------------------------------------------------------

def _render_pipeline_html(line: ProductionLine, label: str = "") -> str:
    """Return self-contained HTML fragment for the results panel."""
    from visualization.html_export import _CSS, _pipeline_html, _summary_html, _upgrade_log_html, _fmt_money

    body = f"""
<div style="padding:20px">
{f'<h2 style="color:#89b4fa;margin-bottom:16px">{label}</h2>' if label else ''}
<h3 style="color:#6c7086;font-size:0.8rem;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px">
  Process Flow
</h3>
{_pipeline_html(line)}
<h3 style="color:#6c7086;font-size:0.8rem;text-transform:uppercase;letter-spacing:.06em;margin:20px 0 10px">
  Economics
</h3>
{_summary_html(line)}
"""
    if line.capex_log:
        body += f"""
<h3 style="color:#6c7086;font-size:0.8rem;text-transform:uppercase;letter-spacing:.06em;margin:20px 0 10px">
  Investments Applied
</h3>
{_upgrade_log_html(line)}
"""
    body += "</div>"

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<style>
body{{background:#0a0a14;color:#cdd6f4;font-family:'Segoe UI',monospace;margin:0}}
h2,h3{{margin:0 0 8px}}
{_CSS}
</style>
</head><body>{body}</body></html>"""


def _render_comparison_html(baseline: ProductionLine, optimized: ProductionLine, agent_label: str) -> str:
    from visualization.html_export import _CSS, _pipeline_html, _summary_html, _upgrade_log_html, _fmt_money

    bp = baseline.gross_profit_per_period
    op = optimized.gross_profit_per_period
    delta = op - bp
    delta_pct = (delta / max(abs(bp), 1)) * 100

    body = f"""
<div style="padding:20px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
  <h2 style="color:#a6e3a1;margin:0">{agent_label} Recommendation</h2>
  <div style="text-align:right">
    <div style="color:#6c7086;font-size:.75rem">PROFIT IMPROVEMENT</div>
    <div style="color:#a6e3a1;font-size:1.4rem;font-weight:bold">
      +{_fmt_money(delta)}/period &nbsp; <span style="font-size:.9rem;color:#a6e3a1">(+{delta_pct:.0f}%)</span>
    </div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
  <div>
    <h3 style="color:#6c7086;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">BEFORE</h3>
    {_pipeline_html(baseline)}
    {_summary_html(baseline)}
  </div>
  <div>
    <h3 style="color:#a6e3a1;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">AFTER OPTIMIZATION</h3>
    {_pipeline_html(optimized)}
    {_summary_html(optimized, bp)}
  </div>
</div>

<h3 style="color:#6c7086;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;margin:20px 0 10px">
  INVESTMENT SEQUENCE
</h3>
{_upgrade_log_html(optimized)}
</div>
"""
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<style>
body{{background:#0a0a14;color:#cdd6f4;font-family:'Segoe UI',monospace;margin:0}}
h2,h3{{margin:0 0 8px}}
{_CSS}
</style>
</head><body>{body}</body></html>"""


def _render_comparison_multi_html(results: list, baseline: ProductionLine) -> str:
    """Side-by-side of multiple agents."""
    from visualization.html_export import _CSS, _fmt_money

    bp = baseline.gross_profit_per_period
    cards = ""
    for agent_name, line in results:
        op = line.gross_profit_per_period
        delta = op - bp
        upgrades = ", ".join(f"{u}" for _, u, _ in line.capex_log) or "none"
        cards += f"""
<div style="background:#1e1e2e;border:1px solid #313244;border-radius:8px;padding:16px">
  <div style="font-weight:bold;color:#89b4fa;margin-bottom:8px">{agent_name}</div>
  <div style="color:#a6e3a1;font-size:1.2rem;font-weight:bold">+{_fmt_money(delta)}/pd</div>
  <div style="color:#6c7086;font-size:.75rem;margin-top:4px">Profit: {_fmt_money(op)}/period</div>
  <div style="color:#6c7086;font-size:.75rem">CAPEX: {_fmt_money(line.total_capex_spent)}</div>
  <div style="color:#cdd6f4;font-size:.75rem;margin-top:8px">{upgrades[:120]}</div>
</div>"""

    body = f"""
<div style="padding:20px">
  <h2 style="color:#89b4fa;margin-bottom:16px">Agent Comparison</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">
    {cards}
  </div>
</div>"""

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<style>body{{background:#0a0a14;color:#cdd6f4;font-family:'Segoe UI',monospace;margin:0}}{_CSS}</style>
</head><body>{body}</body></html>"""


# ------------------------------------------------------------------
# Tool handlers
# ------------------------------------------------------------------

def _fmt_money(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"${v/1_000:.1f}K"
    return f"${v:.0f}"


def _build_line_from_claude_input(inputs: dict) -> ProductionLine:
    steps = []
    for i, raw_step in enumerate(inputs["steps"]):
        upgrades = []
        for j, raw_u in enumerate(raw_step.get("upgrades", [])):
            uid = (
                raw_u["name"].lower().replace(" ", "_")[:18] + f"_{i}_{j}"
            )
            upgrades.append(
                UpgradeOption(
                    id=uid,
                    name=raw_u["name"],
                    description=raw_u.get("description", ""),
                    capex=float(raw_u.get("capex", 0)),
                    opex_delta=float(raw_u.get("opex_delta", 0)),
                    capacity_delta=float(raw_u.get("capacity_delta", 0)),
                    yield_delta=float(raw_u.get("yield_delta", 0)),
                    max_applications=int(raw_u.get("max_applications", 1)),
                )
            )
        step_id = raw_step["name"].lower().replace(" ", "_")[:15] + f"_{i}"
        steps.append(
            ProcessStep(
                id=step_id,
                name=raw_step["name"],
                base_capacity=float(raw_step["capacity"]),
                base_yield_rate=float(raw_step["yield_rate"]),
                base_opex=float(raw_step.get("base_opex", 0)),
                upgrades=upgrades,
            )
        )

    return ProductionLine(
        name=inputs["name"],
        description=inputs.get("description", ""),
        steps=steps,
        unit=inputs.get("unit", "unit"),
        unit_value=float(inputs.get("unit_value", 1.0)),
        hours_per_period=float(inputs.get("hours_per_period", 176.0)),
        budget=float(inputs["budget"]),
        periods=int(inputs.get("periods", 24)),
    )


def _line_text_summary(line: ProductionLine, label: str = "") -> str:
    prefix = f"[{label}] " if label else ""
    m = line.metrics()
    bn = line.bottleneck_step
    return (
        f"{prefix}Bottleneck: {bn.name} ({bn.capacity:.0f} u/h). "
        f"Effective yield: {m.effective_yield*100:.1f}%. "
        f"Net output: {m.net_output_per_period:.0f} {line.unit}s/period. "
        f"Revenue: {_fmt_money(m.revenue_per_period)}/period. "
        f"OPEX: {_fmt_money(m.total_opex_per_period)}/period. "
        f"Gross profit: {_fmt_money(m.gross_profit_per_period)}/period. "
        f"CAPEX spent: {_fmt_money(m.total_capex_spent)}. "
        f"Budget remaining: {_fmt_money(line.remaining_budget)}. "
        f"Payback: {m.payback_periods:.1f} periods."
        if m.payback_periods < 999 else
        f"{prefix}Bottleneck: {bn.name} ({bn.capacity:.0f} u/h). "
        f"Effective yield: {m.effective_yield*100:.1f}%. "
        f"Net output: {m.net_output_per_period:.0f} {line.unit}s/period. "
        f"Gross profit: {_fmt_money(m.gross_profit_per_period)}/period. "
        f"CAPEX: {_fmt_money(m.total_capex_spent)}."
    )


def tool_create_scenario(inputs: dict, session: dict) -> dict:
    line = _build_line_from_claude_input(inputs)
    session["line"] = line
    session["baseline_profit"] = line.gross_profit_per_period
    session["last_agent"] = None

    n_upgrades = sum(len(s.upgrades) for s in line.steps)
    text = (
        f"Scenario '{line.name}' created with {len(line.steps)} steps and "
        f"{n_upgrades} upgrade options. "
        + _line_text_summary(line, "baseline")
    )
    return {"text": text, "html": _render_pipeline_html(line, f"{line.name} — Baseline")}


def tool_run_baseline(session: dict) -> dict:
    line = session.get("line")
    if line is None:
        return {"text": "No scenario loaded. Please create a scenario first.", "html": None}
    baseline = line.reset()
    session["baseline_profit"] = baseline.gross_profit_per_period
    return {
        "text": _line_text_summary(baseline, "baseline"),
        "html": _render_pipeline_html(baseline, f"{line.name} — Baseline"),
    }


def tool_run_optimizer(inputs: dict, session: dict) -> dict:
    from rl.trainer import run_greedy, run_dqn, run_random

    line = session.get("line")
    if line is None:
        return {"text": "No scenario loaded.", "html": None}

    budget_override = inputs.get("budget_override")
    if budget_override is not None:
        line = line.clone()
        line.budget = float(budget_override)
        line.remaining_budget = float(budget_override)

    agent = inputs.get("agent", "greedy")
    session["last_agent"] = agent

    if agent == "dqn":
        episodes = int(inputs.get("episodes", 200))
        best_line, _ = run_dqn(line, episodes=episodes)
        label = f"DQN Optimization ({episodes} episodes)"
    elif agent == "random":
        trials = 300
        best_line, _ = run_random(line, trials=trials)
        label = "Random Search (300 trials)"
    else:
        best_line, _ = run_greedy(line)
        label = "Greedy ROI Optimization"

    baseline = line.reset()
    bp = baseline.gross_profit_per_period
    op = best_line.gross_profit_per_period

    upgrade_sequence = ", ".join(
        f"{u} ({step})" for step, u, _ in best_line.capex_log
    ) or "no upgrades"

    text = (
        f"[{label}] "
        + _line_text_summary(best_line, "optimized")
        + f" Upgrade sequence: {upgrade_sequence}."
        + f" Profit increase: {_fmt_money(op - bp)}/period ({(op-bp)/max(abs(bp),1)*100:.0f}%)."
    )
    return {
        "text": text,
        "html": _render_comparison_html(baseline, best_line, label),
    }


def tool_compare_agents(inputs: dict, session: dict) -> dict:
    from rl.trainer import run_greedy, run_dqn, run_random

    line = session.get("line")
    if line is None:
        return {"text": "No scenario loaded.", "html": None}

    dqn_ep = int(inputs.get("dqn_episodes", 150))
    rand_trials = int(inputs.get("random_trials", 200))

    results = []
    greedy_line, _ = run_greedy(line)
    results.append(("Greedy ROI", greedy_line))

    rand_line, _ = run_random(line, trials=rand_trials)
    results.append(("Random Search", rand_line))

    dqn_line, _ = run_dqn(line, episodes=dqn_ep)
    results.append(("DQN", dqn_line))

    baseline = line.reset()
    bp = baseline.gross_profit_per_period
    summary_parts = []
    for name, res_line in results:
        delta = res_line.gross_profit_per_period - bp
        summary_parts.append(f"{name}: +{_fmt_money(delta)}/period (capex {_fmt_money(res_line.total_capex_spent)})")

    text = "Agent comparison complete. " + "; ".join(summary_parts) + "."
    return {
        "text": text,
        "html": _render_comparison_multi_html(results, baseline),
    }


def tool_update_scenario(inputs: dict, session: dict) -> dict:
    line = session.get("line")
    if line is None:
        return {"text": "No scenario loaded.", "html": None}

    param = inputs["parameter"]
    value = float(inputs["value"])

    if param == "budget":
        line.budget = value
        line.remaining_budget = value
    elif param == "unit_value":
        line.unit_value = value
    elif param == "hours_per_period":
        line.hours_per_period = value

    session["baseline_profit"] = line.reset().gross_profit_per_period

    # Re-run last agent if one was used
    last_agent = session.get("last_agent")
    if last_agent:
        return tool_run_optimizer({"agent": last_agent}, session)

    baseline = line.reset()
    text = f"Updated {param} to {value}. " + _line_text_summary(baseline, "new baseline")
    return {"text": text, "html": _render_pipeline_html(baseline, f"{line.name} — Updated Baseline")}


# ------------------------------------------------------------------
# Dispatch
# ------------------------------------------------------------------

def execute_tool(name: str, inputs: dict, session: dict) -> dict:
    handlers = {
        "create_scenario": tool_create_scenario,
        "run_baseline": lambda i, s: tool_run_baseline(s),
        "run_optimizer": tool_run_optimizer,
        "compare_agents": tool_compare_agents,
        "update_scenario": tool_update_scenario,
    }
    handler = handlers.get(name)
    if handler is None:
        return {"text": f"Unknown tool: {name}", "html": None}

    if name in ("run_baseline",):
        return handler(inputs, session)
    return handler(inputs, session)
