#!/usr/bin/env python3
"""CLI Runner for S&P 500 Top N Strategy Backtesting Engine.

Orchestrates multi-horizon simulation runs (10y, 20y, 30y) for Top N constituents
(N in {3, 5, 10}) comparing pre-tax vs after-tax compounding against the S&P 500 (^GSPC).
Produces CSV reports and an interactive Google Apps Script dashboard.
"""

import argparse
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from engine.backtest import PortfolioSimulator
from engine.data_loader import DataLoader
from engine.exporters import ReportExporter
from engine.metrics import (
    calculate_alpha,
    calculate_benchmark_annual_series,
    calculate_cagr,
    calculate_cumulative_return,
    calculate_max_drawdown,
)
from engine.models import StrategyResult
from engine.selector import BaseSelector, MarketCapSelector, PerformanceSelector


def parse_list_arg(raw: Union[str, Sequence[Any]], item_type=str) -> List[Any]:
    """Parse a command-line argument that may be comma-separated or a list of items.

    Args:
        raw: Comma-separated string or sequence of items.
        item_type: Target constructor/callable for each item (e.g. str, int).

    Returns:
        List of parsed items.
    """
    if isinstance(raw, str):
        raw = [raw]
    items: List[Any] = []
    for item in raw:
        for part in str(item).split(","):
            part = part.strip()
            if part:
                items.append(item_type(part))
    return items


def resolve_horizons(raw_horizons: Union[str, Sequence[str]]) -> List[Tuple[str, int, int]]:
    """Convert horizon strings (e.g. '10y', '20y', '30y') to (label, start_year, end_year) tuples.

    Assumes dataset terminal year is 2024.

    Args:
        raw_horizons: String or sequence of horizon identifiers.

    Returns:
        List of (label, start_year, end_year) tuples.
    """
    parsed = parse_list_arg(raw_horizons, str)
    results: List[Tuple[str, int, int]] = []
    end_year = 2024

    for h in parsed:
        h_str = h.strip().lower()
        if h_str.endswith("y"):
            years = int(h_str[:-1])
        else:
            years = int(h_str)

        start_year = end_year - years
        label = f"{years}y"
        results.append((label, start_year, end_year))

    return results


def resolve_n_values(raw_n: Union[str, Sequence[Any]]) -> List[int]:
    """Convert raw N input into a list of positive integers.

    Args:
        raw_n: Comma-separated string or sequence of integers.

    Returns:
        List of integer N values.
    """
    return parse_list_arg(raw_n, int)


def resolve_selector(strategy_name: str, n: int = 5) -> BaseSelector:
    """Instantiate constituent selector based on strategy name.

    Args:
        strategy_name: 'market_cap' or 'performance'.
        n: Number of constituents to select.

    Returns:
        Instance of BaseSelector.

    Raises:
        ValueError: If strategy_name is unrecognized.
    """
    normalized = strategy_name.strip().lower()
    if normalized in ("market_cap", "marketcap"):
        return MarketCapSelector(n=n)
    elif normalized in ("performance", "momentum"):
        return PerformanceSelector(n=n)
    else:
        raise ValueError(
            f"Unknown strategy: '{strategy_name}'. Expected 'market_cap' or 'performance'."
        )


def build_scenario_and_apps_script_data(
    simulator: PortfolioSimulator,
    data_loader: DataLoader,
    strategy_name: str = "market_cap",
    initial_capital: float = 10000.0,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """Build multi-tier scenario tables and annual sheets for Google Apps Script.

    Runs simulations across tax tiers (0.0%, 15.0%, 20.0%, 30.0%, 37.0%) and
    generates 30-year annual ledgers for Top 3, Top 5, Top 10, plus S&P 500 benchmark.

    Args:
        simulator: PortfolioSimulator instance.
        data_loader: DataLoader instance.
        strategy_name: 'market_cap' or 'performance'.
        initial_capital: Starting capital basis.

    Returns:
        Tuple of (scenario_data, annual_data, trades_data).
    """
    horizons = [("10y", 2014, 2024), ("20y", 2004, 2024), ("30y", 1994, 2024)]
    tax_rates = [
        (0.0, "0.0%"),
        (0.15, "15.0%"),
        (0.20, "20.0%"),
        (0.30, "30.0%"),
        (0.37, "37.0%"),
    ]
    target_n_values = [3, 5, 10]

    # Pre-calculate pre-tax results
    pretax_cache: Dict[Tuple[int, int, int], StrategyResult] = {}
    for n in target_n_values:
        sel = resolve_selector(strategy_name, n=n)
        for _, s_yr, e_yr in horizons:
            pretax_cache[(n, s_yr, e_yr)] = simulator.run_simulation(
                s_yr,
                e_yr,
                n=n,
                selector=sel,
                is_after_tax=False,
                initial_capital=initial_capital,
            )

    scenario_rows: List[List[Any]] = []
    for rate, rate_str in tax_rates:
        for h_label, s_yr, e_yr in horizons:
            pr_levels = [data_loader.get_spx_level(y) for y in range(s_yr, e_yr + 1)]
            tr_levels = [data_loader.get_spx_tr_level(y) for y in range(s_yr, e_yr + 1)]
            horizon_years = e_yr - s_yr
            spx_tr_cagr = calculate_cagr(tr_levels[0], tr_levels[-1], horizon_years)

            if rate == 0.0:
                bench = calculate_benchmark_annual_series(
                    pr_levels=pr_levels,
                    tr_levels=tr_levels,
                    tax_rate=0.0,
                    initial_capital=initial_capital,
                    is_after_tax=False,
                )
                spx_after_cagr = spx_tr_cagr
                spx_post_liq_cagr = spx_tr_cagr
                spx_cum = calculate_cumulative_return(initial_capital, bench["post_liquidation_wealth"])
                spx_final = bench["post_liquidation_wealth"]
                spx_max_dd = calculate_max_drawdown(tr_levels)
                spx_taxes = 0.0
                spx_tax_drag = 0.0
                spx_divs = bench["total_dividends_received"]
            else:
                bench = calculate_benchmark_annual_series(
                    pr_levels=pr_levels,
                    tr_levels=tr_levels,
                    tax_rate=rate,
                    initial_capital=initial_capital,
                    is_after_tax=True,
                )
                val_series = [initial_capital]
                curr_v = initial_capital
                for r_ann in bench["annual_returns"]:
                    curr_v *= (1.0 + r_ann)
                    val_series.append(curr_v)
                spx_max_dd = calculate_max_drawdown(val_series)
                spx_after_cagr = calculate_cagr(initial_capital, bench["pre_liquidation_wealth"], horizon_years)
                spx_post_liq_cagr = calculate_cagr(initial_capital, bench["post_liquidation_wealth"], horizon_years)
                spx_cum = calculate_cumulative_return(initial_capital, bench["post_liquidation_wealth"])
                spx_final = bench["post_liquidation_wealth"]
                spx_taxes = bench["total_taxes_paid"]
                spx_tax_drag = spx_tr_cagr - spx_post_liq_cagr
                spx_divs = bench["total_dividends_received"]

            # S&P 500 entry (14 columns)
            spx_key = f"{h_label}_S&P 500_{rate_str}"
            scenario_rows.append([
                spx_key,
                h_label,
                "S&P 500",
                rate,
                round(spx_tr_cagr, 6),
                round(spx_after_cagr, 6),
                round(spx_post_liq_cagr, 6),
                round(spx_cum, 6),
                round(spx_final, 2),
                round(spx_divs, 2),
                round(spx_max_dd, 6),
                round(spx_taxes, 2),
                round(spx_tax_drag, 6),
                0.0,
            ])

            # Top N entries (14 columns)
            for n in target_n_values:
                pre_res = pretax_cache[(n, s_yr, e_yr)]
                sel = resolve_selector(strategy_name, n=n)
                if rate == 0.0:
                    post_res = pre_res
                    tax_drag = 0.0
                    alpha = post_res.cagr - spx_tr_cagr
                    strat_cum = post_res.cumulative_return
                    strat_final = post_res.final_equity
                else:
                    post_res = simulator.run_simulation(
                        s_yr,
                        e_yr,
                        n=n,
                        selector=sel,
                        is_after_tax=True,
                        tax_rate=rate,
                        initial_capital=initial_capital,
                    )
                    tax_drag = pre_res.cagr - post_res.post_liquidation_cagr
                    alpha = post_res.post_liquidation_cagr - spx_post_liq_cagr
                    strat_cum = calculate_cumulative_return(initial_capital, post_res.post_liquidation_wealth)
                    strat_final = post_res.post_liquidation_wealth

                strat_label = f"Top {n}"
                key = f"{h_label}_{strat_label}_{rate_str}"
                scenario_rows.append([
                    key,
                    h_label,
                    strat_label,
                    rate,
                    round(pre_res.cagr, 6),
                    round(post_res.cagr, 6),
                    round(post_res.post_liquidation_cagr, 6),
                    round(strat_cum, 6),
                    round(strat_final, 2),
                    round(post_res.total_dividends_received, 2),
                    round(post_res.max_drawdown, 6),
                    round(post_res.total_taxes_paid, 2),
                    round(tax_drag, 6),
                    round(alpha, 6),
                ])

    # 30-Year Annual histories & trades at 30% baseline tax rate
    annual_data: Dict[str, List[List[Any]]] = {}
    trade_rows: List[Dict[str, Any]] = []

    for n in target_n_values:
        sel = resolve_selector(strategy_name, n=n)
        res_30y = simulator.run_simulation(
            1994,
            2024,
            n=n,
            selector=sel,
            is_after_tax=True,
            tax_rate=0.30,
            initial_capital=initial_capital,
        )
        trades_30y = simulator.get_trades()

        ledger_rows: List[List[Any]] = []
        for entry in res_30y.annual_history:
            ledger_rows.append([
                entry.year,
                round(entry.start_value, 2),
                round(entry.gross_return, 6),
                round(getattr(entry, "dividend_income", 0.0), 2),
                round(entry.ending_value_pretax, 2),
                round(entry.realized_capital_gain, 2),
                round(entry.net_taxable_gain, 2),
                round(getattr(entry, "capital_gains_tax_paid", 0.0), 2),
                round(getattr(entry, "dividend_tax_paid", 0.0), 2),
                round(entry.tax_paid, 2),
                round(entry.loss_carryforward, 2),
                round(entry.ending_value_aftertax, 2),
                round(entry.cash, 2),
                round(entry.spx_return, 6),
                round(entry.turnover, 6),
            ])
        annual_data[f"top_{n}"] = ledger_rows

        for t in trades_30y:
            trade_rows.append({
                "year": t.year,
                "strategy_name": f"Top {n}",
                "ticker": t.ticker,
                "action": t.action,
                "shares": round(t.shares, 4),
                "price": round(t.price, 2),
                "realized_gain": round(t.realized_gain, 2),
            })

    # S&P 500 30-Year Benchmark Series
    spx_rows: List[List[Any]] = []
    base_level = data_loader.get_spx_level(1994)
    for y in range(1994, 2025):
        lvl = data_loader.get_spx_level(y)
        if y == 1994:
            spx_rows.append([1994, round(lvl, 2), 0.0, round(initial_capital, 2)])
        else:
            lvl_prev = data_loader.get_spx_level(y - 1)
            ann_ret = (lvl - lvl_prev) / lvl_prev
            comp_growth = initial_capital * (lvl / base_level)
            spx_rows.append([y, round(lvl, 2), round(ann_ret, 6), round(comp_growth, 2)])

    annual_data["spx"] = spx_rows
    scenario_data = {"scenario_rows": scenario_rows}

    return scenario_data, annual_data, trade_rows


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
        formatted_rows.append([
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

    # Header line
    hdr_line = ""
    for i, h in enumerate(col_headers):
        if i == 0 or i == 1:
            hdr_line += h.ljust(col_widths[i])
        else:
            hdr_line += h.rjust(col_widths[i])
        if i < len(col_headers) - 1:
            hdr_line += " "
    lines.append(hdr_line)
    lines.append("-" * total_width)

    current_horizon = None
    for r_idx, row in enumerate(formatted_rows):
        horizon = row[0]
        if current_horizon is not None and horizon != current_horizon:
            lines.append("-" * total_width)
        current_horizon = horizon

        line_str = ""
        for i, val in enumerate(row):
            if i == 0 or i == 1:
                line_str += val.ljust(col_widths[i])
            else:
                line_str += val.rjust(col_widths[i])
            if i < len(row) - 1:
                line_str += " "
        lines.append(line_str)

    lines.append("=" * total_width)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="S&P 500 Top N Strategy Backtesting Engine and Report Generator.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--strategy",
        type=str,
        choices=["market_cap", "performance", "momentum", "marketcap"],
        default="market_cap",
        help="Constituent selection algorithm (market_cap, performance, momentum).",
    )
    parser.add_argument(
        "--tax-rate",
        type=float,
        default=0.30,
        help="Flat capital gains tax rate applied to net realized gains.",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=10000.0,
        help="Initial starting portfolio capital ($).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs",
        help="Destination directory for exported CSV reports.",
    )
    parser.add_argument(
        "--scripts-dir",
        type=str,
        default="scripts",
        help="Destination directory for exported Google Apps Script.",
    )
    parser.add_argument(
        "--horizons",
        type=str,
        nargs="*",
        default=["10y", "20y", "30y"],
        help="Evaluation investment horizons (comma-separated or space-separated list).",
    )
    parser.add_argument(
        "--n",
        type=str,
        nargs="*",
        default=["3", "5", "10"],
        help="Number of portfolio constituents to select (comma or space separated).",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress terminal ASCII summary table output.",
    )
    return parser


def run_backtest(args: argparse.Namespace) -> int:
    """Execute backtest simulations, generate reports, and print summary tables.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code 0 on success.
    """
    data_loader = DataLoader()
    simulator = PortfolioSimulator(data_loader)

    horizons = resolve_horizons(args.horizons)
    n_values = resolve_n_values(args.n)

    # Pre-calculate benchmark metrics for reporting
    spx_benchmarks: Dict[Any, Any] = {}
    benchmark_metrics_by_horizon: Dict[str, Dict[str, Any]] = {}

    for h_label, s_yr, e_yr in horizons:
        horizon_years = e_yr - s_yr
        pr_levels = [data_loader.get_spx_level(y) for y in range(s_yr, e_yr + 1)]
        tr_levels = [data_loader.get_spx_tr_level(y) for y in range(s_yr, e_yr + 1)]
        spx_tr_cagr = calculate_cagr(tr_levels[0], tr_levels[-1], horizon_years)
        spx_tr_cum = calculate_cumulative_return(tr_levels[0], tr_levels[-1])
        spx_tr_max_dd = calculate_max_drawdown(tr_levels)

        # Pre-tax benchmark calculation
        bench_pre = calculate_benchmark_annual_series(
            pr_levels=pr_levels,
            tr_levels=tr_levels,
            tax_rate=0.0,
            initial_capital=args.initial_capital,
            is_after_tax=False,
        )

        # After-tax benchmark calculation
        bench_post = calculate_benchmark_annual_series(
            pr_levels=pr_levels,
            tr_levels=tr_levels,
            tax_rate=args.tax_rate,
            initial_capital=args.initial_capital,
            is_after_tax=True,
        )

        val_series = [args.initial_capital]
        curr_val = args.initial_capital
        for r_ann in bench_post["annual_returns"]:
            curr_val *= (1.0 + r_ann)
            val_series.append(curr_val)
        spx_post_max_dd = calculate_max_drawdown(val_series)

        spx_after_cagr = calculate_cagr(args.initial_capital, bench_post["pre_liquidation_wealth"], horizon_years)
        spx_post_liq_cagr = calculate_cagr(args.initial_capital, bench_post["post_liquidation_wealth"], horizon_years)
        spx_post_cum = calculate_cumulative_return(args.initial_capital, bench_post["post_liquidation_wealth"])
        spx_post_taxes = bench_post["total_taxes_paid"]
        spx_post_divs = bench_post["total_dividends_received"]
        spx_tax_drag = spx_tr_cagr - spx_post_liq_cagr

        benchmark_metrics_by_horizon[h_label] = {
            "tr_cagr": spx_tr_cagr,
            "after_cagr": spx_after_cagr,
            "post_liq_cagr": spx_post_liq_cagr,
            "cum_return": spx_post_cum,
            "final_equity": bench_post["post_liquidation_wealth"],
            "max_dd": spx_post_max_dd,
            "total_taxes": spx_post_taxes,
            "total_dividends": spx_post_divs,
            "tax_drag": spx_tax_drag,
            "bench_pre": bench_pre,
            "bench_post": bench_post,
            "tr_cum": spx_tr_cum,
            "tr_max_dd": spx_tr_max_dd,
        }

        # Store in spx_benchmarks for exporter lookups
        spx_benchmarks[h_label] = spx_tr_cagr
        spx_benchmarks[str(horizon_years)] = spx_tr_cagr
        spx_benchmarks[horizon_years] = spx_tr_cagr
        spx_benchmarks[(h_label, False)] = spx_tr_cagr
        spx_benchmarks[(h_label, 0.0)] = spx_tr_cagr
        spx_benchmarks[(h_label, True)] = spx_post_liq_cagr
        spx_benchmarks[(h_label, args.tax_rate)] = spx_post_liq_cagr
        spx_benchmarks[(horizon_years, args.tax_rate)] = spx_post_liq_cagr

    all_results: List[StrategyResult] = []
    trade_records: List[Dict[str, Any]] = []
    table_rows: List[Dict[str, Any]] = []

    # Run simulations for each horizon and N
    for h_label, s_yr, e_yr in horizons:
        bm = benchmark_metrics_by_horizon[h_label]
        spx_tr_cagr = bm["tr_cagr"]
        spx_post_liq_cagr = bm["post_liq_cagr"]

        for n in n_values:
            selector = resolve_selector(args.strategy, n=n)

            # 1. Pre-tax simulation
            res_pre = simulator.run_simulation(
                start_year=s_yr,
                end_year=e_yr,
                n=n,
                selector=selector,
                is_after_tax=False,
                initial_capital=args.initial_capital,
            )
            all_results.append(res_pre)

            # 2. After-tax simulation
            res_post = simulator.run_simulation(
                start_year=s_yr,
                end_year=e_yr,
                n=n,
                selector=selector,
                is_after_tax=True,
                tax_rate=args.tax_rate,
                initial_capital=args.initial_capital,
            )
            all_results.append(res_post)

            # Collect executed trade records
            for t in simulator.get_trades():
                trade_records.append({
                    "strategy_name": res_post.strategy_name,
                    "n": n,
                    "year": t.year,
                    "ticker": t.ticker,
                    "action": t.action,
                    "shares": round(t.shares, 4),
                    "price": round(t.price, 2),
                    "realized_gain": round(t.realized_gain, 2),
                })

            tax_drag = res_pre.cagr - res_post.post_liquidation_cagr
            alpha = calculate_alpha(res_post.post_liquidation_cagr, spx_post_liq_cagr)

            table_rows.append({
                "horizon": h_label,
                "strategy": f"Top {n}",
                "pre_cagr": res_pre.cagr,
                "post_cagr": res_post.cagr,
                "post_liq_cagr": res_post.post_liquidation_cagr,
                "cum_return": calculate_cumulative_return(args.initial_capital, res_post.post_liquidation_wealth),
                "final_equity": res_post.post_liquidation_wealth,
                "max_dd": res_post.max_drawdown,
                "total_taxes": res_post.total_taxes_paid,
                "tax_drag": tax_drag,
                "alpha": alpha,
            })

        # S&P 500 benchmark row in terminal table
        table_rows.append({
            "horizon": h_label,
            "strategy": "S&P 500",
            "pre_cagr": spx_tr_cagr,
            "post_cagr": bm["after_cagr"],
            "post_liq_cagr": spx_post_liq_cagr,
            "cum_return": bm["cum_return"],
            "final_equity": bm["final_equity"],
            "max_dd": bm["max_dd"],
            "total_taxes": bm["total_taxes"],
            "tax_drag": bm["tax_drag"],
            "alpha": 0.0,
        })

        # Pre-tax benchmark StrategyResult for summary_metrics.csv
        spx_res_pre = StrategyResult(
            strategy_name="S&P 500",
            n=0,
            start_year=s_yr,
            end_year=e_yr,
            is_after_tax=False,
            tax_rate=0.0,
            initial_capital=args.initial_capital,
            final_equity=bm["bench_pre"]["final_equity"],
            cagr=spx_tr_cagr,
            cumulative_return=bm["tr_cum"],
            max_drawdown=bm["tr_max_dd"],
            total_taxes_paid=0.0,
            pre_liquidation_wealth=bm["bench_pre"]["pre_liquidation_wealth"],
            post_liquidation_wealth=bm["bench_pre"]["post_liquidation_wealth"],
            post_liquidation_cagr=spx_tr_cagr,
            total_dividends_received=bm["bench_pre"]["total_dividends_received"],
            annual_history=[],
        )
        all_results.append(spx_res_pre)

        # After-tax benchmark StrategyResult for summary_metrics.csv
        spx_res_post = StrategyResult(
            strategy_name="S&P 500",
            n=0,
            start_year=s_yr,
            end_year=e_yr,
            is_after_tax=True,
            tax_rate=args.tax_rate,
            initial_capital=args.initial_capital,
            final_equity=bm["final_equity"],
            cagr=spx_post_liq_cagr,
            cumulative_return=bm["cum_return"],
            max_drawdown=bm["max_dd"],
            total_taxes_paid=bm["total_taxes"],
            pre_liquidation_wealth=bm["bench_post"]["pre_liquidation_wealth"],
            post_liquidation_wealth=bm["bench_post"]["post_liquidation_wealth"],
            post_liquidation_cagr=spx_post_liq_cagr,
            total_dividends_received=bm["total_dividends"],
            annual_history=[],
        )
        all_results.append(spx_res_post)

    # Prepare Google Apps Script data across tax tiers
    scenario_data, annual_data, trades_data = build_scenario_and_apps_script_data(
        simulator=simulator,
        data_loader=data_loader,
        strategy_name=args.strategy,
        initial_capital=args.initial_capital,
    )

    # Export all report artifacts
    exporter = ReportExporter(output_dir=args.output_dir, scripts_dir=args.scripts_dir)
    exported_files = exporter.export_all(
        results=all_results,
        trade_records=trade_records,
        spx_benchmarks=spx_benchmarks,
        scenario_data=scenario_data,
        annual_data=annual_data,
        trades_data=trades_data,
    )

    # Display ASCII terminal comparison table
    if not args.quiet:
        print()
        print(
            format_terminal_table(
                table_rows,
                tax_rate=args.tax_rate,
                initial_capital=args.initial_capital,
                strategy_name=args.strategy,
            )
        )
        print()
        print("Generated Output Artifacts:")
        for name, path in exported_files.items():
            print(f"  - {name}: {path}")
        print()

    return 0


def main() -> None:
    """Primary executable CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run_backtest(args))


if __name__ == "__main__":
    main()
