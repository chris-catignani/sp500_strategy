"""Quantitative performance analytics and tax drag calculators."""

from typing import Dict, Sequence
from engine.models import AnnualLedgerEntry


def calculate_cagr(start_value: float, end_value: float, years: int) -> float:
    """Calculate the Compound Annual Growth Rate (CAGR).

    Formula:
        (end_value / start_value) ** (1 / years) - 1.0

    Guards:
        - years <= 0 -> 0.0
        - start_value <= 0.0 -> 0.0
        - end_value <= 0.0 -> -1.0

    Args:
        start_value: Initial valuation or capital basis.
        end_value: Terminal valuation.
        years: Horizon period in integer years.

    Returns:
        Annualized compound growth rate as a float.
    """
    if years <= 0:
        return 0.0
    if start_value <= 0.0:
        return 0.0
    if end_value <= 0.0:
        return -1.0
    return (end_value / start_value) ** (1.0 / years) - 1.0


def calculate_cumulative_return(start_value: float, end_value: float) -> float:
    """Calculate total cumulative return over a multi-year horizon.

    Formula:
        (end_value - start_value) / start_value

    Guards:
        - start_value <= 0.0 -> 0.0

    Args:
        start_value: Initial capital or start valuation.
        end_value: Ending portfolio valuation.

    Returns:
        Cumulative return as a float (e.g., 1.50 for +150%).
    """
    if start_value <= 0.0:
        return 0.0
    return (end_value - start_value) / start_value


def calculate_max_drawdown(series: Sequence[float]) -> float:
    """Compute peak-to-trough maximum drawdown over a series of valuations.

    Returns a non-positive float representing the largest peak-to-trough decline,
    or 0.0 if there was no drawdown.

    Formula:
        max_dd = min_t ((V_t - peak_t) / peak_t)

    Args:
        series: Sequence of portfolio valuations ordered chronologically.

    Returns:
        Maximum drawdown as a non-positive float (e.g., -0.22 for a 22% drawdown).
    """
    if not series:
        return 0.0

    peak = series[0]
    max_dd = 0.0

    for val in series:
        if val > peak:
            peak = val
        dd = (val - peak) / peak if peak > 0.0 else 0.0
        if dd < max_dd:
            max_dd = dd

    return max_dd


def calculate_turnover(entries: Sequence[AnnualLedgerEntry]) -> float:
    """Calculate the average annual portfolio turnover across all ledger entries.

    Formula:
        (1 / N) * sum_{t=1}^N (entry.turnover)

    Args:
        entries: Sequence of AnnualLedgerEntry instances.

    Returns:
        Average annual turnover as a float (0.0 if entries is empty).
    """
    if not entries:
        return 0.0
    return sum(entry.turnover for entry in entries) / len(entries)


def calculate_tax_drag(cagr_pretax: float, cagr_aftertax: float) -> float:
    """Calculate the tax drag between pre-tax and after-tax annualized returns.

    Formula:
        cagr_pretax - cagr_aftertax

    Args:
        cagr_pretax: Compound annual growth rate before taxes.
        cagr_aftertax: Compound annual growth rate after taxes.

    Returns:
        Tax drag as a float.
    """
    return cagr_pretax - cagr_aftertax


def calculate_terminal_metrics(
    pre_liquidation_wealth: float,
    unrealized_gain: float,
    loss_carryforward: float,
    tax_rate: float,
    initial_capital: float,
    years: int,
    is_after_tax: bool = True,
) -> Dict[str, float]:
    """Calculate terminal liquidation wealth, tax liability, and post-liquidation CAGR.

    Args:
        pre_liquidation_wealth: Ending portfolio valuation before terminal liquidation.
        unrealized_gain: Total unrealized capital gain embedded in terminal holdings.
        loss_carryforward: Unused realized capital loss carryforward available at terminal year.
        tax_rate: Applicable capital gains tax rate.
        initial_capital: Initial investment basis.
        years: Total simulation duration in years.
        is_after_tax: Whether tax settlement applies. If False, terminal tax is 0.0.

    Returns:
        Dictionary containing:
        - 'pre_liquidation_wealth': Ending wealth before terminal liquidation.
        - 'embedded_unrealized_gain': Total unrealized capital gains.
        - 'net_taxable_terminal_gain': Net taxable gain after offsetting loss carryforward.
        - 'terminal_tax': Dollar tax liability upon full liquidation.
        - 'post_liquidation_wealth': Final cash after paying terminal liquidation tax.
        - 'post_liquidation_cagr': Annualized return factoring terminal tax.
        - 'terminal_tax_drag': Difference between pre-liquidation and post-liquidation CAGR.
    """
    if is_after_tax:
        net_taxable_terminal_gain = max(0.0, unrealized_gain - loss_carryforward)
        terminal_tax = net_taxable_terminal_gain * tax_rate
        post_liquidation_wealth = pre_liquidation_wealth - terminal_tax
    else:
        net_taxable_terminal_gain = 0.0
        terminal_tax = 0.0
        post_liquidation_wealth = pre_liquidation_wealth

    pre_liquidation_cagr = calculate_cagr(initial_capital, pre_liquidation_wealth, years)
    post_liquidation_cagr = calculate_cagr(initial_capital, post_liquidation_wealth, years)
    terminal_tax_drag = pre_liquidation_cagr - post_liquidation_cagr

    return {
        "pre_liquidation_wealth": pre_liquidation_wealth,
        "embedded_unrealized_gain": unrealized_gain,
        "net_taxable_terminal_gain": net_taxable_terminal_gain,
        "terminal_tax": terminal_tax,
        "post_liquidation_wealth": post_liquidation_wealth,
        "post_liquidation_cagr": post_liquidation_cagr,
        "terminal_tax_drag": terminal_tax_drag,
    }


def calculate_alpha(strategy_cagr: float, benchmark_cagr: float) -> float:
    """Calculate excess annualized return (alpha) relative to a benchmark.

    Formula:
        strategy_cagr - benchmark_cagr

    Args:
        strategy_cagr: Strategy CAGR.
        benchmark_cagr: Benchmark (e.g., S&P 500) CAGR.

    Returns:
        Alpha as a float.
    """
    return strategy_cagr - benchmark_cagr
