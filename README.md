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

Real-world rebalancing incurs capital gains and dividend taxes when winners are trimmed, exits occur, or cash distributions are paid. A naïve simulation encounters circular dependency: tax liabilities depend on sell proceeds and dividend receipts, but target share quantities depend on net available capital. To solve this mathematically while enforcing strict self-financing (`cash >= 0.0`), the engine implements a **Two-Phase Rebalancing Protocol**:

### 1. Pre-Rebalance Cash Dividend Collection & Pooling
At year-end $t+1$, prior to executing rebalancing trades:
1. **Gross Dividend Calculation**: Cash dividends are computed for all held positions based on the year's split-adjusted dividend per share from `data/sp500_dividends.json`:
   $$\text{Div}_{t+1} = \sum_{i} S_{i}^{\text{held}} \times \text{DPS}_{i, t+1}$$
2. **Cash Pooling**: Gross dividend proceeds are added directly to available portfolio cash:
   $$\text{Cash}_{t+1} = \text{Cash}_t + \text{Div}_{t+1}$$
3. **Pre-Tax Valuation**: The portfolio is marked to market with pooled cash:
   $$V_{\text{total}, t+1} = \sum_{i} (S_{i}^{\text{held}} \times P_{i, t+1}) + \text{Cash}_{t+1}$$

### 2. Phase 1: Portfolio Valuation & Provisional Sell Execution
1. Determine provisional target dollar allocations based on pre-tax wealth:
   $$\text{TargetDollar}_{i, \text{prov}} = V_{\text{total}, t+1} \times w_{i, t+1}$$
2. Execute provisional sells:
   - **Full Exits**: Liquidate 100% of any stock no longer in the Top $N$.
   - **Overweight Trims**: If $S_{i}^{\text{held}} \times P_{i, t+1} > \text{TargetDollar}_{i, \text{prov}}$, sell the excess shares.
   - Retain all underweight holdings without selling.

### 3. Phase 2: Decoupled Dual Tax Settlement & Net Reinvestment
1. **Decoupled Tax Architecture**:
   - **Dividend Tax**: Under IRS tax code rules, dividend income is taxable in the calendar year received and *cannot* be offset by capital loss carryforwards:
     $$\text{Tax}_{\text{div}} = \text{Div}_{t+1} \times \tau$$
   - **Capital Gains Tax**: Realized gain/loss for each sold share is computed via FIFO tax lot matching:
     $$\text{RealizedGain}_i = (\Delta S_i \times P_{i, t+1}) - \text{CostBasis}_{\text{FIFO}}(\Delta S_i)$$
   - **Loss Carryforward Netting**: Capital loss carryforwards offset only realized capital gains:
     $$\text{NetTaxableGain}_{t+1} = \max(0, \sum \text{RealizedGain} - \text{LossCarryforward}_{t})$$
     - If $\text{NetTaxableGain}_{t+1} > 0$: $\text{Tax}_{\text{cap}} = \text{NetTaxableGain}_{t+1} \times \tau$, and carryforward resets to $\$0$.
     - If $\text{NetTaxableGain}_{t+1} \le 0$: $\text{Tax}_{\text{cap}} = \$0$, and unused losses carry forward to year $t+2$.
   - **Total Annual Tax**:
     $$\text{TaxPaid} = \text{Tax}_{\text{div}} + \text{Tax}_{\text{cap}}$$
2. **Iterative Secondary Trims**:
   - In after-tax runs, paying taxes reduces investable equity: $V_{\text{net}} = V_{\text{total}, t+1} - \text{TaxPaid}$.
   - Positions held above their final net target allocation ($V_{\text{net}} \times w_i$) are iteratively trimmed, settling any additional realized capital gains taxes until equilibrium is achieved.
3. **Cash-Clamped Buys (Unleveraged Invariant)**:
   - Final buy orders bring underweight and newly entered constituents to their target allocations.
   - To strictly preserve the unleveraged invariant (`cash >= 0.0`), all buy orders are clamped to available cash proceeds:
     $$\text{BuyCost}_i = \min(\text{DesiredCost}_i, \max(0, \text{Cash}))$$
4. **Default Tax Rate**: $\tau = 30.0\%$ flat (modeling 20% federal long-term capital gains + 3.8% Net Investment Income Tax + state capital gains).

### 4. Dynamic After-Tax S&P 500 Benchmark Modeling
To achieve a true apples-to-apples after-tax comparison, the S&P 500 benchmark is modeled dynamically using both price return (`^GSPC`) and total return (`^SP500TR`) indices:
1. **Synthetic Annual Dividend Yield**:
   $$r_{\text{PR}, t} = \frac{\text{SPX\_PR}_t - \text{SPX\_PR}_{t-1}}{\text{SPX\_PR}_{t-1}}, \quad r_{\text{TR}, t} = \frac{\text{SPX\_TR}_t - \text{SPX\_TR}_{t-1}}{\text{SPX\_TR}_{t-1}}$$
   $$y_t = \max(0, r_{\text{TR}, t} - r_{\text{PR}, t})$$
2. **After-Tax Compounding**:
   $$r_{\text{benchmark}, t} = r_{\text{PR}, t} + y_t \times (1 - \tau)$$
3. **Basis Tracking & Terminal Tax**:
   - Reinvested after-tax dividends increase the benchmark cost basis each year: $\text{Basis}_{t} = \text{Basis}_{t-1} + \text{Wealth}_{t-1} \times y_t \times (1 - \tau)$.
   - Upon terminal liquidation, unrealized benchmark capital gains are taxed:
     $$\text{TerminalTax}_{\text{bench}} = \max(0, V_{\text{pre-liq}} - \text{Basis}_T) \times \tau$$

### 5. Terminal Liquidation & Tax Drag
At the conclusion of the investment horizon (2024):
- **Pre-Liquidation Wealth**: Portfolio value before liquidating remaining holdings.
- **Post-Liquidation Wealth**: True after-tax net wealth assuming 100% liquidation of all open positions and payment of all remaining taxes on unrealized gains (net of unused carryforward).
- **Tax Drag**: The annualized percentage return lost to tax friction:
  $$\text{Tax Drag} = \text{CAGR}_{\text{Pre-Tax}} - \text{Post-Liquidation CAGR}_{\text{After-Tax}}$$

---

## Methodology Note: Dividend Timing Convention

> [!NOTE]
> **Annual Discrete Dividend Timing**:
> In this simulation engine, constituent cash dividends are credited once annually at each rebalance date based on the positions held over the preceding year and the annual dividend distribution rate.
>
> In live markets, companies distribute dividends quarterly or monthly, which could be held in cash or reinvested incrementally throughout the year. The annual discrete convention is standard in long-term quantitative factor models:
> 1. It eliminates the need to introduce arbitrary intra-year reinvestment timing assumptions or high-frequency pricing dependencies.
> 2. It preserves the zero-external-dependency standard library design of the engine.
> 3. It provides a conservative and realistic assessment of after-tax compounding drag, properly taxing all dividend distributions in their earned tax year while maintaining strict self-financing rebalancing without margin debt.

---

## Key Empirical Results (1994–2024)

*Baseline: \$10,000 Initial Capital | 30% Capital Gains & Dividend Tax Rate*

| Horizon | Strategy | Pre-Tax CAGR (Annual) | After-Tax CAGR (Annual) | Post-Liq CAGR (Annual) | Total Return (Cumulative) | Max Drawdown (Worst Drop) | Tax Drag (Annual) | Alpha vs SPX (Annual) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **10-Year** (2014–2024) | **Top 3** | **28.02%** | **25.54%** | **22.92%** | **+872.37%** | -31.04% | 5.10% | **+13.37%** |
| | Top 5 | 23.50% | 21.47% | 18.96% | +599.20% | -36.76% | 4.55% | +9.40% |
| | Top 10 | 21.53% | 19.39% | 17.13% | +488.28% | -33.55% | 4.40% | +7.58% |
| | S&P 500 Index | 12.24% | 11.89% | 9.55% | +149.02% | -18.68% | 2.69% | *Benchmark* |
| **20-Year** (2004–2024) | **Top 3** | **17.42%** | **15.56%** | **14.32%** | **+1,705.03%** | -38.69% | 3.10% | **+6.60%** |
| | Top 5 | 15.48% | 13.74% | 12.52% | +1,213.28% | -36.76% | 2.96% | +4.80% |
| | Top 10 | 14.63% | 12.78% | 11.68% | +1,007.93% | -33.55% | 2.95% | +3.96% |
| | S&P 500 Index | 9.53% | 9.14% | 7.72% | +342.65% | -37.04% | 1.81% | *Benchmark* |
| **30-Year** (1994–2024) | Top 3 | 13.20% | 11.44% | 10.64% | +2,475.66% | -66.74% | 2.56% | +2.00% |
| | Top 5 | 13.33% | 11.45% | 10.65% | +2,481.57% | -64.14% | 2.68% | +2.01% |
| | **Top 10** | **13.95%** | **11.88%** | **11.15%** | **+2,801.01%** | -48.08% | 2.80% | **+2.52%** |
| | S&P 500 Index | 10.11% | 9.74% | 8.64% | +1,100.36% | -38.64% | 1.47% | *Benchmark* |

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
python3 -m unittest tests/test_cli.py
python3 -m unittest tests/test_tax_lots.py
python3 -m unittest tests/test_rebalancing.py
python3 -m unittest tests/test_exporters.py
```

All 110 tests execute in under 0.5 seconds with 100% test pass rate.

---

## License

MIT License. Designed and developed for institutional quantitative research and financial modeling.
