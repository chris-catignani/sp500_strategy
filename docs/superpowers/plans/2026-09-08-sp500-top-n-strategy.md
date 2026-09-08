# S&P 500 Top N Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular, reusable quantitative backtesting engine and interactive Google Sheets integration to analyze buying the largest $N \in \{3, 5, 10\}$ S&P 500 holdings held for 1 year, tracking FIFO capital gains tax lots, pre-tax vs. after-tax compounding (default 30% tax rate), and benchmarking against the S&P 500 across 10y, 20y, and 30y horizons.

**Architecture:** A decoupled Python engine comprising data schemas (`models.py`), a pluggable selection layer (`selector.py` supporting market-cap and momentum rules), a FIFO tax-lot manager with loss carryforwards (`tax_lots.py`), a two-phase rebalancing simulation engine (`backtest.py`), performance analytics (`metrics.py`), and exporters for CSV reports and an interactive Google Apps Script for Google Sheets (`exporters.py`).

**Tech Stack:** Python 3 (standard library: `dataclasses`, `typing`, `json`, `math`, `csv`, `argparse`), `unittest`/`pytest`, Google Apps Script (JavaScript).

## Global Constraints
- Target repository: `/Users/chriscatignani/Developer/sp500_strategy`
- Target Google Sheet: https://docs.google.com/spreadsheets/d/1v8Ig7ZeresaJNX35W2VCrBmarWgYgLxKQD9wPg4O0Ao/edit?usp=sharing
- Time Horizons: 10-Year (2014–2024), 20-Year (2004–2024), 30-Year (1994–2024)
- Portfolios: Top $N \in \{3, 5, 10\}$ weighted proportionally to relative market cap
- Benchmark: S&P 500 Price Return (`^GSPC`), cash dividends excluded for both
- Tax Model: FIFO lot depletion, loss carryforwards, default 30.0% rate, pre-tax & after-tax tracking
- Split & Corporate Action Standard: Split-adjusted prices normalized to 2024-12-31, continuous M&A mapping

---

### Task 1: Data Models & Type Schemas

**Files:**
- Create: `engine/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `ConstituentSnapshot`, `HoldingTarget`, `TaxLot`, `TradeOrder`, `AnnualLedgerEntry`, `StrategyResult`

- [ ] **Step 1: Write the test for models**
Create `tests/test_models.py`:
```python
import unittest
from engine.models import ConstituentSnapshot, HoldingTarget, TaxLot, TradeOrder

class TestModels(unittest.TestCase):
    def test_holding_target(self):
        target = HoldingTarget(ticker="AAPL", target_weight=0.5, target_dollar=5000.0, target_shares=25.0)
        self.assertEqual(target.ticker, "AAPL")
        self.assertEqual(target.target_weight, 0.5)

    def test_tax_lot(self):
        lot = TaxLot(lot_id="lot_1", ticker="MSFT", shares=10.0, purchase_price=100.0, purchase_year=2020)
        self.assertEqual(lot.shares, 10.0)
        self.assertEqual(lot.cost_basis(), 1000.0)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests/test_models.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine'`

- [ ] **Step 3: Implement data models**
Create `engine/__init__.py` and `engine/models.py` with typed dataclasses:
`ConstituentSnapshot`, `HoldingTarget`, `TaxLot`, `TradeOrder`, `AnnualLedgerEntry`, `StrategyResult`.

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests/test_models.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add engine/ tests/test_models.py
git commit -m "feat(engine): add core data models and schemas"
```

---

### Task 2: FIFO Tax-Lot Ledger & Loss Carryforward

**Files:**
- Create: `engine/tax_lots.py`
- Test: `tests/test_tax_lots.py`

**Interfaces:**
- Consumes: `TaxLot`, `TradeOrder` from `engine.models`
- Produces: `FIFOTaxLotManager` with methods `add_lot()`, `sell_shares()`, `calculate_taxes_and_net()`, `unrealized_gains()`

- [ ] **Step 1: Write unit tests for FIFO tax-lot manager**
Create `tests/test_tax_lots.py` covering:
1. Adding lots and tracking balance.
2. FIFO depletion on partial sales.
3. Calculating realized gains/losses across multiple lots.
4. Netting against capital loss carryforward (correct formula from spec review).
5. Carrying forward remaining net losses when losses exceed gains.
6. Unrealized gains calculation for terminal liquidation.

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests/test_tax_lots.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.tax_lots'`

- [ ] **Step 3: Implement FIFOTaxLotManager**
Create `engine/tax_lots.py`:
- `add_lot(ticker, shares, price, year)`
- `sell_shares(ticker, shares_to_sell, current_price, current_year) -> (realized_gain, list_of_closed_lots)`
- `settle_annual_taxes(tax_rate, year) -> (tax_paid, loss_carryforward_next)`
- `get_unrealized_gain(current_prices: dict) -> float`

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests/test_tax_lots.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add engine/tax_lots.py tests/test_tax_lots.py
git commit -m "feat(tax): implement FIFO tax lot manager with capital loss carryforward"
```

---

### Task 3: Pluggable Selector Interface (Market Cap & Momentum)

**Files:**
- Create: `engine/selector.py`
- Test: `tests/test_selector.py`

**Interfaces:**
- Consumes: `ConstituentSnapshot`, `HoldingTarget`
- Produces: `BaseSelector`, `MarketCapSelector`, `PerformanceSelector`

- [ ] **Step 1: Write unit tests for selectors**
Create `tests/test_selector.py`:
- Test `MarketCapSelector` selects top $N$ sorted descending by `market_cap_weight` and normalizes weights to sum to 1.0.
- Test `PerformanceSelector` selects top $N$ sorted descending by `trailing_1y_return` and normalizes weights.

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests/test_selector.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.selector'`

- [ ] **Step 3: Implement BaseSelector, MarketCapSelector, PerformanceSelector**
Create `engine/selector.py` implementing normalized weight computation:
$$w_i = \frac{W_i}{\sum_{j=1}^N W_j}$$

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests/test_selector.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add engine/selector.py tests/test_selector.py
git commit -m "feat(selector): implement pluggable MarketCapSelector and PerformanceSelector"
```

---

### Task 4: Historical S&P 500 Constituent & Price Datasets (1994–2024)

**Files:**
- Create: `data/sp500_constituents.json`
- Create: `data/sp500_prices.json`
- Create: `engine/data_loader.py`
- Test: `tests/test_data_loader.py`

**Interfaces:**
- Produces: `DataLoader.load_universe(year)`, `DataLoader.get_price(ticker, year)`, `DataLoader.get_spx_level(year)`

- [ ] **Step 1: Write test for data loader**
Create `tests/test_data_loader.py`:
- Test loading annual data for 1994 through 2024.
- Test S&P 500 benchmark levels match historical benchmarks (e.g. 1994: 459.27, 2024: 5881.63).
- Test constituents for benchmark years (1995 GE/AT&T/XOM; 2000 GE/XOM/PFE/CSCO; 2020 AAPL/MSFT/AMZN; 2024 AAPL/NVDA/MSFT).

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests/test_data_loader.py`
Expected: FAIL

- [ ] **Step 3: Construct datasets and data loader**
Create `data/sp500_constituents.json`, `data/sp500_prices.json`, and `engine/data_loader.py` covering all 30 years (1994–2024) with split-adjusted prices and index weights.

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests/test_data_loader.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add data/ engine/data_loader.py tests/test_data_loader.py
git commit -m "feat(data): add historical 30-year S&P 500 constituents, prices, and loader"
```

---

### Task 5: Two-Phase Portfolio Simulation Engine

**Files:**
- Create: `engine/backtest.py`
- Test: `tests/test_rebalancing.py`

**Interfaces:**
- Consumes: `DataLoader`, `BaseSelector`, `FIFOTaxLotManager`
- Produces: `PortfolioSimulator.run_simulation(start_year, end_year, n, selector, is_after_tax, tax_rate)`

- [ ] **Step 1: Write tests for two-phase rebalancing**
Create `tests/test_rebalancing.py`:
- Verify Phase 1 (trims/exits) and Phase 2 (tax payment and net buys) match target weights.
- Verify cash neutrality: total portfolio equity equals sum of holding values + cash balance.
- Verify Pre-Tax vs After-Tax results: After-Tax portfolio value is strictly less than or equal to Pre-Tax when positive capital gains occur.

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests/test_rebalancing.py`
Expected: FAIL

- [ ] **Step 3: Implement PortfolioSimulator in engine/backtest.py**
Implement the two-phase annual rebalance loop, trade order creation, execution, and annual ledger recording.

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests/test_rebalancing.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add engine/backtest.py tests/test_rebalancing.py
git commit -m "feat(backtest): implement two-phase portfolio rebalancing simulation engine"
```

---

### Task 6: Quantitative Performance Analytics

**Files:**
- Create: `engine/metrics.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: `AnnualLedgerEntry`, `StrategyResult`
- Produces: `calculate_cagr`, `calculate_cumulative_return`, `calculate_max_drawdown`, `calculate_turnover`, `calculate_tax_drag`, `calculate_terminal_metrics`

- [ ] **Step 1: Write tests for metrics**
Create `tests/test_metrics.py` with known test series:
- CAGR over 10, 20, 30 years.
- Max Drawdown calculation.
- Annual turnover calculation.
- Tax drag calculation ($\text{CAGR}_{\text{pre}} - \text{CAGR}_{\text{post}}$).

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests/test_metrics.py`
Expected: FAIL

- [ ] **Step 3: Implement engine/metrics.py**
Implement mathematical formulas defined in the spec.

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests/test_metrics.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add engine/metrics.py tests/test_metrics.py
git commit -m "feat(metrics): implement quantitative performance and tax drag calculators"
```

---

### Task 7: Reporting & Exporters Suite (CSVs & Google Apps Script)

**Files:**
- Create: `engine/exporters.py`
- Create: `scripts/google_apps_script.js`
- Test: `tests/test_exporters.py`

**Interfaces:**
- Produces:
  - `outputs/summary_metrics.csv`
  - `outputs/annual_breakdown.csv`
  - `outputs/trade_log.csv`
  - `scripts/google_apps_script.js` (complete standalone script ready for Google Sheets)

- [ ] **Step 1: Write test for exporters**
Create `tests/test_exporters.py` checking valid CSV schemas and non-empty Google Apps Script output.

- [ ] **Step 2: Implement engine/exporters.py**
Implement CSV writers and the Apps Script template generator with styled Google Sheets tabs:
- `Executive Summary` (with interactive tax rate input, summary tables, comparison metrics)
- `Top 3 Strategy`, `Top 5 Strategy`, `Top 10 Strategy`
- `S&P 500 Benchmark`
- `Historical Holdings & Trades`

- [ ] **Step 3: Run test to verify it passes**
Run: `python3 -m unittest tests/test_exporters.py`
Expected: PASS

- [ ] **Step 4: Commit**
```bash
git add engine/exporters.py tests/test_exporters.py
git commit -m "feat(exporters): implement CSV report writers and interactive Google Apps Script generator"
```

---

### Task 8: CLI Runner & Documentation

**Files:**
- Create: `run_backtest.py`
- Create: `README.md`

**Interfaces:**
- CLI commands:
  - `python3 run_backtest.py`
  - `python3 run_backtest.py --strategy market_cap --tax-rate 0.30`
  - `python3 run_backtest.py --strategy performance` (for momentum)

- [ ] **Step 1: Implement run_backtest.py**
CLI interface with `argparse`, orchestrating data loading, simulation for $N \in \{3, 5, 10\}$ and SPX across 10y, 20y, 30y, and writing CSVs and Google Apps Script.

- [ ] **Step 2: Execute full backtest suite**
Run: `python3 run_backtest.py`
Verify execution completes with 0 errors, populates `outputs/` and `scripts/google_apps_script.js`.

- [ ] **Step 3: Write README.md**
Comprehensive documentation explaining:
- Overview and strategy logic
- How to run the backtest and customize parameters
- How to add new strategies (like momentum / top performers)
- Step-by-step instructions to paste and run the Google Apps Script in the Google Sheet

- [ ] **Step 4: Run full test suite**
Run: `python3 -m unittest discover tests`
Expected: All tests PASS.

- [ ] **Step 5: Commit**
```bash
git add run_backtest.py README.md outputs/ scripts/
git commit -m "feat(cli): complete CLI backtest runner, reports, and documentation"
```
