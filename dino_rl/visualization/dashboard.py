"""Rich terminal dashboard updated after each generation/episode."""

from typing import List
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
import time


console = Console()


def _sparkline(values: List[float], width: int = 20) -> str:
    bars = " ▁▂▃▄▅▆▇█"
    if not values:
        return " " * width
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    chars = [bars[min(8, int((v - mn) / rng * 8))] for v in values[-width:]]
    return "".join(chars)


class GeneticDashboard:
    def __init__(self, population_size: int):
        self.pop_size = population_size
        self.history: List[dict] = []
        self._live: Live = None

    def __enter__(self):
        self._live = Live(console=console, refresh_per_second=4)
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        if self._live:
            self._live.__exit__(*args)

    def update(self, stats: dict):
        self.history.append(stats)
        if self._live:
            self._live.update(self._render(stats))

    def _render(self, stats: dict) -> Panel:
        gen = stats.get("generation", 0)
        best = stats.get("best_this_gen", 0)
        avg = stats.get("avg_this_gen", 0)
        best_ever = stats.get("best_ever", 0)
        scores = stats.get("agent_scores", [])

        bests = [h.get("best_this_gen", 0) for h in self.history]
        spark = _sparkline(bests)

        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column()

        table.add_row("Generation", f"[bold]{gen}[/bold]")
        table.add_row("Best this gen", f"[green]{best:.1f}[/green]")
        table.add_row("Avg this gen", f"{avg:.1f}")
        table.add_row("Best ever", f"[bold yellow]{best_ever:.1f}[/bold yellow]")
        table.add_row("Progress", spark)

        if scores:
            sorted_scores = sorted(scores, reverse=True)[:5]
            top_str = "  ".join(f"{s:.0f}" for s in sorted_scores)
            table.add_row("Top-5 scores", top_str)

        return Panel(table, title="[bold]Dino RL — Genetic[/bold]", border_style="cyan")


class DQNDashboard:
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

    def update(self, stats: dict):
        self.history.append(stats)
        if self._live:
            self._live.update(self._render(stats))

    def _render(self, stats: dict) -> Panel:
        ep = stats.get("episode", 0)
        score = stats.get("score", 0)
        best = stats.get("best", 0)
        eps = stats.get("epsilon", 1.0)
        buf = stats.get("buffer", 0)

        scores = [h.get("score", 0) for h in self.history]
        spark = _sparkline(scores)

        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column()

        table.add_row("Episode", f"[bold]{ep}[/bold]")
        table.add_row("Score", f"[green]{score:.1f}[/green]")
        table.add_row("Best", f"[bold yellow]{best:.1f}[/bold yellow]")
        table.add_row("Epsilon (ε)", f"{eps:.3f}")
        table.add_row("Buffer", f"{buf}")
        table.add_row("Progress", spark)

        return Panel(table, title="[bold]Dino RL — DQN[/bold]", border_style="magenta")
