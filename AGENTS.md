# Agent Guidelines: S&P 500 Top N Strategy

Quantitative backtesting engine and interactive Google Sheets dashboard for S&P 500 Top N ($N \in \{3, 5, 10\}$) strategies across 10y, 20y, and 30y horizons (1994–2024).

## Core Principles & Invariants
- **Zero External Dependencies**: Python 3 standard library only (`argparse`, `dataclasses`, `csv`, `json`, `math`, `unittest`). Do not introduce pandas, numpy, or third-party packages.
- **Unleveraged Cash Invariant**: `cash >= 0.0` at all times. Rebalancing must remain strictly self-financing without margin borrowing.
- **Tax Model**: FIFO lot depletion, cumulative capital loss carryforwards, default 30.0% rate (`0.30`).
- **Benchmark**: S&P 500 price return (`^GSPC`), cash dividends excluded for both.
- **Pricing**: All prices are split-adjusted to 2024-12-31.

## Architecture
- `engine/models.py`: Domain dataclasses (`ConstituentSnapshot`, `HoldingTarget`, `TaxLot`, `TradeOrder`, `AnnualLedgerEntry`, `StrategyResult`).
- `engine/tax_lots.py`: `FIFOTaxLotManager` (FIFO queues, lot splitting, tax settlement, loss carryforwards, unrealized gains).
- `engine/selector.py`: `BaseSelector`, `MarketCapSelector`, `PerformanceSelector`. Target weight formula: $w_i = W_i / \sum_{j=1}^N W_j$.
- `engine/data_loader.py` & `data/`: 31-year point-in-time constituent datasets and split-adjusted prices (1994–2024).
- `engine/backtest.py`: `PortfolioSimulator` implementing two-phase annual rebalancing:
  - Phase 1: Valuation, full exits, provisional trims.
  - Phase 2: Tax settlement, secondary trims down to net equity $V_{\text{net}} \times w_i$, cash-clamped buys.
- `engine/metrics.py`: Standard math functions (`calculate_cagr`, `calculate_cumulative_return`, `calculate_max_drawdown`, `calculate_turnover`, `calculate_tax_drag`, `calculate_alpha`, `calculate_terminal_metrics`).
- `engine/exporters.py`: CSV report writers and Google Apps Script (`scripts/google_apps_script.js`) generator.
- `run_backtest.py`: Primary CLI runner.

## Common Commands
- Run backtest (default): `python3 run_backtest.py`
- Run custom strategy: `python3 run_backtest.py --strategy performance --tax-rate 0.20 --initial-capital 50000`
- Run full test suite: `python3 -m unittest discover tests`
- Run specific test: `python3 -m unittest tests/test_rebalancing.py`
