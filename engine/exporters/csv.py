"""CSV reporting and export utilities for strategy backtesting results.

Produces:
- summary_metrics.csv
- annual_breakdown.csv
- trade_log.csv
"""

import csv
import os
from typing import Any, Dict, List, Optional, Tuple, Union

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
    spx_benchmarks: Optional[Dict[Any, Any]] = None,
) -> str:
    """Export summary metrics across multi-horizon strategy runs to a CSV file.

    Columns:
        strategy_name, n, horizon, start_year, end_year, is_after_tax, tax_rate,
        initial_capital, final_equity, cumulative_return, cagr, max_drawdown,
        total_taxes_paid, total_dividends_received, pre_liquidation_wealth,
        post_liquidation_wealth, post_liquidation_cagr, tax_drag, alpha_vs_spx

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

        # Tax drag (Pre-tax CAGR minus After-tax CAGR)
        if r.is_after_tax:
            if key in pretax_cagr_map:
                tax_drag = pretax_cagr_map[key] - r.cagr
            else:
                tax_drag = 0.0
        else:
            tax_drag = 0.0

        # Alpha vs S&P 500 Benchmark
        if r.strategy_name == "S&P 500" or r.strategy_name.startswith("S&P 500 ("):
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
                                "after_cagr" if r.is_after_tax else "cagr",
                                val.get("cagr"),
                            )
                        elif hasattr(val, "after_cagr") and r.is_after_tax:
                            spx_cagr = val.after_cagr
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
