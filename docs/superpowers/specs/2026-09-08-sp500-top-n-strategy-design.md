# Design Document: S&P 500 Top N Strategy vs. S&P 500 Benchmark

**Date**: 2026-09-08  
**Status**: Approved (Incorporating Spec Review Fixes)  
**Author**: Antigravity Agent & User  
**Target Repository**: `/Users/chriscatignani/Developer/sp500_strategy`  
**Target Google Sheet**: [Top N vs S&P500](https://docs.google.com/spreadsheets/d/1v8Ig7ZeresaJNX35W2VCrBmarWgYgLxKQD9wPg4O0Ao/edit?usp=sharing)

---

## 1. Executive Summary

This project simulates, analyzes, and evaluates an active equity investment strategy against the benchmark S&P 500 price return index (`^GSPC`) across 10-year (2014–2024), 20-year (2004–2024), and 30-year (1994–2024) periods.

The strategy allocates capital at each year-end to the largest $N$ companies ($N \in \{3, 5, 10\}$) in the S&P 500, weighted proportionally to their relative index market capitalizations. Holdings are held for exactly one full calendar year. At each subsequent year-end, the portfolio is rebalanced to the new Top $N$ holdings and weights.

The backtest tracks both **Pre-Tax Gross Returns** and **After-Tax Net Returns**, maintaining an individual FIFO (First-In, First-Out) tax-lot ledger to compute realized capital gains and losses on every trade. A configurable capital gains tax rate (defaulting to **30.0% flat**, reflecting 20% federal LTCG + 3.8% NIIT + California state capital gains taxes) is accounted for upon rebalance.

The codebase is engineered modularly to support future alternative selection criteria (such as buying the top 1-year performers / momentum leaders) and outputs to both machine-readable audit CSV reports and a self-contained, interactive Google Apps Script for Google Sheets.

---

## 2. Mathematical Formulation & Rebalancing Mechanics

### 2.1 Timeline & Cadence
* **Start Dates**:
  * 30-Year Horizon: December 30, 1994 (Rebalance cycles: 1995 through 2024).
  * 20-Year Horizon: December 31, 2004 (Rebalance cycles: 2005 through 2024).
  * 10-Year Horizon: December 31, 2014 (Rebalance cycles: 2015 through 2024).
* **Evaluation End Date**: December 31, 2024.
* **Initial Capital**: \$10,000 standard basis (configurable).
* **Execution & Pricing**: All equity prices, share counts, and cost bases are maintained on a split-adjusted basis normalized to December 31, 2024. Fractional shares ($S_i \in \mathbb{R}^+$) are supported to eliminate artificial cash drag.
* **Return Convention**: Pure Price Return (cash dividends excluded for both constituents and the benchmark S&P 500 `^GSPC` index, maintaining a strict apples-to-apples comparison).

### 2.2 Universe Selection & Weighting
At the close of trading on the final market day of year $t$:
1. Identify the top $N$ stocks ($N \in \{3, 5, 10\}$) in the S&P 500 by market capitalization.
2. Let $W_i$ denote the S&P 500 index weight of constituent $i \in \{1, \dots, N\}$.
3. Target portfolio weight $w_i$ is normalized to 100%:
   $$w_i = \frac{W_i}{\sum_{j=1}^N W_j}$$

### 2.3 Two-Phase Annual Rebalancing & Tax Lot Accounting

To eliminate circularity between sell orders and tax obligations, rebalancing executes in two sequential phases at each year-end $t+1$:

#### Phase 1: Portfolio Valuation & Sell Execution (Trims & Exits)
1. **Pre-Tax Portfolio Valuation**:
   Let existing position in stock $i$ be $S_{i}^{\text{held}}$ shares with year $t+1$ closing price $P_{i, t+1}$:
   $$V_{i, t+1} = S_{i}^{\text{held}} \times P_{i, t+1}$$
   $$V_{\text{total}, t+1} = \sum_{i} V_{i, t+1}$$
2. **Provisional Target Allocation**:
   $$\text{TargetDollar}_{i, \text{prov}} = V_{\text{total}, t+1} \times w_{i, t+1}$$
   $$\text{TargetShares}_{i, \text{prov}} = \frac{\text{TargetDollar}_{i, \text{prov}}}{P_{i, t+1}}$$
3. **Execution of Sells**:
   * **Full Exits**: Any stock held that is no longer in the Top $N$ is 100% liquidated ($\Delta S_i = S_{i}^{\text{held}}$).
   * **Overweight Trims**: Any held stock where $S_{i}^{\text{held}} > \text{TargetShares}_{i, \text{prov}}$ is trimmed by $\Delta S_i = S_{i}^{\text{held}} - \text{TargetShares}_{i, \text{prov}}$.
   * **Gross Sell Proceeds**:
     $$\text{GrossProceeds}_{t+1} = \sum_{i \in \text{Sells}} \Delta S_i \times P_{i, t+1}$$

#### Phase 2: FIFO Tax Lot Settlement & Net Capital Allocation
1. **FIFO Realized Gains/Losses**:
   For each sold quantity $\Delta S_i$, match against the earliest purchase lots in the FIFO queue:
   $$\text{RealizedGain}_i = (\Delta S_i \times P_{i, t+1}) - \text{CostBasis}_{\text{FIFO}}(\Delta S_i)$$
   $$\text{NetRealizedGain}_{t+1} = \sum_{i \in \text{Sells}} \text{RealizedGain}_i$$

2. **Tax Loss Carryforward & Tax Liability**:
   Net the current year's realized gain against any accumulated loss carryforward from previous years:
   $$\text{NetTaxableGain}_{t+1} = \text{NetRealizedGain}_{t+1} - \text{CapitalLossCarryforward}_{t+1}$$
   * **If $\text{NetTaxableGain}_{t+1} > 0$**:
     $$\text{TaxPaid}_{t+1} = \text{NetTaxableGain}_{t+1} \times \tau$$
     $$\text{CapitalLossCarryforward}_{t+2} = 0$$
   * **If $\text{NetTaxableGain}_{t+1} \le 0$**:
     $$\text{TaxPaid}_{t+1} = 0$$
     $$\text{CapitalLossCarryforward}_{t+2} = |\text{NetTaxableGain}_{t+1}|$$
   *(Where $\tau = 0.30$ default).*

3. **Net Reinvestment & Target Share Finalization**:
   * **In Pre-Tax Simulation**: $\text{TaxPaid}_{t+1} = 0$.
   * **In After-Tax Simulation**: $\text{NetInvestableEquity}_{t+1} = V_{\text{total}, t+1} - \text{TaxPaid}_{t+1}$.
   * Final target dollar for each stock $i$:
     $$\text{TargetDollar}_{i, \text{final}} = \text{NetInvestableEquity}_{t+1} \times w_{i, t+1}$$
     $$\text{TargetShares}_{i, \text{final}} = \frac{\text{TargetDollar}_{i, \text{final}}}{P_{i, t+1}}$$
   * Sells are executed, and available cash buys the required shares for underweight and new entrant stocks. New lots are added to the FIFO ledger: `(ticker, shares_bought, price, year)`.

---

## 3. Metrics & Performance Indicators

To provide complete analytical rigor, the following metrics are tracked across each period ($10\text{y}, 20\text{y}, 30\text{y}$) for each strategy and benchmark:

1. **Cumulative Return**:
   $$\text{Return}_{\text{cum}} = \frac{V_{\text{final}} - V_{\text{initial}}}{V_{\text{initial}}}$$
2. **Compound Annual Growth Rate (CAGR)**:
   $$\text{CAGR} = \left(\frac{V_{\text{final}}}{V_{\text{initial}}}\right)^{\frac{1}{Y}} - 1$$
3. **Annual Portfolio Turnover**:
   $$\text{Turnover}_{t} = \frac{\sum_{i \in \text{Sells}} \text{Proceeds}_{i, t}}{V_{\text{total}, t}}$$
4. **Tax Drag**:
   $$\text{Tax Drag} = \text{CAGR}_{\text{Pre-Tax}} - \text{CAGR}_{\text{After-Tax}}$$
5. **Terminal Wealth & Unrealized Tax Settlement**:
   * **Pre-Liquidation Wealth**: Equity at terminal year-end $t_{\text{end}}$.
   * **Embedded Unrealized Capital Gains**: $\sum (V_{i, t_{\text{end}}} - \text{CostBasis}_i)$.
   * **Post-Liquidation Wealth**: Terminal equity minus taxes due if 100% liquidated at $t_{\text{end}}$.
   * **Post-Liquidation CAGR**: Effective net annualized return factoring in terminal tax.
6. **Maximum Drawdown**:
   $$\text{MaxDD} = \max_{t} \left( \frac{\max_{s \le t} V_s - V_t}{\max_{s \le t} V_s} \right)$$
7. **Alpha vs. S&P 500**:
   $$\alpha = \text{CAGR}_{\text{Strategy}} - \text{CAGR}_{\text{S\&P 500}}$$

---

## 4. Architecture & Modular System Design

```
sp500_strategy/
├── data/
│   ├── sp500_constituents.json     # Point-in-time year-end constituent rankings, market cap weights, returns
│   └── sp500_prices.json           # Split-adjusted close prices for constituents and ^GSPC
├── engine/
│   ├── __init__.py
│   ├── models.py                   # Data schemas (ConstituentSnapshot, HoldingTarget, TradeOrder)
│   ├── selector.py                 # Abstract BaseSelector, MarketCapSelector, PerformanceSelector
│   ├── tax_lots.py                 # TaxLot and FIFOTaxLotManager (with loss carryforward & split handling)
│   ├── metrics.py                  # Standard quantitative metric calculators (CAGR, MaxDD, Turnover)
│   ├── backtest.py                 # PortfolioSimulator (Two-Phase Rebalance Engine)
│   └── exporters.py                # CSV generation and Google Apps Script builder
├── outputs/
│   ├── summary_metrics.csv         # Comprehensive comparison across 10y, 20y, 30y for N=3, 5, 10 vs SPX
│   ├── annual_breakdown.csv        # Year-by-year valuations, cash flows, taxes, and benchmark returns
│   └── trade_log.csv               # Individual trade execution audit trail
├── scripts/
│   └── google_apps_script.js       # Self-contained Apps Script for interactive Google Sheet
├── tests/
│   ├── test_tax_lots.py            # Unit tests verifying FIFO matching & loss carryforwards
│   └── test_rebalancing.py         # Unit tests verifying phase 1/2 cash flow & weight normalization
├── run_backtest.py                 # Primary CLI runner with arguments (--strategy, --n, --tax-rate)
└── README.md                       # Documentation, usage guide, and extensibility instructions
```

### 4.1 Historical Data Pipeline & M&A Handling
* **Constituents**: Historical point-in-time rankings from S&P Dow Jones Indices year-end composition reports (1994–2024).
* **Corporate Actions**:
  * Stock splits (e.g. AAPL, NVDA, GOOGL, MSFT) are normalized to terminal split-adjusted prices.
  * M&A events (e.g. Mobil merging into Exxon in 1999) are mapped to continuous surviving entities and cost bases so portfolio value is preserved accurately without survivorship bias.

---

## 5. Google Sheets Integration Architecture

To ensure mathematical consistency with compounding reinvestment while giving the user full interactivity:

1. **Pre-Calculated Scenario Suite & Formula Structure**:
   * The Google Apps Script embeds the simulation datasets across tax tiers:
     * **0.0%** (Pre-Tax / Tax-Advantaged IRA/401k)
     * **15.0%** (Federal Long-Term Capital Gains lower bracket)
     * **20.0%** (Standard Federal Long-Term Capital Gains)
     * **30.0%** (Baseline: 20% Fed + 3.8% NIIT + California State)
     * **37.0%** (High-income bracket)
   * The `Executive Summary` tab features an interactive dropdown/cell for `Tax Rate` (`B2`).
   * Summary metrics and annual breakdown tabs use dynamic lookup formulas (`INDEX/MATCH` / `XLOOKUP`) pointing to the selected scenario, enabling instantaneous switching without broken compounding formulas.
2. **Interactive Apps Script Recalculate Function**:
   * An embedded Apps Script function `RECALCULATE_STRATEGY(customTaxRate)` allows the user to input any arbitrary tax rate (e.g. 27.5%) to run an on-demand recomputation of the entire sheet.

---

## 6. Verification & Validation Plan

1. **Automated Unit Tests**:
   * `pytest tests/test_tax_lots.py`: Verifies FIFO lot depletion, partial sales, capital loss carryforward netting, and zero-tax equivalence.
   * `pytest tests/test_rebalancing.py`: Verifies two-phase cash neutrality, 100% weight normalization, and fractional share accuracy.
2. **Benchmark Reconciliation**:
   * S&P 500 index levels and annual returns verified against official historical records of `^GSPC`.
3. **Google Apps Script Verification**:
   * Deploy and validate script syntax and structure for Google Sheets compatibility.
