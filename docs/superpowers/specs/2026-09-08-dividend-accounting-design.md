# Design Document: Dividend Accounting & Dynamic After-Tax Benchmarking

**Date**: 2026-09-08  
**Status**: Approved (Incorporating Reviewer Improvements)  
**Author**: Antigravity Agent & User  
**Target Repository**: `/Users/chriscatignani/Developer/sp500_strategy`  
**Target Google Sheet**: [Top N vs S&P500](https://docs.google.com/spreadsheets/d/1v8Ig7ZeresaJNX35W2VCrBmarWgYgLxKQD9wPg4O0Ao/edit?usp=sharing)  

---

## 1. Executive Summary

This design integrates cash dividend flows and dynamic after-tax benchmarking into the S&P 500 Top N ($N \in \{3, 5, 10\}$) quantitative backtesting engine and interactive Google Sheets dashboard.

Previously, the backtesting engine evaluated strategies on a split-adjusted pure price-return basis against the S&P 500 Price Return index (`^GSPC`), excluding cash dividends for both. This upgrade:
1. Incorporates historical split-adjusted cash dividends per share (`DPS`) across 1994–2024.
2. Models pre-rebalance cash pooling and dual tax settlement (segregating capital loss carryforwards from dividend income).
3. Upgrades benchmark evaluation to a dynamic after-tax S&P 500 benchmark utilizing both S&P 500 Price Return (`^GSPC`) and S&P 500 Total Return (`^SP500TR`), adapting dynamically to user-selected tax rates ($\tau \in \{0.0\%, 15.0\%, 20.0\%, 30.0\%, 37.0\%\}$).
4. Expands reports, CSV exports, and the Google Sheets dashboard with dividend metrics, updated formulas, and a prominent timing methodology callout.

---

## 2. Timing Convention & Methodological Callout

### 2.1 Discrete Annual Rebalancing Timing
* **Real-World Reality**: In live trading, corporate dividends are declared and distributed periodically (typically quarterly) and reinvested at prevailing intra-year market prices.
* **Model Convention**: The engine operates on an annual discrete time-step (December 31 year-ends from 1994 to 2024). Cash dividends earned throughout calendar year $t$ are calculated based on shares held during year $t$ and split-adjusted annual cash dividends per share ($\text{DPS}_t$). These dividends are received and pooled into portfolio cash at year-end $t$ immediately prior to rebalancing.
* **Documentation & UI Callouts**:
  * Documented in `README.md` and `AGENTS.md`.
  * Displayed as an informational **Methodology Callout Card** on the Google Sheet Executive Summary tab across Rows 31–36.

---

## 3. Mathematical Formulation & Rebalancing Flow

### 3.1 Pre-Rebalance Dividend Receipt & Cash Pooling
At the close of trading on year-end $t$, before any rebalancing sells or buys occur:
1. Identify all positions held from the previous period: $\{S_i^{\text{held}}\}$.
2. For each held constituent $i$, query the annual split-adjusted cash dividend per share $\text{DPS}_{i, t}$ from `data/sp500_dividends.json` (defaults strictly to $0.0$ if no dividend was paid).
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
To prevent race conditions and ensure cash non-negativity without circularity, the settlement sequence is explicitly decoupled:

1. **Pre-Loop Dividend Tax Settlement**:
   Compute dividend tax once:
   $$\text{Tax}_{\text{div}, t} = \text{DivIncome}_t \times \tau$$
   Deduct from cash immediately:
   $$\text{Cash}_t \leftarrow \text{Cash}_t - \text{Tax}_{\text{div}, t}$$
   Initialize cumulative tax tracker:
   $$\text{total\_tax\_paid} \leftarrow \text{Tax}_{\text{div}, t}$$
   *(Note: Capital loss carryforwards $L_t$ are strictly preserved to offset capital gains; they never offset dividend income).*

2. **Iterative Capital Gains Settlement & Secondary Trims**:
   For up to 20 convergence iterations:
   a. Settle incremental capital gains tax via `FIFOTaxLotManager`:
      $$(\text{tax\_cap\_step}, \text{net\_taxable}, \text{loss\_cf}) \leftarrow \text{tax\_manager.settle\_annual\_taxes}(\tau, t)$$
   b. Accumulate capital gains tax:
      $$\text{total\_tax\_paid} \leftarrow \text{total\_tax\_paid} + \text{tax\_cap\_step}$$
      $$\text{Cash}_t \leftarrow \text{Cash}_t - \text{tax\_cap\_step}$$
   c. If $\text{tax\_cap\_step} \le 10^{-7}$ on this step, convergence is achieved; break.
   d. Compute net investable equity accounting for all taxes paid:
      $$V_{\text{net}, t} = V_{\text{pretax}, t} - \text{total\_tax\_paid}$$
   e. Compute updated target shares:
      $$\text{TargetShares}_{i, \text{final}} = \frac{V_{\text{net}, t} \times w_i}{P_{i, t}}$$
   f. If any held position exceeds $\text{TargetShares}_{i, \text{final}} + 10^{-4}$, sell the excess, add proceeds to $\text{Cash}_t$, record realized capital gain/loss in `tax_manager`, and continue iteration. If no positions required trimming, break.

3. **Phase 2 Buys**:
   Target shares are finalized based on $V_{\text{net}, t}$:
   $$\text{TargetShares}_{i, \text{final}} = \frac{V_{\text{net}, t} \times w_i}{P_{i, t}}$$
   For any constituent where held shares are less than target shares, buy required shares clamped to available cash:
   $$\text{Cost} = \min((\text{TargetShares}_{i, \text{final}} - S_i) \times P_{i, t}, \max(0.0, \text{Cash}_t))$$
   guaranteeing that $\text{Cash}_t \ge 0.0$ holds unconditionally.

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
   $$y_t = \max(0.0, R_{\text{TR}, t} - R_{\text{PR}, t})$$
2. **Annual After-Tax Compounding**:
   $$R_{\text{SPX, After-Tax}, t} = R_{\text{PR}, t} + y_t \times (1 - \tau)$$
   Starting from $V_{\text{SPX}, 0} = \text{Initial Capital}$:
   $$V_{\text{SPX}, t} = V_{\text{SPX}, t-1} \times (1 + R_{\text{SPX, After-Tax}, t})$$
   Reinvested net dividends added to cost basis:
   $$\text{Basis}_{\text{SPX}, t} = \text{Basis}_{\text{SPX}, t-1} + [V_{\text{SPX}, t-1} \times y_t \times (1 - \tau)]$$
   Annual dividend tax paid:
   $$\text{Tax}_{\text{div, SPX}, t} = V_{\text{SPX}, t-1} \times y_t \times \tau$$
3. **Terminal Liquidation**:
   At horizon end year $Y$:
   $$\text{UnrealizedGain}_{\text{SPX}} = \max(0.0, V_{\text{SPX}, Y} - \text{Basis}_{\text{SPX}, Y})$$
   $$\text{LiqTax}_{\text{SPX}} = \text{UnrealizedGain}_{\text{SPX}} \times \tau$$
   $$W_{\text{post-liq}, \text{SPX}} = V_{\text{SPX}, Y} - \text{LiqTax}_{\text{SPX}}$$
   $$\text{CAGR}_{\text{post-liq}, \text{SPX}} = \left(\frac{W_{\text{post-liq}, \text{SPX}}}{V_{\text{SPX}, 0}}\right)^{1/Y} - 1$$
   $$\text{TotalTaxes}_{\text{SPX}} = \sum_{t=1}^Y \text{Tax}_{\text{div, SPX}, t} + \text{LiqTax}_{\text{SPX}}$$
   $$\text{TaxDrag}_{\text{SPX}} = \text{CAGR}_{\text{SP500TR}} - \text{CAGR}_{\text{post-liq}, \text{SPX}}$$
4. **After-Tax Alpha**:
   $$\alpha = \text{Strategy Post-Liquidation CAGR} - \text{Benchmark Post-Liquidation CAGR}$$

### 4.4 S&P 500 Benchmark Row Schema in Scenario Data & Summary Reports
In all reporting tables and `Scenario Data`:
* `Strategy`: `"S&P 500"`
* `PreTaxCAGR`: SP500TR CAGR ($R_{\text{TR}}$)
* `AfterTaxCAGR`: Benchmark annual after-tax CAGR (after annual dividend taxes)
* `PostLiqCAGR`: Benchmark post-liquidation CAGR ($R_{\text{post-liq}, \text{SPX}}$)
* `CumReturn`: Benchmark cumulative return
* `FinalEquity`: Benchmark post-liquidation wealth ($W_{\text{post-liq}, \text{SPX}}$)
* `TotalDividends`: Cumulative gross dollar dividends earned by the benchmark investment
* `MaxDrawdown`: Benchmark maximum drawdown (using after-tax valuation series in after-tax runs)
* `TotalTaxes`: Cumulative annual dividend taxes + terminal liquidation tax paid
* `TaxDrag`: SP500TR CAGR minus Benchmark Post-Liquidation CAGR
* `Alpha`: Exactly `0.00%`

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
* `__init__(self, constituents_path=None, prices_path=None, dividends_path=None)`: Supports test fixture injection.
* `get_dividend(ticker: str, year: int) -> float`: Returns split-adjusted cash dividend per share (returns `0.0` if ticker paid no dividends or has no entry).
* `get_spx_tr_level(year: int) -> float`: Returns `^SP500TR` level for year.
* `get_spx_dividend_yield(year: int) -> float`: Returns $\max(0.0, R_{\text{TR}, \text{year}} - R_{\text{PR}, \text{year}})$.

### 5.4 Dataset Generation Script: `scripts/generate_datasets.py`
Update dataset builder to parse and output `^SP500TR` in `sp500_prices.json` and generate `sp500_dividends.json` to maintain full reproducibility.

---

## 6. Component Architecture & Code Modifications

### 6.1 `engine/models.py`
* [`AnnualLedgerEntry`](file:///Users/chriscatignani/Developer/sp500_strategy/engine/models.py#L52):
  * `dividend_income: float = 0.0`
  * `dividend_tax_paid: float = 0.0`
  * `capital_gains_tax_paid: float = 0.0`
  * `tax_paid: float = 0.0` (Sum of capital gains tax and dividend tax)
  * `spx_return: float = 0.0` (Reflects active benchmark return: $R_{\text{TR}}$ for pre-tax, $R_{\text{SPX, After-Tax}}$ for after-tax)
* [`StrategyResult`](file:///Users/chriscatignani/Developer/sp500_strategy/engine/models.py#L70):
  * `total_dividends_received: float = 0.0`
  * `total_dividend_taxes_paid: float = 0.0`

### 6.2 `engine/backtest.py`
* Pre-rebalance cash pooling of dividends.
* Decoupled dual tax settlement in Phase 2 ensuring cash non-negativity and correct target allocation buys.
* Dynamic benchmark return recording in annual ledger entries.

### 6.3 `engine/metrics.py`
Pure numeric functions for benchmark metrics without I/O dependencies:
```python
def calculate_benchmark_annual_series(
    pr_levels: Sequence[float],
    tr_levels: Sequence[float],
    tax_rate: float = 0.30,
    initial_capital: float = 10000.0,
    is_after_tax: bool = True,
) -> Dict[str, Any]:
    """Compute annual returns, valuation, basis, dividend taxes, and liquidation metrics."""
    ...
```

### 6.4 `engine/exporters.py` & `scripts/google_apps_script.js`

#### Executive Summary Tab Grid (12 Columns: A through L)
* **Header Banner**: `A1:L1`
* **Controls & Instructions**: `A2:B2` (Tax Rate selector), `C2:L2` (Instructions)
* **KPI Scorecards (Rows 4–6)**: 5 cards balanced across Cols A–L:
  * Card 1: Top 5 (30y) Final Wealth: `A4:B6`, formula `=G19`
  * Card 2: S&P 500 (30y) Wealth: `C4:D6`, formula `=G22`
  * Card 3: Top 5 (30y) Annual Return: `E4:F6`, formula `=E19`
  * Card 4: 30-Year Excess Return (Alpha): `G4:I6`, formula `=L19`
  * Card 5: 30-Year Tax Drag: `J4:L6`, formula `=K19`
* **Table Banner**: `A8:L8`
* **Comparison Table (Row 9 Header, Rows 10–22 Data)**:
  * Col 1 (A): Horizon (`10y`, `20y`, `30y`)
  * Col 2 (B): Strategy (`Top 3`, `Top 5`, `Top 10`, `S&P 500`)
  * Col 3 (C): Annual Return (Pre-Tax)
  * Col 4 (D): Annual Return (After-Tax)
  * Col 5 (E): Annual Return (Post-Liq)
  * Col 6 (F): Total Return (Cumulative)
  * Col 7 (G): Ending Wealth ($10k Start)
  * Col 8 (H): Total Dividends Received ($)
  * Col 9 (I): Max Drawdown (Worst Drop)
  * Col 10 (J): Total Taxes Paid ($)
  * Col 11 (K): Annual Tax Drag
  * Col 12 (L): Excess vs S&P 500 (Alpha)
* **Methodology Callout Card (Rows 31–36, Cols A–L)**:
  * Title: "METHODOLOGY NOTE — DIVIDEND TIMING & BENCHMARK CONVENTIONS"
  * Text: Explains annual discrete cash-flow pooling at year-end vs live quarterly distribution, along with dynamic after-tax benchmark compounding.

#### Annual Breakdown Tabs (15 Columns)
Headers: `Year, Start Value, Gross Return, Dividends Received ($), Ending Value (Pre-Tax), Realized Capital Gain, Net Taxable Gain, Capital Gains Tax ($), Dividend Tax ($), Total Tax Paid ($), Loss Carryforward, Ending Value (After-Tax), Cash Reserve, S&P 500 Return, Annual Turnover`.

#### CSV Exporters
* `summary_metrics.csv`: Add `total_dividends_received` column; update `spx_benchmarks` mapping to accept `(horizon, tax_rate)` pairs or a benchmark result object.
* `annual_breakdown.csv`: Add `dividend_income`, `dividend_tax_paid`, and `capital_gains_tax_paid`.

### 6.5 Documentation
* [`README.md`](file:///Users/chriscatignani/Developer/sp500_strategy/README.md) & [`AGENTS.md`](file:///Users/chriscatignani/Developer/sp500_strategy/AGENTS.md) updated with full dividend mechanics, dynamic benchmark methodology, and timing notes.

---

## 7. Verification & Testing Plan

1. **Unit Tests**:
   * `test_dividend_data_loader`: Verify `sp500_dividends.json` loads cleanly and returns accurate DPS or `0.0` defaults.
   * `test_dividend_cash_flow`: Verify holdings receive exact dividends, cash pools correctly, and pre-tax valuation reflects dividend income.
   * `test_secondary_trim_dual_tax`: Verify `Tax_div` is deducted once, secondary trims settle capital gains tax, and `cash >= 0.0` holds strictly without circularity.
   * `test_dynamic_benchmark_math`: Verify hand-calculated benchmark values for known $R_{\text{PR}}$, $R_{\text{TR}}$, and $\tau$ across $0\%$, $15\%$, $20\%$, $30\%$, and $37\%$.
2. **Regression & Integration Tests**:
   * Run full test suite (`python3 -m unittest discover tests`).
   * Run CLI runner across all horizons: `python3 run_backtest.py`.
   * Verify all generated CSVs and `scripts/google_apps_script.js` syntax and structure.
