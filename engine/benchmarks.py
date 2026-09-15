"""Benchmark calculations and performance metrics across multiple horizons and frequencies."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from engine.data_loader import DataLoader
from engine.metrics import (
    calculate_benchmark_annual_series,
    calculate_cagr,
    calculate_cumulative_return,
    calculate_max_drawdown,
    calculate_tax_drag,
)


@dataclass
class BenchmarkMetrics:
    """Standardized performance and risk metrics for a single benchmark horizon."""

    tr_cagr: float
    tr_cum: float
    tr_max_dd: float
    after_cagr: float
    post_liq_cagr: float
    cum_return: float
    final_equity: float
    max_dd: float
    tax_drag: float
    total_dividends: float
    total_taxes: float
    alpha: float = 0.0
    bench_pre: Dict[str, Any] = field(default_factory=dict)
    bench_post: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkSuite:
    """Aggregated benchmark calculations across all tracked market indices and horizons."""

    spx_benchmarks: Dict[Any, Any]
    spx_annual: Dict[str, BenchmarkMetrics]
    spx_quarterly: Dict[str, BenchmarkMetrics]
    msci_annual: Dict[str, BenchmarkMetrics]
    msci_quarterly: Dict[str, BenchmarkMetrics]
    fbgrx_annual: Dict[str, BenchmarkMetrics]
    fbgrx_quarterly: Dict[str, BenchmarkMetrics]
    nasdaq_annual: Dict[str, BenchmarkMetrics]
    nasdaq_quarterly: Dict[str, BenchmarkMetrics]


def _calculate_series_metrics(
    pr_levels: List[float],
    tr_levels: List[float],
    horizon_years: int,
    tax_rate: float,
    initial_capital: float,
    spx_after_cagr: Optional[float] = None,
) -> BenchmarkMetrics:
    """Internal helper to calculate standardized metrics for a given price/total return series."""
    tr_cagr = calculate_cagr(tr_levels[0], tr_levels[-1], horizon_years)
    tr_cum = calculate_cumulative_return(tr_levels[0], tr_levels[-1])
    tr_max_dd = calculate_max_drawdown(tr_levels)

    bench_pre = calculate_benchmark_annual_series(
        pr_levels=pr_levels,
        tr_levels=tr_levels,
        tax_rate=0.0,
        initial_capital=initial_capital,
        is_after_tax=False,
    )

    bench_post = calculate_benchmark_annual_series(
        pr_levels=pr_levels,
        tr_levels=tr_levels,
        tax_rate=tax_rate,
        initial_capital=initial_capital,
        is_after_tax=True,
    )

    val_series = [initial_capital]
    curr_val = initial_capital
    for r_step in bench_post["annual_returns"]:
        curr_val *= (1.0 + r_step)
        val_series.append(curr_val)
    post_max_dd = calculate_max_drawdown(val_series)

    after_cagr = calculate_cagr(initial_capital, bench_post["pre_liquidation_wealth"], horizon_years)
    post_liq_cagr = calculate_cagr(initial_capital, bench_post["post_liquidation_wealth"], horizon_years)
    post_cum = calculate_cumulative_return(initial_capital, bench_post["final_equity"])
    post_taxes = bench_post["total_taxes_paid"]
    post_divs = bench_post["total_dividends_received"]
    tax_drag = calculate_tax_drag(tr_cagr, after_cagr)
    alpha = (after_cagr - spx_after_cagr) if spx_after_cagr is not None else 0.0

    return BenchmarkMetrics(
        tr_cagr=tr_cagr,
        tr_cum=tr_cum,
        tr_max_dd=tr_max_dd,
        after_cagr=after_cagr,
        post_liq_cagr=post_liq_cagr,
        cum_return=post_cum,
        final_equity=bench_post["final_equity"],
        max_dd=post_max_dd,
        tax_drag=tax_drag,
        total_dividends=post_divs,
        total_taxes=post_taxes,
        alpha=alpha,
        bench_pre=bench_pre,
        bench_post=bench_post,
    )


def calculate_spx_benchmark(
    data_loader: DataLoader,
    s_yr: int,
    e_yr: int,
    tax_rate: float,
    initial_capital: float,
    is_quarterly: bool = False,
) -> BenchmarkMetrics:
    """Calculate S&P 500 benchmark metrics for annual or quarterly frequency."""
    horizon_years = e_yr - s_yr
    if is_quarterly:
        pr_levels = [data_loader.get_spx_quarterly_level(s_yr, 4)]
        tr_levels = [data_loader.get_spx_tr_quarterly_level(s_yr, 4)]
        for y in range(s_yr + 1, e_yr + 1):
            for q in (1, 2, 3, 4):
                pr_levels.append(data_loader.get_spx_quarterly_level(y, q))
                tr_levels.append(data_loader.get_spx_tr_quarterly_level(y, q))
    else:
        pr_levels = [data_loader.get_spx_level(y) for y in range(s_yr, e_yr + 1)]
        tr_levels = [data_loader.get_spx_tr_level(y) for y in range(s_yr, e_yr + 1)]

    return _calculate_series_metrics(
        pr_levels=pr_levels,
        tr_levels=tr_levels,
        horizon_years=horizon_years,
        tax_rate=tax_rate,
        initial_capital=initial_capital,
        spx_after_cagr=None,
    )


def calculate_msci_world_benchmark(
    data_loader: DataLoader,
    s_yr: int,
    e_yr: int,
    tax_rate: float,
    initial_capital: float,
    is_quarterly: bool = False,
    spx_after_cagr: Optional[float] = None,
) -> BenchmarkMetrics:
    """Calculate MSCI World benchmark metrics for annual or quarterly frequency."""
    horizon_years = e_yr - s_yr
    if is_quarterly:
        pr_levels = [data_loader.get_msci_world_quarterly_level(s_yr, 4)]
        tr_levels = [data_loader.get_msci_world_tr_quarterly_level(s_yr, 4)]
        for y in range(s_yr + 1, e_yr + 1):
            for q in (1, 2, 3, 4):
                pr_levels.append(data_loader.get_msci_world_quarterly_level(y, q))
                tr_levels.append(data_loader.get_msci_world_tr_quarterly_level(y, q))
    else:
        pr_levels = [data_loader.get_msci_world_level(y) for y in range(s_yr, e_yr + 1)]
        tr_levels = [data_loader.get_msci_world_tr_level(y) for y in range(s_yr, e_yr + 1)]

    if spx_after_cagr is None:
        spx_metrics = calculate_spx_benchmark(
            data_loader, s_yr, e_yr, tax_rate, initial_capital, is_quarterly=is_quarterly
        )
        spx_after_cagr = spx_metrics.after_cagr

    return _calculate_series_metrics(
        pr_levels=pr_levels,
        tr_levels=tr_levels,
        horizon_years=horizon_years,
        tax_rate=tax_rate,
        initial_capital=initial_capital,
        spx_after_cagr=spx_after_cagr,
    )


def calculate_fbgrx_benchmark(
    data_loader: DataLoader,
    s_yr: int,
    e_yr: int,
    tax_rate: float,
    initial_capital: float,
    is_quarterly: bool = False,
    spx_after_cagr: Optional[float] = None,
) -> BenchmarkMetrics:
    """Calculate Fidelity Blue Chip Growth (FBGRX) benchmark metrics for annual or quarterly frequency."""
    horizon_years = e_yr - s_yr
    if is_quarterly:
        pr_levels = [data_loader.get_fbgrx_quarterly_level(s_yr, 4)]
        tr_levels = [data_loader.get_fbgrx_tr_quarterly_level(s_yr, 4)]
        for y in range(s_yr + 1, e_yr + 1):
            for q in (1, 2, 3, 4):
                pr_levels.append(data_loader.get_fbgrx_quarterly_level(y, q))
                tr_levels.append(data_loader.get_fbgrx_tr_quarterly_level(y, q))
    else:
        pr_levels = [data_loader.get_fbgrx_level(y) for y in range(s_yr, e_yr + 1)]
        tr_levels = [data_loader.get_fbgrx_tr_level(y) for y in range(s_yr, e_yr + 1)]

    if spx_after_cagr is None:
        spx_metrics = calculate_spx_benchmark(
            data_loader, s_yr, e_yr, tax_rate, initial_capital, is_quarterly=is_quarterly
        )
        spx_after_cagr = spx_metrics.after_cagr

    return _calculate_series_metrics(
        pr_levels=pr_levels,
        tr_levels=tr_levels,
        horizon_years=horizon_years,
        tax_rate=tax_rate,
        initial_capital=initial_capital,
        spx_after_cagr=spx_after_cagr,
    )


def calculate_nasdaq100_benchmark(
    data_loader: DataLoader,
    s_yr: int,
    e_yr: int,
    tax_rate: float,
    initial_capital: float,
    is_quarterly: bool = False,
    spx_after_cagr: Optional[float] = None,
) -> BenchmarkMetrics:
    """Calculate Nasdaq 100 benchmark metrics for annual or quarterly frequency."""
    horizon_years = e_yr - s_yr
    if is_quarterly:
        pr_levels = [data_loader.get_nasdaq_quarterly_level(s_yr, 4)]
        tr_levels = [data_loader.get_nasdaq_tr_quarterly_level(s_yr, 4)]
        for y in range(s_yr + 1, e_yr + 1):
            for q in (1, 2, 3, 4):
                pr_levels.append(data_loader.get_nasdaq_quarterly_level(y, q))
                tr_levels.append(data_loader.get_nasdaq_tr_quarterly_level(y, q))
    else:
        pr_levels = [data_loader.get_nasdaq_level(y) for y in range(s_yr, e_yr + 1)]
        tr_levels = [data_loader.get_nasdaq_tr_level(y) for y in range(s_yr, e_yr + 1)]

    if spx_after_cagr is None:
        spx_metrics = calculate_spx_benchmark(
            data_loader, s_yr, e_yr, tax_rate, initial_capital, is_quarterly=is_quarterly
        )
        spx_after_cagr = spx_metrics.after_cagr

    return _calculate_series_metrics(
        pr_levels=pr_levels,
        tr_levels=tr_levels,
        horizon_years=horizon_years,
        tax_rate=tax_rate,
        initial_capital=initial_capital,
        spx_after_cagr=spx_after_cagr,
    )


def compute_all_benchmarks(
    data_loader: DataLoader,
    horizons: List[Tuple[str, int, int]],
    tax_rate: float,
    initial_capital: float,
    frequency: str = "annual",
    compare_frequencies: bool = False,
) -> BenchmarkSuite:
    """Compute benchmark suites across all specified horizons and frequencies."""
    spx_benchmarks: Dict[Any, Any] = {}
    spx_annual: Dict[str, BenchmarkMetrics] = {}
    spx_quarterly: Dict[str, BenchmarkMetrics] = {}
    msci_annual: Dict[str, BenchmarkMetrics] = {}
    msci_quarterly: Dict[str, BenchmarkMetrics] = {}
    fbgrx_annual: Dict[str, BenchmarkMetrics] = {}
    fbgrx_quarterly: Dict[str, BenchmarkMetrics] = {}
    nasdaq_annual: Dict[str, BenchmarkMetrics] = {}
    nasdaq_quarterly: Dict[str, BenchmarkMetrics] = {}

    for h_label, s_yr, e_yr in horizons:
        horizon_years = e_yr - s_yr

        # 1. S&P 500 benchmarks (Annual & Quarterly)
        spx_ann = calculate_spx_benchmark(
            data_loader, s_yr, e_yr, tax_rate, initial_capital, is_quarterly=False
        )
        spx_qtr = calculate_spx_benchmark(
            data_loader, s_yr, e_yr, tax_rate, initial_capital, is_quarterly=True
        )
        spx_annual[h_label] = spx_ann
        spx_quarterly[h_label] = spx_qtr

        # 2. MSCI World benchmarks
        msci_annual[h_label] = calculate_msci_world_benchmark(
            data_loader, s_yr, e_yr, tax_rate, initial_capital, is_quarterly=False, spx_after_cagr=spx_ann.after_cagr
        )
        msci_quarterly[h_label] = calculate_msci_world_benchmark(
            data_loader, s_yr, e_yr, tax_rate, initial_capital, is_quarterly=True, spx_after_cagr=spx_qtr.after_cagr
        )

        # 3. FBGRX benchmarks
        fbgrx_annual[h_label] = calculate_fbgrx_benchmark(
            data_loader, s_yr, e_yr, tax_rate, initial_capital, is_quarterly=False, spx_after_cagr=spx_ann.after_cagr
        )
        fbgrx_quarterly[h_label] = calculate_fbgrx_benchmark(
            data_loader, s_yr, e_yr, tax_rate, initial_capital, is_quarterly=True, spx_after_cagr=spx_qtr.after_cagr
        )

        # 4. Nasdaq 100 benchmarks
        nasdaq_annual[h_label] = calculate_nasdaq100_benchmark(
            data_loader, s_yr, e_yr, tax_rate, initial_capital, is_quarterly=False, spx_after_cagr=spx_ann.after_cagr
        )
        nasdaq_quarterly[h_label] = calculate_nasdaq100_benchmark(
            data_loader, s_yr, e_yr, tax_rate, initial_capital, is_quarterly=True, spx_after_cagr=spx_qtr.after_cagr
        )

        # Store in spx_benchmarks for exporter and lookup compatibility
        ref_bench = (
            spx_qtr
            if frequency == "quarterly" and not compare_frequencies
            else spx_ann
        )
        spx_benchmarks[h_label] = ref_bench.tr_cagr
        spx_benchmarks[str(horizon_years)] = ref_bench.tr_cagr
        spx_benchmarks[horizon_years] = ref_bench.tr_cagr
        spx_benchmarks[(h_label, False)] = ref_bench.tr_cagr
        spx_benchmarks[(h_label, 0.0)] = ref_bench.tr_cagr
        spx_benchmarks[(h_label, True)] = ref_bench.after_cagr
        spx_benchmarks[(h_label, tax_rate)] = ref_bench.after_cagr
        spx_benchmarks[(horizon_years, tax_rate)] = ref_bench.after_cagr

    return BenchmarkSuite(
        spx_benchmarks=spx_benchmarks,
        spx_annual=spx_annual,
        spx_quarterly=spx_quarterly,
        msci_annual=msci_annual,
        msci_quarterly=msci_quarterly,
        fbgrx_annual=fbgrx_annual,
        fbgrx_quarterly=fbgrx_quarterly,
        nasdaq_annual=nasdaq_annual,
        nasdaq_quarterly=nasdaq_quarterly,
    )
