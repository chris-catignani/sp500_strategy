"""Reporting and Exporters Suite for S&P 500 Top N Strategy.

Produces:
- summary_metrics.csv
- annual_breakdown.csv
- trade_log.csv
- scripts/google_apps_script.js (Interactive Google Apps Script dashboard)
"""

import csv
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from engine.models import StrategyResult, TradeOrder
from engine.metrics import calculate_cagr, calculate_alpha


def _ensure_dir_exists(filepath: str) -> None:
    """Create parent directories for filepath if they do not exist."""
    dirname = os.path.dirname(filepath)
    if dirname:
        os.makedirs(dirname, exist_ok=True)


def export_summary_metrics_csv(
    results: List[StrategyResult],
    filepath: str,
    spx_benchmarks: Optional[Dict[str, float]] = None,
) -> str:
    """Export summary metrics across multi-horizon strategy runs to a CSV file.

    Columns:
        strategy_name, n, horizon, start_year, end_year, is_after_tax, tax_rate,
        initial_capital, final_equity, cumulative_return, cagr, max_drawdown,
        total_taxes_paid, pre_liquidation_wealth, post_liquidation_wealth,
        post_liquidation_cagr, tax_drag, alpha_vs_spx

    Args:
        results: List of StrategyResult objects.
        filepath: Target CSV destination path.
        spx_benchmarks: Optional mapping of horizon (e.g. '10y', 10) to S&P 500 CAGR.

    Returns:
        The target filepath written to.
    """
    _ensure_dir_exists(filepath)

    fieldnames = [
        "strategy_name",
        "n",
        "horizon",
        "start_year",
        "end_year",
        "is_after_tax",
        "tax_rate",
        "initial_capital",
        "final_equity",
        "cumulative_return",
        "cagr",
        "max_drawdown",
        "total_taxes_paid",
        "total_dividends_received",
        "pre_liquidation_wealth",
        "post_liquidation_wealth",
        "post_liquidation_cagr",
        "tax_drag",
        "alpha_vs_spx",
    ]

    # Map pre-tax CAGRs for matching after-tax results: (strategy_name, n, start_year, end_year)
    pretax_cagr_map: Dict[Tuple[str, int, int, int], float] = {}
    for r in results:
        if not r.is_after_tax:
            key = (r.strategy_name, r.n, r.start_year, r.end_year)
            pretax_cagr_map[key] = r.cagr

    rows: List[Dict[str, Any]] = []
    for r in results:
        horizon_years = r.end_year - r.start_year
        horizon_str = f"{horizon_years}y"
        key = (r.strategy_name, r.n, r.start_year, r.end_year)

        # Tax drag
        if r.is_after_tax:
            if key in pretax_cagr_map:
                tax_drag = pretax_cagr_map[key] - r.post_liquidation_cagr
            else:
                tax_drag = r.cagr - r.post_liquidation_cagr
        else:
            tax_drag = 0.0

        # Alpha vs S&P 500 Benchmark
        if r.strategy_name == "S&P 500":
            alpha_vs_spx = 0.0
        else:
            spx_cagr: Optional[float] = None
            if spx_benchmarks is not None:
                candidates = []
                if r.is_after_tax:
                    candidates.extend([
                        (horizon_str, r.tax_rate),
                        (horizon_years, r.tax_rate),
                        (horizon_str, round(r.tax_rate, 4)),
                        (horizon_years, round(r.tax_rate, 4)),
                        (horizon_str, True),
                        (horizon_years, True),
                    ])
                else:
                    candidates.extend([
                        (horizon_str, 0.0),
                        (horizon_years, 0.0),
                        (horizon_str, False),
                        (horizon_years, False),
                    ])
                candidates.extend([
                    horizon_str,
                    horizon_years,
                    str(horizon_years),
                ])

                for cand in candidates:
                    if cand in spx_benchmarks:
                        val = spx_benchmarks[cand]
                        if isinstance(val, dict):
                            spx_cagr = val.get(
                                "post_liquidation_cagr" if r.is_after_tax else "cagr",
                                val.get("cagr"),
                            )
                        elif hasattr(val, "post_liquidation_cagr") and r.is_after_tax:
                            spx_cagr = val.post_liquidation_cagr
                        elif hasattr(val, "cagr"):
                            spx_cagr = val.cagr
                        elif isinstance(val, (int, float)):
                            spx_cagr = float(val)
                        if spx_cagr is not None:
                            break

            if spx_cagr is None and r.annual_history:
                cum_spx = 1.0
                for entry in r.annual_history:
                    cum_spx *= (1.0 + entry.spx_return)
                spx_cagr = calculate_cagr(1.0, cum_spx, horizon_years)

            if spx_cagr is None:
                spx_cagr = 0.0

            if r.is_after_tax:
                alpha_vs_spx = calculate_alpha(r.post_liquidation_cagr, spx_cagr)
            else:
                alpha_vs_spx = calculate_alpha(r.cagr, spx_cagr)

        rows.append(
            {
                "strategy_name": r.strategy_name,
                "n": r.n,
                "horizon": horizon_str,
                "start_year": r.start_year,
                "end_year": r.end_year,
                "is_after_tax": r.is_after_tax,
                "tax_rate": r.tax_rate,
                "initial_capital": r.initial_capital,
                "final_equity": r.final_equity,
                "cumulative_return": r.cumulative_return,
                "cagr": r.cagr,
                "max_drawdown": r.max_drawdown,
                "total_taxes_paid": r.total_taxes_paid,
                "total_dividends_received": getattr(r, "total_dividends_received", 0.0),
                "pre_liquidation_wealth": r.pre_liquidation_wealth,
                "post_liquidation_wealth": r.post_liquidation_wealth,
                "post_liquidation_cagr": r.post_liquidation_cagr,
                "tax_drag": tax_drag,
                "alpha_vs_spx": alpha_vs_spx,
            }
        )

    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return filepath


def export_annual_breakdown_csv(
    results: List[StrategyResult],
    filepath: str,
) -> str:
    """Export detailed year-by-year accounting ledger entries to a CSV file.

    Columns:
        strategy_name, n, is_after_tax, tax_rate, year, start_value, gross_return,
        dividend_income, ending_value_pretax, realized_capital_gain, net_taxable_gain,
        capital_gains_tax_paid, dividend_tax_paid, tax_paid, loss_carryforward,
        ending_value_aftertax, cash, spx_return, turnover

    Args:
        results: List of StrategyResult objects containing annual_history.
        filepath: Target CSV destination path.

    Returns:
        The target filepath written to.
    """
    _ensure_dir_exists(filepath)

    fieldnames = [
        "strategy_name",
        "n",
        "is_after_tax",
        "tax_rate",
        "year",
        "start_value",
        "gross_return",
        "dividend_income",
        "ending_value_pretax",
        "realized_capital_gain",
        "net_taxable_gain",
        "capital_gains_tax_paid",
        "dividend_tax_paid",
        "tax_paid",
        "loss_carryforward",
        "ending_value_aftertax",
        "cash",
        "spx_return",
        "turnover",
    ]

    rows: List[Dict[str, Any]] = []
    for r in results:
        for entry in r.annual_history:
            rows.append(
                {
                    "strategy_name": r.strategy_name,
                    "n": r.n,
                    "is_after_tax": r.is_after_tax,
                    "tax_rate": r.tax_rate,
                    "year": entry.year,
                    "start_value": entry.start_value,
                    "gross_return": entry.gross_return,
                    "dividend_income": getattr(entry, "dividend_income", 0.0),
                    "ending_value_pretax": entry.ending_value_pretax,
                    "realized_capital_gain": entry.realized_capital_gain,
                    "net_taxable_gain": entry.net_taxable_gain,
                    "capital_gains_tax_paid": getattr(entry, "capital_gains_tax_paid", 0.0),
                    "dividend_tax_paid": getattr(entry, "dividend_tax_paid", 0.0),
                    "tax_paid": entry.tax_paid,
                    "loss_carryforward": entry.loss_carryforward,
                    "ending_value_aftertax": entry.ending_value_aftertax,
                    "cash": entry.cash,
                    "spx_return": entry.spx_return,
                    "turnover": entry.turnover,
                }
            )

    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return filepath


def export_trade_log_csv(
    trade_records: List[Union[Dict[str, Any], Any]],
    filepath: str,
) -> str:
    """Export executed trade transactions and rebalancing audit trail to a CSV file.

    Columns:
        strategy_name, n, year, ticker, action, shares, price, realized_gain

    Args:
        trade_records: List of dictionaries or TradeOrder instances.
        filepath: Target CSV destination path.

    Returns:
        The target filepath written to.
    """
    _ensure_dir_exists(filepath)

    fieldnames = [
        "strategy_name",
        "n",
        "year",
        "ticker",
        "action",
        "shares",
        "price",
        "realized_gain",
    ]

    rows: List[Dict[str, Any]] = []
    for record in trade_records:
        if isinstance(record, dict):
            rows.append(
                {
                    "strategy_name": record.get("strategy_name", ""),
                    "n": record.get("n", ""),
                    "year": record.get("year", ""),
                    "ticker": record.get("ticker", ""),
                    "action": record.get("action", ""),
                    "shares": record.get("shares", 0.0),
                    "price": record.get("price", 0.0),
                    "realized_gain": record.get("realized_gain", 0.0),
                }
            )
        else:
            rows.append(
                {
                    "strategy_name": getattr(record, "strategy_name", ""),
                    "n": getattr(record, "n", ""),
                    "year": getattr(record, "year", ""),
                    "ticker": getattr(record, "ticker", ""),
                    "action": getattr(record, "action", ""),
                    "shares": getattr(record, "shares", 0.0),
                    "price": getattr(record, "price", 0.0),
                    "realized_gain": getattr(record, "realized_gain", 0.0),
                }
            )

    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return filepath


def build_default_scenario_data() -> Dict[str, Any]:
    """Execute standard backtest simulations to generate data for Google Apps Script.

    Returns:
        Dictionary containing:
        - scenario_rows: 2D table for 'Scenario Data' tab
        - top3_annual: 2D table for 'Top 3 Strategy' tab
        - top5_annual: 2D table for 'Top 5 Strategy' tab
        - top10_annual: 2D table for 'Top 10 Strategy' tab
        - spx_data: 2D table for 'S&P 500 Benchmark' tab
        - trades_data: 2D table for 'Historical Holdings & Trades' tab
    """
    from engine.data_loader import DataLoader
    from engine.backtest import PortfolioSimulator
    from engine.metrics import (
        calculate_benchmark_annual_series,
        calculate_cumulative_return,
        calculate_max_drawdown,
    )

    dl = DataLoader()
    sim = PortfolioSimulator(dl)

    horizons = [("10y", 2014, 2024), ("20y", 2004, 2024), ("30y", 1994, 2024)]
    tax_rates = [(0.0, "0.0%"), (0.15, "15.0%"), (0.20, "20.0%"), (0.30, "30.0%"), (0.37, "37.0%")]

    # Cache pre-tax simulations
    pretax_results: Dict[Tuple[int, int, int], StrategyResult] = {}
    for n in [3, 5, 10]:
        for h_label, s_yr, e_yr in horizons:
            pretax_results[(n, s_yr, e_yr)] = sim.run_simulation(s_yr, e_yr, n=n, is_after_tax=False)

    scenario_rows: List[List[Any]] = []
    for rate, rate_str in tax_rates:
        for h_label, s_yr, e_yr in horizons:
            pr_levels = [dl.get_spx_level(y) for y in range(s_yr, e_yr + 1)]
            tr_levels = [dl.get_spx_tr_level(y) for y in range(s_yr, e_yr + 1)]
            horizon_years = e_yr - s_yr
            spx_tr_cagr = calculate_cagr(tr_levels[0], tr_levels[-1], horizon_years)

            if rate == 0.0:
                bench = calculate_benchmark_annual_series(
                    pr_levels=pr_levels,
                    tr_levels=tr_levels,
                    tax_rate=0.0,
                    initial_capital=10000.0,
                    is_after_tax=False,
                )
                spx_after_cagr = spx_tr_cagr
                spx_post_liq_cagr = spx_tr_cagr
                spx_cum = calculate_cumulative_return(10000.0, bench["post_liquidation_wealth"])
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
                    initial_capital=10000.0,
                    is_after_tax=True,
                )
                val_series = [10000.0]
                curr_v = 10000.0
                for r_ann in bench["annual_returns"]:
                    curr_v *= (1.0 + r_ann)
                    val_series.append(curr_v)
                spx_max_dd = calculate_max_drawdown(val_series)
                spx_after_cagr = calculate_cagr(10000.0, bench["pre_liquidation_wealth"], horizon_years)
                spx_post_liq_cagr = calculate_cagr(10000.0, bench["post_liquidation_wealth"], horizon_years)
                spx_cum = calculate_cumulative_return(10000.0, bench["post_liquidation_wealth"])
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

            # Top N strategies (14 columns)
            for n in [3, 5, 10]:
                pre_res = pretax_results[(n, s_yr, e_yr)]
                if rate == 0.0:
                    post_res = pre_res
                    tax_drag = 0.0
                    alpha = post_res.cagr - spx_tr_cagr
                else:
                    post_res = sim.run_simulation(s_yr, e_yr, n=n, is_after_tax=True, tax_rate=rate)
                    tax_drag = pre_res.cagr - post_res.post_liquidation_cagr
                    alpha = post_res.post_liquidation_cagr - spx_post_liq_cagr

                key = f"{h_label}_Top {n}_{rate_str}"
                scenario_rows.append([
                    key,
                    h_label,
                    f"Top {n}",
                    rate,
                    round(pre_res.cagr, 6),
                    round(post_res.cagr, 6),
                    round(post_res.post_liquidation_cagr, 6),
                    round(post_res.cumulative_return, 6),
                    round(post_res.final_equity, 2),
                    round(post_res.total_dividends_received, 2),
                    round(post_res.max_drawdown, 6),
                    round(post_res.total_taxes_paid, 2),
                    round(tax_drag, 6),
                    round(alpha, 6),
                ])

    # 30-Year Annual histories & trades at 30% baseline tax rate
    annual_data: Dict[str, List[List[Any]]] = {}
    trade_rows: List[List[Any]] = []

    for n in [3, 5, 10]:
        res_30y = sim.run_simulation(1994, 2024, n=n, is_after_tax=True, tax_rate=0.30)
        trades_30y = sim.get_trades()

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
            trade_rows.append([
                t.year,
                f"Top {n}",
                t.ticker,
                t.action,
                round(t.shares, 4),
                round(t.price, 2),
                round(t.realized_gain, 2),
            ])

    # S&P 500 30-Year Benchmark Series
    spx_rows: List[List[Any]] = []
    base_level = dl.get_spx_level(1994)
    for y in range(1994, 2025):
        lvl = dl.get_spx_level(y)
        if y == 1994:
            spx_rows.append([1994, round(lvl, 2), 0.0, 10000.0])
        else:
            lvl_prev = dl.get_spx_level(y - 1)
            ann_ret = (lvl - lvl_prev) / lvl_prev
            comp_growth = 10000.0 * (lvl / base_level)
            spx_rows.append([y, round(lvl, 2), round(ann_ret, 6), round(comp_growth, 2)])

    return {
        "scenario_rows": scenario_rows,
        "top3_annual": annual_data["top_3"],
        "top5_annual": annual_data["top_5"],
        "top10_annual": annual_data["top_10"],
        "spx_data": spx_rows,
        "trades_data": trade_rows,
    }


def generate_google_apps_script(
    scenario_data: Optional[Dict[str, Any]] = None,
    annual_data: Optional[Dict[str, Any]] = None,
    trades_data: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Generate a complete, self-contained Google Apps Script (.js).

    The script creates and formats:
    - Executive Summary (Interactive Dashboard with tax rate selector in B2)
    - Top 3 Strategy (30-year annual breakdown)
    - Top 5 Strategy (30-year annual breakdown)
    - Top 10 Strategy (30-year annual breakdown)
    - S&P 500 Benchmark (Annual levels & compounded growth)
    - Historical Holdings & Trades (Detailed transaction logs)
    - Scenario Data (Pre-calculated lookup matrix across tax tiers: 0%, 15%, 20%, 30%, 37%)

    Args:
        scenario_data: Optional custom scenario dataset.
        annual_data: Optional custom annual ledger dataset.
        trades_data: Optional custom trades dataset.

    Returns:
        A JavaScript string ready to be installed in Google Sheets Script Editor.
    """
    if scenario_data is None or annual_data is None or trades_data is None:
        defaults = build_default_scenario_data()
        if scenario_data is None:
            scenario_rows = defaults["scenario_rows"]
        else:
            scenario_rows = scenario_data.get("scenario_rows", defaults["scenario_rows"])

        if annual_data is None:
            top3_annual = defaults["top3_annual"]
            top5_annual = defaults["top5_annual"]
            top10_annual = defaults["top10_annual"]
            spx_data = defaults["spx_data"]
        else:
            top3_annual = annual_data.get("top_3", defaults["top3_annual"])
            top5_annual = annual_data.get("top_5", defaults["top5_annual"])
            top10_annual = annual_data.get("top_10", defaults["top10_annual"])
            spx_data = annual_data.get("spx", defaults["spx_data"])

        if trades_data is None:
            final_trade_rows = defaults["trades_data"]
        else:
            final_trade_rows = []
            for t in trades_data:
                if isinstance(t, dict):
                    final_trade_rows.append([
                        t.get("year", 0),
                        t.get("strategy_name", ""),
                        t.get("ticker", ""),
                        t.get("action", ""),
                        round(float(t.get("shares", 0.0)), 4),
                        round(float(t.get("price", 0.0)), 2),
                        round(float(t.get("realized_gain", 0.0)), 2),
                    ])
                else:
                    final_trade_rows.append([
                        getattr(t, "year", 0),
                        getattr(t, "strategy_name", ""),
                        getattr(t, "ticker", ""),
                        getattr(t, "action", ""),
                        round(float(getattr(t, "shares", 0.0)), 4),
                        round(float(getattr(t, "price", 0.0)), 2),
                        round(float(getattr(t, "realized_gain", 0.0)), 2),
                    ])
    else:
        scenario_rows = scenario_data.get("scenario_rows", [])
        top3_annual = annual_data.get("top_3", [])
        top5_annual = annual_data.get("top_5", [])
        top10_annual = annual_data.get("top_10", [])
        spx_data = annual_data.get("spx", [])
        final_trade_rows = []
        for t in trades_data:
            if isinstance(t, dict):
                final_trade_rows.append([
                    t.get("year", 0),
                    t.get("strategy_name", ""),
                    t.get("ticker", ""),
                    t.get("action", ""),
                    round(float(t.get("shares", 0.0)), 4),
                    round(float(t.get("price", 0.0)), 2),
                    round(float(t.get("realized_gain", 0.0)), 2),
                ])
            else:
                final_trade_rows.append([
                    getattr(t, "year", 0),
                    getattr(t, "strategy_name", ""),
                    getattr(t, "ticker", ""),
                    getattr(t, "action", ""),
                    round(float(getattr(t, "shares", 0.0)), 4),
                    round(float(getattr(t, "price", 0.0)), 2),
                    round(float(getattr(t, "realized_gain", 0.0)), 2),
                ])

    scenario_json = json.dumps(scenario_rows)
    top3_json = json.dumps(top3_annual)
    top5_json = json.dumps(top5_annual)
    top10_json = json.dumps(top10_annual)
    spx_json = json.dumps(spx_data)
    trades_json = json.dumps(final_trade_rows)

    js_template = f"""/**
 * Google Apps Script for S&P 500 Top N Strategy Interactive Dashboard
 * Generated automatically by engine/exporters.py
 *
 * Instructions:
 * 1. Open your Google Sheet.
 * 2. Go to Extensions > Apps Script.
 * 3. Replace all text in Code.gs with this script.
 * 4. Save and return to Google Sheets.
 * 5. Refresh the sheet, then click the new menu: "S&P 500 Strategy" > "Build All Sheets".
 */

// ==========================================
// Embedded Simulation Data
// ==========================================
var SCENARIO_HEADERS = [
  "LookupKey", "Horizon", "Strategy", "TaxRate", "PreTaxCAGR",
  "AfterTaxCAGR", "PostLiqCAGR", "CumReturn", "FinalEquity",
  "TotalDividends", "MaxDD", "TotalTaxes", "TaxDrag", "Alpha"
];
var SCENARIO_DATA = {scenario_json};

var ANNUAL_HEADERS = [
  "Year", "Start Value", "Gross Return", "Dividends Received ($)", "Ending Value (Pre-Tax)",
  "Realized Capital Gain", "Net Taxable Gain", "Capital Gains Tax ($)", "Dividend Tax ($)",
  "Total Tax Paid ($)", "Loss Carryforward", "Ending Value (After-Tax)", "Cash Reserve",
  "S&P 500 Return", "Annual Turnover"
];
var TOP3_ANNUAL_DATA = {top3_json};
var TOP5_ANNUAL_DATA = {top5_json};
var TOP10_ANNUAL_DATA = {top10_json};

var SPX_HEADERS = ["Year", "S&P 500 Level", "Annual Return", "Compounded Growth ($10,000 Invested)"];
var SPX_DATA = {spx_json};

var TRADE_HEADERS = ["Year", "Strategy", "Ticker", "Action", "Shares", "Execution Price", "Realized Gain"];
var TRADE_DATA = {trades_json};

// ==========================================
// Google Sheets UI & Menu Triggers
// ==========================================
function onOpen() {{
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('S&P 500 Strategy')
    .addItem('Build All Sheets', 'buildAllSheets')
    .addItem('Recalculate Sheet', 'recalculateSheet')
    .addToUi();
}}

// ==========================================
// Primary Build Coordinator
// ==========================================
function buildAllSheets() {{
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  // 1. Scenario Data Tab
  buildScenarioDataSheet(ss);

  // 2. Executive Summary Dashboard Tab
  buildExecutiveSummarySheet(ss);

  // 3. Strategy Tabs
  buildAnnualSheet(ss, 'Top 3 Strategy', TOP3_ANNUAL_DATA);
  buildAnnualSheet(ss, 'Top 5 Strategy', TOP5_ANNUAL_DATA);
  buildAnnualSheet(ss, 'Top 10 Strategy', TOP10_ANNUAL_DATA);

  // 4. Benchmark Tab
  buildBenchmarkSheet(ss);

  // 5. Holdings & Trades Tab
  buildTradesSheet(ss);

  // Organize tab order: Executive Summary is always tab 1
  var tabOrder = [
    'Executive Summary',
    'Top 3 Strategy',
    'Top 5 Strategy',
    'Top 10 Strategy',
    'S&P 500 Benchmark',
    'Historical Holdings & Trades',
    'Scenario Data'
  ];
  for (var i = 0; i < tabOrder.length; i++) {{
    var sheet = ss.getSheetByName(tabOrder[i]);
    if (sheet) {{
      ss.setActiveSheet(sheet);
      ss.moveActiveSheet(i + 1);
    }}
  }}

  // Activate Executive Summary
  var execSheet = ss.getSheetByName('Executive Summary');
  if (execSheet) {{
    ss.setActiveSheet(execSheet);
  }}

  SpreadsheetApp.flush();
  ss.toast('All sheets successfully created and styled!', 'Build Complete', 4);
}}

// ==========================================
// Tab 1: Scenario Data (Lookup Engine)
// ==========================================
function buildScenarioDataSheet(ss) {{
  var sheet = getOrCreateSheet(ss, 'Scenario Data');
  sheet.setHiddenGridlines(false);

  var rows = [SCENARIO_HEADERS].concat(SCENARIO_DATA);
  sheet.getRange(1, 1, rows.length, SCENARIO_HEADERS.length).setValues(rows);

  // Header Styling
  var headerRange = sheet.getRange(1, 1, 1, SCENARIO_HEADERS.length);
  headerRange.setBackground('#1B365D')
             .setFontColor('#FFFFFF')
             .setFontWeight('bold')
             .setHorizontalAlignment('center');

  // Number Formatting
  if (SCENARIO_DATA.length > 0) {{
    sheet.getRange(2, 5, SCENARIO_DATA.length, 4).setNumberFormat('0.00%').setHorizontalAlignment('right');
    sheet.getRange(2, 9, SCENARIO_DATA.length, 2).setNumberFormat('$#,##0.00').setHorizontalAlignment('right');
    sheet.getRange(2, 11, SCENARIO_DATA.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right');
    sheet.getRange(2, 12, SCENARIO_DATA.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right');
    sheet.getRange(2, 13, SCENARIO_DATA.length, 2).setNumberFormat('0.00%').setHorizontalAlignment('right');
  }}

  sheet.autoResizeColumns(1, SCENARIO_HEADERS.length);
  sheet.setFrozenRows(1);
}}

// ==========================================
// Tab 2: Executive Summary Dashboard
// ==========================================
function buildExecutiveSummarySheet(ss) {{
  var sheet = getOrCreateSheet(ss, 'Executive Summary');
  sheet.setHiddenGridlines(false);

  // 1. Banner Header
  sheet.getRange('A1:L1').merge()
       .setValue('S&P 500 TOP N STRATEGY - EXECUTIVE DASHBOARD')
       .setBackground('#1B365D')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(14)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle')
       .setWrapStrategy(SpreadsheetApp.WrapStrategy.OVERFLOW);

  // 2. Interactive Tax Rate Parameter Control in B2
  sheet.getRange('A2').setValue('Tax Rate:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle')
       .setWrapStrategy(SpreadsheetApp.WrapStrategy.CLIP);

  var b2 = sheet.getRange('B2');
  b2.setValue(0.30)
    .setNumberFormat('0.0%')
    .setFontWeight('bold')
    .setFontSize(12)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['0.0%', '15.0%', '20.0%', '30.0%', '37.0%'], true)
    .setAllowInvalid(false)
    .build();
  b2.setDataValidation(rule);

  sheet.getRange('C2:L2').merge()
       .setValue('Select a tax rate in B2 to dynamically update after-tax returns, ending wealth, and tax drag across all horizons.')
       .setFontStyle('italic')
       .setFontColor('#4A5568')
       .setVerticalAlignment('middle')
       .setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);

  // 3. KPI Summary Scorecards (Rows 4-6)
  // 5 cards balanced seamlessly across columns A through L:
  // Card 1: Top 5 (30y) Final Wealth (Cols A-B)
  sheet.getRange('A4:B4').merge().setValue('Top 5 Final Wealth (30y)').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A5:B5').merge().setFormula('=G19').setFontWeight('bold').setFontSize(14).setFontColor('#22543D').setNumberFormat('$#,##0.00').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A6:B6').merge().setValue('After all taxes ($10k start)').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A4:B6').setBackground('#E6FFFA').setBorder(true, true, true, true, false, false, '#B2F5EA', SpreadsheetApp.BorderStyle.SOLID);

  // Card 2: S&P 500 (30y) Wealth (Cols C-D)
  sheet.getRange('C4:D4').merge().setValue('S&P 500 Wealth (30y)').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('C5:D5').merge().setFormula('=G21').setFontWeight('bold').setFontSize(14).setFontColor('#4A5568').setNumberFormat('$#,##0.00').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('C6:D6').merge().setValue('Passive buy & hold').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('C4:D6').setBackground('#EDF2F7').setBorder(true, true, true, true, false, false, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);

  // Card 3: Top 5 (30y) Annual Return (Cols E-F)
  sheet.getRange('E4:F4').merge().setValue('Top 5 Annual Return (30y)').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('E5:F5').merge().setFormula('=E19').setFontWeight('bold').setFontSize(14).setFontColor('#1B365D').setNumberFormat('0.00%').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('E6:F6').merge().setValue('Net post-liquidation CAGR').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('E4:F6').setBackground('#EBF8FF').setBorder(true, true, true, true, false, false, '#BEE3F8', SpreadsheetApp.BorderStyle.SOLID);

  // Card 4: 30-Year Excess Return (Cols G-I)
  sheet.getRange('G4:I4').merge().setValue('30-Year Excess Return').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('G5:I5').merge().setFormula('=L19').setFontWeight('bold').setFontSize(14).setFontColor('#22543D').setNumberFormat('+0.00%;-0.00%;0.00%').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('G6:I6').merge().setValue('Annual Alpha vs S&P 500').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('G4:I6').setBackground('#F0FFF4').setBorder(true, true, true, true, false, false, '#C6F6D5', SpreadsheetApp.BorderStyle.SOLID);

  // Card 5: 30-Year Tax Drag (Cols J-L)
  sheet.getRange('J4:L4').merge().setValue('30-Year Tax Drag').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('J5:L5').merge().setFormula('=K19').setFontWeight('bold').setFontSize(14).setFontColor('#9B2C2C').setNumberFormat('0.00%').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('J6:L6').merge().setValue('Annual return lost to taxes').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('J4:L6').setBackground('#FFF5F5').setBorder(true, true, true, true, false, false, '#FED7D7', SpreadsheetApp.BorderStyle.SOLID);

  // 4. Multi-Horizon Strategy Comparison Table
  // Row 8: Title
  sheet.getRange('A8:L8').merge()
       .setValue('MULTI-HORIZON PERFORMANCE & TAX COMPARISON (10Y, 20Y, 30Y)')
       .setBackground('#1B365D')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(11)
       .setHorizontalAlignment('left')
       .setVerticalAlignment('middle')
       .setWrapStrategy(SpreadsheetApp.WrapStrategy.OVERFLOW);

  // Row 9: Table Header
  var tableHeaders = [
    'Horizon', 'Strategy', 'Annual Return (Pre-Tax)', 'Annual Return (After-Tax)', 'Annual Return (Post-Liq)',
    'Total Return (Cumulative)', 'Ending Wealth ($10k Start)', 'Total Dividends Received',
    'Max Drawdown (Worst Drop)', 'Total Taxes Paid', 'Annual Tax Drag', 'Excess vs S&P 500 (Alpha)'
  ];
  sheet.getRange(9, 1, 1, tableHeaders.length).setValues([tableHeaders])
       .setBackground('#2C5282')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle')
       .setWrap(true);

  // Rows 10 to 21 (Dynamic lookup formulas pointing to Scenario Data tab)
  var horizons = ['10y', '20y', '30y'];
  var strategies = ['Top 3', 'Top 5', 'Top 10', 'S&P 500'];
  var tableRows = [];
  var rowIdx = 10;
  for (var h = 0; h < horizons.length; h++) {{
    for (var s = 0; s < strategies.length; s++) {{
      var horiz = horizons[h];
      var strat = strategies[s];
      tableRows.push([
        horiz,
        strat,
        makeLookupFormula(rowIdx, 5),
        makeLookupFormula(rowIdx, 6),
        makeLookupFormula(rowIdx, 7),
        makeLookupFormula(rowIdx, 8),
        makeLookupFormula(rowIdx, 9),
        makeLookupFormula(rowIdx, 10),
        makeLookupFormula(rowIdx, 11),
        makeLookupFormula(rowIdx, 12),
        makeLookupFormula(rowIdx, 13),
        makeLookupFormula(rowIdx, 14)
      ]);
      rowIdx++;
    }}
  }}

  sheet.getRange(10, 1, tableRows.length, tableHeaders.length).setValues(tableRows);

  // Formatting comparison table
  sheet.getRange(10, 1, tableRows.length, 1).setHorizontalAlignment('center').setFontWeight('bold').setVerticalAlignment('middle');
  sheet.getRange(10, 2, tableRows.length, 1).setFontWeight('bold').setVerticalAlignment('middle');
  sheet.getRange(10, 3, tableRows.length, 3).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(10, 6, tableRows.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(10, 7, tableRows.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(10, 8, tableRows.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(10, 9, tableRows.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(10, 10, tableRows.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(10, 11, tableRows.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(10, 12, tableRows.length, 1).setNumberFormat('+0.00%;-0.00%;0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');

  // Alternating background colors
  for (var r = 0; r < tableRows.length; r++) {{
    var bg = (Math.floor(r / 4) % 2 === 0) ? '#FFFFFF' : '#F7FAFC';
    sheet.getRange(10 + r, 1, 1, tableHeaders.length).setBackground(bg);
  }}

  // Borders
  sheet.getRange(9, 1, tableRows.length + 1, tableHeaders.length).setBorder(true, true, true, true, true, true, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);

  // Explicit, proportional column widths (avoids autoResize stretching from merged headers/banners)
  var colWidths = [80, 95, 105, 105, 105, 105, 110, 110, 100, 100, 95, 95];
  for (var c = 0; c < colWidths.length; c++) {{
    sheet.setColumnWidth(c + 1, colWidths[c]);
  }}

  // Explicit row heights for polished vertical rhythm
  sheet.setRowHeight(1, 40);
  sheet.setRowHeight(2, 32);
  sheet.setRowHeight(3, 10);
  sheet.setRowHeight(4, 22);
  sheet.setRowHeight(5, 32);
  sheet.setRowHeight(6, 20);
  sheet.setRowHeight(7, 14);
  sheet.setRowHeight(8, 30);
  sheet.setRowHeight(9, 36);
  for (var dr = 10; dr <= 21; dr++) {{
    sheet.setRowHeight(dr, 24);
  }}

  // 5. Key Metrics Glossary & Explanations (Rows 23-29)
  sheet.getRange('A23:L23').merge()
       .setValue('KEY METRIC DEFINITIONS & GLOSSARY')
       .setBackground('#EDF2F7')
       .setFontColor('#2D3748')
       .setFontWeight('bold')
       .setFontSize(10)
       .setHorizontalAlignment('left')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(23, 24);

  var explanations = [
    ['Annual Return (CAGR):', 'Compound Annual Growth Rate — the smoothed annual percentage your money grew every year compounded steadily.'],
    ['Total Return (Cumulative):', 'The total unannualized percentage gain over the entire period (e.g. +795.6% means $10k turned into $89.5k).'],
    ['Post-Liquidation Return:', 'True net annual return assuming all remaining stock holdings are sold at the end and all final taxes paid.'],
    ['Annual Tax Drag:', 'Annual percentage of return lost to taxes. Calculated as Pre-Tax Annual Return minus Post-Liquidation Annual Return.'],
    ['Excess vs S&P 500 (Alpha):', 'Additional annual return earned above the S&P 500 benchmark (+5.81% means beating the market by 5.81%/yr).'],
    ['Max Drawdown:', 'Worst percentage drop from peak to trough during market downturns before a new high was reached.']
  ];

  for (var e = 0; e < explanations.length; e++) {{
    var r = 24 + e;
    sheet.getRange('A' + r + ':B' + r).merge()
         .setValue(explanations[e][0])
         .setFontWeight('bold')
         .setFontSize(9)
         .setFontColor('#4A5568')
         .setHorizontalAlignment('right')
         .setVerticalAlignment('middle');
    sheet.getRange('C' + r + ':L' + r).merge()
         .setValue(explanations[e][1])
         .setFontSize(9)
         .setFontColor('#718096')
         .setHorizontalAlignment('left')
         .setVerticalAlignment('middle');
    sheet.setRowHeight(r, 20);
  }}

  // 6. Methodology Note Callout Card (Rows 31-36)
  sheet.setRowHeight(30, 14);
  sheet.getRange('A31:L31').merge()
       .setValue('METHODOLOGY NOTE — DIVIDEND TIMING')
       .setBackground('#2D3748')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(10)
       .setHorizontalAlignment('left')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(31, 24);

  var methodNote = '• Annual Discrete Dividends: Historical dividends are credited once annually at the rebalance date based on prior-year holdings and dividend distribution rates.\\n' +
                   '• Tax Settlement: Dividend and realized capital gains taxes are settled annually at the selected marginal tax rate, with capital loss carryforwards applied.\\n' +
                   '• Self-Financing Rebalancing: Net dividend income is reinvested into target holdings alongside rebalancing trade proceeds without margin borrowing (cash >= 0).\\n' +
                   '• Post-Liquidation Terminal Wealth: Terminal equity reflects a full simulated liquidation of all portfolio holdings with final capital gains taxes paid.\\n' +
                   '• Benchmark Alignment: S&P 500 total return benchmark reflects split- and dividend-adjusted performance over identical holding periods.';

  sheet.getRange('A32:L36').merge()
       .setValue(methodNote)
       .setFontSize(9)
       .setFontColor('#4A5568')
       .setHorizontalAlignment('left')
       .setVerticalAlignment('middle')
       .setWrap(true);

  sheet.getRange('A31:L36').setBorder(true, true, true, true, false, false, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);
  sheet.getRange('A32:L36').setBackground('#F7FAFC');
  for (var mr = 32; mr <= 36; mr++) {{
    sheet.setRowHeight(mr, 18);
  }}

  sheet.setFrozenRows(9);
}}

// ==========================================
// Strategy Tabs (Top 3, Top 5, Top 10)
// ==========================================
function buildAnnualSheet(ss, sheetName, annualData) {{
  var sheet = getOrCreateSheet(ss, sheetName);
  sheet.setHiddenGridlines(false);

  var rows = [ANNUAL_HEADERS].concat(annualData);
  sheet.getRange(1, 1, rows.length, ANNUAL_HEADERS.length).setValues(rows);

  // Header Styling
  var headerRange = sheet.getRange(1, 1, 1, ANNUAL_HEADERS.length);
  headerRange.setBackground('#1B365D')
             .setFontColor('#FFFFFF')
             .setFontWeight('bold')
             .setHorizontalAlignment('center')
             .setVerticalAlignment('middle')
             .setWrap(true);

  sheet.setRowHeight(1, 36);

  if (annualData.length > 0) {{
    // Col 1: Year
    sheet.getRange(2, 1, annualData.length, 1).setNumberFormat('#,##0').setHorizontalAlignment('center').setVerticalAlignment('middle');
    // Col 2: Start Value
    sheet.getRange(2, 2, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 3: Gross Return
    sheet.getRange(2, 3, annualData.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 4: Dividends Received ($)
    sheet.getRange(2, 4, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 5: Pre-Tax Ending Value
    sheet.getRange(2, 5, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 6: Realized Capital Gain
    sheet.getRange(2, 6, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 7: Net Taxable Gain
    sheet.getRange(2, 7, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 8: Capital Gains Tax ($)
    sheet.getRange(2, 8, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 9: Dividend Tax ($)
    sheet.getRange(2, 9, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 10: Total Tax Paid ($)
    sheet.getRange(2, 10, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 11: Loss Carryforward
    sheet.getRange(2, 11, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 12: Ending Value (After-Tax)
    sheet.getRange(2, 12, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 13: Cash Reserve
    sheet.getRange(2, 13, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 14: SPX Return
    sheet.getRange(2, 14, annualData.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 15: Turnover
    sheet.getRange(2, 15, annualData.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');

    // Alternating rows
    for (var r = 0; r < annualData.length; r++) {{
      var bg = (r % 2 === 0) ? '#FFFFFF' : '#F7FAFC';
      sheet.getRange(2 + r, 1, 1, ANNUAL_HEADERS.length).setBackground(bg);
      sheet.setRowHeight(2 + r, 22);
    }}
    sheet.getRange(1, 1, annualData.length + 1, ANNUAL_HEADERS.length).setBorder(true, true, true, true, true, true, '#E2E8F0', SpreadsheetApp.BorderStyle.SOLID);
  }}

  var annualColWidths = [70, 110, 95, 115, 115, 115, 110, 110, 105, 105, 110, 120, 100, 95, 90];
  for (var ac = 0; ac < annualColWidths.length; ac++) {{
    sheet.setColumnWidth(ac + 1, annualColWidths[ac]);
  }}
  sheet.setFrozenRows(1);
}}

// ==========================================
// Benchmark Tab: S&P 500 Benchmark
// ==========================================
function buildBenchmarkSheet(ss) {{
  var sheet = getOrCreateSheet(ss, 'S&P 500 Benchmark');
  sheet.setHiddenGridlines(false);

  var rows = [SPX_HEADERS].concat(SPX_DATA);
  sheet.getRange(1, 1, rows.length, SPX_HEADERS.length).setValues(rows);

  // Header Styling
  var headerRange = sheet.getRange(1, 1, 1, SPX_HEADERS.length);
  headerRange.setBackground('#1B365D')
             .setFontColor('#FFFFFF')
             .setFontWeight('bold')
             .setHorizontalAlignment('center')
             .setVerticalAlignment('middle')
             .setWrap(true);

  sheet.setRowHeight(1, 36);

  if (SPX_DATA.length > 0) {{
    sheet.getRange(2, 1, SPX_DATA.length, 1).setNumberFormat('#,##0').setHorizontalAlignment('center').setVerticalAlignment('middle');
    sheet.getRange(2, 2, SPX_DATA.length, 1).setNumberFormat('#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    sheet.getRange(2, 3, SPX_DATA.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
    sheet.getRange(2, 4, SPX_DATA.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');

    for (var r = 0; r < SPX_DATA.length; r++) {{
      var bg = (r % 2 === 0) ? '#FFFFFF' : '#F7FAFC';
      sheet.getRange(2 + r, 1, 1, SPX_HEADERS.length).setBackground(bg);
      sheet.setRowHeight(2 + r, 22);
    }}
    sheet.getRange(1, 1, SPX_DATA.length + 1, SPX_HEADERS.length).setBorder(true, true, true, true, true, true, '#E2E8F0', SpreadsheetApp.BorderStyle.SOLID);
  }}

  var spxColWidths = [80, 115, 140, 175];
  for (var sc = 0; sc < spxColWidths.length; sc++) {{
    sheet.setColumnWidth(sc + 1, spxColWidths[sc]);
  }}
  sheet.setFrozenRows(1);
}}

// ==========================================
// Tab 6: Historical Holdings & Trades
// ==========================================
function buildTradesSheet(ss) {{
  var sheet = getOrCreateSheet(ss, 'Historical Holdings & Trades');
  sheet.setHiddenGridlines(false);

  var rows = [TRADE_HEADERS].concat(TRADE_DATA);
  sheet.getRange(1, 1, rows.length, TRADE_HEADERS.length).setValues(rows);

  // Header Styling
  var headerRange = sheet.getRange(1, 1, 1, TRADE_HEADERS.length);
  headerRange.setBackground('#1B365D')
             .setFontColor('#FFFFFF')
             .setFontWeight('bold')
             .setHorizontalAlignment('center')
             .setVerticalAlignment('middle')
             .setWrap(true);

  sheet.setRowHeight(1, 36);

  if (TRADE_DATA.length > 0) {{
    sheet.getRange(2, 1, TRADE_DATA.length, 1).setNumberFormat('#,##0').setHorizontalAlignment('center').setVerticalAlignment('middle');
    sheet.getRange(2, 2, TRADE_DATA.length, 1).setHorizontalAlignment('center').setVerticalAlignment('middle');
    sheet.getRange(2, 3, TRADE_DATA.length, 1).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
    sheet.getRange(2, 4, TRADE_DATA.length, 1).setHorizontalAlignment('center').setVerticalAlignment('middle');
    sheet.getRange(2, 5, TRADE_DATA.length, 1).setNumberFormat('#,##0.0000').setHorizontalAlignment('right').setVerticalAlignment('middle');
    sheet.getRange(2, 6, TRADE_DATA.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    sheet.getRange(2, 7, TRADE_DATA.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');

    for (var r = 0; r < TRADE_DATA.length; r++) {{
      var bg = (r % 2 === 0) ? '#FFFFFF' : '#F7FAFC';
      sheet.getRange(2 + r, 1, 1, TRADE_HEADERS.length).setBackground(bg);
      sheet.setRowHeight(2 + r, 20);
    }}
    sheet.getRange(1, 1, TRADE_DATA.length + 1, TRADE_HEADERS.length).setBorder(true, true, true, true, true, true, '#E2E8F0', SpreadsheetApp.BorderStyle.SOLID);
  }}

  var tradeColWidths = [75, 140, 85, 80, 110, 125, 125];
  for (var tc = 0; tc < tradeColWidths.length; tc++) {{
    sheet.setColumnWidth(tc + 1, tradeColWidths[tc]);
  }}
  sheet.setFrozenRows(1);
}}


// ==========================================
// Utility & Custom Spreadsheet Functions
// ==========================================
function recalculateSheet() {{
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('Executive Summary');
  if (!sheet) {{
    SpreadsheetApp.getUi().alert('Executive Summary sheet not found.');
    return;
  }}
  var taxRateVal = sheet.getRange('B2').getValue();
  var taxRateStr = (typeof taxRateVal === 'number') ? (taxRateVal * 100).toFixed(1) + '%' : String(taxRateVal);
  SpreadsheetApp.flush();
  ss.toast('Executive Summary updated for tax rate: ' + taxRateStr, 'Recalculation Complete', 3);
}}

/**
 * Custom formula to calculate estimated 30-year after-tax CAGR for an arbitrary tax rate.
 * @param {{number|string}} taxRate Tax rate as decimal (e.g. 0.30) or percentage ("30%").
 * @return {{number|string}} Estimated post-liquidation CAGR.
 * @customfunction
 */
function RECALCULATE_STRATEGY(taxRate) {{
  var rate = (typeof taxRate === 'string') ? parseFloat(taxRate.replace('%', '')) / 100 : Number(taxRate);
  if (isNaN(rate) || rate < 0 || rate > 1) {{
    return 'Invalid tax rate';
  }}
  // Linear interpolation based on Top 5 30-year empirical results:
  // 0% -> 11.27%, 30% -> 9.21%
  var baseCagr = 0.1127;
  var drag = rate * 0.0687;
  return baseCagr - drag;
}}

function makeLookupFormula(rowIdx, col) {{
  var sheetRef = "'Scenario Data'!$A:$N";
  return '=VLOOKUP($A' + rowIdx + ' & "_" & $B' + rowIdx + ' & "_" & TEXT($B$2, "0.0%"), ' + sheetRef + ', ' + col + ', FALSE)';
}}

function getOrCreateSheet(ss, name) {{
  var sheet = ss.getSheetByName(name);
  if (sheet) {{
    sheet.clear();
  }} else {{
    sheet = ss.insertSheet(name);
  }}
  return sheet;
}}
"""
    return js_template


def export_google_apps_script(
    filepath: str,
    scenario_data: Optional[Dict[str, Any]] = None,
    annual_data: Optional[Dict[str, Any]] = None,
    trades_data: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Write the complete Google Apps Script file to disk.

    Args:
        filepath: Target filepath (e.g. 'scripts/google_apps_script.js').
        scenario_data: Optional custom scenario dataset.
        annual_data: Optional custom annual ledger dataset.
        trades_data: Optional custom trades dataset.

    Returns:
        The target filepath written to.
    """
    _ensure_dir_exists(filepath)
    js_code = generate_google_apps_script(
        scenario_data=scenario_data,
        annual_data=annual_data,
        trades_data=trades_data,
    )
    with open(filepath, mode="w", encoding="utf-8") as f:
        f.write(js_code)
    return filepath


class ReportExporter:
    """Coordinates reporting and file export pipelines for backtest results."""

    def __init__(self, output_dir: str = "outputs", scripts_dir: str = "scripts") -> None:
        """Initialize ReportExporter with target output directories.

        Args:
            output_dir: Directory for CSV outputs.
            scripts_dir: Directory for generated Google Apps Script file.
        """
        self.output_dir = output_dir
        self.scripts_dir = scripts_dir

    def export_summary(
        self,
        results: List[StrategyResult],
        spx_benchmarks: Optional[Dict[str, float]] = None,
        filename: str = "summary_metrics.csv",
    ) -> str:
        """Export summary metrics to CSV."""
        filepath = os.path.join(self.output_dir, filename)
        return export_summary_metrics_csv(results, filepath, spx_benchmarks=spx_benchmarks)

    def export_annual_breakdown(
        self,
        results: List[StrategyResult],
        filename: str = "annual_breakdown.csv",
    ) -> str:
        """Export annual ledger breakdowns to CSV."""
        filepath = os.path.join(self.output_dir, filename)
        return export_annual_breakdown_csv(results, filepath)

    def export_trade_log(
        self,
        trade_records: List[Union[Dict[str, Any], Any]],
        filename: str = "trade_log.csv",
    ) -> str:
        """Export trade transactions to CSV."""
        filepath = os.path.join(self.output_dir, filename)
        return export_trade_log_csv(trade_records, filepath)

    def export_apps_script(
        self,
        filename: str = "google_apps_script.js",
        scenario_data: Optional[Dict[str, Any]] = None,
        annual_data: Optional[Dict[str, Any]] = None,
        trades_data: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Export standalone Google Apps Script file."""
        filepath = os.path.join(self.scripts_dir, filename)
        return export_google_apps_script(
            filepath,
            scenario_data=scenario_data,
            annual_data=annual_data,
            trades_data=trades_data,
        )

    def export_all(
        self,
        results: List[StrategyResult],
        trade_records: Optional[List[Union[Dict[str, Any], Any]]] = None,
        spx_benchmarks: Optional[Dict[str, float]] = None,
        scenario_data: Optional[Dict[str, Any]] = None,
        annual_data: Optional[Dict[str, Any]] = None,
        trades_data: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, str]:
        """Export summary metrics, annual breakdown, trade log, and Apps Script.

        Args:
            results: List of StrategyResult objects.
            trade_records: Optional list of trade records.
            spx_benchmarks: Optional mapping of horizon to benchmark CAGR.
            scenario_data: Optional scenario dataset for Google Apps Script.
            annual_data: Optional annual dataset for Google Apps Script.
            trades_data: Optional trades dataset for Google Apps Script.

        Returns:
            Dictionary mapping artifact names to their created file paths.
        """
        files: Dict[str, str] = {}
        files["summary_metrics"] = self.export_summary(results, spx_benchmarks=spx_benchmarks)
        files["annual_breakdown"] = self.export_annual_breakdown(results)
        if trade_records is not None:
            files["trade_log"] = self.export_trade_log(trade_records)
        files["google_apps_script"] = self.export_apps_script(
            scenario_data=scenario_data,
            annual_data=annual_data,
            trades_data=trades_data,
        )
        return files


def export_all(
    results: List[StrategyResult],
    trade_records: Optional[List[Union[Dict[str, Any], Any]]] = None,
    output_dir: str = "outputs",
    scripts_dir: str = "scripts",
    spx_benchmarks: Optional[Dict[str, float]] = None,
    scenario_data: Optional[Dict[str, Any]] = None,
    annual_data: Optional[Dict[str, Any]] = None,
    trades_data: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, str]:
    """Convenience helper function to export all report artifacts into target directories.

    Args:
        results: List of StrategyResult objects.
        trade_records: Optional list of trade records.
        output_dir: Output directory for CSV files.
        scripts_dir: Output directory for script files.
        spx_benchmarks: Optional mapping of horizon to benchmark CAGR.
        scenario_data: Optional scenario dataset for Google Apps Script.
        annual_data: Optional annual dataset for Google Apps Script.
        trades_data: Optional trades dataset for Google Apps Script.

    Returns:
        Dictionary mapping artifact names to their created file paths.
    """
    exporter = ReportExporter(output_dir=output_dir, scripts_dir=scripts_dir)
    return exporter.export_all(
        results=results,
        trade_records=trade_records,
        spx_benchmarks=spx_benchmarks,
        scenario_data=scenario_data,
        annual_data=annual_data,
        trades_data=trades_data,
    )
