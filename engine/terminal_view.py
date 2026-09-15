"""Terminal presentation utilities for strategy backtesting results.

Formats summary metrics and multi-horizon comparisons into clean ASCII tables.
"""

from typing import Any, Dict, List, Optional

from engine.benchmarks import BenchmarkMetrics
from engine.metrics import calculate_tax_drag
from engine.models import StrategyResult


def build_strategy_row(
    res_pre: StrategyResult,
    res_post: StrategyResult,
    horizon_label: str,
    spx_after_cagr: float,
    strategy_label: Optional[str] = None,
    universe_label: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct a table row dictionary representing a strategy run.

    Args:
        res_pre: Pre-tax strategy result.
        res_post: After-tax strategy result.
        horizon_label: Horizon period identifier (e.g., '10y', '20y', '30y').
        spx_after_cagr: Benchmark S&P 500 after-tax CAGR for alpha comparison.
        strategy_label: Optional display label overriding `res_post.strategy_name`.
        universe_label: Optional universe name (e.g., 'S&P 500', 'Nasdaq 100').

    Returns:
        Dictionary mapping column names to metric values for the terminal table.
    """
    row: Dict[str, Any] = {}
    if universe_label is not None:
        row["universe"] = universe_label
    row["horizon"] = horizon_label
    row["strategy"] = strategy_label if strategy_label is not None else res_post.strategy_name
    row["pre_cagr"] = res_pre.cagr
    row["post_cagr"] = res_post.cagr
    row["post_liq_cagr"] = res_post.post_liquidation_cagr
    row["cum_return"] = res_post.cumulative_return
    row["max_dd"] = res_post.max_drawdown
    row["tax_drag"] = calculate_tax_drag(res_pre.cagr, res_post.cagr)
    row["alpha"] = res_post.cagr - spx_after_cagr
    return row


def build_benchmark_row(
    name: str,
    metrics: BenchmarkMetrics,
    horizon_label: str,
    spx_after_cagr: float,
    universe_label: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct a table row dictionary representing an index or fund benchmark.

    Args:
        name: Benchmark display name (e.g., 'S&P 500', 'Nasdaq 100', 'MSCI World').
        metrics: Computed benchmark performance and risk metrics.
        horizon_label: Horizon period identifier (e.g., '10y', '20y', '30y').
        spx_after_cagr: Benchmark S&P 500 after-tax CAGR for alpha comparison.
        universe_label: Optional universe name (e.g., 'S&P 500', 'Nasdaq 100').

    Returns:
        Dictionary mapping column names to metric values for the terminal table.
    """
    row: Dict[str, Any] = {}
    if universe_label is not None:
        row["universe"] = universe_label
    row["horizon"] = horizon_label
    row["strategy"] = name
    row["pre_cagr"] = metrics.tr_cagr
    row["post_cagr"] = metrics.after_cagr
    row["post_liq_cagr"] = metrics.post_liq_cagr
    row["cum_return"] = metrics.cum_return
    row["max_dd"] = metrics.max_dd
    row["tax_drag"] = metrics.tax_drag
    row["alpha"] = (
        0.0
        if "S&P 500" in name and not any(other in name for other in ["World", "FBGRX", "Nasdaq"])
        else (metrics.after_cagr - spx_after_cagr)
    )
    return row





def format_terminal_table(
    rows: List[Dict[str, Any]],
    tax_rate: float = 0.30,
    initial_capital: float = 10000.0,
    strategy_name: str = "market_cap",
    weight_by: str = "market_cap",
    show_footnotes: bool = True,
) -> str:
    """Format strategy performance metrics into an ASCII comparison table.

    Args:
        rows: List of metric dictionaries.
        tax_rate: Capital gains tax rate.
        initial_capital: Starting capital.
        strategy_name: Selector name.
        weight_by: Weighting mode ('market_cap' or 'equal').
        show_footnotes: Whether to append explanatory table footnotes.

    Returns:
        Formatted ASCII table string.
    """
    strat_title = "Market Cap" if "cap" in strategy_name.lower() else "Performance"
    weight_title = "Equal Weight" if weight_by == "equal" else "Market Cap"
    header_title = (
        f"S&P 500 Top N Strategy Performance ({strat_title} - {weight_title}) | "
        f"Tax Rate: {tax_rate:.1%} | Capital: ${initial_capital:,.2f}"
    )

    has_universe = any("universe" in r for r in rows)
    if has_universe:
        col_headers = [
            "Universe",
            "Horizon",
            "Strategy",
            "Pre-Tax CAGR",
            "After-Tax CAGR",
            "Post-Liq CAGR",
            "Cum Return",
            "Max DD",
            "Tax Drag",
            "Alpha vs SPX",
        ]
    else:
        col_headers = [
            "Horizon",
            "Strategy",
            "Pre-Tax CAGR",
            "After-Tax CAGR",
            "Post-Liq CAGR",
            "Cum Return",
            "Max DD",
            "Tax Drag",
            "Alpha vs SPX",
        ]

    # Pre-format rows
    formatted_rows: List[List[str]] = []
    for r in rows:
        row_vals: List[str] = []
        if has_universe:
            row_vals.append(r.get("universe", "S&P 500"))
        row_vals.extend([
            r["horizon"],
            r["strategy"],
            f"{r['pre_cagr']:.2%}",
            f"{r['post_cagr']:.2%}",
            f"{r['post_liq_cagr']:.2%}",
            f"{r['cum_return']:.2%}",
            f"{r['max_dd']:.2%}",
            f"{r['tax_drag']:.2%}",
            f"{r['alpha']:+.2%}" if r["strategy"] != "S&P 500" else "0.00%",
        ])
        formatted_rows.append(row_vals)

    # Calculate column widths
    col_widths = [len(h) for h in col_headers]
    for row in formatted_rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    # Add padding
    col_widths = [w + 2 for w in col_widths]
    total_width = sum(col_widths) + len(col_widths) - 1

    lines: List[str] = []
    lines.append("=" * total_width)
    lines.append(header_title.center(total_width))
    lines.append("=" * total_width)

    left_align_count = 3 if has_universe else 2

    # Header line
    hdr_line = ""
    for i, h in enumerate(col_headers):
        if i < left_align_count:
            hdr_line += h.ljust(col_widths[i])
        else:
            hdr_line += h.rjust(col_widths[i])
        if i < len(col_headers) - 1:
            hdr_line += " "
    lines.append(hdr_line)
    lines.append("-" * total_width)

    current_group = None
    for r_idx, row in enumerate(formatted_rows):
        group_key = (row[0], row[1]) if has_universe else row[0]
        if current_group is not None and group_key != current_group:
            lines.append("-" * total_width)
        current_group = group_key

        line_str = ""
        for i, val in enumerate(row):
            if i < left_align_count:
                line_str += val.ljust(col_widths[i])
            else:
                line_str += val.rjust(col_widths[i])
            if i < len(row) - 1:
                line_str += " "
        lines.append(line_str)

    lines.append("=" * total_width)
    if show_footnotes:
        lines.append("  * Note: Max Drawdown is measured at discrete rebalance observation dates (annual/quarterly).")
        lines.append("  * Note: Pre-Tax and After-Tax CAGRs reflect pre-liquidation wealth; Post-Liq CAGR reflects terminal liquidation.")
    return "\n".join(lines)
