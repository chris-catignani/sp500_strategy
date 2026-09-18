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
- [Methodology Note: Dividend Timing & Rebalancing Frequencies](#methodology-note-dividend-timing--rebalancing-frequencies)
- [Financial Metrics & Acronym Guide](#financial-metrics--acronym-guide)
- [Getting Started](#getting-started)
- [CLI Runner Usage](#cli-runner-usage)
- [Extensibility: Adding Custom Selectors](#extensibility-adding-custom-selectors)
- [Google Sheets Integration Guide](#google-sheets-integration-guide)
- [Running Unit Tests](#running-unit-tests)
- [Historical Data Sources & Provenance](#historical-data-sources--provenance)
- [License](#license)


---

## Executive Summary & Strategy Logic

Passive market-cap-weighted indices are dominated by their largest constituents due to the power-law distribution of mega-cap equities. This strategy evaluates whether actively concentrating capital into the top tier of S&P 500 winners outperforms holding the entire index:

1. **Constituent Selection**: At the close of trading on the final market day of year $t$, select the top $N$ stocks ($N \in \{3, 5, 10\}$) from the S&P 500 universe. Selection operates at the company/issuer level: dual-class share structures (such as Alphabet Class A `GOOGL` and Class C `GOOG`) are aggregated into a single enterprise holding based on combined market capitalization, with execution mapped to the primary liquid share class (`GOOGL`). Consolidation is applied wherever the underlying source reports each class separately. That now covers 2014-2024: the 2020-2024 SPY filings and, since issue #45, the Vanguard 500 Index Fund's December-31 schedules for 2014-2019. Before Alphabet's Class C was created in April 2014 there is nothing to consolidate (see [`docs/DATA_PROVENANCE.md`](docs/DATA_PROVENANCE.md#438-dual-class-issuer-consolidation--execution-convention)).
2. **Relative Market Cap Weighting**: Capital is allocated in proportion to each constituent's relative index market capitalization:
   $$w_i = \frac{W_i}{\sum_{j=1}^N W_j}$$
   where $W_i$ is the company's S&P 500 index weight, consolidated across share classes where the source permits.
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
> - **Quarterly Rebalancing**: At the end of each quarter (March 31, June 30, September 30, December 31), exact split-adjusted dividends paid across that 3-month window are credited to cash prior to rebalancing. This captures authentic intra-year dividend increases (e.g., Apple, Microsoft, ExxonMobil dividend raises) in the exact quarter they took effect. Candidate pools for Q1–Q3 dynamically drift the prior December's **Top 20** point-in-time factsheet constituents relative to index performance, re-anchoring to official factsheet weights at Q4. Ranks #1–#12 use S&P Dow Jones year-end factsheet weights, 2020–2024 candidates derive directly from SPY's audited Form NPORT-P XML filings, and ranks #13–#20 for all other years are **unverified estimates** — no primary source in this repository reports a capitalization for them, and each such row is labelled accordingly in [`docs/historical_weights_table.csv`](docs/historical_weights_table.csv). Against the archived `SPY` filings in `data/raw/ground_truth/sec_filings/`, the drift model's Top 10 accuracy is quoted **out-of-sample only**: the Q4 NPORT-P filings are the same documents the year-end candidate lists are parsed from, so they match by construction, and any headline spanning every quarter is inflated by them. Of the mid-year promotions from ranks #13–#20 that the expansion enables, only **a minority are corroborated by an audited filing** (Oracle 2000, Citigroup 1999, NVIDIA 2021, Tesla 2023); most fall in quarters with no archived filing, and one — Walmart in 2008-Q3 — is **contradicted** by the filing, which places it at #11.
> - **Selector Dynamics under Top 20 Expansion (issue #41, decided)**: Two separate effects are easy to conflate. *Pool size alone* (holding the constituent data fixed, per `scripts/audit_quarterly_expansion.py`): `MarketCapSelector` is **never hurt** — Top 3 and Top 5 are unchanged at every horizon on both paths, and Top 10 gains. `PerformanceSelector` is **hurt on average**, negative in most quarterly cells and worst at Top 10, because a wider pool gives a momentum selector more recent winners to chase and the largest recent gainer out of 20 mean-reverts more often than out of 12. **The pool stays uniform at 20**: the sign of the momentum effect flips with N and with rebalancing frequency, so a rule fitting it would need pool size to depend on selector x N x frequency — twelve parameters on one 31-year sample — while the shipped market-cap default is hurt nowhere. The asymmetry is documented rather than tuned. *Separately*, correcting the 2021–2023 year-end weights against the NPORT-P filings changed the underlying data and therefore moved the reported results downward, because the prior data ranked NVIDIA #3 at year-end 2023 where the filing shows it behind Alphabet — so the Top 3 book no longer holds NVIDIA through its 2024 run. **Magnitudes for both effects, and the commands that regenerate them, are in `docs/DATA_PROVENANCE.md` §4.3.7**; they move whenever the data improves, which is why they are not quoted here.
> - **Issuer-Level Consolidation & Dual-Class Execution**: Multi-class share structures are consolidated at the corporate issuer level based on combined market capitalization, mapping trade execution to the primary liquid voting share class (Alphabet Class A `GOOGL`). Read as filed in SPY's Form NPORT-P filings, Alphabet is split into two positions (Class A `02079K305` and Class C `02079K107`), and the S&P 500 index ranks each share class independently. At year-end 2023 the raw filing ranks Alphabet's two classes separately, each below NVIDIA. Aggregating them establishes a combined enterprise weight ranking **#3**, placing Alphabet in the 2024 Top 3 portfolio, where unconsolidated as-filed rankings yield AAPL/MSFT/AMZN. The per-class weights as filed are in §4.3.8. Holding both classes in Top 10 books consumes two slots and creates portfolio degeneracy. **The consolidation runs only where the source reports each class separately.** That was once the 2020-2024 NPORT-P filings alone, leaving Alphabet's 2014-2019 weights as hand-entered factsheet anchors of undetermined share-class basis. Issue #45 settled them against the Vanguard 500 Index Fund's audited December-31 schedules, which report both classes: three of the six years turned out to cover Class A only and were corrected, and no row in [`docs/historical_weights_table.csv`](docs/historical_weights_table.csv) is marked share-class unverified any more. Correcting the under-ranking **lowered** the reported S&P 500 returns at every horizon rather than raising them; the magnitudes are in §4.3.21. For the full filing breakdown and execution convention rationale, see Section 4.3.8 in [`docs/DATA_PROVENANCE.md`](docs/DATA_PROVENANCE.md#438-dual-class-issuer-consolidation--execution-convention).
> - **Annual Rebalancing**: Constituent cash dividends are credited once annually at year-end based on the cumulative distributions over the calendar year.
>
> In both modes:
> 1. Dividends are derived directly from primary corporate action event logs (`data/raw/tickers/`) and are **never** simply divided by 4.
> 2. Cash dividends are pooled into available cash prior to rebalancing, preserving the zero-external-dependency, self-financing invariant ($C \ge 0$) without margin debt.
> 3. Dividend income is taxed in the exact period earned at marginal rate $\tau$, decoupled from capital gains under IRS rules.
> 4. Audited ground truth and sensitivity can be inspected via `python3 scripts/audit_quarterly_expansion.py`.

## Financial Metrics & Acronym Guide

Every metric reported in the CLI, CSV files, and Google Sheets dashboard is defined below, including whether it represents an **annualized rate** or a **total cumulative return**:

| Metric | Frequency | Plain-English Definition | Interpretation & Context |
| :--- | :---: | :--- | :--- |
| **CAGR** *(Compound Annual Growth Rate)* | **Annual** | The smoothed annual return your money grew each year, assuming steady compound interest. It answers: *"What constant annual return would turn my starting capital into my ending wealth?"* | Geometric mean growth rate per annum over the investment horizon. |
| **Pre-Tax CAGR** | **Annual** | Annual compounded growth before deducting any taxes on rebalancing gains and dividends. | Compound annual return before deducting any annual taxes. |
| **After-Tax CAGR** | **Annual** | Annual compounded growth of your live portfolio after paying annual taxes on dividends and net realized capital gains. | Compound annual return net of annual dividend and capital gains taxes. |
| **Post-Liquidation CAGR** | **Annual** | True net "walk-away" annual return assuming you sell 100% of remaining holdings at the end of the horizon and pay all final taxes on unrealized gains. | Walk-away annual return after paying all terminal liquidation taxes. |
| **Cumulative Return** | **Total** | The complete percentage gain over the entire 10, 20, or 30 year horizon. | Overall percentage growth from starting capital to ending equity. |
| **Alpha vs S&P 500** | **Annual** | The excess annual return earned above the dynamic after-tax S&P 500 Total Return benchmark. | Annualized excess return relative to the after-tax benchmark. |
| **Tax Drag** | **Annual** | Annual compounding performance lost to ongoing lifecycle taxes. Calculated as $\text{Pre-Tax CAGR} - \text{After-Tax CAGR}$ (pre-liquidation). For final liquidation, Terminal Tax Drag is $\text{Pre-Liquidation CAGR} - \text{Post-Liquidation CAGR}$. | Annualized compound growth reduced by ongoing dividend and rebalancing taxes. |
| **Max Drawdown** | **Total** | The worst peak-to-trough decline during market crashes before recovering to new highs. | Measured across discrete periodic observation dates. |
| **Total Dividends Received** | **Total** | Cumulative gross dollar dividends credited to the portfolio from constituent holdings. | Total cash distributions pooled prior to rebalancing. |
| **Dividend Tax Paid** | **Annual** | Annual tax paid on gross dividend distributions ($\text{Div} \times \tau$). Per IRS rules, dividends cannot be offset by capital loss carryforwards. | Taxed periodically at marginal rate $\tau$. |
| **Capital Gains Tax Paid** | **Annual** | Annual tax paid on net realized capital gains after FIFO lot depletion and loss carryforward offsets. | Taxed periodically at capital gains rate $\tau$. |
| **SPX / `^GSPC`** | *Index* | The standard ticker symbol for the S&P 500 Price Return Index. | Historical benchmark price level |
| **`^SP500TR`** | *Index* | The standard ticker symbol for the S&P 500 Total Return Index (reinvested gross dividends). | Total return benchmark series |

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
- A custom spreadsheet function `=RECALCULATE_STRATEGY(taxRate, [strategy], [horizon], [weighting], [universe], [frequency], [metric])` is also available for ad-hoc financial modeling directly in sheet formulas. It queries the generated `Scenario Data` matrix to return exact empirical metrics for standard simulated tax tiers (`0.0%`, `15.0%`, `20.0%`, `30.0%`, `37.0%`), and computes piecewise linear interpolation between bounding tiers for non-standard intermediate rates (e.g., `24.5%`). Defaults: Top 5, 30y, Market Cap, S&P 500, Annual, PostLiqCAGR.
- Top N lookups require a matching universe and weighting. Invalid combinations return `Scenario not found`; only named benchmarks may ignore these dimensions when selecting their benchmark rows.
- Legacy AT&T's September and December 1996 endpoints use derived parent-only valuations so separately credited Lucent/NCR proceeds are not counted twice. These values are model approximations, with source observations and the calculation documented in [Data Provenance](docs/DATA_PROVENANCE.md#1996-endpoint-reconciliation-derived-valuations).
- After changing datasets or templates, regenerate exports with `python3 run_backtest.py --compare-frequencies`. Updating the local `scripts/google_apps_script.js` does not update the live Google Sheet; install the regenerated script using the setup steps above.

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

All unit tests pass with zero external dependencies.

---

## Historical Data Sources & Provenance

For detailed technical specifications on benchmark index levels (`^GSPC`, `^SP500TR`), constituent point-in-time rankings, corporate action split adjustments (`WMT`, `GE`, `AIG`, `UNH`), dividend cash accounting, and the 47-filing SEC EDGAR regulatory archive (`data/raw/ground_truth/sec_filings/`), see [`docs/DATA_PROVENANCE.md`](docs/DATA_PROVENANCE.md).

---

## License

MIT License. Designed and developed for institutional quantitative research and financial modeling.
