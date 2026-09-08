# Design Document: S&P 500 Top N Strategy vs. S&P 500 Benchmark

**Date**: 2026-09-08  
**Status**: Approved  
**Author**: Antigravity Agent & User  
**Target Repository**: `/Users/chriscatignani/.gemini/antigravity/scratch/sp500_strategy`  
**Target Google Sheet**: [Top N vs S&P500](https://docs.google.com/spreadsheets/d/1v8Ig7ZeresaJNX35W2VCrBmarWgYgLxKQD9wPg4O0Ao/edit?usp=sharing)

---

## 1. Executive Summary

This project simulates and evaluates an active equity investment strategy against the benchmark S&P 500 price return index (`^GSPC`) across 10-year (2014–2024), 20-year (2004–2024), and 30-year (1994–2024) periods.

The strategy allocates capital at each year-end to the largest $N$ companies ($N \in \{3, 5, 10\}$) in the S&P 500, weighted proportionally to their relative market capitalizations. Holdings are maintained for exactly one full calendar year. At each subsequent year-end, the portfolio is rebalanced to the new Top $N$ holdings and weights. 

The backtest tracks both **Pre-Tax Gross Returns** and **After-Tax Net Returns**, maintaining a FIFO (First-In, First-Out) tax-lot ledger to compute realized capital gains and losses on every trade. A configurable capital gains tax rate (defaulting to **30.0% flat**, reflecting 20% federal LTCG + 3.8% NIIT + California state capital gains taxes) is deducted from reinvestable cash upon rebalance.

The codebase is engineered modularly to support future alternative selection criteria (e.g. top 1-year performers / momentum leaders) and outputs to both audit-grade CSV reports and a dynamic, interactive Google Apps Script for Google Sheets.

---

## 2. Core Strategy Rules & Mathematical Formulation

### 2.1 Timeline & Cadence
* **Start Dates**:
  * 30-Year Horizon: December 30, 1994 (Rebalance cycles: 1995 through 2024).
  * 20-Year Horizon: December 31, 2004 (Rebalance cycles: 2005 through 2024).
  * 10-Year Horizon: December 31, 2014 (Rebalance cycles: 2015 through 2024).
* **Evaluation End Date**: December 31, 2024.
* **Initial Capital**: \$10,000 standard basis (configurable).

### 2.2 Universe Selection & Weighting
At the close of trading on the final market day of year $t$:
1. Identify the top $N$ stocks ($N \in \{3, 5, 10\}$) in the S&P 500 by market capitalization.
2. Let $W_i$ denote the S&P 500 index weight of constituent $i \in \{1, \dots, N\}$.
3. Target portfolio weight $w_i$ is normalized to 100%:
   $$w_i = \frac{W_i}{\sum_{j=1}^N W_j}$$
4. Target dollar allocation for stock $i$:
   $$\text{TargetDollar}_i = \text{InvestableCapital} \times w_i$$
5. Target shares for stock $i$ at split-adjusted closing price $P_{i, t}$:
   $$\text{TargetShares}_i = \frac{\text{TargetDollar}_i}{P_{i, t}}$$

### 2.3 Annual Rebalancing & Tax Lot Accounting (FIFO)
At year-end $t+1$, let existing position in stock $i$ be $S_{i}^{\text{held}}$ shares with current price $P_{i, t+1}$:
* **Current Position Value**:
  $$V_{i, t+1} = S_{i}^{\text{held}} \times P_{i, t+1}$$
* **Total Portfolio Pre-Tax Value**:
  $$V_{\text{total}, t+1} = \sum_{i} V_{i, t+1}$$

#### Sell Orders & Realized Capital Gain/Loss:
* If stock $i$ is no longer in the Top $N$, or if $V_{i, t+1} > \text{TargetDollar}_i$:
  * Shares sold: $\Delta S_i = S_{i}^{\text{held}} - \text{TargetShares}_i$.
  * Sale proceeds: $\text{Proceeds}_i = \Delta S_i \times P_{i, t+1}$.
  * Cost basis for $\Delta S_i$ is matched against purchase tax lots via FIFO:
    $$\text{Gain}_i = \text{Proceeds}_i - \text{CostBasis}(\Delta S_i)$$
* **Net Realized Capital Gain**:
  $$\text{NetRealizedGain}_{t+1} = \sum_{i \in \text{Sales}} \text{Gain}_i$$

#### Tax Liability & Reinvestment:
* Tax rate $\tau = 0.30$ (configurable).
* If $\text{NetRealizedGain}_{t+1} > 0$:
  $$\text{TaxPaid}_{t+1} = \text{NetRealizedGain}_{t+1} \times \tau$$
  $$\text{CapitalLossCarryforward}_{t+2} = 0$$
* If $\text{NetRealizedGain}_{t+1} \le 0$:
  $$\text{TaxPaid}_{t+1} = 0$$
  $$\text{CapitalLossCarryforward}_{t+2} = |\text{NetRealizedGain}_{t+1}|$$
* **Reinvestable Capital (After-Tax)**:
  $$\text{InvestableCapital}_{t+1} = V_{\text{total}, t+1} - \text{TaxPaid}_{t+1}$$
* **Reinvestable Capital (Pre-Tax Baseline)**:
  $$\text{InvestableCapital}_{t+1} = V_{\text{total}, t+1}$$

---

## 3. Architecture & Modular System Design

The architecture isolates data, selection logic, tax tracking, simulation, and output generation into independent modules:

```
sp500_strategy/
├── data/
│   ├── sp500_constituents.json     # Year-end constituent rankings, market cap weights, 1y returns (1994-2024)
│   └── sp500_prices.json           # Split-adjusted year-end close prices for constituents and ^GSPC
├── engine/
│   ├── __init__.py
│   ├── selector.py                 # Abstract Base Class BaseSelector & Concrete Implementations:
│   │                               #   • MarketCapSelector (Largest N by market cap)
│   │                               #   • PerformanceSelector (Top N by 1-year trailing return)
│   ├── tax_lots.py                 # TaxLot and FIFOTaxLotManager classes
│   └── backtest.py                 # PortfolioSimulator (orchestrates pre-tax and after-tax runs)
├── outputs/
│   ├── summary_metrics.csv         # Comparative metrics table (10y, 20y, 30y for N=3, 5, 10, SPX)
│   ├── annual_breakdown.csv        # Detailed annual ledger (values, gains, taxes, returns)
│   └── trade_log.csv               # Granular trade execution logs
├── scripts/
│   └── google_apps_script.js       # Complete script to generate styled interactive Google Sheet
├── run_backtest.py                 # CLI interface with argparse
└── README.md                       # Comprehensive guide, execution commands, and extensibility docs
```

### 3.1 Selector Interface (`engine/selector.py`)
```python
class BaseSelector(ABC):
    @abstractmethod
    def select(self, year: int, n: int, universe_data: dict) -> List[HoldingTarget]:
        """
        Given the historical year-end universe snapshot, returns the Top N
        constituents with their target portfolio weights (normalized to 1.0).
        """
        pass
```
* `MarketCapSelector`: Sorts constituents descending by `market_cap_weight` and normalizes weights.
* `PerformanceSelector`: Sorts constituents descending by `trailing_1y_return` for momentum strategy analysis.

### 3.2 Tax Lot Manager (`engine/tax_lots.py`)
Tracks individual buy lots: `(ticker, shares, purchase_price, year_purchased)`.
When selling, exhausts earliest lots first (FIFO), records holding period, realized gain, and maintains residual partial lots.

---

## 4. Google Sheets Model & Interactive Structure

The script `google_apps_script.js` targets the provided sheet URL:
`https://docs.google.com/spreadsheets/d/1v8Ig7ZeresaJNX35W2VCrBmarWgYgLxKQD9wPg4O0Ao/edit`

### 4.1 Tabs Created
1. **`Executive Summary`**:
   * Cells `B2:B3`: Interactive Inputs:
     * `Tax Rate`: `30.0%`
     * `Initial Capital`: `$10,000`
   * Key Metric Comparison Table:
     * Top 3 Pre-Tax, Top 3 After-Tax
     * Top 5 Pre-Tax, Top 5 After-Tax
     * Top 10 Pre-Tax, Top 10 After-Tax
     * S&P 500 Benchmark
     * Columns: 10-Year Return / CAGR, 20-Year Return / CAGR, 30-Year Return / CAGR, Total Taxes Paid, Max Drawdown, Tax Drag.
2. **`Top 3 Strategy`**:
   * Complete year-by-year cash flow and holdings table (1995–2024).
   * Column for Tax Liability dynamically references `=F{row}*'Executive Summary'!$B$2`.
3. **`Top 5 Strategy`**:
   * Year-by-year cash flow, rebalance trades, and dynamic tax calculation.
4. **`Top 10 Strategy`**:
   * Year-by-year cash flow, rebalance trades, and dynamic tax calculation.
5. **`S&P 500 Benchmark`**:
   * Annual level, annual price return, and cumulative \$10,000 growth.
6. **`Historical Holdings & Trades`**:
   * Audit log of all constituent allocations and historical trades.

---

## 5. Verification & Test Plan

1. **Unit Tests (`test_tax_lots.py`)**:
   * Verify FIFO cost basis matching on partial sales.
   * Verify capital loss carryforward offsets next year's gains.
   * Verify 0% tax rate matches Pre-Tax simulation exactly.
2. **Rebalancing Logic Verification**:
   * Verify target weights always sum to $1.0000 \pm 10^{-6}$.
   * Verify cash proceeds from sells accurately fund new buys.
3. **Benchmark Reconciliation**:
   * Verify S&P 500 annual returns match official S&P Dow Jones historical index levels.
4. **Google Apps Script Validation**:
   * Syntax and structure validation for seamless execution via Google Apps Script editor.
