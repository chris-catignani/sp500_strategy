# S&P 500 Top N Investment Strategy & Tax-Aware Backtesting Engine

An institutional-grade, zero-dependency quantitative backtesting engine and reporting suite that models, simulates, and evaluates an active equity strategy against the S&P 500 Total Return benchmark (`^GSPC` price return + `^SP500TR` total return) across 10-year (2014–2024), 20-year (2004–2024), and 30-year (1994–2024) investment horizons.

The engine features rigorous **two-phase annual rebalancing**, **pre-rebalance cash dividend pooling**, **decoupled dual tax settlement** (capital loss carryforwards only offset capital gains), full **FIFO (First-In, First-Out) tax lot depletion**, **loss carryforward netting**, **terminal liquidation accounting**, and export pipelines for both audit CSVs and an interactive **Google Apps Script dashboard**.

---

## How This Project Works: Python Simulation + Google Apps Script

A common question when opening this repository is: **"Why is the project written in Python, but there is also a JavaScript file (`scripts/google_apps_script.js`)? What is the purpose of both?"**

Here is how the system works together:

1. **The Python Simulation Engine (`engine/` & `run_backtest.py`)**:
   - Google Sheets cannot execute heavy historical backtests or process 31 years of point-in-time constituent data natively.
   - The **Python engine** handles all the quantitative computation: it processes 31 years of split-adjusted S&P 500 constituent weights, prices, and cash dividends (1994–2024), simulates annual rebalancing for Top 3, Top 5, and Top 10 portfolios, pools cash dividends pre-rebalance, tracks FIFO tax lots, calculates capital loss carryforwards, and computes multi-horizon performance across multiple tax tiers ($0\%, 15\%, 20\%, 30\%, 37\%$) against dynamic pre-tax and after-tax S&P 500 Total Return benchmarks.
   - Built with **zero external dependencies** (uses only the Python 3 standard library: no `pip install`, `pandas`, or `numpy` required).

2. **The Standalone JavaScript File (`scripts/google_apps_script.js`)**:
   - Google Sheets is powered by **Google Apps Script** (a cloud-based JavaScript runtime built into Google Workspace).
   - When Python runs, it automatically compiles all simulation matrices, 30-year annual accounting ledgers, trade audit logs, and dashboard styling formulas into a single, self-contained JavaScript file: [`scripts/google_apps_script.js`](scripts/google_apps_script.js).
   - **For the user**: You don't need to know JavaScript or configure APIs. You simply copy and paste this one file into Google Sheets (`Extensions > Apps Script`), click run, and it instantly builds a complete, interactive, beautifully formatted financial dashboard with dynamic dropdowns.

3. **CSV Audit Exports (`outputs/`)**:
   - Python simultaneously exports clean CSV files (`summary_metrics.csv`, `annual_breakdown.csv`, `trade_log.csv`) for independent spreadsheet analysis, reporting, or automated workflows.

---

## Table of Contents

- [How This Project Works: Python + Apps Script](#how-this-project-works-python-simulation--google-apps-script)
- [Executive Summary & Strategy Logic](#executive-summary--strategy-logic)
- [Two-Phase Rebalancing & Tax Model](#two-phase-rebalancing--tax-model)
- [Methodology Note: Dividend Timing Convention](#methodology-note-dividend-timing-convention)
- [Key Empirical Results (1994–2024)](#key-empirical-results-19942024)
- [Financial Metrics & Acronym Guide](#financial-metrics--acronym-guide)
- [Getting Started](#getting-started)
- [CLI Runner Usage](#cli-runner-usage)
- [Extensibility: Adding Custom Selectors](#extensibility-adding-custom-selectors)
- [Google Sheets Integration Guide](#google-sheets-integration-guide)
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
4. **Apples-to-Apples Comparison**: Returns are calculated on a total return basis (split-adjusted prices and cash dividends from `data/sp500_dividends.json` included for all strategy constituents) against the official S&P 500 Total Return benchmark (`^SP500TR`). In after-tax runs, the benchmark is modeled dynamically (`^GSPC` price return + `^SP500TR` synthetic dividend yield) with annual dividend taxation and terminal capital gains liquidation tax.

---

### Two-Phase Rebalancing & Tax Model

Real-world rebalancing incurs capital gains and dividend taxes when winners are trimmed, exits occur, or cash distributions are paid. A naïve simulation encounters circular dependency: tax liabilities depend on sell proceeds and dividend receipts, but target share quantities depend on net available capital.

To solve this mathematically while enforcing strict self-financing without leverage (`cash >= 0.0`), the engine implements a **deterministic two-phase rebalancing cycle**:
1. **Pre-Rebalance Cash Dividend Pooling**: Annual cash dividends from `data/sp500_dividends.json` are credited to available cash prior to rebalancing trades.
2. **Phase 1 (Provisional Exits & Trims)**: Overweight positions and exited constituents are provisionally trimmed based on pre-tax wealth.
3. **Phase 2 (Decoupled Tax Settlement & Net Reinvestment)**:
   - **Dividend income** is taxed separately at rate $\tau$ (cannot be offset by capital loss carryforwards under IRS rules).
   - **Realized capital gains** are computed via FIFO lot accounting and netted against prior capital loss carryforwards.
   - Secondary trims bring overweight positions down to net equity ($V_{\text{net}} \times w_i$).
   - Buy orders are clamped to available cash (`cash >= 0.0`).
4. **Dynamic After-Tax Benchmark Modeling**: The S&P 500 benchmark is modeled dynamically using `^GSPC` price return + `^SP500TR` synthetic dividend yield with annual dividend taxation and terminal capital gains liquidation tax.

For full mathematical derivations, sequence diagrams, and tax-loss carryforward formulas, see:
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Methodology Note: Dividend Timing & Rebalancing Frequencies

> [!NOTE]
> **Discrete Dividend Timing & Quarterly Rebalancing**:
> This simulation engine supports both **Annual** and **Quarterly** discrete rebalancing cycles:
> - **Quarterly Rebalancing**: At the end of each quarter (March 31, June 30, September 30, December 31), exact split-adjusted dividends paid across that 3-month window are credited to cash prior to rebalancing. This captures authentic intra-year dividend increases (e.g., Apple, Microsoft, ExxonMobil dividend raises) in the exact quarter they took effect.
> - **Annual Rebalancing**: Constituent cash dividends are credited once annually at year-end based on the cumulative distributions over the calendar year.
>
> In both modes:
> 1. Dividends are derived directly from primary corporate action event logs (`data/raw/tickers/`) and are **never** simply divided by 4.
> 2. Cash dividends are pooled into available cash prior to rebalancing, preserving the zero-external-dependency, self-financing invariant ($C \ge 0$) without margin debt.
> 3. Dividend income is taxed in the exact period earned at marginal rate $\tau$, decoupled from capital gains under IRS rules.

---

## Key Empirical Results (1994–2024)

*Baseline: \$10,000 Initial Capital | 30% Capital Gains & Dividend Tax Rate*

| Horizon | Strategy | Pre-Tax CAGR (Annual) | After-Tax CAGR (Annual) | Post-Liq CAGR (Annual) | Total Return (Cumulative) | Max Drawdown (Worst Drop) | Tax Drag (Annual) | Alpha vs SPX (Annual) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **10-Year** (2014–2024) | **Top 3** | **28.02%** | **25.54%** | **22.92%** | **+687.61%** | -31.04% | 5.10% | **+13.37%** |
| | Top 5 | 23.50% | 21.47% | 18.96% | +467.42% | -36.76% | 4.55% | +9.40% |
| | Top 10 | 21.53% | 19.39% | 17.13% | +385.96% | -33.55% | 4.40% | +7.58% |
| | S&P 500 Index | 12.24% | 11.89% | 9.55% | +149.02% | -18.68% | 2.69% | *Benchmark* |
| **20-Year** (2004–2024) | **Top 3** | **17.30%** | **15.49%** | **14.24%** | **+1,334.18%** | -39.56% | 3.06% | **+6.52%** |
| | Top 5 | 15.41% | 13.69% | 12.47% | +949.41% | -36.76% | 2.93% | +4.75% |
| | Top 10 | 14.50% | 12.69% | 11.59% | +796.31% | -33.55% | 2.91% | +3.87% |
| | S&P 500 Index | 9.53% | 9.14% | 7.72% | +342.65% | -37.04% | 1.81% | *Benchmark* |
| **30-Year** (1994–2024) | **Top 3** | **15.18%** | **13.20%** | **12.38%** | **+3,220.82%** | -56.50% | 2.79% | **+3.75%** |
| | Top 5 | 14.95% | 12.85% | 12.04% | +2,932.26% | -54.82% | 2.91% | +3.41% |
| | Top 10 | 14.74% | 12.58% | 11.85% | +2,778.09% | -40.32% | 2.89% | +3.21% |
| | S&P 500 Index | 10.11% | 9.74% | 8.64% | +1,100.36% | -38.64% | 1.47% | *Benchmark* |

*Note: Total Return (Cumulative) reflects true post-liquidation net wealth for both strategy and benchmark under the baseline 30% tax rate.*

---

## Financial Metrics & Acronym Guide

Every metric reported in the CLI, CSV files, and Google Sheets dashboard is defined below, including whether it represents an **annualized rate** or a **total cumulative return**:

| Metric | Frequency | Plain-English Definition | Example |
| :--- | :---: | :--- | :--- |
| **CAGR** *(Compound Annual Growth Rate)* | **Annual** | The smoothed annual return your money grew each year, assuming steady compound interest. It answers: *"What constant annual return would turn my starting capital into my ending wealth?"* | A 10-year CAGR of 25.54% means your portfolio grew at an effective pace of 25.54% per year. |
| **Pre-Tax CAGR** | **Annual** | Annual compounded growth before deducting any taxes on rebalancing gains and dividends. | 28.02% / year (Top 3, 10y) |
| **After-Tax CAGR** | **Annual** | Annual compounded growth of your live portfolio after paying annual taxes on dividends and net realized capital gains. | 25.54% / year (Top 3, 10y) |
| **Post-Liquidation CAGR** | **Annual** | True net "walk-away" annual return assuming you sell 100% of remaining holdings at the end of the horizon and pay all final taxes on unrealized gains. | 22.92% / year (Top 3, 10y) |
| **Cumulative Return** | **Total** | The complete percentage gain over the entire 10, 20, or 30 year horizon. | **+872.37%** over 10 years means $\$10,000$ turned into $\$97,237$ total. |
| **Alpha vs S&P 500** | **Annual** | The excess annual return earned above the dynamic after-tax S&P 500 Total Return benchmark. | An alpha of **+13.37%** means beating the benchmark by 13.37% each year. |
| **Tax Drag** | **Annual** | The annual percentage of return lost to taxes each year. Calculated as $\text{Pre-Tax CAGR} - \text{Post-Liquidation CAGR}$. | A tax drag of 5.10% means taxes reduced annual compounding from 28.02% to 22.92%. |
| **Max Drawdown** | **Total** | The worst peak-to-trough decline during market crashes before recovering to new highs. | -36.76% drop during the 2022 bear market. |
| **Total Dividends Received** | **Total** | Cumulative gross dollar dividends credited to the portfolio from constituent holdings. | $\$1,245.50$ in dividends received over the horizon. |
| **Dividend Tax Paid** | **Annual** | Annual tax paid on gross dividend distributions ($\text{Div} \times \tau$). Per IRS rules, dividends cannot be offset by capital loss carryforwards. | Taxed annually at rate $\tau$. |
| **Capital Gains Tax Paid** | **Annual** | Annual tax paid on net realized capital gains after FIFO lot depletion and loss carryforward offsets. | Taxed annually at rate $\tau$. |
| **SPX / `^GSPC`** | *Index* | The standard ticker symbol for the S&P 500 Price Return Index. | Historical price levels |
| **`^SP500TR`** | *Index* | The standard ticker symbol for the S&P 500 Total Return Index (reinvested gross dividends). | Total return benchmark |

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

#### 4. Quarterly Rebalancing & Side-by-Side Frequency Comparison
Run quarterly rebalancing or compare Annual vs. Quarterly side-by-side in the terminal:
```bash
# Run quarterly rebalancing
python3 run_backtest.py --frequency quarterly

# Run and display both Annual and Quarterly side-by-side
python3 run_backtest.py --compare-frequencies
```

#### 5. Silent Execution (for CI/CD or Scripts)
Suppress terminal table output:
```bash
python3 run_backtest.py --quiet
```

### All Available Flags

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--strategy` | `str` | `market_cap` | Selector algorithm (`market_cap` or `performance`). |
| `--frequency` | `str` | `annual` | Rebalancing frequency (`annual` or `quarterly`). |
| `--compare-frequencies` | `flag` | `False` | Run and display both annual and quarterly rebalancing side-by-side. |
| `--tax-rate` | `float` | `0.30` | Flat capital gains tax rate applied to net realized gains. |
| `--initial-capital` | `float` | `10000.0` | Initial portfolio starting value in dollars. |
| `--horizons` | `str` | `10y,20y,30y` | Investment evaluation periods (e.g. `10y,20y` or `10y 20y`). |
| `--n` | `str` | `3,5,10` | Constituent portfolio sizes (e.g. `3,5,10` or `5`). |
| `--universes` | `str` | `sp500,world` | Constituent universes to simulate (`sp500`, `world`). |
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
   The script automatically creates and orders 7 sheets, ensuring **Executive Summary** is the first tab:
   1. **Executive Summary** (Tab 1): 12-column interactive dashboard (Columns A through L) featuring 5 balanced KPI summary cards, a multi-horizon comparison table driven by dynamic `=INDEX(..., MATCH(...))` formulas linked to cell B2, a financial metric glossary, and an explicit dividend timing methodology callout card.
   2. **Top 3 Strategy** (Tab 2): Full 30-year 15-column annual accounting ledger (Year, Start Value, Gross Return, Dividends Received ($), Ending Value (Pre-Tax), Realized Capital Gain, Net Taxable Gain, Capital Gains Tax ($), Dividend Tax ($), Total Tax Paid ($), Loss Carryforward, Ending Value (After-Tax), Cash Reserve, S&P 500 Return, Annual Turnover).
   3. **Top 5 Strategy** (Tab 3): Full 30-year 15-column annual accounting ledger.
   4. **Top 10 Strategy** (Tab 4): Full 30-year 15-column annual accounting ledger.
   5. **S&P 500 Benchmark** (Tab 5): 30-year historical index levels, annual returns, and compounded growth.
   6. **Historical Holdings & Trades** (Tab 6): Comprehensive audit trail of every buy and sell order executed (Year, Strategy, Ticker, Action, Shares, Execution Price, Realized Gain).
   7. **Scenario Data** (Tab 7): 14-column pre-computed lookup matrix across 5 tax tiers (`0.0%`, `15.0%`, `20.0%`, `30.0%`, `37.0%`) powering dynamic formula recalculations.

### Interactive Dashboard Controls

- **Cell B2 on Executive Summary**: Features an interactive dropdown list allowing you to switch tax brackets on the fly (`0.0%`, `15.0%`, `20.0%`, `30.0%`, `37.0%`).
- Selecting a new tax rate instantly recalculates after-tax CAGRs, ending portfolio equity, tax drag, and alpha across all horizons (10y, 20y, 30y) using dynamic lookup formulas.
- A custom spreadsheet function `=RECALCULATE_STRATEGY(taxRate)` is also available for ad-hoc financial modeling directly in sheet formulas.

---

## Running Unit Tests

The test suite covers models, FIFO lot accounting, tax netting, universe data loaders, dividend queries, dynamic benchmark analytics, rebalancing mechanics, exporter pipelines, and CLI argument handling:

```bash
# Run the entire test suite
python3 -m unittest discover tests

# Run specific test suites
python3 -m unittest tests/test_dataset_integrity.py
python3 -m unittest tests/test_cli.py
python3 -m unittest tests/test_tax_lots.py
python3 -m unittest tests/test_rebalancing.py
python3 -m unittest tests/test_exporters.py
```

All 126 tests execute in ~1.4 seconds with 100% test pass rate.

---

## Historical Data Sources & Provenance

For detailed technical specifications on benchmark index levels (`^GSPC`, `^SP500TR`), constituent point-in-time rankings, corporate action split adjustments (`WMT`, `GE`, `AIG`, `UNH`), and dividend cash accounting, see [`docs/DATA_PROVENANCE.md`](docs/DATA_PROVENANCE.md).

---

## License

MIT License. Designed and developed for institutional quantitative research and financial modeling.
