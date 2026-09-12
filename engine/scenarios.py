"""Scenario orchestration and multi-horizon matrix generation.

Generates pre-calculated simulation datasets across tax tiers and horizons
for reporting, interactive Google Apps Script sheets, and CLI comparisons.
"""

from typing import Any, Dict, List, Optional, Tuple

from engine.backtest import PortfolioSimulator
from engine.data_loader import DataLoader
from engine.metrics import (
    calculate_alpha,
    calculate_benchmark_annual_series,
    calculate_cagr,
    calculate_cumulative_return,
    calculate_max_drawdown,
)
from engine.models import StrategyResult, TradeOrder
from engine.selector import resolve_selector


def compute_scenario_grid(
    simulator: Optional[PortfolioSimulator] = None,
    data_loader: Optional[DataLoader] = None,
    strategy_name: str = "market_cap",
    initial_capital: float = 10000.0,
    universes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Execute quantitative backtest simulations across universes, tax tiers, and horizons.

    Runs multi-horizon simulations and pre-calculates portfolio results and benchmark
    series independently of Google Apps Script presentation formatting.

    Args:
        simulator: Optional PortfolioSimulator instance (created if None).
        data_loader: Optional DataLoader instance (created if None).
        strategy_name: 'market_cap' or 'performance'.
        initial_capital: Starting capital basis.
        universes: Optional list of constituent universe names (default: ['sp500', 'world']).

    Returns:
        Dict containing raw quantitative simulation results, benchmark metrics,
        30-year ledgers, and trade records.
    """
    if data_loader is None:
        data_loader = DataLoader()
    if simulator is None:
        simulator = PortfolioSimulator(data_loader)
    if universes is None:
        universes = ["sp500", "world"]

    horizons = [("10y", 2014, 2024), ("20y", 2004, 2024), ("30y", 1994, 2024)]
    tax_rates = [
        (0.0, "0.0%"),
        (0.15, "15.0%"),
        (0.20, "20.0%"),
        (0.30, "30.0%"),
        (0.37, "37.0%"),
    ]
    target_n_values = [3, 5, 10]
    weighting_schemes = [("market_cap", "Market Cap"), ("equal", "Equal Weight")]

    # Pre-calculate pre-tax results across universes, weighting schemes, and frequencies
    pretax_cache: Dict[Tuple[str, int, str, str, int, int], StrategyResult] = {}
    for univ in universes:
        for n in target_n_values:
            for w_key, _ in weighting_schemes:
                sel = resolve_selector(strategy_name, n=n, weight_by=w_key)
                for freq in ("annual", "quarterly"):
                    for _, s_yr, e_yr in horizons:
                        pretax_cache[(univ, n, w_key, freq, s_yr, e_yr)] = simulator.run_simulation(
                            s_yr,
                            e_yr,
                            n=n,
                            selector=sel,
                            is_after_tax=False,
                            initial_capital=initial_capital,
                            universe=univ,
                            rebalance_frequency=freq,
                        )

    active_results: List[Dict[str, Any]] = []
    spx_benchmarks: List[Dict[str, Any]] = []
    spx_q_benchmarks: List[Dict[str, Any]] = []
    msci_benchmarks: List[Dict[str, Any]] = []
    msci_q_benchmarks: List[Dict[str, Any]] = []
    fbgrx_benchmarks: List[Dict[str, Any]] = []
    fbgrx_q_benchmarks: List[Dict[str, Any]] = []

    for rate, rate_str in tax_rates:
        for h_label, s_yr, e_yr in horizons:
            horizon_years = e_yr - s_yr

            # S&P 500 Annual Benchmark
            pr_levels = [data_loader.get_spx_level(y) for y in range(s_yr, e_yr + 1)]
            tr_levels = [data_loader.get_spx_tr_level(y) for y in range(s_yr, e_yr + 1)]
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
                spx_cum = calculate_cumulative_return(initial_capital, bench["final_equity"])
                spx_final = bench["final_equity"]
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
                spx_cum = calculate_cumulative_return(initial_capital, bench["final_equity"])
                spx_final = bench["final_equity"]
                spx_taxes = bench["total_taxes_paid"]
                spx_tax_drag = spx_tr_cagr - spx_after_cagr
                spx_divs = bench["total_dividends_received"]

            spx_benchmarks.append({
                "rate": rate,
                "rate_str": rate_str,
                "h_label": h_label,
                "s_yr": s_yr,
                "e_yr": e_yr,
                "tr_cagr": spx_tr_cagr,
                "after_cagr": spx_after_cagr,
                "post_liq_cagr": spx_post_liq_cagr,
                "cum": spx_cum,
                "final": spx_final,
                "divs": spx_divs,
                "max_dd": spx_max_dd,
                "taxes": spx_taxes,
                "tax_drag": spx_tax_drag,
            })

            # S&P 500 Quarterly Benchmark
            spx_q_pr = [data_loader.get_spx_quarterly_level(s_yr, 4)]
            spx_q_tr = [data_loader.get_spx_tr_quarterly_level(s_yr, 4)]
            for y in range(s_yr + 1, e_yr + 1):
                for q in (1, 2, 3, 4):
                    spx_q_pr.append(data_loader.get_spx_quarterly_level(y, q))
                    spx_q_tr.append(data_loader.get_spx_tr_quarterly_level(y, q))
            spx_q_tr_cagr = calculate_cagr(spx_q_tr[0], spx_q_tr[-1], horizon_years)

            if rate == 0.0:
                spx_q_bench = calculate_benchmark_annual_series(
                    pr_levels=spx_q_pr,
                    tr_levels=spx_q_tr,
                    tax_rate=0.0,
                    initial_capital=initial_capital,
                    is_after_tax=False,
                )
                spx_q_after_cagr = spx_q_tr_cagr
                spx_q_post_liq_cagr = spx_q_tr_cagr
                spx_q_cum = calculate_cumulative_return(initial_capital, spx_q_bench["final_equity"])
                spx_q_final = spx_q_bench["final_equity"]
                spx_q_max_dd = calculate_max_drawdown(spx_q_tr)
                spx_q_taxes = 0.0
                spx_q_tax_drag = 0.0
                spx_q_divs = spx_q_bench["total_dividends_received"]
            else:
                spx_q_bench = calculate_benchmark_annual_series(
                    pr_levels=spx_q_pr,
                    tr_levels=spx_q_tr,
                    tax_rate=rate,
                    initial_capital=initial_capital,
                    is_after_tax=True,
                )
                spx_q_val_series = [initial_capital]
                q_curr_v = initial_capital
                for r_step in spx_q_bench["annual_returns"]:
                    q_curr_v *= (1.0 + r_step)
                    spx_q_val_series.append(q_curr_v)
                spx_q_max_dd = calculate_max_drawdown(spx_q_val_series)
                spx_q_after_cagr = calculate_cagr(initial_capital, spx_q_bench["pre_liquidation_wealth"], horizon_years)
                spx_q_post_liq_cagr = calculate_cagr(initial_capital, spx_q_bench["post_liquidation_wealth"], horizon_years)
                spx_q_cum = calculate_cumulative_return(initial_capital, spx_q_bench["final_equity"])
                spx_q_final = spx_q_bench["final_equity"]
                spx_q_taxes = spx_q_bench["total_taxes_paid"]
                spx_q_tax_drag = spx_q_tr_cagr - spx_q_after_cagr
                spx_q_divs = spx_q_bench["total_dividends_received"]

            spx_q_benchmarks.append({
                "rate": rate,
                "rate_str": rate_str,
                "h_label": h_label,
                "s_yr": s_yr,
                "e_yr": e_yr,
                "tr_cagr": spx_q_tr_cagr,
                "after_cagr": spx_q_after_cagr,
                "post_liq_cagr": spx_q_post_liq_cagr,
                "cum": spx_q_cum,
                "final": spx_q_final,
                "divs": spx_q_divs,
                "max_dd": spx_q_max_dd,
                "taxes": spx_q_taxes,
                "tax_drag": spx_q_tax_drag,
            })

            # 1. Active Strategy Portfolios for each universe, weighting, and frequency
            for univ in universes:
                univ_label = "S&P 500" if univ == "sp500" else "All World"
                for n in target_n_values:
                    for w_key, w_label in weighting_schemes:
                        for freq_str in ("Annual", "Quarterly"):
                            freq_key = freq_str.lower()
                            pre_res = pretax_cache[(univ, n, w_key, freq_key, s_yr, e_yr)]
                            sel = resolve_selector(strategy_name, n=n, weight_by=w_key)
                            ref_spx_tr = spx_q_tr_cagr if freq_str == "Quarterly" else spx_tr_cagr
                            ref_spx_after = spx_q_after_cagr if freq_str == "Quarterly" else spx_after_cagr

                            if rate == 0.0:
                                post_res = pre_res
                                tax_drag = 0.0
                                alpha = post_res.cagr - ref_spx_tr
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
                                    universe=univ,
                                    rebalance_frequency=freq_key,
                                )
                                tax_drag = pre_res.cagr - post_res.cagr
                                alpha = post_res.cagr - ref_spx_after
                                strat_cum = post_res.cumulative_return
                                strat_final = post_res.final_equity

                            strat_label = f"Top {n}"
                            key = f"{h_label}_{univ_label}_{strat_label}_{w_label}_{freq_str}_{rate_str}"
                            active_results.append({
                                "key": key,
                                "rate": rate,
                                "univ_label": univ_label,
                                "h_label": h_label,
                                "strat_label": strat_label,
                                "w_label": w_label,
                                "freq_str": freq_str,
                                "pre_cagr": pre_res.cagr,
                                "post_cagr": post_res.cagr,
                                "post_liq_cagr": post_res.post_liquidation_cagr,
                                "strat_cum": strat_cum,
                                "strat_final": strat_final,
                                "total_dividends": post_res.total_dividends_received,
                                "max_drawdown": post_res.max_drawdown,
                                "total_taxes": post_res.total_taxes_paid,
                                "tax_drag": tax_drag,
                                "alpha": alpha,
                            })

            # 3a. MSCI World Index Benchmark (Annual)
            msci_pr_levels = [data_loader.get_msci_world_level(y) for y in range(s_yr, e_yr + 1)]
            msci_tr_levels = [data_loader.get_msci_world_tr_level(y) for y in range(s_yr, e_yr + 1)]
            msci_tr_cagr = calculate_cagr(msci_tr_levels[0], msci_tr_levels[-1], horizon_years)

            if rate == 0.0:
                msci_bench = calculate_benchmark_annual_series(
                    pr_levels=msci_pr_levels,
                    tr_levels=msci_tr_levels,
                    tax_rate=0.0,
                    initial_capital=initial_capital,
                    is_after_tax=False,
                )
                msci_after_cagr = msci_tr_cagr
                msci_post_liq_cagr = msci_tr_cagr
                msci_cum = calculate_cumulative_return(initial_capital, msci_bench["final_equity"])
                msci_final = msci_bench["final_equity"]
                msci_max_dd = calculate_max_drawdown(msci_tr_levels)
                msci_taxes = 0.0
                msci_tax_drag = 0.0
                msci_divs = msci_bench["total_dividends_received"]
            else:
                msci_bench = calculate_benchmark_annual_series(
                    pr_levels=msci_pr_levels,
                    tr_levels=msci_tr_levels,
                    tax_rate=rate,
                    initial_capital=initial_capital,
                    is_after_tax=True,
                )
                msci_val_series = [initial_capital]
                m_curr_v = initial_capital
                for r_ann in msci_bench["annual_returns"]:
                    m_curr_v *= (1.0 + r_ann)
                    msci_val_series.append(m_curr_v)
                msci_max_dd = calculate_max_drawdown(msci_val_series)
                msci_after_cagr = calculate_cagr(initial_capital, msci_bench["pre_liquidation_wealth"], horizon_years)
                msci_post_liq_cagr = calculate_cagr(initial_capital, msci_bench["post_liquidation_wealth"], horizon_years)
                msci_cum = calculate_cumulative_return(initial_capital, msci_bench["final_equity"])
                msci_final = msci_bench["final_equity"]
                msci_taxes = msci_bench["total_taxes_paid"]
                msci_tax_drag = msci_tr_cagr - msci_after_cagr
                msci_divs = msci_bench["total_dividends_received"]

            msci_alpha = round(msci_after_cagr - spx_after_cagr, 6)
            msci_benchmarks.append({
                "rate": rate,
                "rate_str": rate_str,
                "h_label": h_label,
                "s_yr": s_yr,
                "e_yr": e_yr,
                "tr_cagr": msci_tr_cagr,
                "after_cagr": msci_after_cagr,
                "post_liq_cagr": msci_post_liq_cagr,
                "cum": msci_cum,
                "final": msci_final,
                "divs": msci_divs,
                "max_dd": msci_max_dd,
                "taxes": msci_taxes,
                "tax_drag": msci_tax_drag,
                "alpha": msci_alpha,
            })

            # 3b. MSCI World Index Benchmark (Quarterly)
            msci_q_pr = [data_loader.get_msci_world_quarterly_level(s_yr, 4)]
            msci_q_tr = [data_loader.get_msci_world_tr_quarterly_level(s_yr, 4)]
            for y in range(s_yr + 1, e_yr + 1):
                for q in (1, 2, 3, 4):
                    msci_q_pr.append(data_loader.get_msci_world_quarterly_level(y, q))
                    msci_q_tr.append(data_loader.get_msci_world_tr_quarterly_level(y, q))
            msci_q_tr_cagr = calculate_cagr(msci_q_tr[0], msci_q_tr[-1], horizon_years)

            if rate == 0.0:
                msci_q_bench = calculate_benchmark_annual_series(
                    pr_levels=msci_q_pr,
                    tr_levels=msci_q_tr,
                    tax_rate=0.0,
                    initial_capital=initial_capital,
                    is_after_tax=False,
                )
                msci_q_after_cagr = msci_q_tr_cagr
                msci_q_post_liq_cagr = msci_q_tr_cagr
                msci_q_cum = calculate_cumulative_return(initial_capital, msci_q_bench["final_equity"])
                msci_q_final = msci_q_bench["final_equity"]
                msci_q_max_dd = calculate_max_drawdown(msci_q_tr)
                msci_q_taxes = 0.0
                msci_q_tax_drag = 0.0
                msci_q_divs = msci_q_bench["total_dividends_received"]
            else:
                msci_q_bench = calculate_benchmark_annual_series(
                    pr_levels=msci_q_pr,
                    tr_levels=msci_q_tr,
                    tax_rate=rate,
                    initial_capital=initial_capital,
                    is_after_tax=True,
                )
                msci_q_val_series = [initial_capital]
                mq_curr_v = initial_capital
                for r_step in msci_q_bench["annual_returns"]:
                    mq_curr_v *= (1.0 + r_step)
                    msci_q_val_series.append(mq_curr_v)
                msci_q_max_dd = calculate_max_drawdown(msci_q_val_series)
                msci_q_after_cagr = calculate_cagr(initial_capital, msci_q_bench["pre_liquidation_wealth"], horizon_years)
                msci_q_post_liq_cagr = calculate_cagr(initial_capital, msci_q_bench["post_liquidation_wealth"], horizon_years)
                msci_q_cum = calculate_cumulative_return(initial_capital, msci_q_bench["final_equity"])
                msci_q_final = msci_q_bench["final_equity"]
                msci_q_taxes = msci_q_bench["total_taxes_paid"]
                msci_q_tax_drag = msci_q_tr_cagr - msci_q_after_cagr
                msci_q_divs = msci_q_bench["total_dividends_received"]

            msci_q_alpha = round(msci_q_after_cagr - spx_q_after_cagr, 6)
            msci_q_benchmarks.append({
                "rate": rate,
                "rate_str": rate_str,
                "h_label": h_label,
                "s_yr": s_yr,
                "e_yr": e_yr,
                "tr_cagr": msci_q_tr_cagr,
                "after_cagr": msci_q_after_cagr,
                "post_liq_cagr": msci_q_post_liq_cagr,
                "cum": msci_q_cum,
                "final": msci_q_final,
                "divs": msci_q_divs,
                "max_dd": msci_q_max_dd,
                "taxes": msci_q_taxes,
                "tax_drag": msci_q_tax_drag,
                "alpha": msci_q_alpha,
            })

            # 3c. FBGRX Mutual Fund Benchmark (Annual)
            fbgrx_pr_levels = [data_loader.get_fbgrx_level(y) for y in range(s_yr, e_yr + 1)]
            fbgrx_tr_levels = [data_loader.get_fbgrx_tr_level(y) for y in range(s_yr, e_yr + 1)]
            fbgrx_tr_cagr = calculate_cagr(fbgrx_tr_levels[0], fbgrx_tr_levels[-1], horizon_years)

            if rate == 0.0:
                fbgrx_bench = calculate_benchmark_annual_series(
                    pr_levels=fbgrx_pr_levels,
                    tr_levels=fbgrx_tr_levels,
                    tax_rate=0.0,
                    initial_capital=initial_capital,
                    is_after_tax=False,
                )
                fbgrx_after_cagr = fbgrx_tr_cagr
                fbgrx_post_liq_cagr = fbgrx_tr_cagr
                fbgrx_cum = calculate_cumulative_return(initial_capital, fbgrx_bench["final_equity"])
                fbgrx_final = fbgrx_bench["final_equity"]
                fbgrx_max_dd = calculate_max_drawdown(fbgrx_tr_levels)
                fbgrx_taxes = 0.0
                fbgrx_tax_drag = 0.0
                fbgrx_divs = fbgrx_bench["total_dividends_received"]
            else:
                fbgrx_bench = calculate_benchmark_annual_series(
                    pr_levels=fbgrx_pr_levels,
                    tr_levels=fbgrx_tr_levels,
                    tax_rate=rate,
                    initial_capital=initial_capital,
                    is_after_tax=True,
                )
                fbgrx_val_series = [initial_capital]
                f_curr_v = initial_capital
                for r_ann in fbgrx_bench["annual_returns"]:
                    f_curr_v *= (1.0 + r_ann)
                    fbgrx_val_series.append(f_curr_v)
                fbgrx_max_dd = calculate_max_drawdown(fbgrx_val_series)
                fbgrx_after_cagr = calculate_cagr(initial_capital, fbgrx_bench["pre_liquidation_wealth"], horizon_years)
                fbgrx_post_liq_cagr = calculate_cagr(initial_capital, fbgrx_bench["post_liquidation_wealth"], horizon_years)
                fbgrx_cum = calculate_cumulative_return(initial_capital, fbgrx_bench["final_equity"])
                fbgrx_final = fbgrx_bench["final_equity"]
                fbgrx_taxes = fbgrx_bench["total_taxes_paid"]
                fbgrx_tax_drag = fbgrx_tr_cagr - fbgrx_after_cagr
                fbgrx_divs = fbgrx_bench["total_dividends_received"]

            fbgrx_alpha = round(fbgrx_after_cagr - spx_after_cagr, 6)
            fbgrx_benchmarks.append({
                "rate": rate,
                "rate_str": rate_str,
                "h_label": h_label,
                "s_yr": s_yr,
                "e_yr": e_yr,
                "tr_cagr": fbgrx_tr_cagr,
                "after_cagr": fbgrx_after_cagr,
                "post_liq_cagr": fbgrx_post_liq_cagr,
                "cum": fbgrx_cum,
                "final": fbgrx_final,
                "divs": fbgrx_divs,
                "max_dd": fbgrx_max_dd,
                "taxes": fbgrx_taxes,
                "tax_drag": fbgrx_tax_drag,
                "alpha": fbgrx_alpha,
            })

            # 3d. FBGRX Mutual Fund Benchmark (Quarterly)
            fbgrx_q_pr = [data_loader.get_fbgrx_quarterly_level(s_yr, 4)]
            fbgrx_q_tr = [data_loader.get_fbgrx_tr_quarterly_level(s_yr, 4)]
            for y in range(s_yr + 1, e_yr + 1):
                for q in (1, 2, 3, 4):
                    fbgrx_q_pr.append(data_loader.get_fbgrx_quarterly_level(y, q))
                    fbgrx_q_tr.append(data_loader.get_fbgrx_tr_quarterly_level(y, q))
            fbgrx_q_tr_cagr = calculate_cagr(fbgrx_q_tr[0], fbgrx_q_tr[-1], horizon_years)

            if rate == 0.0:
                fbgrx_q_bench = calculate_benchmark_annual_series(
                    pr_levels=fbgrx_q_pr,
                    tr_levels=fbgrx_q_tr,
                    tax_rate=0.0,
                    initial_capital=initial_capital,
                    is_after_tax=False,
                )
                fbgrx_q_after_cagr = fbgrx_q_tr_cagr
                fbgrx_q_post_liq_cagr = fbgrx_q_tr_cagr
                fbgrx_q_cum = calculate_cumulative_return(initial_capital, fbgrx_q_bench["final_equity"])
                fbgrx_q_final = fbgrx_q_bench["final_equity"]
                fbgrx_q_max_dd = calculate_max_drawdown(fbgrx_q_tr)
                fbgrx_q_taxes = 0.0
                fbgrx_q_tax_drag = 0.0
                fbgrx_q_divs = fbgrx_q_bench["total_dividends_received"]
            else:
                fbgrx_q_bench = calculate_benchmark_annual_series(
                    pr_levels=fbgrx_q_pr,
                    tr_levels=fbgrx_q_tr,
                    tax_rate=rate,
                    initial_capital=initial_capital,
                    is_after_tax=True,
                )
                fbgrx_q_val_series = [initial_capital]
                fq_curr_v = initial_capital
                for r_step in fbgrx_q_bench["annual_returns"]:
                    fq_curr_v *= (1.0 + r_step)
                    fbgrx_q_val_series.append(fq_curr_v)
                fbgrx_q_max_dd = calculate_max_drawdown(fbgrx_q_val_series)
                fbgrx_q_after_cagr = calculate_cagr(initial_capital, fbgrx_q_bench["pre_liquidation_wealth"], horizon_years)
                fbgrx_q_post_liq_cagr = calculate_cagr(initial_capital, fbgrx_q_bench["post_liquidation_wealth"], horizon_years)
                fbgrx_q_cum = calculate_cumulative_return(initial_capital, fbgrx_q_bench["final_equity"])
                fbgrx_q_final = fbgrx_q_bench["final_equity"]
                fbgrx_q_taxes = fbgrx_q_bench["total_taxes_paid"]
                fbgrx_q_tax_drag = fbgrx_q_tr_cagr - fbgrx_q_after_cagr
                fbgrx_q_divs = fbgrx_q_bench["total_dividends_received"]

            fbgrx_q_alpha = round(fbgrx_q_after_cagr - spx_q_after_cagr, 6)
            fbgrx_q_benchmarks.append({
                "rate": rate,
                "rate_str": rate_str,
                "h_label": h_label,
                "s_yr": s_yr,
                "e_yr": e_yr,
                "tr_cagr": fbgrx_q_tr_cagr,
                "after_cagr": fbgrx_q_after_cagr,
                "post_liq_cagr": fbgrx_q_post_liq_cagr,
                "cum": fbgrx_q_cum,
                "final": fbgrx_q_final,
                "divs": fbgrx_q_divs,
                "max_dd": fbgrx_q_max_dd,
                "taxes": fbgrx_q_taxes,
                "tax_drag": fbgrx_q_tax_drag,
                "alpha": fbgrx_q_alpha,
            })

    # 30-Year Annual histories & trades at 30% baseline tax rate across universes
    res_30y_map: Dict[Tuple[str, int, str], StrategyResult] = {}
    trades_30y_map: Dict[Tuple[str, int], List[TradeOrder]] = {}

    for univ in universes:
        for n in target_n_values:
            sel = resolve_selector(strategy_name, n=n)
            for freq in ("annual", "quarterly"):
                res_30y = simulator.run_simulation(
                    1994,
                    2024,
                    n=n,
                    selector=sel,
                    is_after_tax=True,
                    tax_rate=0.30,
                    initial_capital=initial_capital,
                    universe=univ,
                    rebalance_frequency=freq,
                )
                res_30y_map[(univ, n, freq)] = res_30y
                if freq == "annual":
                    trades_30y_map[(univ, n)] = simulator.get_trades()

    return {
        "universes": universes,
        "horizons": horizons,
        "tax_rates": tax_rates,
        "target_n_values": target_n_values,
        "weighting_schemes": weighting_schemes,
        "initial_capital": initial_capital,
        "strategy_name": strategy_name,
        "pretax_cache": pretax_cache,
        "active_results": active_results,
        "spx_benchmarks": spx_benchmarks,
        "spx_q_benchmarks": spx_q_benchmarks,
        "msci_benchmarks": msci_benchmarks,
        "msci_q_benchmarks": msci_q_benchmarks,
        "fbgrx_benchmarks": fbgrx_benchmarks,
        "fbgrx_q_benchmarks": fbgrx_q_benchmarks,
        "res_30y_map": res_30y_map,
        "trades_30y_map": trades_30y_map,
        "data_loader": data_loader,
    }


def format_apps_script_payloads(
    grid: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """Format quantitative simulation grid data into Google Apps Script matrices.

    Translates quantitative results into 2D tables, formatted columns, and lookup
    matrices for Google Sheets.

    Args:
        grid: Output dictionary from compute_scenario_grid.

    Returns:
        Tuple of (scenario_data, annual_data, trades_data).
    """
    universes = grid["universes"]
    target_n_values = grid["target_n_values"]
    initial_capital = grid["initial_capital"]
    pretax_cache = grid["pretax_cache"]
    res_30y_map = grid["res_30y_map"]
    trades_30y_map = grid["trades_30y_map"]
    data_loader: DataLoader = grid["data_loader"]

    # Build scenario_rows
    scenario_rows: List[List[Any]] = []

    # Map benchmark rows by (rate, h_label)
    spx_bench_map = {(b["rate"], b["h_label"]): b for b in grid["spx_benchmarks"]}
    spx_q_bench_map = {(b["rate"], b["h_label"]): b for b in grid["spx_q_benchmarks"]}
    msci_bench_map = {(b["rate"], b["h_label"]): b for b in grid["msci_benchmarks"]}
    msci_q_bench_map = {(b["rate"], b["h_label"]): b for b in grid["msci_q_benchmarks"]}
    fbgrx_bench_map = {(b["rate"], b["h_label"]): b for b in grid["fbgrx_benchmarks"]}
    fbgrx_q_bench_map = {(b["rate"], b["h_label"]): b for b in grid["fbgrx_q_benchmarks"]}

    # Group active results by (rate, h_label) to maintain identical row order
    active_by_rate_h: Dict[Tuple[float, str], List[Dict[str, Any]]] = {}
    for ar in grid["active_results"]:
        key_pair = (ar["rate"], ar["h_label"])
        active_by_rate_h.setdefault(key_pair, []).append(ar)

    for rate, rate_str in grid["tax_rates"]:
        for h_label, _, _ in grid["horizons"]:
            key_pair = (rate, h_label)
            # 1. Active strategies for this (rate, horizon)
            for ar in active_by_rate_h.get(key_pair, []):
                scenario_rows.append([
                    ar["key"],
                    ar["rate"],
                    ar["univ_label"],
                    ar["h_label"],
                    ar["strat_label"],
                    ar["w_label"],
                    ar["freq_str"],
                    round(ar["pre_cagr"], 6),
                    round(ar["post_cagr"], 6),
                    round(ar["post_liq_cagr"], 6),
                    round(ar["strat_cum"], 6),
                    round(ar["strat_final"], 2),
                    round(ar["total_dividends"], 2),
                    round(ar["max_drawdown"], 6),
                    round(ar["total_taxes"], 2),
                    round(ar["tax_drag"], 6),
                    round(ar["alpha"], 6),
                    "Strategy",
                ])

            # 2a. S&P 500 Index Benchmark (Annual)
            spx_b = spx_bench_map[key_pair]
            spx_key = f"{h_label}_S&P 500_S&P 500_Annual_{rate_str}"
            scenario_rows.append([
                spx_key,
                rate,
                "S&P 500",
                h_label,
                "S&P 500",
                "Market Cap",
                "Annual",
                round(spx_b["tr_cagr"], 6),
                round(spx_b["after_cagr"], 6),
                round(spx_b["post_liq_cagr"], 6),
                round(spx_b["cum"], 6),
                round(spx_b["final"], 2),
                round(spx_b["divs"], 2),
                round(spx_b["max_dd"], 6),
                round(spx_b["taxes"], 2),
                round(spx_b["tax_drag"], 6),
                0.0,
                "Index",
            ])

            # 2b. S&P 500 Index Benchmark (Quarterly)
            spx_qb = spx_q_bench_map[key_pair]
            spx_q_key = f"{h_label}_S&P 500_S&P 500_Quarterly_{rate_str}"
            scenario_rows.append([
                spx_q_key,
                rate,
                "S&P 500",
                h_label,
                "S&P 500",
                "Market Cap",
                "Quarterly",
                round(spx_qb["tr_cagr"], 6),
                round(spx_qb["after_cagr"], 6),
                round(spx_qb["post_liq_cagr"], 6),
                round(spx_qb["cum"], 6),
                round(spx_qb["final"], 2),
                round(spx_qb["divs"], 2),
                round(spx_qb["max_dd"], 6),
                round(spx_qb["taxes"], 2),
                round(spx_qb["tax_drag"], 6),
                0.0,
                "Index",
            ])

            # 3a. MSCI World Index Benchmark (Annual)
            msci_b = msci_bench_map[key_pair]
            msci_key = f"{h_label}_All World_MSCI World_Annual_{rate_str}"
            scenario_rows.append([
                msci_key,
                rate,
                "All World",
                h_label,
                "MSCI World",
                "Market Cap",
                "Annual",
                round(msci_b["tr_cagr"], 6),
                round(msci_b["after_cagr"], 6),
                round(msci_b["post_liq_cagr"], 6),
                round(msci_b["cum"], 6),
                round(msci_b["final"], 2),
                round(msci_b["divs"], 2),
                round(msci_b["max_dd"], 6),
                round(msci_b["taxes"], 2),
                round(msci_b["tax_drag"], 6),
                msci_b["alpha"],
                "Index",
            ])

            # 3b. MSCI World Index Benchmark (Quarterly)
            msci_qb = msci_q_bench_map[key_pair]
            msci_q_key = f"{h_label}_All World_MSCI World_Quarterly_{rate_str}"
            scenario_rows.append([
                msci_q_key,
                rate,
                "All World",
                h_label,
                "MSCI World",
                "Market Cap",
                "Quarterly",
                round(msci_qb["tr_cagr"], 6),
                round(msci_qb["after_cagr"], 6),
                round(msci_qb["post_liq_cagr"], 6),
                round(msci_qb["cum"], 6),
                round(msci_qb["final"], 2),
                round(msci_qb["divs"], 2),
                round(msci_qb["max_dd"], 6),
                round(msci_qb["taxes"], 2),
                round(msci_qb["tax_drag"], 6),
                msci_qb["alpha"],
                "Index",
            ])

            # 4a. FBGRX Benchmark (Annual)
            fbgrx_b = fbgrx_bench_map[key_pair]
            fbgrx_key = f"{h_label}_FBGRX_FBGRX_Annual_{rate_str}"
            scenario_rows.append([
                fbgrx_key,
                rate,
                "FBGRX",
                h_label,
                "FBGRX",
                "Market Cap",
                "Annual",
                round(fbgrx_b["tr_cagr"], 6),
                round(fbgrx_b["after_cagr"], 6),
                round(fbgrx_b["post_liq_cagr"], 6),
                round(fbgrx_b["cum"], 6),
                round(fbgrx_b["final"], 2),
                round(fbgrx_b["divs"], 2),
                round(fbgrx_b["max_dd"], 6),
                round(fbgrx_b["taxes"], 2),
                round(fbgrx_b["tax_drag"], 6),
                fbgrx_b["alpha"],
                "Mutual Fund",
            ])

            # 4b. FBGRX Benchmark (Quarterly)
            fbgrx_qb = fbgrx_q_bench_map[key_pair]
            fbgrx_q_key = f"{h_label}_FBGRX_FBGRX_Quarterly_{rate_str}"
            scenario_rows.append([
                fbgrx_q_key,
                rate,
                "FBGRX",
                h_label,
                "FBGRX",
                "Market Cap",
                "Quarterly",
                round(fbgrx_qb["tr_cagr"], 6),
                round(fbgrx_qb["after_cagr"], 6),
                round(fbgrx_qb["post_liq_cagr"], 6),
                round(fbgrx_qb["cum"], 6),
                round(fbgrx_qb["final"], 2),
                round(fbgrx_qb["divs"], 2),
                round(fbgrx_qb["max_dd"], 6),
                round(fbgrx_qb["taxes"], 2),
                round(fbgrx_qb["tax_drag"], 6),
                fbgrx_qb["alpha"],
                "Mutual Fund",
            ])

    # 30-Year Annual histories & trades at 30% baseline tax rate
    annual_data: Dict[str, List[List[Any]]] = {}
    trade_rows: List[Dict[str, Any]] = []

    for univ in universes:
        prefix = "" if univ == "sp500" else "World "
        key_prefix = "" if univ == "sp500" else "world_"
        for n in target_n_values:
            res_30y = res_30y_map[(univ, n, "annual")]
            trades_30y = trades_30y_map.get((univ, n), [])

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
            annual_data[f"{key_prefix}top_{n}"] = ledger_rows

            for t in trades_30y:
                trade_rows.append({
                    "year": t.year,
                    "strategy_name": f"{prefix}Top {n}",
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

    # Historical Market Regime Breakdown (5 Eras across Universe x Frequency)
    eras = [
        ("1995-1999", 1995, 1999, "Late '90s Dot-Com Boom"),
        ("2000-2009", 2000, 2009, "The 'Lost Decade' (Tech Bust & GFC)"),
        ("2010-2019", 2010, 2019, "ZIRP & Tech Expansion"),
        ("2020-2024", 2020, 2024, "Mega-Cap Tech & AI Concentration"),
        ("1995-2024", 1995, 2024, "Full 30-Year Horizon"),
    ]

    def _cagr(rets: List[float]) -> float:
        p = 1.0
        for r in rets:
            p *= (1.0 + r)
        return (p ** (1.0 / len(rets)) - 1.0) if rets else 0.0

    era_matrix: List[List[Any]] = []
    era_rows: List[List[Any]] = []

    for u in universes:
        u_label = "S&P 500" if u == "sp500" else "All World"
        for f_key in ("annual", "quarterly"):
            f_label = "Annual" if f_key == "annual" else "Quarterly"
            lookup_key = f"{u_label}_{f_label}"
            t3_p = pretax_cache.get((u, 3, "market_cap", f_key, 1994, 2024))
            t5_p = pretax_cache.get((u, 5, "market_cap", f_key, 1994, 2024))
            t10_p = pretax_cache.get((u, 10, "market_cap", f_key, 1994, 2024))

            bench_annual_rets: Dict[int, float] = {}
            if u == "sp500":
                if f_key == "annual":
                    for y in range(1995, 2025):
                        tr_now = data_loader.get_spx_tr_level(y)
                        tr_prev = data_loader.get_spx_tr_level(y - 1)
                        bench_annual_rets[y] = (tr_now - tr_prev) / tr_prev
                else:
                    for y in range(1995, 2025):
                        tr_now = data_loader.get_spx_tr_quarterly_level(y, 4)
                        tr_prev = data_loader.get_spx_tr_quarterly_level(y - 1, 4)
                        bench_annual_rets[y] = (tr_now - tr_prev) / tr_prev
            else:
                if f_key == "annual":
                    for y in range(1995, 2025):
                        tr_now = data_loader.get_msci_world_tr_level(y)
                        tr_prev = data_loader.get_msci_world_tr_level(y - 1)
                        bench_annual_rets[y] = (tr_now - tr_prev) / tr_prev
                else:
                    for y in range(1995, 2025):
                        tr_now = data_loader.get_msci_world_tr_quarterly_level(y, 4)
                        tr_prev = data_loader.get_msci_world_tr_quarterly_level(y - 1, 4)
                        bench_annual_rets[y] = (tr_now - tr_prev) / tr_prev

            if t3_p and t5_p and t10_p:
                for label, sy, ey, desc in eras:
                    ny = ey - sy + 1
                    t3_sub = [e.gross_return for e in t3_p.annual_history if sy <= e.year <= ey]
                    t5_sub = [e.gross_return for e in t5_p.annual_history if sy <= e.year <= ey]
                    t10_sub = [e.gross_return for e in t10_p.annual_history if sy <= e.year <= ey]
                    bench_sub = [bench_annual_rets.get(y, 0.0) for y in range(sy, ey + 1)]

                    c3, c5, c10, cbench = _cagr(t3_sub), _cagr(t5_sub), _cagr(t10_sub), _cagr(bench_sub)
                    wins10 = sum(1 for a, b in zip(t10_sub, bench_sub) if a > b)
                    win_rate = wins10 / ny if ny > 0 else 0.0
                    alpha10 = c10 - cbench

                    era_matrix.append([
                        lookup_key,
                        label,
                        desc,
                        round(c3, 6),
                        round(c5, 6),
                        round(c10, 6),
                        round(cbench, 6),
                        round(alpha10, 6),
                        round(win_rate, 4),
                    ])

                    if u == "sp500" and f_key == "annual":
                        era_rows.append([
                            label,
                            desc,
                            round(c3, 6),
                            round(c5, 6),
                            round(c10, 6),
                            round(cbench, 6),
                            round(alpha10, 6),
                            round(win_rate, 4),
                        ])

    # 30-Year Wealth Accumulation & Drawdown Trajectories (After-Tax 30% Baseline)
    years_30y = list(range(1994, 2025))

    def _calc_dd(vals: List[float]) -> List[float]:
        if not vals:
            return []
        peak = vals[0]
        dds: List[float] = []
        for v in vals:
            if v > peak:
                peak = v
            dds.append((v - peak) / peak if peak > 0 else 0.0)
        return dds

    # Benchmark Trajectories (30y)
    pr_30y_spx = [data_loader.get_spx_level(y) for y in range(1994, 2025)]
    tr_30y_spx = [data_loader.get_spx_tr_level(y) for y in range(1994, 2025)]
    spx_bench_ann = calculate_benchmark_annual_series(
        pr_levels=pr_30y_spx,
        tr_levels=tr_30y_spx,
        tax_rate=0.30,
        initial_capital=initial_capital,
        is_after_tax=True,
    )
    spx_val_ann = initial_capital
    spx_traj_ann = [initial_capital]
    for r in spx_bench_ann["annual_returns"]:
        spx_val_ann *= (1.0 + r)
        spx_traj_ann.append(spx_val_ann)

    spx_q_pr_30y = [data_loader.get_spx_quarterly_level(1994, 4)]
    spx_q_tr_30y = [data_loader.get_spx_tr_quarterly_level(1994, 4)]
    for y in range(1995, 2025):
        for q in (1, 2, 3, 4):
            spx_q_pr_30y.append(data_loader.get_spx_quarterly_level(y, q))
            spx_q_tr_30y.append(data_loader.get_spx_tr_quarterly_level(y, q))
    spx_bench_q = calculate_benchmark_annual_series(
        pr_levels=spx_q_pr_30y,
        tr_levels=spx_q_tr_30y,
        tax_rate=0.30,
        initial_capital=initial_capital,
        is_after_tax=True,
    )
    spx_q_val = initial_capital
    spx_traj_q = [initial_capital]
    for idx, r_step in enumerate(spx_bench_q["annual_returns"], start=1):
        spx_q_val *= (1.0 + r_step)
        if idx % 4 == 0:
            spx_traj_q.append(spx_q_val)

    msci_pr_30y = [data_loader.get_msci_world_level(y) for y in range(1994, 2025)]
    msci_tr_30y = [data_loader.get_msci_world_tr_level(y) for y in range(1994, 2025)]
    msci_bench_ann = calculate_benchmark_annual_series(
        pr_levels=msci_pr_30y,
        tr_levels=msci_tr_30y,
        tax_rate=0.30,
        initial_capital=initial_capital,
        is_after_tax=True,
    )
    msci_val_ann = initial_capital
    msci_traj_ann = [initial_capital]
    for r in msci_bench_ann["annual_returns"]:
        msci_val_ann *= (1.0 + r)
        msci_traj_ann.append(msci_val_ann)

    msci_q_pr_30y = [data_loader.get_msci_world_quarterly_level(1994, 4)]
    msci_q_tr_30y = [data_loader.get_msci_world_tr_quarterly_level(1994, 4)]
    for y in range(1995, 2025):
        for q in (1, 2, 3, 4):
            msci_q_pr_30y.append(data_loader.get_msci_world_quarterly_level(y, q))
            msci_q_tr_30y.append(data_loader.get_msci_world_tr_quarterly_level(y, q))
    msci_bench_q = calculate_benchmark_annual_series(
        pr_levels=msci_q_pr_30y,
        tr_levels=msci_q_tr_30y,
        tax_rate=0.30,
        initial_capital=initial_capital,
        is_after_tax=True,
    )
    msci_q_val = initial_capital
    msci_traj_q = [initial_capital]
    for idx, r_step in enumerate(msci_bench_q["annual_returns"], start=1):
        msci_q_val *= (1.0 + r_step)
        if idx % 4 == 0:
            msci_traj_q.append(msci_q_val)

    fbgrx_pr_30y = [data_loader.get_fbgrx_level(y) for y in range(1994, 2025)]
    fbgrx_tr_30y = [data_loader.get_fbgrx_tr_level(y) for y in range(1994, 2025)]
    fbgrx_bench_ann = calculate_benchmark_annual_series(
        pr_levels=fbgrx_pr_30y,
        tr_levels=fbgrx_tr_30y,
        tax_rate=0.30,
        initial_capital=initial_capital,
        is_after_tax=True,
    )
    fbgrx_val_ann = initial_capital
    fbgrx_traj_ann = [initial_capital]
    for r in fbgrx_bench_ann["annual_returns"]:
        fbgrx_val_ann *= (1.0 + r)
        fbgrx_traj_ann.append(fbgrx_val_ann)

    fbgrx_q_pr_30y = [data_loader.get_fbgrx_quarterly_level(1994, 4)]
    fbgrx_q_tr_30y = [data_loader.get_fbgrx_tr_quarterly_level(1994, 4)]
    for y in range(1995, 2025):
        for q in (1, 2, 3, 4):
            fbgrx_q_pr_30y.append(data_loader.get_fbgrx_quarterly_level(y, q))
            fbgrx_q_tr_30y.append(data_loader.get_fbgrx_tr_quarterly_level(y, q))
    fbgrx_bench_q = calculate_benchmark_annual_series(
        pr_levels=fbgrx_q_pr_30y,
        tr_levels=fbgrx_q_tr_30y,
        tax_rate=0.30,
        initial_capital=initial_capital,
        is_after_tax=True,
    )
    fbgrx_q_val = initial_capital
    fbgrx_traj_q = [initial_capital]
    for idx, r_step in enumerate(fbgrx_bench_q["annual_returns"], start=1):
        fbgrx_q_val *= (1.0 + r_step)
        if idx % 4 == 0:
            fbgrx_traj_q.append(fbgrx_q_val)

    benchmarks = [
        ("S&P 500", spx_traj_ann, spx_traj_q),
        ("MSCI World", msci_traj_ann, msci_traj_q),
        ("FBGRX", fbgrx_traj_ann, fbgrx_traj_q),
    ]

    trajectory_matrix: List[List[Any]] = []
    drawdown_matrix: List[List[Any]] = []
    trajectory_rows: List[List[Any]] = []
    drawdown_rows: List[List[Any]] = []

    for u in universes:
        u_label = "S&P 500" if u == "sp500" else "All World"
        for b_label, b_ann, b_q in benchmarks:
            for f_key in ("annual", "quarterly"):
                f_label = "Annual" if f_key == "annual" else "Quarterly"
                lookup_key = f"{u_label}_{b_label}_{f_label}"

                t3_r = res_30y_map.get((u, 3, f_key))
                t5_r = res_30y_map.get((u, 5, f_key))
                t10_r = res_30y_map.get((u, 10, f_key))

                t3_t = [initial_capital] + ([e.ending_value_aftertax for e in t3_r.annual_history] if t3_r else [])
                t5_t = [initial_capital] + ([e.ending_value_aftertax for e in t5_r.annual_history] if t5_r else [])
                t10_t = [initial_capital] + ([e.ending_value_aftertax for e in t10_r.annual_history] if t10_r else [])

                bench_t = b_ann if f_key == "annual" else b_q

                dd3_m = _calc_dd(t3_t)
                dd5_m = _calc_dd(t5_t)
                dd10_m = _calc_dd(t10_t)
                ddbench_m = _calc_dd(bench_t)

                for y, v3, v5, v10, vb in zip(years_30y, t3_t, t5_t, t10_t, bench_t):
                    trajectory_matrix.append([
                        lookup_key,
                        y,
                        round(v3, 2),
                        round(v5, 2),
                        round(v10, 2),
                        round(vb, 2),
                    ])

                for y, d3, d5, d10, db in zip(years_30y, dd3_m, dd5_m, dd10_m, ddbench_m):
                    drawdown_matrix.append([
                        lookup_key,
                        y,
                        round(d3, 6),
                        round(d5, 6),
                        round(d10, 6),
                        round(db, 6),
                    ])

                if (u == "sp500" or u == universes[0]) and b_label == "S&P 500" and f_key == "annual" and not trajectory_rows:
                    for y, v3, v5, v10, vb in zip(years_30y, t3_t, t5_t, t10_t, bench_t):
                        trajectory_rows.append([y, round(v3, 2), round(v5, 2), round(v10, 2), round(vb, 2)])
                    for y, d3, d5, d10, db in zip(years_30y, dd3_m, dd5_m, dd10_m, ddbench_m):
                        drawdown_rows.append([y, round(d3, 6), round(d5, 6), round(d10, 6), round(db, 6)])

    annual_data["spx"] = spx_rows
    annual_data["era_data"] = era_rows
    annual_data["trajectory_data"] = trajectory_rows
    annual_data["drawdown_data"] = drawdown_rows
    annual_data["era_matrix"] = era_matrix
    annual_data["trajectory_matrix"] = trajectory_matrix
    annual_data["drawdown_matrix"] = drawdown_matrix
    scenario_data = {"scenario_rows": scenario_rows}

    return scenario_data, annual_data, trade_rows


def build_scenario_and_apps_script_data(
    simulator: Optional[PortfolioSimulator] = None,
    data_loader: Optional[DataLoader] = None,
    strategy_name: str = "market_cap",
    initial_capital: float = 10000.0,
    universes: Optional[List[str]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """Build multi-tier scenario tables and annual sheets for Google Apps Script.

    High-level facade orchestrating compute_scenario_grid and format_apps_script_payloads.
    """
    grid = compute_scenario_grid(
        simulator=simulator,
        data_loader=data_loader,
        strategy_name=strategy_name,
        initial_capital=initial_capital,
        universes=universes,
    )
    return format_apps_script_payloads(grid)


def build_default_scenario_data() -> Dict[str, Any]:
    """Execute standard backtest simulations to generate data for Google Apps Script.

    Backward-compatible helper returning a consolidated dictionary.
    """
    scenario_data, annual_data, trades_data = build_scenario_and_apps_script_data()
    return {
        "scenario_rows": scenario_data["scenario_rows"],
        "top3_annual": annual_data["top_3"],
        "top5_annual": annual_data["top_5"],
        "top10_annual": annual_data["top_10"],
        "world_top3_annual": annual_data.get("world_top_3", []),
        "world_top5_annual": annual_data.get("world_top_5", []),
        "world_top10_annual": annual_data.get("world_top_10", []),
        "spx_data": annual_data["spx"],
        "trades_data": trades_data,
        "era_data": annual_data["era_data"],
        "trajectory_data": annual_data["trajectory_data"],
        "drawdown_data": annual_data["drawdown_data"],
        "era_matrix": annual_data.get("era_matrix", []),
        "trajectory_matrix": annual_data.get("trajectory_matrix", []),
        "drawdown_matrix": annual_data.get("drawdown_matrix", []),
    }
