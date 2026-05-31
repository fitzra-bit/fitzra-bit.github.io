"""Factory Simulation RL Optimizer.

Usage:
    python main.py                                         # inspect baseline, then run all 3 agents
    python main.py --scenario scenarios/widget_factory.yaml
    python main.py --agent dqn --episodes 400
    python main.py --agent greedy                          # single greedy pass
    python main.py --agent random --trials 500
    python main.py --inspect-only                          # just show baseline HTML + table
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.rule import Rule

from simulation.loader import load_scenario
from simulation.line import ProductionLine
from visualization import dashboard as dash
from visualization.html_export import export

console = Console()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def show_baseline(line: ProductionLine, html_path: Path):
    console.print(Rule("[bold cyan]Baseline — Process Line State[/bold cyan]"))
    console.print(dash.render_line_table(line))
    console.print(dash.render_summary(line))
    export(line, html_path)
    console.print(f"\n[dim]HTML visualization saved → [bold]{html_path}[/bold][/dim]\n")


def show_result(label: str, optimized: ProductionLine, baseline: ProductionLine, html_path: Path):
    console.print(Rule(f"[bold green]{label} — Optimized Result[/bold green]"))
    console.print(dash.render_line_table(optimized))
    console.print(dash.render_summary(optimized, baseline.gross_profit_per_period))

    console.print("\n[bold]Upgrade decisions:[/bold]")
    if optimized.capex_log:
        for step_name, uname, capex in optimized.capex_log:
            console.print(f"  • {step_name}: [yellow]{uname}[/yellow]  ({_fmt_money(capex)})")
    else:
        console.print("  [dim]No upgrades applied.[/dim]")

    export(optimized, html_path, baseline_line=baseline)
    console.print(f"\n[dim]HTML saved → [bold]{html_path}[/bold][/dim]\n")


def _fmt_money(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"${v/1_000:.1f}K"
    return f"${v:.0f}"


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Factory Sim RL Optimizer")
    parser.add_argument(
        "--scenario",
        default="scenarios/widget_factory.yaml",
        help="Path to YAML scenario file",
    )
    parser.add_argument(
        "--agent",
        choices=["all", "greedy", "random", "dqn"],
        default="all",
        help="Which agent(s) to run",
    )
    parser.add_argument("--episodes", type=int, default=300, help="DQN training episodes")
    parser.add_argument("--trials", type=int, default=300, help="Random search trials")
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Show baseline only, no training",
    )
    args = parser.parse_args()

    scenario_path = Path(args.scenario)
    if not scenario_path.exists():
        console.print(f"[red]Scenario file not found: {scenario_path}[/red]")
        sys.exit(1)

    line = load_scenario(scenario_path)
    baseline = line.reset()
    out_dir = scenario_path.parent

    console.print(f"\n[bold cyan]Factory Sim RL[/bold cyan] — {line.name}\n")

    baseline_html = out_dir / f"{scenario_path.stem}_baseline.html"
    show_baseline(baseline, baseline_html)

    if args.inspect_only:
        return

    run_agents = (
        ["greedy", "random", "dqn"] if args.agent == "all" else [args.agent]
    )

    # ── Greedy ─────────────────────────────────────────────────────
    if "greedy" in run_agents:
        console.print(Rule("[bold]Running Greedy ROI Agent[/bold]"))
        from rl.trainer import run_greedy
        best_line, record = run_greedy(line)
        greedy_html = out_dir / f"{scenario_path.stem}_greedy.html"
        show_result("Greedy ROI", best_line, baseline, greedy_html)

    # ── Random ─────────────────────────────────────────────────────
    if "random" in run_agents:
        console.print(Rule("[bold]Running Random Search[/bold]"))
        from rl.trainer import run_random
        with dash.RandomTrainingDash(args.trials) as d:
            best_line, _ = run_random(line, trials=args.trials, on_trial=d.update)
        random_html = out_dir / f"{scenario_path.stem}_random.html"
        show_result("Random Search", best_line, baseline, random_html)

    # ── DQN ────────────────────────────────────────────────────────
    if "dqn" in run_agents:
        console.print(Rule("[bold]Running DQN Agent[/bold]"))
        from rl.trainer import run_dqn
        with dash.DQNTrainingDash() as d:
            best_line, _ = run_dqn(line, episodes=args.episodes, on_episode=d.update)
        dqn_html = out_dir / f"{scenario_path.stem}_dqn.html"
        show_result("DQN", best_line, baseline, dqn_html)

    console.print(Rule("[bold green]Done[/bold green]"))


if __name__ == "__main__":
    main()
