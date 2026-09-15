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
- **Risk & Drawdown Measurement**: Max Drawdown is measured across discrete periodic observation dates (annual year-end or quarterly quarter-end valuations), reflecting endpoint rebalance valuations rather than continuous daily extremes.
- **Token & Diff Efficiency**: Large exports (`outputs/*.csv`, `scripts/google_apps_script.js`) and raw archives (`data/raw/`) are marked `-diff` in `.gitattributes` and excluded in `.ignore`. Always run `python3 run_backtest.py --no-export` for testing. When reviewing diffs, use `git diff -- . ':!outputs/' ':!scripts/google_apps_script.js'`. To inspect intentional diffs on datasets, use `git diff --text data/`.

## Architecture
See `docs/ARCHITECTURE.md` for full component diagrams and schema details.
- `engine/models.py`: Domain dataclasses (`ConstituentSnapshot`, `HoldingTarget`, `TaxLot`, `TradeOrder`, `AnnualLedgerEntry`, `StrategyResult`).
- `engine/tax_lots.py`: `FIFOTaxLotManager` (FIFO queues, lot splitting, capital gains tax settlement, loss carryforwards, unrealized gains).
- `engine/selector.py`: `BaseSelector`, `MarketCapSelector`, `PerformanceSelector` ($w_i = W_i / \sum_{j=1}^N W_j$).
- `engine/data_loader.py`: Point-in-time constituent datasets, split-adjusted prices, and split-adjusted dividend history (1994–2024).
- `engine/backtest.py`: `PortfolioSimulator` implementing dividend cash pooling and two-phase rebalancing (pre-tax valuation, exits/trims, decoupled dual tax, secondary trims, cash-clamped buys).
- `engine/metrics.py`: Math functions (`calculate_cagr`, `calculate_cumulative_return`, `calculate_max_drawdown`, `calculate_turnover`, `calculate_tax_drag`, `calculate_alpha`, `calculate_terminal_metrics`, `calculate_benchmark_annual_series`).
- `engine/scenarios.py`: Multi-tier scenario matrix builder across tax tiers, frequencies, and horizons.
- `engine/terminal_view.py`: Terminal presentation utilities (`format_terminal_table`).
- `engine/templates/`: Modular Google Apps Script dashboard templates (`gas/00_` to `05_`).
- `engine/exporters/`: CSV report writers, Google Apps Script generator, and pipeline orchestrator.
- `run_backtest.py`: Primary CLI runner (`--frequency`, `--compare-frequencies`, `--no-export`, `--benchmark`).

## Common Commands
- Run backtest (fast, no file exports): `python3 run_backtest.py --no-export`
- Run backtest & regenerate full exports: `python3 run_backtest.py --compare-frequencies`
- Run quarterly backtest: `python3 run_backtest.py --frequency quarterly --no-export`
- Token-lean review diff: `git diff -- . ':!outputs/' ':!scripts/google_apps_script.js'`
- Run full test suite: `python3 -m unittest discover tests`
- Run quarterly test suite: `python3 -m unittest tests/test_quarterly.py`
