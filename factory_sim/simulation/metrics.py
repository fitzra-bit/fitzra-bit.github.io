"""KPI calculations derived from a ProductionLine snapshot."""

from dataclasses import dataclass
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.line import ProductionLine


@dataclass
class LineMetrics:
    bottleneck_step: str
    bottleneck_capacity: float   # units/hour
    effective_yield: float       # 0–1, product of all step yields
    system_throughput: float     # units/hour at bottleneck (before yield)
    net_output_per_hour: float   # throughput × effective_yield
    net_output_per_period: float # net_output_per_hour × hours_per_period
    revenue_per_period: float    # net_output_per_period × unit_value
    total_opex_per_period: float
    gross_profit_per_period: float  # revenue - opex
    total_capex_spent: float
    payback_periods: float       # capex / profit_delta (vs baseline)
    baseline_profit_per_period: float
    delta_profit_per_period: float


def compute_metrics(line: "ProductionLine", baseline_profit: float = 0.0) -> LineMetrics:
    from simulation.line import ProductionLine

    bneck = line.bottleneck_step
    throughput = bneck.capacity
    eff_yield = line.effective_yield
    net_per_hour = throughput * eff_yield
    net_per_period = net_per_hour * line.hours_per_period
    revenue = net_per_period * line.unit_value
    opex = line.total_opex_per_period
    profit = revenue - opex
    delta_profit = profit - baseline_profit
    capex = line.total_capex_spent
    payback = (capex / delta_profit) if delta_profit > 0 else float("inf")

    return LineMetrics(
        bottleneck_step=bneck.name,
        bottleneck_capacity=throughput,
        effective_yield=eff_yield,
        system_throughput=throughput,
        net_output_per_hour=net_per_hour,
        net_output_per_period=net_per_period,
        revenue_per_period=revenue,
        total_opex_per_period=opex,
        gross_profit_per_period=profit,
        total_capex_spent=capex,
        payback_periods=payback,
        baseline_profit_per_period=baseline_profit,
        delta_profit_per_period=delta_profit,
    )
