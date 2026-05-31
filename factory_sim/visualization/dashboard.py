"""Rich terminal components for live training progress and line state display."""

from typing import List
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich import box

from simulation.line import ProductionLine
from simulation.metrics import LineMetrics, compute_metrics

console = Console()


def _fmt_money(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"${v/1_000:.1f}K"
    return f"${v:.0f}"


def _spark(values: List[float], width: int = 24) -> str:
    bars = " ▁▂▃▄▅▆▇█"
    if not values:
        return " " * width
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    return "".join(bars[min(8, int((v - mn) / rng * 8))] for v in values[-width:])


def render_line_table(line: ProductionLine) -> Table:
    """Table showing every step with capacity, yield, bottleneck flag, upgrades."""
    bottleneck_id = line.bottleneck_step.id
    t = Table(box=box.SIMPLE_HEAD, show_footer=False, expand=True)
    t.add_column("Step", style="bold")
    t.add_column("Cap (u/h)", justify="right")
    t.add_column("Yield", justify="right")
    t.add_column("Eff.Out", justify="right")
    t.add_column("OPEX/pd", justify="right")
    t.add_column("Bottleneck", justify="center")
    t.add_column("Upgrades")

    for step in line.steps:
        is_bn = step.id == bottleneck_id
        style = "bold red" if is_bn else ""
        eff_out = step.capacity * step.yield_rate
        upgrades_desc = ", ".join(
            f"{u.name}×{u.times_applied}" for u in step.upgrades if u.times_applied > 0
        ) or "—"
        t.add_row(
            step.name,
            f"{step.capacity:.0f}",
            f"{step.yield_rate*100:.1f}%",
            f"{eff_out:.1f}",
            _fmt_money(step.opex),
            "[bold red]◄ HERE[/bold red]" if is_bn else "",
            upgrades_desc,
            style=style,
        )

    return t


def render_summary(line: ProductionLine, baseline_profit: float = 0.0) -> Panel:
    m = line.metrics(baseline_profit)
    g = Table.grid(padding=(0, 3))
    g.add_column(style="cyan")
    g.add_column()
    g.add_row("System throughput", f"[bold]{m.system_throughput:.1f}[/bold] u/h")
    g.add_row("Effective yield", f"[bold]{m.effective_yield*100:.2f}%[/bold]")
    g.add_row("Net output / period", f"[green]{m.net_output_per_period:.0f}[/green] units")
    g.add_row("Revenue / period", f"[green]{_fmt_money(m.revenue_per_period)}[/green]")
    g.add_row("OPEX / period", _fmt_money(m.total_opex_per_period))
    g.add_row("Gross profit / period", f"[bold yellow]{_fmt_money(m.gross_profit_per_period)}[/bold yellow]")
    g.add_row("Total CAPEX spent", _fmt_money(m.total_capex_spent))
    g.add_row("Budget remaining", _fmt_money(line.remaining_budget))
    if m.payback_periods < float("inf"):
        g.add_row("Payback period", f"{m.payback_periods:.1f} periods")
    else:
        g.add_row("Payback period", "N/A (no profit delta)")

    return Panel(g, title="[bold]Line Economics[/bold]", border_style="green")


# ------------------------------------------------------------------
# Live training dashboards
# ------------------------------------------------------------------

class DQNTrainingDash:
    def __init__(self):
        self.history: List[dict] = []
        self._live: Live = None

    def __enter__(self):
        self._live = Live(console=console, refresh_per_second=4)
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        if self._live:
            self._live.__exit__(*args)

    def update(self, record: dict):
        self.history.append(record)
        if self._live:
            self._live.update(self._render(record))

    def _render(self, r: dict) -> Panel:
        profits = [h["profit"] for h in self.history]
        g = Table.grid(padding=(0, 3))
        g.add_column(style="cyan")
        g.add_column()
        g.add_row("Episode", f"[bold]{r['episode']}[/bold]")
        g.add_row("Profit/period", f"[green]{_fmt_money(r['profit'])}[/green]")
        g.add_row("Best profit", f"[bold yellow]{_fmt_money(r['best'])}[/bold yellow]")
        g.add_row("CAPEX spent", _fmt_money(r['capex']))
        g.add_row("Epsilon (ε)", f"{r['epsilon']:.3f}")
        g.add_row("Progress", _spark(profits))
        return Panel(g, title="[bold]DQN Training[/bold]", border_style="magenta")


class RandomTrainingDash:
    def __init__(self, trials: int):
        self.trials = trials
        self.history: List[dict] = []
        self._live: Live = None

    def __enter__(self):
        self._live = Live(console=console, refresh_per_second=4)
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        if self._live:
            self._live.__exit__(*args)

    def update(self, record: dict):
        self.history.append(record)
        if self._live:
            self._live.update(self._render(record))

    def _render(self, r: dict) -> Panel:
        profits = [h["profit"] for h in self.history]
        g = Table.grid(padding=(0, 3))
        g.add_column(style="cyan")
        g.add_column()
        g.add_row("Trial", f"{r['trial']+1} / {self.trials}")
        g.add_row("This trial profit", f"[green]{_fmt_money(r['profit'])}[/green]")
        g.add_row("Best found", f"[bold yellow]{_fmt_money(r['best'])}[/bold yellow]")
        g.add_row("Progress", _spark(profits))
        return Panel(g, title="[bold]Random Search[/bold]", border_style="blue")
