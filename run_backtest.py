#!/usr/bin/env python3
"""CLI Runner for S&P 500 Top N Strategy Backtesting Engine.

Orchestrates multi-horizon simulation runs (10y, 20y, 30y) for Top N constituents
(N in {3, 5, 10}) comparing pre-tax vs after-tax compounding against market benchmarks.
Produces CSV reports and an interactive Google Apps Script dashboard.
"""

import argparse
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from engine.backtest import PortfolioSimulator
from engine.benchmarks import BenchmarkSuite, compute_all_benchmarks
from engine.data_loader import DataLoader
from engine.exporters import ReportExporter
from engine.models import StrategyResult
from engine.scenarios import build_scenario_and_apps_script_data
from engine.selector import BaseSelector, MarketCapSelector, PerformanceSelector, resolve_selector
from engine.terminal_view import (
    build_benchmark_row,
    build_strategy_row,
    format_terminal_table,
)


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
        "--weight-by",
        type=str,
        choices=["market_cap", "equal"],
        default="market_cap",
        help="Constituent weighting algorithm ('market_cap' or 'equal').",
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
        "--benchmark",
        type=str,
        choices=[
            "all",
            "sp500",
            "msci_world",
            "fbgrx",
            "nasdaq_100",
            "nasdaq 100",
            "nasdaq100",
            "qqq",
            "ndx",
        ],
        default="all",
        help="Benchmark comparison display ('all', 'sp500', 'msci_world', 'fbgrx', 'nasdaq_100').",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress terminal ASCII summary table output.",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        default=False,
        help="Suppress exporting CSV reports and Google Apps Script to disk.",
    )
    return parser


build_argument_parser = build_parser


def run_simulation_matrix(
    simulator: PortfolioSimulator,
    horizons: List[Tuple[str, int, int]],
    n_values: List[int],
    universes: List[str],
    strategy_name: str,
    weight_by: str,
    tax_rate: float,
    initial_capital: float,
    frequency: str,
    compare_frequencies: bool,
    benchmark_suite: BenchmarkSuite,
    benchmark_filter: str = "all",
) -> Tuple[List[StrategyResult], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Execute strategy simulations across horizons, universes, and constituent sizes.

    Args:
        simulator: PortfolioSimulator instance.
        horizons: List of (label, start_year, end_year) evaluation periods.
        n_values: List of top N constituent counts to test.
        universes: List of universe identifiers (e.g. ['sp500', 'world']).
        strategy_name: Selector strategy algorithm name.
        weight_by: Constituent weighting method ('market_cap' or 'equal').
        tax_rate: Capital gains tax rate.
        initial_capital: Starting portfolio capital ($).
        frequency: Rebalance frequency ('annual' or 'quarterly').
        compare_frequencies: If True, simulate both annual and quarterly frequencies.
        benchmark_suite: Pre-calculated benchmark metrics for all horizons and indices.
        benchmark_filter: Benchmark comparison filter ('all', 'sp500', 'msci_world', 'fbgrx', 'nasdaq_100').

    Returns:
        Tuple of (simulation_results, trade_records, table_rows).
    """
    simulation_results: List[StrategyResult] = []
    trade_records: List[Dict[str, Any]] = []
    table_rows: List[Dict[str, Any]] = []

    bmk_filter = (benchmark_filter or "all").lower().replace(" ", "_")
    if bmk_filter in ("qqq", "nasdaq100", "ndx"):
        bmk_filter = "nasdaq_100"
    include_spx = bmk_filter in ("all", "sp500")
    include_msci = bmk_filter in ("all", "msci_world")
    include_fbgrx = bmk_filter in ("all", "fbgrx")
    include_nasdaq = bmk_filter in ("all", "nasdaq_100")

    for h_label, s_yr, e_yr in horizons:
        bm = benchmark_suite.spx_annual[h_label]
        q_bm = benchmark_suite.spx_quarterly[h_label]
        msci = benchmark_suite.msci_annual[h_label]
        q_msci = benchmark_suite.msci_quarterly[h_label]
        fbgrx_bm = benchmark_suite.fbgrx_annual[h_label]
        q_fbgrx_bm = benchmark_suite.fbgrx_quarterly[h_label]
        nasdaq_bm = benchmark_suite.nasdaq_annual[h_label]
        q_nasdaq_bm = benchmark_suite.nasdaq_quarterly[h_label]

        for univ in universes:
            univ_label = "S&P 500" if univ == "sp500" else "All World"
            prefix = "" if univ == "sp500" else "World "
            ew_suffix = " (EW)" if weight_by == "equal" else ""

            for n in n_values:
                sel = resolve_selector(strategy_name, n=n, weight_by=weight_by)
                frequencies = ["annual", "quarterly"] if compare_frequencies else [frequency]

                for freq in frequencies:
                    freq_suffix = f" ({freq.capitalize()})" if (len(frequencies) > 1 or freq == "quarterly") else ""

                    # 1. Pre-tax simulation
                    res_pre = simulator.run_simulation(
                        start_year=s_yr,
                        end_year=e_yr,
                        n=n,
                        selector=sel,
                        is_after_tax=False,
                        initial_capital=initial_capital,
                        universe=univ,
                        rebalance_frequency=freq,
                    )
                    if weight_by == "equal":
                        res_pre.strategy_name = f"{res_pre.strategy_name}_EW"
                    simulation_results.append(res_pre)

                    # 2. After-tax simulation
                    res_post = simulator.run_simulation(
                        start_year=s_yr,
                        end_year=e_yr,
                        n=n,
                        selector=sel,
                        is_after_tax=True,
                        tax_rate=tax_rate,
                        initial_capital=initial_capital,
                        universe=univ,
                        rebalance_frequency=freq,
                    )
                    if weight_by == "equal":
                        res_post.strategy_name = f"{res_post.strategy_name}_EW"
                    simulation_results.append(res_post)

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
                            "weighting": weight_by,
                        })

                    ref_spx_after = (
                        q_bm.after_cagr
                        if freq == "quarterly"
                        else bm.after_cagr
                    )
                    strat_label = f"{prefix}Top {n}{ew_suffix}{freq_suffix}"
                    table_rows.append(
                        build_strategy_row(
                            res_pre=res_pre,
                            res_post=res_post,
                            horizon_label=h_label,
                            spx_after_cagr=ref_spx_after,
                            strategy_label=strat_label,
                            universe_label=univ_label,
                        )
                    )

        # Benchmark rows (S&P 500, MSCI World, FBGRX, Nasdaq 100)
        if compare_frequencies:
            bench_configs = [
                ("Annual", bm, msci, fbgrx_bm, nasdaq_bm),
                ("Quarterly", q_bm, q_msci, q_fbgrx_bm, q_nasdaq_bm),
            ]
        elif frequency == "quarterly":
            bench_configs = [
                ("", q_bm, q_msci, q_fbgrx_bm, q_nasdaq_bm),
            ]
        else:
            bench_configs = [
                ("", bm, msci, fbgrx_bm, nasdaq_bm),
            ]

        for freq_tag, s_bm, m_bm, f_bm, n_bm in bench_configs:
            spx_label = f"S&P 500 ({freq_tag})" if freq_tag else "S&P 500"
            msci_label = f"MSCI World ({freq_tag})" if freq_tag else "MSCI World"
            fbgrx_label = f"FBGRX ({freq_tag})" if freq_tag else "FBGRX"
            nasdaq_label = f"Nasdaq 100 ({freq_tag})" if freq_tag else "Nasdaq 100"

            if include_spx:
                table_rows.append(
                    build_benchmark_row(
                        name=spx_label,
                        metrics=s_bm,
                        horizon_label=h_label,
                        spx_after_cagr=s_bm.after_cagr,
                        universe_label="S&P 500",
                    )
                )

            if include_msci:
                table_rows.append(
                    build_benchmark_row(
                        name=msci_label,
                        metrics=m_bm,
                        horizon_label=h_label,
                        spx_after_cagr=s_bm.after_cagr,
                        universe_label="All World",
                    )
                )

            if include_fbgrx:
                table_rows.append(
                    build_benchmark_row(
                        name=fbgrx_label,
                        metrics=f_bm,
                        horizon_label=h_label,
                        spx_after_cagr=s_bm.after_cagr,
                        universe_label="Mutual Fund",
                    )
                )

            if include_nasdaq:
                table_rows.append(
                    build_benchmark_row(
                        name=nasdaq_label,
                        metrics=n_bm,
                        horizon_label=h_label,
                        spx_after_cagr=s_bm.after_cagr,
                        universe_label="Nasdaq 100",
                    )
                )

    return simulation_results, trade_records, table_rows


def run_backtest(args: argparse.Namespace) -> int:
    """Execute backtest simulations, generate reports, and print summary tables.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code 0 on success.
    """
    data_loader = DataLoader()
    horizons = resolve_horizons(args.horizons)
    universes = resolve_universes(
        getattr(args, "universes", ["sp500", "world"]),
        data_loader.get_available_universes(),
    )
    n_values = resolve_n_values(args.n)
    weight_by = getattr(args, "weight_by", "market_cap")

    # 1. Compute benchmark suite
    benchmark_suite = compute_all_benchmarks(
        data_loader=data_loader,
        horizons=horizons,
        tax_rate=args.tax_rate,
        initial_capital=args.initial_capital,
        frequency=getattr(args, "frequency", "annual"),
        compare_frequencies=getattr(args, "compare_frequencies", False),
    )

    # 2. Run simulation matrix
    simulator = PortfolioSimulator(data_loader=data_loader)

    simulation_results, trade_records, table_rows = run_simulation_matrix(
        simulator=simulator,
        horizons=horizons,
        n_values=n_values,
        universes=universes,
        strategy_name=args.strategy,
        weight_by=weight_by,
        tax_rate=args.tax_rate,
        initial_capital=args.initial_capital,
        frequency=getattr(args, "frequency", "annual"),
        compare_frequencies=getattr(args, "compare_frequencies", False),
        benchmark_suite=benchmark_suite,
        benchmark_filter=getattr(args, "benchmark", "all"),
    )

    # 3. Export all report artifacts (unless suppressed)
    exported_files = {}
    if not getattr(args, "no_export", False):
        all_results = simulation_results + benchmark_suite.build_synthetic_results(
            horizons=horizons,
            tax_rate=args.tax_rate,
            initial_capital=args.initial_capital,
            frequency=getattr(args, "frequency", "annual"),
            compare_frequencies=getattr(args, "compare_frequencies", False),
        )
        scenario_data, annual_data, trades_data = build_scenario_and_apps_script_data(
            simulator=simulator,
            data_loader=data_loader,
            strategy_name=args.strategy,
            initial_capital=args.initial_capital,
            universes=universes,
        )
        exporter = ReportExporter(output_dir=args.output_dir, scripts_dir=args.scripts_dir)
        exported_files = exporter.export_all(
            results=all_results,
            trade_records=trade_records,
            spx_benchmarks=benchmark_suite.spx_benchmarks,
            scenario_data=scenario_data,
            annual_data=annual_data,
            trades_data=trades_data,
            initial_capital=args.initial_capital,
        )

    # 4. Display ASCII terminal comparison table
    if not args.quiet:
        print()
        print(
            format_terminal_table(
                table_rows,
                tax_rate=args.tax_rate,
                initial_capital=args.initial_capital,
                strategy_name=args.strategy,
                weight_by=weight_by,
            )
        )
        if exported_files:
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
