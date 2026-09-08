# Design Document: Dividend Accounting & Dynamic After-Tax Benchmarking

**Date**: 2026-09-08  
**Status**: Proposed (Pending User Review)  
**Author**: Antigravity Agent & User  
**Target Repository**: `/Users/chriscatignani/Developer/sp500_strategy`  
**Target Google Sheet**: [Top N vs S&P500](https://docs.google.com/spreadsheets/d/1v8Ig7ZeresaJNX35W2VCrBmarWgYgLxKQD9wPg4O0Ao/edit?usp=sharing)  

---

## 1. Executive Summary

This design integrates cash dividend flows and dynamic after-tax benchmarking into the S&P 500 Top N ($N \in \{3, 5, 10\}$) quantitative backtesting engine and interactive Google Sheets dashboard.

Previously, the backtesting engine evaluated strategies on a split-adjusted pure price-return basis against the S&P 500 Price Return index (`^GSPC`), excluding cash dividends for both. This upgrade incorporates historical cash dividends per share (`DPS`) across 1994–2024, tracks cumulative dividend income, incorporates dividend taxation in after-tax portfolio runs, and upgrades the benchmark comparison to a dynamic after-tax S&P 500 benchmark utilizing both S&P 500 Price Return (`^GSPC`) and S&P 500 Total Return (`^SP500TR`).

Additionally, because the engine runs on an annual discrete frequency, the timing difference between intra-year distributions and year-end rebalancing is explicitly documented in the codebase, reports, and Google Sheets UI.

---

## 2. Timing Convention & Methodological Callout

### 2.1 Discrete Annual Rebalancing Timing
* **Real-World Reality**: In live trading, corporate dividends are declared and distributed periodically (typically quarterly) and reinvested at prevailing intra-year market prices.
* **Model Convention**: The engine operates on an annual discrete time-step (December 31 year-ends from 1994 to 2024). Cash dividends earned throughout calendar year $t$ are calculated based on shares held during year $t$ and split-adjusted annual cash dividends per share ($\text{DPS}_t$). These dividends are received and pooled into portfolio cash at year-end $t$ immediately prior to rebalancing.
* **Documentation & UI Callouts**:
  * Added to `README.md` and `AGENTS.md`.
  * Displayed as an informational **Methodology Callout Card** on the Google Sheet Executive Summary tab.

---

## 3. Mathematical Formulation & Rebalancing Flow

### 3.1 Pre-Rebalance Dividend Receipt & Cash Pooling
At the close of trading on year-end $t$, before any rebalancing sells or buys occur:
1. Identify all positions held from the previous period: $\{S_i^{\text{held}}\}$.
2. For each held constituent $i$, query the annual split-adjusted cash dividend per share $\text{DPS}_{i, t}$ from `data/sp500_dividends.json` (defaults to $0.0$ if no dividend was paid).
3. Calculate total gross dividend income for year $t$:
   $$\text{DivIncome}_t = \sum_{i} S_i^{\text{held}} \times \text{DPS}_{i, t}$$
4. Pool gross dividend income directly into portfolio cash:
   $$\text{Cash}_t \leftarrow \text{Cash}_{t, \text{prior}} + \text{DivIncome}_t$$

### 3.2 Pre-Tax Valuation & Gross Return
Total pre-tax portfolio value reflects both equity positions at year-end prices and the collected dividend cash:
$$V_{\text{pretax}, t} = \sum_{i} (S_i^{\text{held}} \times P_{i, t}) + \text{Cash}_t$$

The gross portfolio return for year $t$ compounds both price return and dividend yield:
$$R_{\text{gross}, t} = \frac{V_{\text{pretax}, t} - V_{\text{start}, t-1}}{V_{\text{start}, t-1}}$$

### 3.3 Phase 1: Rebalancing Sells (Trims & Exits)
1. Select new Top $N$ constituents and target weights $w_i$.
2. Calculate provisional target share allocations based on total pre-tax equity:
   $$\text{TargetShares}_{i, \text{prov}} = \frac{V_{\text{pretax}, t} \times w_i}{P_{i, t}}$$
3. Execute necessary sells:
   * **Full Exits**: Liquidate $100\%$ of shares for constituents no longer in Top $N$.
   * **Overweight Trims**: Sell excess shares down to provisional targets for constituents whose held shares exceed targets.
4. Realized capital gains and losses are computed via FIFO tax lot depletion.
5. Gross sell proceeds are added to $\text{Cash}_t$.

### 3.4 Phase 2: Dual Tax Settlement, Secondary Trims, and Buys
In taxable simulations (`is_after_tax=True` with tax rate $\tau$):
1. **Dividend Tax**:
   Dividends are taxed annually as current income:
   $$\text{Tax}_{\text{div}, t} = \text{DivIncome}_t \times \tau$$
2. **Capital Gains Tax**:
   Net realized capital gains are offset by cumulative loss carryforwards $L_t$:
   $$\text{NetTaxableGain}_t = \max(0.0, \text{RealizedGain}_t - L_t)$$
   $$\text{Tax}_{\text{cap}, t} = \text{NetTaxableGain}_t \times \tau$$
   $$L_{t+1} = \max(0.0, L_t - \text{RealizedGain}_t) + \max(0.0, -\text{RealizedGain}_t)$$
   *(Note: Net capital losses offset future capital gains; they do not offset dividend income).*
3. **Total Annual Tax**:
   $$\text{Tax}_{\text{total}, t} = \text{Tax}_{\text{cap}, t} + \text{Tax}_{\text{div}, t}$$
4. **Secondary Trim Convergence**:
   Tax is paid out of cash: $\text{Cash}_t \leftarrow \text{Cash}_t - \text{Tax}_{\text{total}, t}$.
   If cash is insufficient to satisfy $\text{Tax}_{\text{total}, t}$, secondary trims iteratively liquidate overweight positions down to net investable equity:
   $$V_{\text{net}, t} = V_{\text{pretax}, t} - \text{Tax}_{\text{total}, t}$$
   guaranteeing that the unleveraged cash invariant $\text{Cash}_t \ge 0.0$ holds strictly.
5. **Phase 2 Buys**:
   Target shares are updated based on net investable equity:
   $$\text{TargetShares}_{i, \text{final}} = \frac{V_{\text{net}, t} \times w_i}{P_{i, t}}$$
   Underweight constituents are purchased using available cash, with purchases cash-clamped to guarantee non-negative cash.

---

## 4. Dynamic S&P 500 Benchmark Architecture

To preserve a mathematically authentic comparison against a passive S&P 500 buy-and-hold investor:

### 4.1 Data Series
* `^GSPC`: S&P 500 Price Return Index levels (1994–2024).
* `^SP500TR`: S&P 500 Total Return Index levels (1994–2024).

### 4.2 Pre-Tax Comparison (`is_after_tax=False`)
* Benchmark annual return:
  $$R_{\text{SPX}, t} = \frac{\text{SPX\_TR}_t}{\text{SPX\_TR}_{t-1}} - 1$$
* Benchmark CAGR is the compound annual growth rate of `^SP500TR`.
* Pre-tax Alpha:
  $$\alpha = \text{CAGR}_{\text{Strategy}} - \text{CAGR}_{\text{SP500TR}}$$

### 4.3 Dynamic After-Tax Comparison (`is_after_tax=True`)
A passive index investor pays annual tax on index dividends, while deferring capital gains until the end of the horizon:
1. **Annual Yield Decomposition**:
   $$R_{\text{PR}, t} = \frac{\text{SPX\_PR}_t}{\text{SPX\_PR}_{t-1}} - 1, \quad R_{\text{TR}, t} = \frac{\text{SPX\_TR}_t}{\text{SPX\_TR}_{t-1}} - 1$$
   $$y_t = R_{\text{TR}, t} - R_{\text{PR}, t}$$
2. **Annual After-Tax Compounding**:
   $$R_{\text{SPX, After-Tax}, t} = R_{\text{PR}, t} + y_t \times (1 - \tau)$$
   Starting from $V_{\text{SPX}, 0} = \text{Initial Capital}$:
   $$V_{\text{SPX}, t} = V_{\text{SPX}, t-1} \times (1 + R_{\text{SPX, After-Tax}, t})$$
   Reinvested net dividends added to cost basis:
   $$\text{Basis}_{\text{SPX}, t} = \text{Basis}_{\text{SPX}, t-1} + [V_{\text{SPX}, t-1} \times y_t \times (1 - \tau)]$$
3. **Terminal Liquidation**:
   At horizon end year $Y$:
   $$\text{UnrealizedGain}_{\text{SPX}} = \max(0.0, V_{\text{SPX}, Y} - \text{Basis}_{\text{SPX}, Y})$$
   $$\text{LiqTax}_{\text{SPX}} = \text{UnrealizedGain}_{\text{SPX}} \times \tau$$
   $$W_{\text{post-liq}, \text{SPX}} = V_{\text{SPX}, Y} - \text{LiqTax}_{\text{SPX}}$$
   $$\text{CAGR}_{\text{post-liq}, \text{SPX}} = \left(\frac{W_{\text{post-liq}, \text{SPX}}}{V_{\text{SPX}, 0}}\right)^{1/Y} - 1$$
4. **After-Tax Alpha**:
   $$\alpha = \text{Strategy Post-Liquidation CAGR} - \text{Benchmark Post-Liquidation CAGR}$$

---

## 5. Data Architecture & Schemas

### 5.1 New Dataset: `data/sp500_dividends.json`
Stores annual split-adjusted cash dividend per share for all constituents across 1994–2024:
```json
{
  "AAPL": { "2014": 0.45, "2015": 0.52, "2024": 0.99 },
  "KO": { "1994": 0.20, "2024": 1.94 },
  "MSFT": { "2003": 0.16, "2024": 3.00 }
}
```

### 5.2 Updated Dataset: `data/sp500_prices.json`
Add `^SP500TR` alongside `^GSPC`:
```json
{
  "^GSPC": { "1994": 459.27, ..., "2024": 5881.63 },
  "^SP500TR": { "1994": 753.86, ..., "2024": 13543.82 }
}
```

### 5.3 `engine/data_loader.py` Interface Additions
* `get_dividend(ticker: str, year: int) -> float`: Returns split-adjusted cash dividend per share (returns `0.0` if ticker paid no dividends).
* `get_spx_tr_level(year: int) -> float`: Returns `^SP500TR` level for year.
* `get_spx_dividend_yield(year: int) -> float`: Computes annual index dividend yield.

---

## 6. Component Architecture & Code Modifications

### 6.1 `engine/models.py`
* `AnnualLedgerEntry`:
  * `dividend_income: float = 0.0`
  * `dividend_tax_paid: float = 0.0`
  * `capital_gains_tax_paid: float = 0.0`
* `StrategyResult`:
  * `total_dividends_received: float = 0.0`
  * `total_dividend_taxes_paid: float = 0.0`

### 6.2 `engine/backtest.py`
* Compute pre-rebalance annual dividends:
  $$\text{div\_cash} = \sum (\text{shares} \times \text{dps})$$
  and add to `self.cash`.
* Settle dividend tax in Phase 2 alongside capital gains.
* Record dividend metrics in ledger entries and strategy result.

### 6.3 `engine/metrics.py`
* Add benchmark helper functions:
  * `calculate_benchmark_annual_series(...)`
  * `calculate_benchmark_terminal_metrics(...)`

### 6.4 `engine/exporters.py` & `scripts/google_apps_script.js`
* Add `total_dividends_received` to `summary_metrics.csv`.
* Add `dividend_income` and `dividend_tax_paid` to `annual_breakdown.csv`.
* Executive Summary Google Sheet Tab:
  * Add "Total Dividends Received" column to multi-horizon comparison table.
  * Embed "Methodology Note — Dividend Timing Convention" card.
  * Update scenario matrices in Scenario Data tab to support dynamic after-tax benchmark and dividend totals.
* Annual Breakdown Google Sheet Tabs:
  * Add "Dividends Received ($)" and "Dividend Tax ($)" columns to annual tables.

### 6.5 Documentation
* Update `README.md` and `AGENTS.md` with dividend architecture, formulas, and timing notes.

---

## 7. Verification & Testing Plan

1. **Unit Tests**:
   * `test_dividend_data_loader`: Verify `sp500_dividends.json` loads cleanly and returns accurate DPS or `0.0` defaults.
   * `test_dividend_cash_flow`: Verify holdings receive exact dividends, cash pools correctly, and pre-tax valuation reflects dividend income.
   * `test_dividend_taxation`: Verify dividend income is taxed at tax rate $\tau$, separate from capital loss carryforwards.
   * `test_unleveraged_cash_invariant`: Verify `cash >= 0.0` holds under all combinations of heavy dividend taxes and rebalancing sells/buys.
   * `test_dynamic_benchmark`: Verify after-tax benchmark compounding and terminal liquidation across $0\%$, $15\%$, $20\%$, $30\%$, and $37\%$ tax rates.
2. **Regression & Integration Tests**:
   * Run full test suite (`python3 -m unittest discover tests`).
   * Run CLI runner across all horizons: `python3 run_backtest.py`.
   * Verify all generated CSVs and `scripts/google_apps_script.js` syntax and structure.
