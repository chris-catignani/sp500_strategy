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


def resolve_universes(
    raw_universes: Union[str, Sequence[str]],
    available_universes: Optional[Sequence[str]] = None,
) -> List[str]:
    """Convert raw universe input into validated list of universe keys.

    Args:
        raw_universes: Comma-separated string or sequence of universe identifiers.
        available_universes: Optional sequence of valid universe names.

    Returns:
        List of normalized universe keys (e.g. ['sp500', 'world']).
    """
    parsed = parse_list_arg(raw_universes, str)
    normalized: List[str] = []
    for u in parsed:
        u_clean = u.strip().lower()
        if u_clean in ("sp500", "sp_500", "s&p500", "s&p 500", "us"):
            u_norm = "sp500"
        elif u_clean in ("world", "all_world", "allworld", "global"):
            u_norm = "world"
        else:
            u_norm = u_clean

        if available_universes and u_norm not in available_universes:
            raise ValueError(
                f"Unknown universe '{u}'. Available universes: {list(available_universes)}"
            )
        if u_norm not in normalized:
            normalized.append(u_norm)
    return normalized or ["sp500"]


# Re-export key helpers for backward compatibility and test suites
from engine.selector import resolve_selector
from engine.scenarios import build_scenario_and_apps_script_data
from engine.terminal_view import format_terminal_table


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="S&P 500 & World Top N Strategy Backtesting Engine and Report Generator.",
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
        "--universes",
        type=str,
        nargs="*",
        default=["sp500", "world"],
        help="Constituent universes to simulate ('sp500', 'world', or comma-separated list).",
    )
    parser.add_argument(
        "--frequency",
        type=str,
        choices=["annual", "quarterly"],
        default="annual",
        help="Rebalancing frequency ('annual' or 'quarterly').",
    )
    parser.add_argument(
        "--compare-frequencies",
        action="store_true",
        default=False,
        help="Run and display both annual and quarterly rebalancing side-by-side.",
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
    universes = resolve_universes(
        getattr(args, "universes", ["sp500", "world"]),
        data_loader.get_available_universes(),
    )

    # Pre-calculate benchmark metrics for reporting
    spx_benchmarks: Dict[Any, Any] = {}
    benchmark_metrics_by_horizon: Dict[str, Dict[str, Any]] = {}
    msci_metrics_by_horizon: Dict[str, Dict[str, Any]] = {}

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

        # Pre-calculate MSCI World benchmark
        msci_pr_levels = [data_loader.get_msci_world_level(y) for y in range(s_yr, e_yr + 1)]
        msci_tr_levels = [data_loader.get_msci_world_tr_level(y) for y in range(s_yr, e_yr + 1)]
        msci_tr_cagr = calculate_cagr(msci_tr_levels[0], msci_tr_levels[-1], horizon_years)
        msci_tr_cum = calculate_cumulative_return(msci_tr_levels[0], msci_tr_levels[-1])
        msci_tr_max_dd = calculate_max_drawdown(msci_tr_levels)

        msci_bench_pre = calculate_benchmark_annual_series(
            pr_levels=msci_pr_levels,
            tr_levels=msci_tr_levels,
            tax_rate=0.0,
            initial_capital=args.initial_capital,
            is_after_tax=False,
        )
        msci_bench_post = calculate_benchmark_annual_series(
            pr_levels=msci_pr_levels,
            tr_levels=msci_tr_levels,
            tax_rate=args.tax_rate,
            initial_capital=args.initial_capital,
            is_after_tax=True,
        )
        m_series = [args.initial_capital]
        m_curr = args.initial_capital
        for r_ann in msci_bench_post["annual_returns"]:
            m_curr *= (1.0 + r_ann)
            m_series.append(m_curr)
        msci_post_max_dd = calculate_max_drawdown(m_series)

        msci_after_cagr = calculate_cagr(args.initial_capital, msci_bench_post["pre_liquidation_wealth"], horizon_years)
        msci_post_liq_cagr = calculate_cagr(args.initial_capital, msci_bench_post["post_liquidation_wealth"], horizon_years)
        msci_post_cum = calculate_cumulative_return(args.initial_capital, msci_bench_post["post_liquidation_wealth"])
        msci_post_taxes = msci_bench_post["total_taxes_paid"]
        msci_post_divs = msci_bench_post["total_dividends_received"]
        msci_tax_drag = msci_tr_cagr - msci_post_liq_cagr
        msci_alpha = msci_post_liq_cagr - spx_post_liq_cagr

        msci_metrics_by_horizon[h_label] = {
            "tr_cagr": msci_tr_cagr,
            "after_cagr": msci_after_cagr,
            "post_liq_cagr": msci_post_liq_cagr,
            "cum_return": msci_post_cum,
            "final_equity": msci_bench_post["post_liquidation_wealth"],
            "max_dd": msci_post_max_dd,
            "total_taxes": msci_post_taxes,
            "total_dividends": msci_post_divs,
            "tax_drag": msci_tax_drag,
            "alpha": msci_alpha,
            "bench_pre": msci_bench_pre,
            "bench_post": msci_bench_post,
            "tr_cum": msci_tr_cum,
            "tr_max_dd": msci_tr_max_dd,
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

    # Run simulations for each horizon, universe, and N
    for h_label, s_yr, e_yr in horizons:
        bm = benchmark_metrics_by_horizon[h_label]
        spx_tr_cagr = bm["tr_cagr"]
        spx_post_liq_cagr = bm["post_liq_cagr"]

        frequencies = ["annual", "quarterly"] if getattr(args, "compare_frequencies", False) else [getattr(args, "frequency", "annual")]

        for univ in universes:
            univ_label = "S&P 500" if univ == "sp500" else "All World"
            prefix = "" if univ == "sp500" else "World "

            for n in n_values:
                selector = resolve_selector(args.strategy, n=n)

                for freq in frequencies:
                    freq_suffix = f" ({freq.capitalize()})" if (len(frequencies) > 1 or freq == "quarterly") else ""

                    # 1. Pre-tax simulation
                    res_pre = simulator.run_simulation(
                        start_year=s_yr,
                        end_year=e_yr,
                        n=n,
                        selector=selector,
                        is_after_tax=False,
                        initial_capital=args.initial_capital,
                        universe=univ,
                        rebalance_frequency=freq,
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
                        universe=univ,
                        rebalance_frequency=freq,
                    )
                    all_results.append(res_post)

                    # Collect executed trade records
                    for t in simulator.get_trades():
                        trade_records.append({
                            "strategy_name": f"{res_post.strategy_name}{freq_suffix}",
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
                        "universe": univ_label,
                        "horizon": h_label,
                        "strategy": f"{prefix}Top {n}{freq_suffix}",
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
            "universe": "S&P 500",
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

        # MSCI World benchmark row in terminal table
        msci = msci_metrics_by_horizon[h_label]
        table_rows.append({
            "universe": "All World",
            "horizon": h_label,
            "strategy": "MSCI World",
            "pre_cagr": msci["tr_cagr"],
            "post_cagr": msci["after_cagr"],
            "post_liq_cagr": msci["post_liq_cagr"],
            "cum_return": msci["cum_return"],
            "final_equity": msci["final_equity"],
            "max_dd": msci["max_dd"],
            "total_taxes": msci["total_taxes"],
            "tax_drag": msci["tax_drag"],
            "alpha": msci["alpha"],
        })

        # Pre-tax MSCI World benchmark StrategyResult for summary_metrics.csv
        msci_res_pre = StrategyResult(
            strategy_name="MSCI World",
            n=0,
            start_year=s_yr,
            end_year=e_yr,
            is_after_tax=False,
            tax_rate=0.0,
            initial_capital=args.initial_capital,
            final_equity=msci["bench_pre"]["final_equity"],
            cagr=msci["tr_cagr"],
            cumulative_return=msci["tr_cum"],
            max_drawdown=msci["tr_max_dd"],
            total_taxes_paid=0.0,
            pre_liquidation_wealth=msci["bench_pre"]["pre_liquidation_wealth"],
            post_liquidation_wealth=msci["bench_pre"]["post_liquidation_wealth"],
            post_liquidation_cagr=msci["tr_cagr"],
            total_dividends_received=msci["bench_pre"]["total_dividends_received"],
            annual_history=[],
        )
        all_results.append(msci_res_pre)

        # After-tax MSCI World benchmark StrategyResult for summary_metrics.csv
        msci_res_post = StrategyResult(
            strategy_name="MSCI World",
            n=0,
            start_year=s_yr,
            end_year=e_yr,
            is_after_tax=True,
            tax_rate=args.tax_rate,
            initial_capital=args.initial_capital,
            final_equity=msci["final_equity"],
            cagr=msci["post_liq_cagr"],
            cumulative_return=msci["cum_return"],
            max_drawdown=msci["max_dd"],
            total_taxes_paid=msci["total_taxes"],
            pre_liquidation_wealth=msci["bench_post"]["pre_liquidation_wealth"],
            post_liquidation_wealth=msci["bench_post"]["post_liquidation_wealth"],
            post_liquidation_cagr=msci["post_liq_cagr"],
            total_dividends_received=msci["total_dividends"],
            annual_history=[],
        )
        all_results.append(msci_res_post)

    # Prepare Google Apps Script data across tax tiers
    scenario_data, annual_data, trades_data = build_scenario_and_apps_script_data(
        simulator=simulator,
        data_loader=data_loader,
        strategy_name=args.strategy,
        initial_capital=args.initial_capital,
        universes=universes,
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
