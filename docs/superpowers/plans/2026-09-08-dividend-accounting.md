# Dividend Accounting & Dynamic After-Tax Benchmarking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement cash dividend accounting, decoupled dual tax settlement (preserving capital loss carryforwards strictly for capital gains), dynamic after-tax S&P 500 benchmarking (`^GSPC` + `^SP500TR`), and an expanded 12-column Google Sheets dashboard with an explicit methodology timing note.

**Architecture:** 
A split-adjusted dividend per share (`DPS`) dataset (`data/sp500_dividends.json`) and Total Return benchmark series (`^SP500TR` in `data/sp500_prices.json`) feed `DataLoader`. Pre-rebalance dividend cash pooling and an explicitly decoupled Phase 2 secondary trim engine guarantee the unleveraged non-negative cash invariant. Pure numeric functions in `metrics.py` compute dynamic benchmark after-tax returns, feeding updated CSV exporters, `run_backtest.py`, and a revised 12-column Google Apps Script dashboard.

**Tech Stack:** Python 3 standard library only (`dataclasses`, `typing`, `json`, `math`, `csv`, `argparse`, `unittest`), Google Apps Script (JavaScript).

## Global Constraints
- Target repository: `/Users/chriscatignani/Developer/sp500_strategy`
- Target Google Sheet: https://docs.google.com/spreadsheets/d/1v8Ig7ZeresaJNX35W2VCrBmarWgYgLxKQD9wPg4O0Ao/edit?usp=sharing
- Time Horizons: 10-Year (2014–2024), 20-Year (2004–2024), 30-Year (1994–2024)
- Zero external dependencies: Python standard library only (no pandas, numpy, or 3rd party packages)
- Unleveraged cash invariant: `cash >= 0.0` at all times; no margin borrowing
- Tax Model: FIFO lot depletion, loss carryforwards offset capital gains only, dividends taxed annually as ordinary income at `tax_rate` ($\tau$)
- Split & Pricing Standard: Split-adjusted prices and dividends normalized to 2024-12-31

---

### Task 1: Historical Dividend Dataset & `^SP500TR` Benchmark Series

**Files:**
- Create: `data/sp500_dividends.json`
- Modify: `scripts/generate_datasets.py:1-439`
- Modify: `data/sp500_prices.json`
- Test: `tests/test_dataset_integrity.py`

**Interfaces:**
- Produces: `data/sp500_dividends.json` mapping `ticker -> {year_str: dps_float}`
- Produces: `^SP500TR` key in `data/sp500_prices.json` mapping `{year_str: level_float}`

- [ ] **Step 1: Write dataset integrity test**
Create `tests/test_dataset_integrity.py`:
```python
import json
import unittest
from pathlib import Path

class TestDatasetIntegrity(unittest.TestCase):
    def setUp(self):
        self.data_dir = Path(__file__).resolve().parent.parent / "data"
        self.dividends_path = self.data_dir / "sp500_dividends.json"
        self.prices_path = self.data_dir / "sp500_prices.json"

    def test_dividends_dataset_exists_and_valid(self):
        self.assertTrue(self.dividends_path.exists(), "sp500_dividends.json missing")
        with open(self.dividends_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("AAPL", data)
        self.assertIn("MSFT", data)
        self.assertIn("KO", data)
        # Check that dividend per share is non-negative
        for ticker, years in data.items():
            for yr, dps in years.items():
                self.assertGreaterEqual(dps, 0.0, f"Negative DPS for {ticker} in {yr}")

    def test_sp500_tr_series_present(self):
        with open(self.prices_path, "r", encoding="utf-8") as f:
            prices = json.load(f)
        self.assertIn("^GSPC", prices)
        self.assertIn("^SP500TR", prices)
        for yr in range(1994, 2025):
            str_yr = str(yr)
            self.assertIn(str_yr, prices["^SP500TR"])
            self.assertGreater(prices["^SP500TR"][str_yr], 0.0)
            # Total return index level must exceed or equal price return index in all years
            self.assertGreaterEqual(prices["^SP500TR"][str_yr], prices["^GSPC"][str_yr])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests/test_dataset_integrity.py`
Expected: FAIL with missing file or key `^SP500TR`

- [ ] **Step 3: Update `scripts/generate_datasets.py` and generate datasets**
Update `scripts/generate_datasets.py` to:
1. Define official S&P 500 Total Return index levels `SP500_TR_PRICES` (1993: 651.98, 1994: 753.86, ..., 2024: 13543.82).
2. Define split-adjusted annual dividend per share table `STOCK_DIVIDENDS` for all constituents (1994–2024).
3. Output `data/sp500_dividends.json` and include `"^SP500TR"` in `data/sp500_prices.json`.
Execute: `python3 scripts/generate_datasets.py`.

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests/test_dataset_integrity.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add data/sp500_dividends.json data/sp500_prices.json scripts/generate_datasets.py tests/test_dataset_integrity.py
git commit -m "feat(data): add sp500_dividends.json and ^SP500TR total return series"
```

---

### Task 2: Data Loader Extension

**Files:**
- Modify: `engine/data_loader.py:1-136`
- Modify: `tests/test_data_loader.py`

**Interfaces:**
- Consumes: `data/sp500_dividends.json`, `data/sp500_prices.json`
- Produces: 
  - `DataLoader.__init__(..., dividends_path=None)`
  - `DataLoader.get_dividend(ticker: str, year: int) -> float`
  - `DataLoader.get_spx_tr_level(year: int) -> float`
  - `DataLoader.get_spx_dividend_yield(year: int) -> float`

- [ ] **Step 1: Write test for DataLoader dividend methods**
Add to `tests/test_data_loader.py`:
```python
def test_get_dividend(self):
    # Apple paid dividends in 2024
    aapl_div = self.loader.get_dividend("AAPL", 2024)
    self.assertGreater(aapl_div, 0.0)
    # Ticker with no entry or non-payer returns 0.0
    unknown_div = self.loader.get_dividend("NONEXISTENT", 2024)
    self.assertEqual(unknown_div, 0.0)

def test_spx_tr_and_dividend_yield(self):
    tr_2024 = self.loader.get_spx_tr_level(2024)
    self.assertGreater(tr_2024, 0.0)
    # Annual dividend yield must be strictly non-negative
    yield_2024 = self.loader.get_spx_dividend_yield(2024)
    self.assertGreaterEqual(yield_2024, 0.0)
    self.assertLess(yield_2024, 0.10)  # S&P 500 yield is realistically between 1% and 4%
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests/test_data_loader.py`
Expected: FAIL with `AttributeError: 'DataLoader' object has no attribute 'get_dividend'`

- [ ] **Step 3: Implement `DataLoader` methods**
Update `engine/data_loader.py`:
- Add `dividends_path: Optional[Union[str, Path]] = None` to `__init__`.
- Load `self._raw_dividends: Dict[str, Dict[str, float]]`.
- Implement `get_dividend(ticker: str, year: int) -> float` (returns `float(self._raw_dividends.get(ticker, {}).get(str(year), 0.0))`).
- Implement `get_spx_tr_level(year: int) -> float` (delegates to `get_price("^SP500TR", year)`).
- Implement `get_spx_dividend_yield(year: int) -> float`:
  ```python
  tr_curr = self.get_spx_tr_level(year)
  tr_prev = self.get_spx_tr_level(year - 1)
  r_tr = (tr_curr - tr_prev) / tr_prev
  pr_curr = self.get_spx_level(year)
  pr_prev = self.get_spx_level(year - 1)
  r_pr = (pr_curr - pr_prev) / pr_prev
  return max(0.0, r_tr - r_pr)
  ```

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests/test_data_loader.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add engine/data_loader.py tests/test_data_loader.py
git commit -m "feat(data_loader): add dividend querying and benchmark total return methods"
```

---

### Task 3: Domain Models & Benchmark Mathematical Analytics

**Files:**
- Modify: `engine/models.py:52-88`
- Modify: `engine/metrics.py:1-170`
- Test: `tests/test_metrics.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: 
  - `AnnualLedgerEntry` fields: `dividend_income`, `dividend_tax_paid`, `capital_gains_tax_paid`
  - `StrategyResult` fields: `total_dividends_received`, `total_dividend_taxes_paid`
  - `metrics.calculate_benchmark_annual_series(pr_levels, tr_levels, tax_rate, initial_capital, is_after_tax)`

- [ ] **Step 1: Write test for models and benchmark analytics**
Add to `tests/test_metrics.py`:
```python
def test_calculate_benchmark_annual_series_pretax(self):
    pr_levels = [100.0, 110.0]   # 10% price return
    tr_levels = [100.0, 112.0]   # 12% total return (2% dividend yield)
    res = calculate_benchmark_annual_series(
        pr_levels=pr_levels,
        tr_levels=tr_levels,
        tax_rate=0.30,
        initial_capital=10000.0,
        is_after_tax=False
    )
    self.assertAlmostEqual(res["annual_returns"][0], 0.12, places=6)
    self.assertAlmostEqual(res["final_equity"], 11200.0, places=2)
    self.assertAlmostEqual(res["total_taxes_paid"], 0.0, places=2)
    self.assertAlmostEqual(res["post_liquidation_wealth"], 11200.0, places=2)

def test_calculate_benchmark_annual_series_aftertax(self):
    pr_levels = [100.0, 110.0]   # 10% price return
    tr_levels = [100.0, 112.0]   # 12% total return (2% dividend yield)
    # At 30% tax rate:
    # Div yield = 2% ($200 on $10k). Dividend tax = $60. Reinvested net div = $140.
    # Ending wealth pretax before liquidation = $10,000 * 1.114 = $11,140.
    # Basis = $10,000 + $140 = $10,140.
    # Unrealized gain = $11,140 - $10,140 = $1,000.
    # Liquidation tax = $1,000 * 0.30 = $300.
    # Post-liq wealth = $11,140 - $300 = $10,840.
    res = calculate_benchmark_annual_series(
        pr_levels=pr_levels,
        tr_levels=tr_levels,
        tax_rate=0.30,
        initial_capital=10000.0,
        is_after_tax=True
    )
    self.assertAlmostEqual(res["annual_returns"][0], 0.114, places=6)
    self.assertAlmostEqual(res["pre_liquidation_wealth"], 11140.0, places=2)
    self.assertAlmostEqual(res["post_liquidation_wealth"], 10840.0, places=2)
    self.assertAlmostEqual(res["total_taxes_paid"], 360.0, places=2) # $60 div tax + $300 liq tax
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests/test_metrics.py`
Expected: FAIL with `ImportError: cannot import name 'calculate_benchmark_annual_series'`

- [ ] **Step 3: Update `engine/models.py` and `engine/metrics.py`**
1. In `engine/models.py`, add `dividend_income: float = 0.0`, `dividend_tax_paid: float = 0.0`, `capital_gains_tax_paid: float = 0.0` to `AnnualLedgerEntry`.
2. Add `total_dividends_received: float = 0.0`, `total_dividend_taxes_paid: float = 0.0` to `StrategyResult`.
3. In `engine/metrics.py`, implement `calculate_benchmark_annual_series` with pure sequence inputs:
   - Calculate annual $R_{\text{PR}, t}$ and $R_{\text{TR}, t}$.
   - $y_t = \max(0.0, R_{\text{TR}, t} - R_{\text{PR}, t})$.
   - If `is_after_tax=False`: return gross TR series.
   - If `is_after_tax=True`: return net compounding series with annual dividend tax tracking, basis accumulation, and terminal liquidation tax.

- [ ] **Step 4: Run tests to verify they pass**
Run: `python3 -m unittest tests/test_metrics.py tests/test_models.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add engine/models.py engine/metrics.py tests/test_metrics.py tests/test_models.py
git commit -m "feat(metrics): add benchmark dynamic after-tax analytics and update domain models"
```

---

### Task 4: Portfolio Simulator Dual Tax Rebalancing Engine

**Files:**
- Modify: `engine/backtest.py:1-383`
- Test: `tests/test_rebalancing.py`
- Test: `tests/test_simulation.py`

**Interfaces:**
- Consumes: `DataLoader.get_dividend`, `DataLoader.get_spx_tr_level`, `calculate_benchmark_annual_series`
- Produces: `PortfolioSimulator.run_simulation(...) -> StrategyResult` (with dividend cash pooling and decoupled secondary trims)

- [ ] **Step 1: Write tests for dividend cash pooling and tax settlement**
Add to `tests/test_rebalancing.py`:
```python
def test_dividend_cash_pooling_and_tax_separation(self):
    sim = PortfolioSimulator()
    # Run a 1-year after-tax backtest
    result = sim.run_simulation(start_year=2023, end_year=2024, n=3, is_after_tax=True, tax_rate=0.30)
    self.assertGreater(result.total_dividends_received, 0.0)
    entry_2024 = result.annual_history[0]
    self.assertGreater(entry_2024.dividend_income, 0.0)
    self.assertAlmostEqual(entry_2024.dividend_tax_paid, entry_2024.dividend_income * 0.30, places=4)
    # Check that total tax paid is exactly sum of capital gains tax + dividend tax
    self.assertAlmostEqual(entry_2024.tax_paid, entry_2024.capital_gains_tax_paid + entry_2024.dividend_tax_paid, places=4)
    # Unleveraged cash invariant
    for c in sim.cash_history:
        self.assertGreaterEqual(c, 0.0)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests/test_rebalancing.py`
Expected: FAIL (attributes not yet populated / dividend cash not yet added)

- [ ] **Step 3: Update `engine/backtest.py` implementation**
1. At the beginning of each rebalance year $t$:
   ```python
   positions = self.tax_manager.get_all_positions()
   annual_dividends = sum(
       shares * self.data_loader.get_dividend(ticker, current_year)
       for ticker, shares in positions.items()
   )
   self.cash += annual_dividends
   ```
2. Total pre-tax valuation: `total_pretax_value = sum(shares * price) + self.cash`.
3. In Phase 2:
   If `is_after_tax=True`:
   - Compute `tax_div = annual_dividends * tax_rate`.
   - Deduct `self.cash -= tax_div`.
   - Set `total_tax_paid = tax_div`.
   - In secondary trim convergence loop (`for _ in range(20)`):
     - Settle capital gains: `tax_cap_step, net_taxable, loss_cf = self.tax_manager.settle_annual_taxes(tax_rate, current_year)`.
     - `total_tax_paid += tax_cap_step`.
     - `self.cash -= tax_cap_step`.
     - `net_investable_equity = total_pretax_value - total_tax_paid`.
     - Trim positions exceeding updated target shares down to target.
     - Break when `tax_cap_step <= 1e-7` or no positions trimmed.
   - Set `entry.capital_gains_tax_paid = total_tax_paid - tax_div`.
   - Set `entry.dividend_tax_paid = tax_div`.
   - Set `entry.tax_paid = total_tax_paid`.
4. Set `entry.spx_return`:
   - If `is_after_tax=False`: gross TR return $R_{\text{TR}}$.
   - If `is_after_tax=True`: net after-tax benchmark return $R_{\text{SPX, After-Tax}}$.
5. Compute and store `total_dividends_received` and `total_dividend_taxes_paid` in `StrategyResult`.

- [ ] **Step 4: Run all rebalancing and simulation tests**
Run: `python3 -m unittest tests/test_rebalancing.py tests/test_simulation.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add engine/backtest.py tests/test_rebalancing.py
git commit -m "feat(backtest): integrate dividend cash pooling and decoupled dual tax rebalancing"
```

---

### Task 5: Exporter Suite & Multi-Horizon S&P Benchmark Dynamic Integration

**Files:**
- Modify: `engine/exporters.py:1-400`
- Modify: `run_backtest.py:1-500`
- Test: `tests/test_exporters.py`

**Interfaces:**
- Consumes: `StrategyResult`, `calculate_benchmark_annual_series`
- Produces: Updated `summary_metrics.csv`, `annual_breakdown.csv` with dividend and dynamic benchmark fields

- [ ] **Step 1: Write test for exporter column schemas**
Add to `tests/test_exporters.py`:
```python
def test_summary_csv_has_dividend_column(self):
    # Verify export_summary_metrics_csv includes total_dividends_received
    ...
def test_annual_csv_has_dividend_columns(self):
    # Verify export_annual_breakdown_csv includes dividend_income, dividend_tax_paid
    ...
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests/test_exporters.py`
Expected: FAIL with missing column headers

- [ ] **Step 3: Update `engine/exporters.py` and `run_backtest.py`**
1. In `export_summary_metrics_csv`:
   - Add `"total_dividends_received"` to CSV fieldnames.
   - Update `spx_benchmarks` parameter to handle `(horizon, tax_rate)` lookup or benchmark result objects.
2. In `export_annual_breakdown_csv`:
   - Add `"dividend_income"`, `"dividend_tax_paid"`, `"capital_gains_tax_paid"`.
3. In `run_backtest.py`:
   - Compute dynamic S&P 500 benchmark metrics for each horizon and tax tier using `calculate_benchmark_annual_series`.
   - Populate benchmark row in `summary_metrics.csv` with full after-tax stats (`TotalDividends`, `TotalTaxes`, `TaxDrag`).

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests/test_exporters.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add engine/exporters.py run_backtest.py tests/test_exporters.py
git commit -m "feat(exporters): add dividend fields to CSVs and dynamic benchmark calculations"
```

---

### Task 6: Google Apps Script Interactive Dashboard Generation

**Files:**
- Modify: `engine/exporters.py:401-1231`
- Test: `tests/test_google_apps_script.py`
- Generate: `scripts/google_apps_script.js`

**Interfaces:**
- Produces: `scripts/google_apps_script.js` containing the complete interactive 12-column dashboard

- [ ] **Step 1: Write test for Google Apps Script generation**
Update `tests/test_google_apps_script.py`:
- Test that `scripts/google_apps_script.js` contains 12 columns in Executive Summary table.
- Test that KPI formulas `=G19`, `=G22`, `=E19`, `=L19`, `=K19` exist and match the revised grid.
- Test that Methodology Callout Card is present.
- Test that Annual Breakdown tables contain `Dividends Received ($)` and `Dividend Tax ($)`.

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests/test_google_apps_script.py`
Expected: FAIL

- [ ] **Step 3: Implement 12-column grid and Methodology Note in `engine/exporters.py`**
1. In `buildExecutiveSummarySheet`:
   - Banner: `A1:L1`
   - B2 parameter cell, `C2:L2` instruction banner.
   - 5 KPI Scorecards across `Cols A–L`:
     - Card 1: `A4:B6` (`=G19`)
     - Card 2: `C4:D6` (`=G22`)
     - Card 3: `E4:F6` (`=E19`)
     - Card 4: `G4:I6` (`=L19`)
     - Card 5: `J4:L6` (`=K19`)
   - Comparison Table: Header on Row 9 with 12 columns:
     `Horizon, Strategy, Annual Return (Pre-Tax), Annual Return (After-Tax), Annual Return (Post-Liq), Total Return (Cumulative), Ending Wealth ($10k Start), Total Dividends Received, Max Drawdown (Worst Drop), Total Taxes Paid, Annual Tax Drag, Excess vs S&P 500 (Alpha)`.
   - Rows 31–36: Add Methodology Note Callout Card across `A31:L36` explaining the annual discrete dividend convention.
2. In `buildScenarioDataSheet`:
   - Store all 12 metrics per strategy/benchmark row across all 5 tax rates.
3. In `buildAnnualSheet`:
   - Add `Dividends Received ($)` and `Dividend Tax ($)` columns.
4. Regenerate `scripts/google_apps_script.js`.

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests/test_google_apps_script.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add engine/exporters.py scripts/google_apps_script.js tests/test_google_apps_script.py
git commit -m "feat(sheets): upgrade Google Apps Script dashboard to 12-column grid with methodology note"
```

---

### Task 7: Documentation Updates & Full End-to-End Verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Test: Full test suite (`python3 -m unittest discover tests`)
- Test: CLI run (`python3 run_backtest.py`)

- [ ] **Step 1: Update documentation**
1. In `AGENTS.md`: Update Core Principles & Invariants to document `data/sp500_dividends.json`, `^SP500TR`, cash dividend pooling, and dynamic after-tax benchmarking.
2. In `README.md`: Update Architecture, Financial Glossary, Methodology Callout, and Google Sheets UX sections.

- [ ] **Step 2: Run full unit test suite**
Run: `python3 -m unittest discover tests`
Expected: All tests PASS with 0 failures and 0 errors.

- [ ] **Step 3: Run full CLI backtest runner**
Run: `python3 run_backtest.py`
Expected: Successfully generates `outputs/summary_metrics.csv`, `outputs/annual_breakdown.csv`, `outputs/trade_log.csv`, and `scripts/google_apps_script.js`.

- [ ] **Step 4: Commit**
```bash
git add README.md AGENTS.md outputs/ scripts/google_apps_script.js
git commit -m "docs: document dividend accounting, dynamic benchmarking, and update outputs"
```
