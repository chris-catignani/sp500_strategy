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
from engine.models import StrategyResult
from engine.selector import resolve_selector


def build_scenario_and_apps_script_data(
    simulator: Optional[PortfolioSimulator] = None,
    data_loader: Optional[DataLoader] = None,
    strategy_name: str = "market_cap",
    initial_capital: float = 10000.0,
    universes: Optional[List[str]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """Build multi-tier scenario tables and annual sheets for Google Apps Script.

    Runs simulations across tax tiers (0.0%, 15.0%, 20.0%, 30.0%, 37.0%) and
    generates 30-year annual ledgers for Top 3, Top 5, Top 10, plus S&P 500 benchmark.

    Args:
        simulator: Optional PortfolioSimulator instance (created if None).
        data_loader: Optional DataLoader instance (created if None).
        strategy_name: 'market_cap' or 'performance'.
        initial_capital: Starting capital basis.
        universes: Optional list of constituent universe names (default: ['sp500', 'world']).

    Returns:
        Tuple of (scenario_data, annual_data, trades_data).
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

    # Pre-calculate pre-tax results across universes
    pretax_cache: Dict[Tuple[str, int, int, int], StrategyResult] = {}
    for univ in universes:
        for n in target_n_values:
            sel = resolve_selector(strategy_name, n=n)
            for _, s_yr, e_yr in horizons:
                pretax_cache[(univ, n, s_yr, e_yr)] = simulator.run_simulation(
                    s_yr,
                    e_yr,
                    n=n,
                    selector=sel,
                    is_after_tax=False,
                    initial_capital=initial_capital,
                    universe=univ,
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

            # 1. Active Strategy Portfolios for each universe
            for univ in universes:
                univ_label = "S&P 500" if univ == "sp500" else "All World"
                for n in target_n_values:
                    pre_res = pretax_cache[(univ, n, s_yr, e_yr)]
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
                            universe=univ,
                        )
                        tax_drag = pre_res.cagr - post_res.post_liquidation_cagr
                        alpha = post_res.post_liquidation_cagr - spx_post_liq_cagr
                        strat_cum = calculate_cumulative_return(initial_capital, post_res.post_liquidation_wealth)
                        strat_final = post_res.post_liquidation_wealth

                    strat_label = f"Top {n}"
                    key = f"{h_label}_{univ_label}_{strat_label}_{rate_str}"
                    scenario_rows.append([
                        key,
                        rate,
                        univ_label,
                        h_label,
                        strat_label,
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
                        "Strategy",
                    ])

            # 2. S&P 500 Index Benchmark (16 columns)
            spx_key = f"{h_label}_S&P 500_S&P 500_{rate_str}"
            scenario_rows.append([
                spx_key,
                rate,
                "S&P 500",
                h_label,
                "S&P 500",
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
                "Index",
            ])

            # 3. MSCI World Index Benchmark (16 columns)
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
                msci_cum = calculate_cumulative_return(initial_capital, msci_bench["post_liquidation_wealth"])
                msci_final = msci_bench["post_liquidation_wealth"]
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
                msci_cum = calculate_cumulative_return(initial_capital, msci_bench["post_liquidation_wealth"])
                msci_final = msci_bench["post_liquidation_wealth"]
                msci_taxes = msci_bench["total_taxes_paid"]
                msci_tax_drag = msci_tr_cagr - msci_post_liq_cagr
                msci_divs = msci_bench["total_dividends_received"]

            msci_alpha = round(msci_post_liq_cagr - spx_post_liq_cagr, 6)
            msci_key = f"{h_label}_All World_MSCI World_{rate_str}"
            scenario_rows.append([
                msci_key,
                rate,
                "All World",
                h_label,
                "MSCI World",
                round(msci_tr_cagr, 6),
                round(msci_after_cagr, 6),
                round(msci_post_liq_cagr, 6),
                round(msci_cum, 6),
                round(msci_final, 2),
                round(msci_divs, 2),
                round(msci_max_dd, 6),
                round(msci_taxes, 2),
                round(msci_tax_drag, 6),
                msci_alpha,
                "Index",
            ])

    # 30-Year Annual histories & trades at 30% baseline tax rate across universes
    annual_data: Dict[str, List[List[Any]]] = {}
    trade_rows: List[Dict[str, Any]] = []
    res_30y_map: Dict[Tuple[str, int], StrategyResult] = {}

    for univ in universes:
        prefix = "" if univ == "sp500" else "World "
        key_prefix = "" if univ == "sp500" else "world_"
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
                universe=univ,
            )
            res_30y_map[(univ, n)] = res_30y
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

    # Historical Market Regime Breakdown (4 Eras + Full 30-Year)
    eras = [
        ("1995-1999", 1995, 1999, "Late '90s Dot-Com Boom"),
        ("2000-2009", 2000, 2009, "The 'Lost Decade' (Tech Bust & GFC)"),
        ("2010-2019", 2010, 2019, "ZIRP & Tech Expansion"),
        ("2020-2024", 2020, 2024, "Mega-Cap Tech & AI Concentration"),
        ("1995-2024", 1995, 2024, "Full 30-Year Horizon"),
    ]
    baseline_univ = "sp500" if "sp500" in universes else (universes[0] if universes else "sp500")
    t3_pre = pretax_cache.get((baseline_univ, 3, 1994, 2024))
    t5_pre = pretax_cache.get((baseline_univ, 5, 1994, 2024))
    t10_pre = pretax_cache.get((baseline_univ, 10, 1994, 2024))

    era_rows: List[List[Any]] = []
    if t3_pre and t5_pre and t10_pre:
        for label, sy, ey, desc in eras:
            ny = ey - sy + 1
            t3_sub = [e.gross_return for e in t3_pre.annual_history if sy <= e.year <= ey]
            t5_sub = [e.gross_return for e in t5_pre.annual_history if sy <= e.year <= ey]
            t10_sub = [e.gross_return for e in t10_pre.annual_history if sy <= e.year <= ey]
            spx_sub = [e.spx_return for e in t10_pre.annual_history if sy <= e.year <= ey]

            def _cagr(rets: List[float]) -> float:
                p = 1.0
                for r in rets:
                    p *= (1.0 + r)
                return (p ** (1.0 / len(rets)) - 1.0) if rets else 0.0

            c3, c5, c10, cspx = _cagr(t3_sub), _cagr(t5_sub), _cagr(t10_sub), _cagr(spx_sub)
            wins10 = sum(1 for a, b in zip(t10_sub, spx_sub) if a > b)
            win_rate = wins10 / ny if ny > 0 else 0.0
            alpha10 = c10 - cspx
            era_rows.append([
                label,
                desc,
                round(c3, 6),
                round(c5, 6),
                round(c10, 6),
                round(cspx, 6),
                round(alpha10, 6),
                round(win_rate, 4),
            ])

    # 30-Year Wealth Accumulation & Drawdown Trajectories (After-Tax 30% Baseline)
    pr_30y = [data_loader.get_spx_level(y) for y in range(1994, 2025)]
    tr_30y = [data_loader.get_spx_tr_level(y) for y in range(1994, 2025)]
    spx_bench_30y = calculate_benchmark_annual_series(
        pr_levels=pr_30y,
        tr_levels=tr_30y,
        tax_rate=0.30,
        initial_capital=initial_capital,
        is_after_tax=True,
    )
    spx_val = initial_capital
    spx_traj = [initial_capital]
    for r_spx in spx_bench_30y["annual_returns"]:
        spx_val *= (1.0 + r_spx)
        spx_traj.append(spx_val)

    t3_res = res_30y_map.get((baseline_univ, 3))
    t5_res = res_30y_map.get((baseline_univ, 5))
    t10_res = res_30y_map.get((baseline_univ, 10))

    t3_traj = [initial_capital] + ([e.ending_value_aftertax for e in t3_res.annual_history] if t3_res else [])
    t5_traj = [initial_capital] + ([e.ending_value_aftertax for e in t5_res.annual_history] if t5_res else [])
    t10_traj = [initial_capital] + ([e.ending_value_aftertax for e in t10_res.annual_history] if t10_res else [])

    years_30y = list(range(1994, 2025))
    trajectory_rows = [
        [y, round(v3, 2), round(v5, 2), round(v10, 2), round(vspx, 2)]
        for y, v3, v5, v10, vspx in zip(years_30y, t3_traj, t5_traj, t10_traj, spx_traj)
    ]

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

    dd3 = _calc_dd(t3_traj)
    dd5 = _calc_dd(t5_traj)
    dd10 = _calc_dd(t10_traj)
    ddspx = _calc_dd(spx_traj)

    drawdown_rows = [
        [y, round(d3, 6), round(d5, 6), round(d10, 6), round(dspx, 6)]
        for y, d3, d5, d10, dspx in zip(years_30y, dd3, dd5, dd10, ddspx)
    ]

    annual_data["spx"] = spx_rows
    annual_data["era_data"] = era_rows
    annual_data["trajectory_data"] = trajectory_rows
    annual_data["drawdown_data"] = drawdown_rows
    scenario_data = {"scenario_rows": scenario_rows}

    return scenario_data, annual_data, trade_rows


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
    }
