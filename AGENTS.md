# Agent Guidelines: S&P 500 Top N Strategy

Quantitative backtesting engine and interactive Google Sheets dashboard for S&P 500 Top N ($N \in \{3, 5, 10\}$) strategies across 10y, 20y, and 30y horizons (1994–2024).

## Core Principles & Invariants
- **Zero External Dependencies**: Python 3 standard library only (`argparse`, `dataclasses`, `csv`, `json`, `math`, `unittest`). Do not introduce pandas, numpy, or third-party packages.
- **Unleveraged Cash Invariant**: `cash >= 0.0` at all times. Rebalancing must remain strictly self-financing without margin borrowing. Buys are clamped to available cash proceeds.
- **Dividend Accounting & Cash Pooling**: Split-adjusted cash dividends from `data/sp500_dividends.json` (annual) or `data/sp500_quarterly_dividends.json` (quarterly) are credited prior to rebalancing and pooled into available cash. Exact corporate action dates and amounts are used (never divided by 4).
- **Tax Model**: Decoupled dual tax settlement (dividend income taxed separately at $\tau$; capital loss carryforwards offset only realized capital gains, never dividend income). FIFO lot depletion, cumulative capital loss carryforwards, default 30.0% rate (`0.30`).
- **Rebalancing Frequencies**: Supports both Annual and Quarterly rebalancing. Q1–Q3 dynamically drift constituent weights by price performance relative to the index; Q4 re-anchors to official year-end factsheet weights.
- **Benchmark**: S&P 500 Total Return (`^SP500TR`) for pre-tax comparisons, and dynamic after-tax total return modeling (`^GSPC` price return + `^SP500TR` synthetic dividend yield with dividend taxation and terminal liquidation tax) for after-tax comparisons.
- **Pricing & Dividends**: All prices (`data/sp500_prices.json`, `data/sp500_quarterly_prices.json`) and dividends per share (`data/sp500_dividends.json`, `data/sp500_quarterly_dividends.json`) are split-adjusted to 2024-12-31.

## Architecture
- `engine/models.py`: Domain dataclasses (`ConstituentSnapshot`, `HoldingTarget`, `TaxLot`, `TradeOrder`, `AnnualLedgerEntry` with `quarter` metadata and decoupled tax fields, `StrategyResult` with cumulative dividend metrics and `quarterly_history`).
- `engine/tax_lots.py`: `FIFOTaxLotManager` (FIFO queues, lot splitting, capital gains tax settlement, loss carryforwards, unrealized gains, quarter metadata).
- `engine/selector.py`: `BaseSelector`, `MarketCapSelector`, `PerformanceSelector`. Target weight formula: $w_i = W_i / \sum_{j=1}^N W_j$.
- `engine/data_loader.py` & `data/`: 31-year point-in-time constituent datasets, split-adjusted prices, and split-adjusted dividend history (1994–2024) for both annual and quarterly frequencies across S&P 500 and All World. Methods: `get_dividend`, `get_quarterly_dividend`, `get_quarterly_price`, `load_quarterly_universe`, `get_spx_tr_level`, `get_spx_dividend_yield`.
- `engine/backtest.py`: `PortfolioSimulator` implementing dividend cash pooling and two-phase annual/quarterly rebalancing:
  - Step 1: Pre-rebalance cash dividend collection & cash pooling (`self.cash += period_dividends`).
  - Step 2: Pre-tax portfolio valuation ($V_{\text{pretax}} = \text{holdings} + \text{cash}$).
  - Step 3-4 (Phase 1): Full exits and provisional trims of overweight positions.
  - Step 5 (Phase 2): Decoupled tax settlement (dividend tax + iterative capital gains tax with loss carryforward netting), secondary trims down to net equity $V_{\text{net}} \times w_i$, cash-clamped buys.
- `engine/metrics.py`: Standard math functions (`calculate_cagr`, `calculate_cumulative_return`, `calculate_max_drawdown`, `calculate_turnover`, `calculate_tax_drag`, `calculate_alpha`, `calculate_terminal_metrics`, `calculate_benchmark_annual_series`).
- `engine/scenarios.py`: Multi-tier scenario matrix builder (`build_scenario_and_apps_script_data`, `build_default_scenario_data`) across tax tiers, frequencies (Annual & Quarterly), and horizons.
- `engine/terminal_view.py`: Terminal presentation utilities (`format_terminal_table`) for ASCII comparison tables.
- `engine/templates/`: Standalone Google Apps Script dashboard template (`google_apps_script.template.js`) with 14-column layout, Control 6 frequency dropdown, and spill-safe row 80 glossary.
- `engine/exporters/`: Modular report writers:
  - `csv.py`: CSV report writers (19-column summary metrics, 19-column annual breakdown, 8-column trade log).
  - `apps_script.py`: Google Apps Script generator injecting simulation data into the external JS template.
  - `pipeline.py`: `ReportExporter` and `export_all` orchestrating exports.
- `run_backtest.py`: Primary CLI runner with multi-horizon simulation, frequency selection (`--frequency`, `--compare-frequencies`), and dynamic benchmark analysis.

## Common Commands
- Run backtest (default): `python3 run_backtest.py`
- Run quarterly backtest: `python3 run_backtest.py --frequency quarterly`
- Run side-by-side comparison: `python3 run_backtest.py --compare-frequencies`
- Run custom strategy: `python3 run_backtest.py --strategy performance --tax-rate 0.20 --initial-capital 50000`
- Run full test suite: `python3 -m unittest discover tests`
- Run quarterly test suite: `python3 -m unittest tests/test_quarterly.py`
