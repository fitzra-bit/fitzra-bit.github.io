"""Execute tool calls from Claude and return (text_for_claude, html_for_panel) pairs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "factory_sim"))
sys.path.insert(0, str(Path(__file__).parent.parent))  # factory_chat root

from simulation.upgrade import UpgradeOption
from simulation.step import ProcessStep
from simulation.line import ProductionLine


# ------------------------------------------------------------------
# HTML rendering helpers
# ------------------------------------------------------------------

def _fmt_money(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"${v/1_000:.1f}K"
    return f"${v:.0f}"


def _render_pipeline_html(line: ProductionLine, label: str = "") -> str:
    from visualization.html_export import _CSS, _pipeline_html, _summary_html, _upgrade_log_html

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
    from visualization.html_export import _CSS, _pipeline_html, _summary_html, _upgrade_log_html

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
    from visualization.html_export import _CSS

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


def _render_scenario_list_html(records: list) -> str:
    from visualization.html_export import _CSS

    def _tag(t):
        colors = {
            "vendor-deal": "#89b4fa", "market-change": "#f9e2af",
            "budget": "#cba6f7", "in-flight": "#89dceb",
        }
        c = colors.get(t, "#6c7086")
        return f'<span style="background:rgba(255,255,255,.07);color:{c};font-size:.68rem;padding:1px 6px;border-radius:3px">{t}</span>'

    cards = ""
    for r in records:
        opt = r.get("optimization") or {}
        opt_html = ""
        if opt.get("profit_delta"):
            opt_html = f'<div style="color:#a6e3a1;font-size:.82rem;margin-top:6px">▲ +{_fmt_money(opt["profit_delta"])}/period optimized</div>'

        changes = r.get("changes", {})
        change_parts = []
        if changes.get("budget"):
            change_parts.append(f'Budget: {_fmt_money(changes["budget"])}')
        if changes.get("unit_value"):
            change_parts.append(f'Unit price: ${changes["unit_value"]:.2f}')
        if changes.get("upgrade_cost_overrides"):
            n = len(changes["upgrade_cost_overrides"])
            change_parts.append(f'{n} upgrade price overrides')
        changes_html = (
            f'<div style="color:#f9e2af;font-size:.72rem;margin-top:4px">'
            f'Changes: {" · ".join(change_parts)}</div>'
        ) if change_parts else ""

        in_flight = r.get("in_flight", [])
        inflight_html = ""
        if in_flight:
            items = [f"{inv['upgrade_id']} ({inv.get('status','?')})" for inv in in_flight[:3]]
            inflight_html = (
                f'<div style="color:#89dceb;font-size:.72rem;margin-top:4px">'
                f'In-flight: {", ".join(items)}'
                f'{"…" if len(in_flight) > 3 else ""}</div>'
            )

        tags_html = " ".join(_tag(t) for t in (r.get("tags") or []))
        created = r.get("created_at", "")[:10]

        cards += f"""
<div style="background:#1a1a2a;border:1px solid #2a2a3e;border-radius:10px;padding:14px 16px;display:flex;flex-direction:column;gap:6px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
    <div style="font-size:.9rem;font-weight:700;color:#cdd6f4">{r["name"]}</div>
    <div style="font-size:.68rem;color:#45475a;flex-shrink:0">{created}</div>
  </div>
  {f'<div style="display:flex;gap:4px;flex-wrap:wrap">{tags_html}</div>' if tags_html else ''}
  <div style="font-size:.78rem;color:#6c7086;line-height:1.45">{r.get("rationale","")[:120]}</div>
  <div style="font-size:.7rem;color:#45475a;font-family:monospace">ID: {r["id"]}</div>
  {changes_html}
  {inflight_html}
  {opt_html}
</div>"""

    body = f"""
<div style="padding:20px">
  <h2 style="color:#89b4fa;margin-bottom:16px">Saved Scenarios ({len(records)})</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px">
    {cards}
  </div>
  <p style="color:#45475a;font-size:.75rem;margin-top:16px">
    To load a scenario, tell OptiFlow: "load scenario [ID]" or "compare [ID1] and [ID2]"
  </p>
</div>"""

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<style>body{{background:#0a0a14;color:#cdd6f4;font-family:'Segoe UI',monospace;margin:0}}{_CSS}</style>
</head><body>{body}</body></html>"""


def _render_scenario_compare_html(lines_data: list) -> str:
    from visualization.html_export import _CSS, _pipeline_html, _summary_html

    cols = ""
    for r, line in lines_data:
        m = line.metrics()
        changes = r.get("changes", {})
        change_parts = []
        if changes.get("budget"):
            change_parts.append(f"Budget {_fmt_money(changes['budget'])}")
        if changes.get("unit_value"):
            change_parts.append(f"Price ${changes['unit_value']:.2f}")
        if changes.get("upgrade_cost_overrides"):
            change_parts.append(f"{len(changes['upgrade_cost_overrides'])} repriced")
        changes_str = " · ".join(change_parts) if change_parts else "Baseline parameters"

        opt = r.get("optimization") or {}
        opt_html = ""
        if opt.get("profit_delta"):
            opt_html = f'<div style="color:#a6e3a1;font-size:.8rem;margin:6px 0">Optimized: +{_fmt_money(opt["profit_delta"])}/pd</div>'

        cols += f"""
<div style="background:#1a1a2a;border:1px solid #2a2a3e;border-radius:8px;padding:14px;display:flex;flex-direction:column;gap:10px">
  <div>
    <div style="font-size:.9rem;font-weight:700;color:#89b4fa">{r["name"]}</div>
    <div style="font-size:.72rem;color:#f9e2af;margin-top:3px">{changes_str}</div>
    <div style="font-size:.72rem;color:#6c7086;margin-top:2px">{r.get("rationale","")[:80]}</div>
  </div>
  {_pipeline_html(line)}
  {_summary_html(line)}
  {opt_html}
</div>"""

    body = f"""
<div style="padding:20px">
  <h2 style="color:#89b4fa;margin-bottom:16px">Scenario Comparison</h2>
  <div style="display:grid;grid-template-columns:repeat({len(lines_data)},1fr);gap:16px">
    {cols}
  </div>
</div>"""

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<style>body{{background:#0a0a14;color:#cdd6f4;font-family:'Segoe UI',monospace;margin:0}}{_CSS}</style>
</head><body>{body}</body></html>"""


# ------------------------------------------------------------------
# Scenario JSON builder (for frontend configurator)
# ------------------------------------------------------------------

def _line_to_scenario_json(
    line: ProductionLine,
    plant_data: dict = None,
    scenario_id: str = None,
    scenario_name: str = None,
) -> dict:
    catalog = {}
    if plant_data:
        for u in plant_data.get("upgrade_catalog", []):
            catalog[u["id"]] = u

    return {
        "id": scenario_id,
        "name": scenario_name or line.name,
        "description": line.description,
        "unit": line.unit,
        "unit_value": line.unit_value,
        "budget": line.budget,
        "hours_per_period": line.hours_per_period,
        "periods": line.periods,
        "steps": [
            {
                "id": s.id,
                "name": s.name,
                "capacity": s.base_capacity,
                "yield_rate": s.base_yield_rate,
                "base_opex": s.base_opex,
                "upgrades": [
                    {
                        "id": u.id,
                        "name": u.name,
                        "description": u.description,
                        "capex": u.capex,
                        "opex_delta": u.opex_delta,
                        "capacity_delta": u.capacity_delta,
                        "yield_delta": u.yield_delta,
                        "max_applications": u.max_applications,
                        **({"vendor": catalog[u.id]["vendor"]}
                           if u.id in catalog and "vendor" in catalog[u.id] else {}),
                        **({"quote_date": catalog[u.id]["quote_date"]}
                           if u.id in catalog and "quote_date" in catalog[u.id] else {}),
                    }
                    for u in s.upgrades
                ],
            }
            for s in line.steps
        ],
    }


# ------------------------------------------------------------------
# Text summary helpers
# ------------------------------------------------------------------

def _line_text_summary(line: ProductionLine, label: str = "") -> str:
    prefix = f"[{label}] " if label else ""
    m = line.metrics()
    bn = line.bottleneck_step
    base = (
        f"{prefix}Bottleneck: {bn.name} ({bn.capacity:.0f} u/h). "
        f"Effective yield: {m.effective_yield*100:.1f}%. "
        f"Net output: {m.net_output_per_period:.0f} {line.unit}s/period. "
        f"Revenue: {_fmt_money(m.revenue_per_period)}/period. "
        f"OPEX: {_fmt_money(m.total_opex_per_period)}/period. "
        f"Gross profit: {_fmt_money(m.gross_profit_per_period)}/period. "
        f"CAPEX spent: {_fmt_money(m.total_capex_spent)}. "
        f"Budget remaining: {_fmt_money(line.remaining_budget)}."
    )
    if m.payback_periods < 999:
        base += f" Payback: {m.payback_periods:.1f} periods."
    return base


# ------------------------------------------------------------------
# Tool handlers
# ------------------------------------------------------------------

def tool_load_plant(inputs: dict, session: dict) -> dict:
    from plant.loader import load_plant_data, plant_to_line, apply_in_flight

    plant_data = load_plant_data()
    line = plant_to_line(plant_data)
    in_flight = plant_data.get("in_flight_investments", [])

    session["plant_data"] = plant_data
    session["line"] = line
    session["baseline_profit"] = line.gross_profit_per_period
    session["last_agent"] = None
    session["scenario_id"] = None
    session["scenario_changes"] = {}
    session["scenario_in_flight"] = []

    scenario_json = _line_to_scenario_json(line, plant_data)

    plant_info = plant_data.get("plant", {})
    catalog = plant_data.get("upgrade_catalog", [])
    m = line.metrics()
    bn = line.bottleneck_step
    step_names = " → ".join(s.name for s in line.steps)

    text_parts = [
        f"Plant loaded: {plant_info.get('name', line.name)}.",
        f"Steps: {step_names}.",
        f"Current bottleneck: {bn.name} at {bn.base_capacity:.0f} u/h.",
        f"Baseline yield: {m.effective_yield*100:.1f}%, "
        f"output: {m.net_output_per_period:.0f} {line.unit}s/period, "
        f"gross profit: {_fmt_money(m.gross_profit_per_period)}/period.",
        f"Capital available: {_fmt_money(line.budget)}.",
        f"Upgrade catalog: {len(catalog)} vendor options.",
    ]

    if in_flight:
        include = inputs.get("include_in_flight", True)
        items = [f"{inv['upgrade_id']} ({inv.get('status','approved')})" for inv in in_flight]
        line_if = apply_in_flight(line, in_flight)
        m_if = line_if.metrics()
        text_parts.append(
            f"In-flight investments ({len(in_flight)}): {', '.join(items)}. "
            f"Once operational: output {m_if.net_output_per_period:.0f} units/period, "
            f"profit {_fmt_money(m_if.gross_profit_per_period)}/period."
        )
    else:
        text_parts.append("No in-flight investments on record.")

    return {
        "text": " ".join(text_parts),
        "html": _render_pipeline_html(line, f"{plant_info.get('name', line.name)} — Current State"),
        "scenario_json": scenario_json,
    }


def tool_create_scenario(inputs: dict, session: dict) -> dict:
    from plant.loader import load_plant_data, plant_to_line
    from tools.scenario_manager import save_scenario

    plant_data = session.get("plant_data")
    if plant_data is None:
        plant_data = load_plant_data()
        session["plant_data"] = plant_data

    name = inputs["name"]
    rationale = inputs["rationale"]
    tags = inputs.get("tags", [])
    changes = inputs.get("changes", {})
    in_flight_new = inputs.get("in_flight", [])

    plant_in_flight = plant_data.get("in_flight_investments", [])
    all_in_flight = plant_in_flight + in_flight_new

    line = plant_to_line(plant_data, changes)
    session["line"] = line
    session["baseline_profit"] = line.gross_profit_per_period
    session["last_agent"] = None
    session["scenario_changes"] = changes
    session["scenario_in_flight"] = all_in_flight

    saved = save_scenario(
        name=name,
        rationale=rationale,
        changes=changes,
        in_flight=all_in_flight,
        pre_committed=[],
        tags=tags,
    )
    session["scenario_id"] = saved["id"]

    scenario_json = _line_to_scenario_json(
        line, plant_data, scenario_id=saved["id"], scenario_name=name
    )

    baseline = line.reset()
    m = baseline.metrics()
    bn = baseline.bottleneck_step

    catalog = {u["id"]: u for u in plant_data.get("upgrade_catalog", [])}
    change_desc = []
    if changes.get("budget"):
        change_desc.append(f"budget {_fmt_money(changes['budget'])}")
    if changes.get("unit_value"):
        change_desc.append(f"unit price ${changes['unit_value']:.2f}")
    if changes.get("hours_per_period"):
        change_desc.append(f"hours/period {changes['hours_per_period']:.0f}")
    for uid, cost in (changes.get("upgrade_cost_overrides") or {}).items():
        uname = catalog.get(uid, {}).get("name", uid)
        change_desc.append(f"{uname} repriced to {_fmt_money(cost)}")

    inflight_str = ""
    if in_flight_new:
        items = [f"{inv['upgrade_id']} ({inv.get('status','approved')})" for inv in in_flight_new]
        inflight_str = f" New in-flight tracked: {', '.join(items)}."

    text = (
        f"Scenario '{name}' saved (ID: {saved['id']}). "
        f"Rationale: {rationale}. "
        + (f"Changes from baseline: {'; '.join(change_desc)}. " if change_desc
           else "No parameter changes from baseline plant. ")
        + inflight_str
        + f" Baseline metrics: {bn.name} bottleneck ({bn.base_capacity:.0f} u/h), "
        + f"yield {m.effective_yield*100:.1f}%, "
        + f"profit {_fmt_money(m.gross_profit_per_period)}/period, "
        + f"budget {_fmt_money(line.budget)}."
    )

    return {
        "text": text,
        "html": _render_pipeline_html(baseline, f"{name} — Baseline"),
        "scenario_json": scenario_json,
    }


def tool_save_current_as_scenario(inputs: dict, session: dict) -> dict:
    from tools.scenario_manager import save_scenario

    line = session.get("line")
    if line is None:
        return {"text": "No scenario loaded. Load the plant first.", "html": None}

    name = inputs["name"]
    rationale = inputs["rationale"]
    tags = inputs.get("tags", [])

    saved = save_scenario(
        name=name,
        rationale=rationale,
        changes=session.get("scenario_changes", {}),
        in_flight=session.get("scenario_in_flight", []),
        pre_committed=[],
        tags=tags,
    )
    session["scenario_id"] = saved["id"]

    text = (
        f"Scenario '{name}' saved (ID: {saved['id']}). "
        f"Rationale: {rationale}. "
        f"Find it in the Scenarios tab."
    )
    return {"text": text, "html": None}


def tool_list_scenarios(inputs: dict, session: dict) -> dict:
    from tools.scenario_manager import list_scenarios as _list_all

    records = _list_all()
    if not records:
        return {"text": "No scenarios saved yet. Create a scenario first.", "html": None}

    lines_text = []
    for r in records:
        opt = r.get("optimization") or {}
        opt_str = (
            f", optimized +{_fmt_money(opt['profit_delta'])}/pd"
            if opt.get("profit_delta") else ""
        )
        tag_str = f" [{', '.join(r['tags'])}]" if r.get("tags") else ""
        lines_text.append(
            f"• [{r['id']}] {r['name']}: {r.get('rationale','')[:80]}{tag_str}{opt_str}"
        )

    text = f"Saved scenarios ({len(records)}):\n" + "\n".join(lines_text)
    return {"text": text, "html": _render_scenario_list_html(records)}


def tool_load_saved_scenario(inputs: dict, session: dict) -> dict:
    from tools.scenario_manager import load_scenario
    from plant.loader import load_plant_data, plant_to_line

    scenario_id = inputs["scenario_id"]
    record = load_scenario(scenario_id)
    if record is None:
        return {"text": f"Scenario '{scenario_id}' not found.", "html": None}

    plant_data = session.get("plant_data")
    if plant_data is None:
        plant_data = load_plant_data()
        session["plant_data"] = plant_data

    changes = record.get("changes", {})
    in_flight = record.get("in_flight", [])

    line = plant_to_line(plant_data, changes)
    session["line"] = line
    session["baseline_profit"] = line.gross_profit_per_period
    session["scenario_id"] = scenario_id
    session["scenario_changes"] = changes
    session["scenario_in_flight"] = in_flight
    session["last_agent"] = None

    scenario_json = _line_to_scenario_json(
        line, plant_data, scenario_id=scenario_id, scenario_name=record["name"]
    )

    baseline = line.reset()
    m = baseline.metrics()
    bn = baseline.bottleneck_step

    text = (
        f"Loaded scenario '{record['name']}' (ID: {scenario_id}). "
        f"Rationale: {record['rationale']}. "
        f"Baseline: {bn.name} bottleneck, {m.effective_yield*100:.1f}% yield, "
        f"{_fmt_money(m.gross_profit_per_period)}/period profit."
    )
    opt = record.get("optimization") or {}
    if opt.get("profit_delta"):
        text += f" Previous optimization found +{_fmt_money(opt['profit_delta'])}/period."

    return {
        "text": text,
        "html": _render_pipeline_html(baseline, f"{record['name']} — Loaded"),
        "scenario_json": scenario_json,
    }


def tool_compare_scenarios(inputs: dict, session: dict) -> dict:
    from tools.scenario_manager import compare_scenarios as _compare
    from plant.loader import load_plant_data, plant_to_line

    scenario_ids = inputs["scenario_ids"]
    records = _compare(scenario_ids)
    if not records:
        return {"text": "No matching scenarios found.", "html": None}

    plant_data = session.get("plant_data")
    if plant_data is None:
        plant_data = load_plant_data()
        session["plant_data"] = plant_data

    lines_data = []
    for r in records:
        try:
            line = plant_to_line(plant_data, r.get("changes", {}))
            lines_data.append((r, line))
        except Exception:
            pass

    if not lines_data:
        return {"text": "Could not build comparison — check scenario IDs.", "html": None}

    text_parts = [f"Comparing {len(lines_data)} scenarios:"]
    for r, line in lines_data:
        m = line.metrics()
        opt = r.get("optimization") or {}
        opt_str = f", optimized +{_fmt_money(opt['profit_delta'])}/pd" if opt.get("profit_delta") else ""
        text_parts.append(
            f"• {r['name']}: profit {_fmt_money(m.gross_profit_per_period)}/pd, "
            f"budget {_fmt_money(line.budget)}{opt_str}"
        )

    return {
        "text": "\n".join(text_parts),
        "html": _render_scenario_compare_html(lines_data),
    }


def tool_run_baseline(session: dict) -> dict:
    line = session.get("line")
    if line is None:
        return {"text": "No scenario loaded. Call load_plant first.", "html": None}
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
        best_line, _ = run_random(line, trials=300)
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

    # Persist optimization result in saved scenario if one is active
    sid = session.get("scenario_id")
    if sid:
        try:
            from tools.scenario_manager import update_optimization
            update_optimization(sid, {
                "agent": agent,
                "profit_delta": op - bp,
                "capex_total": best_line.total_capex_spent,
                "upgrades": [(step, u) for step, u, _ in best_line.capex_log],
            })
        except Exception:
            pass

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
        summary_parts.append(
            f"{name}: +{_fmt_money(delta)}/period (capex {_fmt_money(res_line.total_capex_spent)})"
        )

    return {
        "text": "Agent comparison complete. " + "; ".join(summary_parts) + ".",
        "html": _render_comparison_multi_html(results, baseline),
    }


def _build_line_from_claude_input(inputs: dict) -> ProductionLine:
    steps = []
    for i, raw_step in enumerate(inputs["steps"]):
        upgrades = []
        for j, raw_u in enumerate(raw_step.get("upgrades", [])):
            uid = raw_u["name"].lower().replace(" ", "_")[:18] + f"_{i}_{j}"
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


def tool_build_custom_scenario(inputs: dict, session: dict) -> dict:
    line = _build_line_from_claude_input(inputs)
    session["line"] = line
    session["baseline_profit"] = line.gross_profit_per_period
    session["last_agent"] = None
    session["scenario_id"] = None
    session["scenario_changes"] = {}
    session["scenario_in_flight"] = []

    n_upgrades = sum(len(s.upgrades) for s in line.steps)
    text = (
        f"Custom scenario '{line.name}' created with {len(line.steps)} steps and "
        f"{n_upgrades} upgrade options. "
        + _line_text_summary(line, "baseline")
    )
    return {
        "text": text,
        "html": _render_pipeline_html(line, f"{line.name} — Baseline"),
        "scenario_json": _line_to_scenario_json(line),
    }


# ------------------------------------------------------------------
# Dispatch
# ------------------------------------------------------------------

def execute_tool(name: str, inputs: dict, session: dict) -> dict:
    handlers = {
        "load_plant":               lambda i, s: tool_load_plant(i, s),
        "create_scenario":          lambda i, s: tool_create_scenario(i, s),
        "save_current_as_scenario": lambda i, s: tool_save_current_as_scenario(i, s),
        "list_scenarios":           lambda i, s: tool_list_scenarios(i, s),
        "load_saved_scenario":      lambda i, s: tool_load_saved_scenario(i, s),
        "compare_scenarios":        lambda i, s: tool_compare_scenarios(i, s),
        "run_baseline":             lambda i, s: tool_run_baseline(s),
        "run_optimizer":            lambda i, s: tool_run_optimizer(i, s),
        "compare_agents":           lambda i, s: tool_compare_agents(i, s),
        "build_custom_scenario":    lambda i, s: tool_build_custom_scenario(i, s),
    }
    handler = handlers.get(name)
    if handler is None:
        return {"text": f"Unknown tool: {name}", "html": None}
    return handler(inputs, session)
