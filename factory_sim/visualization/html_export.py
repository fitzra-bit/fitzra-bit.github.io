"""Generate a self-contained HTML visualization of a ProductionLine state.

Produces a single .html file with:
 - Process flow diagram (step cards with capacity/yield bars)
 - Bottleneck highlighted in red
 - Economics summary panel
 - Optional: side-by-side baseline vs. optimized comparison
 - Optional: upgrade decision log
"""

from pathlib import Path
from typing import Optional
from simulation.line import ProductionLine


_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0f0f1a; color: #cdd6f4; font-family: 'Segoe UI', monospace; padding: 24px; }
h1 { font-size: 1.4rem; color: #89dceb; margin-bottom: 4px; }
.subtitle { color: #6c7086; font-size: 0.85rem; margin-bottom: 24px; }
h2 { font-size: 1rem; color: #89b4fa; margin: 20px 0 10px; }

/* Pipeline */
.pipeline { display: flex; align-items: stretch; overflow-x: auto; padding-bottom: 8px; gap: 0; }
.arrow { display: flex; align-items: center; padding: 0 4px; color: #45475a; font-size: 1.6rem; flex-shrink: 0; }
.step-card {
  min-width: 170px; max-width: 200px; flex-shrink: 0;
  background: #1e1e2e; border: 2px solid #313244;
  border-radius: 10px; padding: 14px 14px 12px;
}
.step-card.bottleneck {
  border-color: #f38ba8;
  box-shadow: 0 0 18px rgba(243,139,168,0.3);
}
.step-card.healthy { border-color: #a6e3a1; }
.step-name { font-weight: bold; font-size: 0.85rem; color: #cdd6f4; margin-bottom: 10px; }
.bottleneck .step-name { color: #f38ba8; }
.bn-badge {
  display: inline-block; background: #f38ba8; color: #1e1e2e;
  font-size: 0.65rem; font-weight: bold; border-radius: 4px;
  padding: 1px 5px; margin-left: 6px; vertical-align: middle;
}
.kv { display: flex; justify-content: space-between; font-size: 0.78rem; margin: 3px 0; color: #bac2de; }
.kv span:last-child { color: #cdd6f4; font-weight: 500; }
.bar-row { margin: 6px 0 2px; }
.bar-label { font-size: 0.68rem; color: #6c7086; margin-bottom: 2px; }
.bar-bg { background: #313244; height: 7px; border-radius: 4px; }
.bar-fill { height: 7px; border-radius: 4px; transition: width 0.4s; }
.cap-bar { background: #89b4fa; }
.yield-bar { background: #a6e3a1; }
.upgrades { margin-top: 8px; font-size: 0.72rem; color: #f9e2af; min-height: 16px; }

/* Summary grid */
.summary-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px; margin-top: 8px;
}
.kpi-card {
  background: #1e1e2e; border: 1px solid #313244; border-radius: 8px;
  padding: 14px 16px;
}
.kpi-label { font-size: 0.72rem; color: #6c7086; text-transform: uppercase; letter-spacing: 0.05em; }
.kpi-value { font-size: 1.35rem; font-weight: bold; color: #89dceb; margin-top: 4px; }
.kpi-card.profit .kpi-value { color: #a6e3a1; }
.kpi-card.bottleneck-kpi .kpi-value { color: #f38ba8; }

/* Comparison layout */
.comparison { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.comparison-block h2 { margin-top: 0; }
@media (max-width: 900px) { .comparison { grid-template-columns: 1fr; } }

/* Upgrade log */
.upgrade-log { list-style: none; margin-top: 8px; }
.upgrade-log li {
  background: #1e1e2e; border-left: 3px solid #cba6f7;
  padding: 7px 12px; margin-bottom: 6px; border-radius: 0 6px 6px 0;
  font-size: 0.82rem; color: #cdd6f4;
}
.upgrade-log li .cost { color: #f38ba8; font-weight: bold; float: right; }

/* Separator */
hr { border: none; border-top: 1px solid #313244; margin: 24px 0; }
"""


def _fmt_money(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"${v/1_000:.1f}K"
    return f"${v:.0f}"


def _pipeline_html(line: ProductionLine) -> str:
    bottleneck_id = line.bottleneck_step.id
    max_cap = max(s.capacity for s in line.steps)

    html = '<div class="pipeline">'
    for i, step in enumerate(line.steps):
        is_bn = step.id == bottleneck_id
        cls = "step-card bottleneck" if is_bn else "step-card healthy"
        bn_badge = '<span class="bn-badge">BOTTLENECK</span>' if is_bn else ""
        cap_pct = min(100, step.capacity / max(max_cap, 1) * 100)
        yield_pct = step.yield_rate * 100
        upgrades_html = ", ".join(
            f"{u.name} ×{u.times_applied}" for u in step.upgrades if u.times_applied > 0
        ) or "—"

        html += f"""
<div class="{cls}">
  <div class="step-name">{step.name}{bn_badge}</div>
  <div class="kv"><span>Capacity</span><span>{step.capacity:.0f} u/h</span></div>
  <div class="bar-row">
    <div class="bar-label">Capacity</div>
    <div class="bar-bg"><div class="bar-fill cap-bar" style="width:{cap_pct:.1f}%"></div></div>
  </div>
  <div class="kv"><span>Yield</span><span>{step.yield_rate*100:.1f}%</span></div>
  <div class="bar-row">
    <div class="bar-label">Yield</div>
    <div class="bar-bg"><div class="bar-fill yield-bar" style="width:{yield_pct:.1f}%"></div></div>
  </div>
  <div class="kv"><span>OPEX/pd</span><span>{_fmt_money(step.opex)}</span></div>
  <div class="upgrades">Upgrades: {upgrades_html}</div>
</div>"""
        if i < len(line.steps) - 1:
            html += '<div class="arrow">→</div>'

    html += "</div>"
    return html


def _summary_html(line: ProductionLine, baseline_profit: float = 0.0) -> str:
    m = line.metrics(baseline_profit)
    payback = f"{m.payback_periods:.1f} pd" if m.payback_periods < 9999 else "N/A"

    cards = [
        ("System Throughput", f"{m.system_throughput:.1f} u/h", "bottleneck-kpi"),
        ("Effective Yield", f"{m.effective_yield*100:.2f}%", ""),
        ("Output / Period", f"{m.net_output_per_period:.0f} units", ""),
        ("Revenue / Period", _fmt_money(m.revenue_per_period), "profit"),
        ("OPEX / Period", _fmt_money(m.total_opex_per_period), ""),
        ("Gross Profit / pd", _fmt_money(m.gross_profit_per_period), "profit"),
        ("CAPEX Spent", _fmt_money(m.total_capex_spent), ""),
        ("Budget Remaining", _fmt_money(line.remaining_budget), ""),
        ("Payback Period", payback, ""),
    ]

    html = '<div class="summary-grid">'
    for label, value, extra_cls in cards:
        html += f"""
<div class="kpi-card {extra_cls}">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value}</div>
</div>"""
    html += "</div>"
    return html


def _upgrade_log_html(line: ProductionLine) -> str:
    if not line.capex_log:
        return "<p style='color:#6c7086'>No upgrades applied.</p>"
    html = '<ul class="upgrade-log">'
    for step_name, upgrade_name, capex in line.capex_log:
        html += f'<li><strong>{step_name}</strong> — {upgrade_name} <span class="cost">{_fmt_money(capex)}</span></li>'
    html += "</ul>"
    return html


def export(
    line: ProductionLine,
    output_path: str | Path,
    baseline_line: Optional[ProductionLine] = None,
    title: Optional[str] = None,
):
    """Write a self-contained HTML file.

    If baseline_line is given, renders a before/after comparison.
    """
    output_path = Path(output_path)
    page_title = title or line.name
    baseline_profit = baseline_line.gross_profit_per_period if baseline_line else 0.0

    if baseline_line:
        content = f"""
<h1>{page_title}</h1>
<p class="subtitle">{line.description}</p>
<div class="comparison">
  <div class="comparison-block">
    <h2>Baseline</h2>
    {_pipeline_html(baseline_line)}
    {_summary_html(baseline_line)}
  </div>
  <div class="comparison-block">
    <h2>Optimized</h2>
    {_pipeline_html(line)}
    {_summary_html(line, baseline_profit)}
  </div>
</div>
<hr>
<h2>Upgrade Decisions</h2>
{_upgrade_log_html(line)}
"""
    else:
        content = f"""
<h1>{page_title}</h1>
<p class="subtitle">{line.description}</p>
<h2>Process Flow</h2>
{_pipeline_html(line)}
<h2>Economics</h2>
{_summary_html(line)}
<hr>
<h2>Upgrades Applied</h2>
{_upgrade_log_html(line)}
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title} — Factory Sim</title>
<style>{_CSS}</style>
</head>
<body>
{content}
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    return output_path
