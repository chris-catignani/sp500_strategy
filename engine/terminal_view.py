"""Terminal presentation utilities for strategy backtesting results.

Formats summary metrics and multi-horizon comparisons into clean ASCII tables.
"""

from typing import Any, Dict, List


def format_terminal_table(
    rows: List[Dict[str, Any]],
    tax_rate: float = 0.30,
    initial_capital: float = 10000.0,
    strategy_name: str = "market_cap",
) -> str:
    """Format strategy performance metrics into an ASCII comparison table.

    Args:
        rows: List of metric dictionaries.
        tax_rate: Capital gains tax rate.
        initial_capital: Starting capital.
        strategy_name: Selector name.

    Returns:
        Formatted ASCII table string.
    """
    strat_title = "Market Cap" if "cap" in strategy_name.lower() else "Performance"
    header_title = (
        f"S&P 500 Top N Strategy Performance ({strat_title}) | "
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
    return "\n".join(lines)
