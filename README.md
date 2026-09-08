# S&P 500 Top N Investment Strategy & Tax-Aware Backtesting Engine

An institutional-grade, zero-dependency quantitative backtesting engine and reporting suite that models, simulates, and evaluates an active equity strategy against the S&P 500 price return benchmark (`^GSPC`) across 10-year (2014–2024), 20-year (2004–2024), and 30-year (1994–2024) investment horizons.

The engine features rigorous **two-phase annual rebalancing**, full **FIFO (First-In, First-Out) tax lot depletion**, **loss carryforward netting**, **terminal liquidation accounting**, and export pipelines for both audit CSVs and an interactive **Google Apps Script dashboard**.

---

## Table of Contents

- [Executive Summary & Strategy Logic](#executive-summary--strategy-logic)
- [Two-Phase Rebalancing & Tax Model](#two-phase-rebalancing--tax-model)
  - [1. Phase 1: Portfolio Valuation & Sell Execution](#1-phase-1-portfolio-valuation--sell-execution)
  - [2. Phase 2: FIFO Tax Settlement & Reinvestment](#2-phase-2-fifo-tax-settlement--reinvestment)
  - [3. Terminal Liquidation & Tax Drag](#3-terminal-liquidation--tax-drag)
- [Key Empirical Results (1994–2024)](#key-empirical-results-19942024)
- [Architecture & Directory Layout](#architecture--directory-layout)
- [Getting Started](#getting-started)
- [CLI Runner Usage](#cli-runner-usage)
  - [Basic Execution](#basic-execution)
  - [Custom Strategies & Parameters](#custom-strategies--parameters)
  - [All Available Flags](#all-available-flags)
- [Extensibility: Adding Custom Selectors](#extensibility-adding-custom-selectors)
- [Google Sheets Integration Guide](#google-sheets-integration-guide)
  - [Target Spreadsheet](#target-spreadsheet)
  - [Deployment Instructions](#deployment-instructions)
  - [Interactive Dashboard Controls](#interactive-dashboard-controls)
- [Running Unit Tests](#running-unit-tests)
- [License](#license)

---

## Executive Summary & Strategy Logic

Passive market-cap-weighted indices are dominated by their largest constituents due to the power-law distribution of mega-cap equities. This strategy evaluates whether actively concentrating capital into the top tier of S&P 500 winners outperforms holding the entire index:

1. **Constituent Selection**: At the close of trading on the final market day of year $t$, select the top $N$ stocks ($N \in \{3, 5, 10\}$) from the S&P 500 universe.
2. **Relative Market Cap Weighting**: Capital is allocated in proportion to each constituent's relative index market capitalization:
   $$w_i = \frac{W_i}{\sum_{j=1}^N W_j}$$
   where $W_i$ is the constituent's S&P 500 index weight.
3. **Holding Period**: Holdings are held undisturbed for exactly one full calendar year.
4. **Apples-to-Apples Comparison**: Returns are calculated on a pure price-return basis (split-adjusted, dividends excluded) against the official S&P 500 price return index (`^GSPC`).

---

## Two-Phase Rebalancing & Tax Model

Real-world rebalancing incurs capital gains taxes when winners are trimmed or exited. A naïve simulation encounters circular dependency: tax liabilities depend on sell proceeds, but target share quantities depend on net available capital. To solve this mathematically, the engine implements a **Two-Phase Rebalancing Protocol**:

### 1. Phase 1: Portfolio Valuation & Sell Execution
At year-end $t+1$:
1. Mark all existing positions to market: $V_{\text{total}, t+1} = \sum_{i} S_{i}^{\text{held}} \times P_{i, t+1}$.
2. Determine provisional target dollar allocations: $\text{TargetDollar}_{i, \text{prov}} = V_{\text{total}, t+1} \times w_{i, t+1}$.
3. Execute necessary sells:
   - **Full Exits**: Liquidate 100% of any stock no longer in the Top $N$.
   - **Overweight Trims**: If $S_{i}^{\text{held}} \times P_{i, t+1} > \text{TargetDollar}_{i, \text{prov}}$, sell the excess shares.
   - Retain all underweight holdings without selling.

### 2. Phase 2: FIFO Tax Settlement & Reinvestment
1. **FIFO Lot Depletion**: Realized gain/loss is computed for each sold share by matching against the earliest tax lots in the portfolio queue:
   $$\text{RealizedGain}_i = (\Delta S_i \times P_{i, t+1}) - \text{CostBasis}_{\text{FIFO}}(\Delta S_i)$$
2. **Loss Carryforward Netting**: Current-year realized gains are offset against any accumulated prior-year losses:
   $$\text{NetTaxableGain}_{t+1} = \sum \text{RealizedGain} - \text{LossCarryforward}_{t}$$
   - If $\text{NetTaxableGain} > 0$: $\text{TaxPaid} = \text{NetTaxableGain} \times \tau$, and carryforward resets to $\$0$.
   - If $\text{NetTaxableGain} \le 0$: $\text{TaxPaid} = \$0$, and remainder becomes new loss carryforward.
3. **Net Reinvestment**: In after-tax simulations, taxes are deducted immediately from cash proceeds:
   $$\text{NetInvestableEquity} = V_{\text{total}, t+1} - \text{TaxPaid}$$
   Final buy orders are executed to bring underweight and newly entered constituents to their exact target weights.
4. **Default Tax Rate**: $\tau = 30.0\%$ flat (modeling 20% federal long-term capital gains + 3.8% Net Investment Income Tax + California state capital gains).

### 3. Terminal Liquidation & Tax Drag
At the end of the investment horizon (2024), we calculate:
- **Pre-Liquidation Wealth**: Final portfolio value before closing open positions.
- **Post-Liquidation Wealth**: True after-tax wealth assuming all unrealized capital gains in open positions are fully liquidated and taxed at rate $\tau$ (net of remaining carryforward).
- **Tax Drag**: The annualized percentage return lost to tax friction:
  $$\text{Tax Drag} = \text{CAGR}_{\text{Pre-Tax}} - \text{Post-Liquidation CAGR}_{\text{After-Tax}}$$

---

## Key Empirical Results (1994–2024)

*Baseline: \$10,000 Initial Capital | 30% Capital Gains Tax Rate*

| Horizon | Strategy | Pre-Tax CAGR | After-Tax CAGR | Post-Liq CAGR | Cumulative Return | Max Drawdown | Tax Drag | Alpha vs SPX |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **10-Year** (2014–2024) | **Top 3** | **26.64%** | **24.51%** | **21.91%** | **795.64%** | -31.44% | 4.73% | **+13.45%** |
| | Top 5 | 22.41% | 20.67% | 18.17% | 554.67% | -37.01% | 4.25% | +9.60% |
| | Top 10 | 20.20% | 18.41% | 16.16% | 441.87% | -33.86% | 4.04% | +7.34% |
| | S&P 500 Index | 11.07% | 11.07% | 11.07% | 185.67% | -19.44% | 0.00% | *Benchmark* |
| **20-Year** (2004–2024) | **Top 3** | **15.29%** | **14.03%** | **12.80%** | **1,282.25%** | -42.73% | 2.49% | **+5.81%** |
| | Top 5 | 13.33% | 12.21% | 11.00% | 901.64% | -37.01% | 2.33% | +3.99% |
| | Top 10 | 12.22% | 11.05% | 9.96% | 713.94% | -33.86% | 2.26% | +2.83% |
| | S&P 500 Index | 8.22% | 8.22% | 8.22% | 385.32% | -38.49% | 0.00% | *Benchmark* |
| **30-Year** (1994–2024) | Top 3 | 11.12% | 9.98% | 9.19% | 1,636.90% | -72.21% | 1.94% | +1.11% |
| | Top 5 | 11.27% | 10.00% | 9.21% | 1,644.15% | -70.65% | 2.06% | +1.13% |
| | **Top 10** | **11.73%** | **10.28%** | **9.55%** | **1,781.59%** | -54.28% | 2.18% | **+1.41%** |
| | S&P 500 Index | 8.87% | 8.87% | 8.87% | 1,180.65% | -40.12% | 0.00% | *Benchmark* |

---

## Architecture & Directory Layout

```
sp500_strategy/
├── run_backtest.py                 # Primary executable CLI runner and table presenter
├── data/
│   ├── sp500_constituents.json     # Point-in-time constituent weights and returns (1994–2024)
│   └── sp500_prices.json           # Split-adjusted year-end close prices and S&P 500 levels
├── engine/
│   ├── __init__.py                 # Package exports
│   ├── models.py                   # Data models (ConstituentSnapshot, TaxLot, TradeOrder, etc.)
│   ├── tax_lots.py                 # FIFO lot queue, depletion, and loss carryforward engine
│   ├── selector.py                 # Strategy selectors (MarketCapSelector, PerformanceSelector)
│   ├── data_loader.py              # JSON point-in-time universe and price loader
│   ├── backtest.py                 # Two-phase simulation coordinator and trade ledger
│   ├── metrics.py                  # CAGR, cumulative returns, max drawdown, alpha, tax drag
│   └── exporters.py                # CSV exporters and Google Apps Script dashboard generator
├── outputs/
│   ├── summary_metrics.csv         # Multi-horizon summary table across all strategies
│   ├── annual_breakdown.csv        # Year-by-year valuation, turnover, taxes, and cash history
│   └── trade_log.csv               # Complete audit trail of all buy/sell transactions
├── scripts/
│   ├── google_apps_script.js       # Complete self-contained Google Apps Script dashboard
│   └── generate_datasets.py        # Historical data builder and validator
└── tests/
    ├── test_models.py              # Unit tests for core data models
    ├── test_tax_lots.py            # Unit tests for FIFO lot queue and loss netting
    ├── test_selector.py            # Unit tests for weighting and selection logic
    ├── test_data_loader.py         # Unit tests for data loading and pricing lookups
    ├── test_rebalancing.py         # Unit tests for two-phase rebalancing simulation
    ├── test_metrics.py             # Unit tests for quantitative calculations
    ├── test_exporters.py           # Unit tests for CSVs and Google Apps Script export
    └── test_cli.py                 # Unit tests for CLI runner and parameter parsing
```

---

## Getting Started

### Requirements
- **Python 3.8+**
- **Zero external dependencies!** The engine is built exclusively using the Python Standard Library (`argparse`, `dataclasses`, `json`, `csv`, `math`, `typing`, `unittest`).

No `pip install` or virtual environment required.

---

## CLI Runner Usage

### Basic Execution

Run the complete backtest suite across all horizons (10y, 20y, 30y) and $N \in \{3, 5, 10\}$:

```bash
python3 run_backtest.py
```

This outputs a terminal ASCII comparison table and generates:
- `outputs/summary_metrics.csv`
- `outputs/annual_breakdown.csv`
- `outputs/trade_log.csv`
- `scripts/google_apps_script.js`

### Custom Strategies & Parameters

#### 1. Momentum / 1-Year Performance Strategy
Test selecting constituents by trailing 1-year total return rather than market cap:
```bash
python3 run_backtest.py --strategy performance
```

#### 2. Custom Capital Gains Tax Rate
Evaluate returns under a 20% federal-only capital gains rate:
```bash
python3 run_backtest.py --tax-rate 0.20
```

#### 3. Custom Starting Capital and Specific Horizon
Run a \$100,000 backtest strictly on the 10-year horizon for Top 5:
```bash
python3 run_backtest.py --initial-capital 100000 --horizons 10y --n 5
```

#### 4. Silent Execution (for CI/CD or Scripts)
Suppress terminal table output:
```bash
python3 run_backtest.py --quiet
```

### All Available Flags

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--strategy` | `str` | `market_cap` | Selector algorithm (`market_cap` or `performance`). |
| `--tax-rate` | `float` | `0.30` | Flat capital gains tax rate applied to net realized gains. |
| `--initial-capital` | `float` | `10000.0` | Initial portfolio starting value in dollars. |
| `--horizons` | `str` | `10y,20y,30y` | Investment evaluation periods (e.g. `10y,20y` or `10y 20y`). |
| `--n` | `str` | `3,5,10` | Constituent portfolio sizes (e.g. `3,5,10` or `5`). |
| `--output-dir` | `str` | `outputs` | Target directory for CSV report artifacts. |
| `--scripts-dir` | `str` | `scripts` | Target directory for generated Google Apps Script. |
| `-q`, `--quiet` | `flag` | `False` | Suppress terminal ASCII summary table. |

---

## Extensibility: Adding Custom Selectors

The engine is engineered around the abstract base class [`BaseSelector`](engine/selector.py). You can easily implement alternative quantitative factor selection rules (e.g., Dividend Yield, Low Volatility, or Fundamental Value):

```python
from typing import List, Optional, Sequence
from engine.models import ConstituentSnapshot, HoldingTarget
from engine.selector import BaseSelector

class DividendYieldSelector(BaseSelector):
    """Selects top N constituents ranked by dividend yield."""

    def select(
        self,
        universe: Sequence[ConstituentSnapshot],
        n: Optional[int] = None,
    ) -> List[HoldingTarget]:
        eff_n = self.n if n is None else n
        if not universe:
            return []

        # Sort universe by custom metric descending (assuming metric exists on snapshot)
        sorted_stocks = sorted(
            universe,
            key=lambda c: getattr(c, "dividend_yield", 0.0),
            reverse=True,
        )
        selected = sorted_stocks[:eff_n]

        # Compute normalized target weights ('market_cap' or 'equal')
        weights = self._compute_weights(selected, weight_by=self.weight_by)

        return [
            HoldingTarget(ticker=c.ticker, target_weight=w)
            for c, w in zip(selected, weights)
        ]
```

To use it in simulations:
```python
from engine.backtest import PortfolioSimulator
from engine.data_loader import DataLoader

sim = PortfolioSimulator(DataLoader())
selector = DividendYieldSelector(n=5, weight_by="equal")
result = sim.run_simulation(2014, 2024, selector=selector, is_after_tax=True)
print(f"Dividend Strategy CAGR: {result.cagr:.2%}")
```

---

## Google Sheets Integration Guide

### Target Spreadsheet
Access the live target Google Sheet here:  
🔗 **[Google Sheets: S&P 500 Top N Strategy Dashboard](https://docs.google.com/spreadsheets/d/1v8Ig7ZeresaJNX35W2VCrBmarWgYgLxKQD9wPg4O0Ao/edit?usp=sharing)**

### Deployment Instructions

1. **Generate Script**: Run `python3 run_backtest.py` to ensure `scripts/google_apps_script.js` is up to date with the latest simulation runs.
2. **Open Apps Script**:
   - Open your target Google Spreadsheet.
   - Click **Extensions** > **Apps Script** from the top menu bar.
3. **Paste Script**:
   - In the script editor, select all text in `Code.gs` (or create a new script file).
   - Copy the entire contents of [`scripts/google_apps_script.js`](scripts/google_apps_script.js) and paste it into the editor.
   - Click the **Save** icon (disk icon or `Cmd+S` / `Ctrl+S`).
4. **Authorize & Build**:
   - Return to your Google Spreadsheet and reload the browser page.
   - A new custom menu titled **"S&P 500 Strategy"** will appear in the Google Sheets toolbar.
   - Click **S&P 500 Strategy** > **Build All Sheets**.
   - If prompted by Google for authorization ("Authorization Required"), click **Continue**, select your account, click **Advanced**, and then click **Go to Untitled project (unsafe)** to grant permissions.
   - Click **S&P 500 Strategy** > **Build All Sheets** once more.
5. **Sheets Created**:
   The script will automatically format and generate 6 polished tabs:
   - **Executive Summary**: Interactive dashboard with KPI cards, multi-horizon comparison, and dropdowns.
   - **Top 3 Strategy**: Full 30-year annual accounting ledger (start value, gross return, taxes paid, carryforward, turnover).
   - **Top 5 Strategy**: Full 30-year annual accounting ledger.
   - **Top 10 Strategy**: Full 30-year annual accounting ledger.
   - **S&P 500 Benchmark**: 30-year historical index levels, annual returns, and compounded growth.
   - **Historical Holdings & Trades**: Comprehensive audit trail of every buy and sell order executed.
   - **Scenario Data**: Pre-computed matrix across tax tiers (0%, 15%, 20%, 30%, 37%).

### Interactive Dashboard Controls

- **Cell B2 on Executive Summary**: Features an interactive dropdown list allowing you to switch tax brackets on the fly (`0.0%`, `15.0%`, `20.0%`, `30.0%`, `37.0%`).
- Selecting a new tax rate instantly recalculates after-tax CAGRs, ending portfolio equity, tax drag, and alpha across all horizons (10y, 20y, 30y) using dynamic lookup formulas.
- A custom spreadsheet function `=RECALCULATE_STRATEGY(taxRate)` is also available for ad-hoc financial modeling directly in sheet formulas.

---

## Running Unit Tests

The test suite covers models, FIFO lot accounting, tax netting, universe data loaders, rebalancing mechanics, exporter pipelines, and CLI argument handling:

```bash
# Run the entire test suite
python3 -m unittest discover tests

# Run specific test suites
python3 -m unittest tests/test_cli.py
python3 -m unittest tests/test_tax_lots.py
python3 -m unittest tests/test_rebalancing.py
python3 -m unittest tests/test_exporters.py
```

All 98 tests execute in under 0.5 seconds with 100% test pass rate.

---

## License

MIT License. Designed and developed for institutional quantitative research and financial modeling.
