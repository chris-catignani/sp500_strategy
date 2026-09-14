# Nasdaq 100 Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the **Nasdaq 100** index into the quantitative backtest engine, CLI runner, and Google Apps Script dashboard as a full first-class benchmark (GitHub Issue #19).

**Architecture:** A continuous 31-year (1993–2024) dual-series dataset is constructed from `^NDX` (Price Return) and composite `^NDXT` (Total Return, seamlessly backward-chained from 2006 `^NDXT`, 1999–2006-Q1 QQQ distributions, and 1993–1998 nominal yield). The engine models pre-tax and after-tax CAGR, dividend tax drag, basis tracking, and terminal liquidation tax across 10y, 20y, and 30y horizons for both annual and quarterly rebalancing frequencies.

**Tech Stack:** Python 3 standard library only (`json`, `math`, `argparse`, `dataclasses`, `unittest`, `urllib`). External dependencies prohibited.

## Global Constraints
- Python 3 standard library only. No third-party packages.
- Zero external dependencies at engine runtime (100% offline using `data/`).
- Invariant: `cash >= 0.0` at all times.
- Decoupled dual tax model: dividend income taxed separately; capital loss carryforwards offset capital gains only.
- Discrete periodic observation dates (annual year-end or quarterly quarter-end valuations).
- Benchmark display name: `"Nasdaq 100"`.

---

### Task 1: Fetch Raw Market Data & Build Continuous Datasets

**Files:**
- Modify: `scripts/fetch_raw_market_data.py`
- Modify: `scripts/build_datasets_from_raw.py`
- Modify: `data/README.md`
- Output: `data/raw/benchmarks/NDX.json`, `data/raw/benchmarks/NDXT.json`, `data/raw/benchmarks/QQQ.json`
- Output: `data/sp500_prices.json`, `data/sp500_quarterly_prices.json`, `data/world_prices.json`, `data/world_quarterly_prices.json`

**Interfaces:**
- Consumes: Yahoo Finance raw JSON chart responses.
- Produces: `^NDX` and `^NDXT` price dictionaries for 1993–2024 (annual) and 1993-Q4 to 2024-Q4 (quarterly) in all price datasets.

- [ ] **Step 1: Update `scripts/fetch_raw_market_data.py` to include Nasdaq benchmarks**

Add `^NDX`, `^NDXT`, and `QQQ` to `BENCHMARKS` and `BENCHMARK_FILE_MAP`:
```python
BENCHMARKS = ["^GSPC", "^SP500TR", "URTH", "FBGRX", "^NDX", "^NDXT", "QQQ"]
BENCHMARK_FILE_MAP = {
    "^GSPC": "GSPC.json",
    "^SP500TR": "SP500TR.json",
    "URTH": "URTH.json",
    "FBGRX": "FBGRX.json",
    "^NDX": "NDX.json",
    "^NDXT": "NDXT.json",
    "QQQ": "QQQ.json",
}
```

- [ ] **Step 2: Fetch and save raw JSON fixtures into `data/raw/benchmarks/`**

Run: `python3 scripts/fetch_raw_market_data.py` (unsandboxed / network enabled).
Verify `data/raw/benchmarks/NDX.json`, `NDXT.json`, and `QQQ.json` exist and have non-zero file sizes.

- [ ] **Step 3: Update `scripts/build_datasets_from_raw.py` with backward-chaining synthesis**

1. Add `"^NDX"` and `"^NDXT"` to `BENCHMARK_PRICE_KEYS`.
2. Extract year-end and quarterly closes for `^NDX`.
3. Build quarterly composite `^NDXT` backwards from 2006-Q1 official `^NDXT` level keeping raw float precision:
   $$TR_{t-1} = \frac{TR_t}{1 + r_{\text{tr}, t}}$$
   with $r_{\text{tr}, t} = r_{\text{pr}, t} + y_t$, where $r_{\text{pr}, t} = \frac{NDX_t - NDX_{t-1}}{NDX_{t-1}}$:
   - For 1999-Q2 to 2006-Q1: $y_t = \frac{\text{Div}_{\text{QQQ}, t}}{P_{\text{QQQ}, t-1}}$ using unadjusted QQQ cash dividends and quarter-end closes.
   - For 1999-Q1: $y_t = 0.0$ (QQQ launched March 10, 1999).
   - For 1993-Q1 to 1998-Q4: $y_t = \frac{0.0025}{4} = 0.000625$ (0.25% annualized nominal yield).
4. Extract annual `^NDXT` closes from Q4: $TR_{\text{year}} = TR_{\text{year-Q4}}$.
5. Round final dictionary values to 2 decimals (e.g. `round(val, 2)`) when assigning to export maps.
6. Add `^NDX` and `^NDXT` to `all_prices_data` and `all_quarterly_prices_data`.

- [ ] **Step 4: Run dataset build script and verify outputs**

Run: `python3 scripts/build_datasets_from_raw.py`
Verify `data/sp500_prices.json` and `data/sp500_quarterly_prices.json` contain `^NDX` and `^NDXT` for all years 1993–2024 and quarters 1993-Q4 to 2024-Q4.

- [ ] **Step 5: Document provenance in `data/README.md`**

Add a dedicated "Nasdaq 100 (^NDX / ^NDXT)" section to `data/README.md` documenting the 2006–2024 official `^NDXT`, 1999-Q2 to 2006-Q1 QQQ distribution bridge, and 1993–1998 nominal yield bridge.

- [ ] **Step 6: Commit Task 1 changes**

```bash
git add scripts/fetch_raw_market_data.py scripts/build_datasets_from_raw.py data/README.md data/raw/benchmarks/NDX.json data/raw/benchmarks/NDXT.json data/raw/benchmarks/QQQ.json data/sp500_prices.json data/sp500_quarterly_prices.json data/world_prices.json data/world_quarterly_prices.json
git commit -m "feat(data): add Nasdaq 100 (^NDX/^NDXT) dual-series datasets (#19)"
```

---

### Task 2: DataLoader Methods & Tests

**Files:**
- Modify: `engine/data_loader.py:259-355`
- Create: `tests/test_nasdaq_benchmark.py`

**Interfaces:**
- Consumes: `data/sp500_prices.json` and `data/sp500_quarterly_prices.json`
- Produces:
  - `DataLoader.get_nasdaq_level(year: int) -> float`
  - `DataLoader.get_nasdaq_tr_level(year: int) -> float`
  - `DataLoader.get_nasdaq_quarterly_level(year: int, quarter: int) -> float`
  - `DataLoader.get_nasdaq_tr_quarterly_level(year: int, quarter: int) -> float`
  - `DataLoader.get_nasdaq_quarterly_tr_level(year: int, quarter: int) -> float` (alias)
  - `DataLoader.get_nasdaq_dividend_yield(year: int) -> float`

- [ ] **Step 1: Write failing tests in `tests/test_nasdaq_benchmark.py`**

```python
import unittest
from engine.data_loader import DataLoader
from engine.metrics import calculate_benchmark_annual_series, calculate_cagr, calculate_tax_drag

class TestNasdaqDataLoader(unittest.TestCase):
    def setUp(self):
        self.loader = DataLoader()

    def test_nasdaq_annual_levels(self):
        pr_1993 = self.loader.get_nasdaq_level(1993)
        tr_1993 = self.loader.get_nasdaq_tr_level(1993)
        pr_2024 = self.loader.get_nasdaq_level(2024)
        tr_2024 = self.loader.get_nasdaq_tr_level(2024)
        self.assertGreater(pr_1993, 0.0)
        self.assertGreater(tr_1993, 0.0)
        self.assertGreater(pr_2024, pr_1993)
        self.assertGreater(tr_2024, tr_1993)

    def test_nasdaq_key_map_aliases(self):
        aliases = ["nasdaq_100", "nasdaq 100", "nasdaq100", "qqq", "^ndx", "ndx", "^ndxt", "ndxt"]
        for alias in aliases:
            self.assertEqual(self.loader.get_benchmark_level(alias, 2024), self.loader.get_nasdaq_level(2024))
            self.assertEqual(self.loader.get_benchmark_tr_level(alias, 2024), self.loader.get_nasdaq_tr_level(2024))

    def test_nasdaq_quarterly_levels(self):
        pr_q4_1993 = self.loader.get_nasdaq_quarterly_level(1993, 4)
        tr_q4_1993 = self.loader.get_nasdaq_tr_quarterly_level(1993, 4)
        alias_tr_q4 = self.loader.get_nasdaq_quarterly_tr_level(1993, 4)
        self.assertEqual(tr_q4_1993, alias_tr_q4)
        self.assertGreater(pr_q4_1993, 0.0)
        self.assertGreater(tr_q4_1993, 0.0)
        self.assertAlmostEqual(pr_q4_1993, self.loader.get_nasdaq_level(1993), places=2)
        self.assertAlmostEqual(tr_q4_1993, self.loader.get_nasdaq_tr_level(1993), places=2)

    def test_nasdaq_dividend_yield_non_negative(self):
        for yr in range(1994, 2025):
            yld = self.loader.get_nasdaq_dividend_yield(yr)
            self.assertGreaterEqual(yld, 0.0)


class TestNasdaqPerformanceCalculations(unittest.TestCase):
    def setUp(self):
        self.loader = DataLoader()

    def test_nasdaq_30y_series_modeling(self):
        years = list(range(1993, 2025))
        pr_series = [self.loader.get_nasdaq_level(y) for y in years]
        tr_series = [self.loader.get_nasdaq_tr_level(y) for y in years]

        res_pre = calculate_benchmark_annual_series(
            pr_levels=pr_series,
            tr_levels=tr_series,
            tax_rate=0.0,
            initial_capital=10000.0,
            is_after_tax=False,
        )
        self.assertEqual(res_pre["total_taxes_paid"], 0.0)
        self.assertEqual(res_pre["cost_basis"], res_pre["final_equity"])
        cagr_pre = calculate_cagr(10000.0, res_pre["final_equity"], 31)
        self.assertGreater(cagr_pre, 0.05)

        res_post = calculate_benchmark_annual_series(
            pr_levels=pr_series,
            tr_levels=tr_series,
            tax_rate=0.30,
            initial_capital=10000.0,
            is_after_tax=True,
        )
        self.assertGreater(res_post["total_taxes_paid"], 0.0)
        self.assertLess(res_post["final_equity"], res_pre["final_equity"])
        cagr_post = calculate_cagr(10000.0, res_post["pre_liquidation_wealth"], 31)
        drag = calculate_tax_drag(cagr_pre, cagr_post)
        self.assertGreaterEqual(drag, 0.0)
```

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/test_nasdaq_benchmark.py`
Expected: FAIL with `AttributeError: 'DataLoader' object has no attribute 'get_nasdaq_level'`

- [ ] **Step 3: Implement methods in `engine/data_loader.py`**

1. Update `BENCHMARK_KEY_MAP` with all 8 Nasdaq 100 aliases.
2. Add `get_nasdaq_level`, `get_nasdaq_tr_level`, `get_nasdaq_quarterly_level`, `get_nasdaq_tr_quarterly_level`, `get_nasdaq_quarterly_tr_level`, and `get_nasdaq_dividend_yield`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_nasdaq_benchmark.py`
Expected: PASS

- [ ] **Step 5: Commit Task 2 changes**

```bash
git add engine/data_loader.py tests/test_nasdaq_benchmark.py
git commit -m "feat(engine): add DataLoader support for Nasdaq 100 benchmark (#19)"
```

---

### Task 3: Quantitative Scenarios Matrix & 30-Year Trajectory

**Files:**
- Modify: `engine/scenarios.py`
- Modify: `tests/test_scenarios.py`

**Interfaces:**
- Consumes: `DataLoader` Nasdaq benchmark accessors.
- Produces:
  - `nasdaq_benchmarks` and `nasdaq_q_benchmarks` in `compute_scenario_grid`.
  - Matrix rows: `{h_label}_Nasdaq 100_Nasdaq 100_{Annual/Quarterly}_{rate_str}`.
  - `("Nasdaq 100", nasdaq_traj_ann, nasdaq_traj_q)` in `benchmarks` inside `format_apps_script_payloads`.

- [ ] **Step 1: Update `tests/test_scenarios.py` with new dimension expectations**

Update assertions in `tests/test_scenarios.py`:
- Line 28: assert `len(active_results) == 180` (60 per universe * 3) or verify active results unchanged.
- Line 34: assert `len(scenario_rows) == 480` (was 450).
- Lines 70, 74, 100, 101: assert `len(trajectory_matrix) == 496` for 2 universes (was 372) and `248` for 1 universe (was 186); same for `drawdown_matrix`.
- Assert presence of `"nasdaq_benchmarks"` and `"nasdaq_q_benchmarks"` in grid.

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/test_scenarios.py`
Expected: FAIL due to row count mismatches.

- [ ] **Step 3: Implement Nasdaq 100 in `engine/scenarios.py`**

1. In `compute_scenario_grid`:
   - Initialize `nasdaq_benchmarks: List[Dict[str, Any]] = []` and `nasdaq_q_benchmarks: List[Dict[str, Any]] = []`.
   - Calculate Annual and Quarterly series using `calculate_benchmark_annual_series`.
   - Calculate alpha relative to `spx_after_cagr` / `spx_q_after_cagr`.
   - Add to return dictionary.
2. In `format_apps_script_payloads`:
   - Format scenario rows for Annual and Quarterly Nasdaq 100 under keys:
     - `{h_label}_Nasdaq 100_Nasdaq 100_Annual_{rate_str}`
     - `{h_label}_Nasdaq 100_Nasdaq 100_Quarterly_{rate_str}`
   - At line 1050 inside `format_apps_script_payloads`, compute 30-year `nasdaq_traj_ann` and `nasdaq_traj_q`, and append `("Nasdaq 100", nasdaq_traj_ann, nasdaq_traj_q)` to `benchmarks`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests/test_scenarios.py`
Expected: PASS

- [ ] **Step 5: Commit Task 3 changes**

```bash
git add engine/scenarios.py tests/test_scenarios.py
git commit -m "feat(scenarios): add Nasdaq 100 to scenario grid and trajectory matrices (#19)"
```

---

### Task 4: CLI Runner & ASCII Table Reporting

**Files:**
- Modify: `run_backtest.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `DataLoader` and `calculate_benchmark_annual_series`.
- Produces: CLI `--benchmark` support for `"nasdaq_100"`, `"nasdaq 100"`, `"nasdaq100"`, `"qqq"`, and output rows in terminal tables and `outputs/summary_metrics.csv`.

- [ ] **Step 1: Write test in `tests/test_cli.py` for Nasdaq benchmark options**

Add test cases for running CLI with `--benchmark nasdaq_100` and `--benchmark qqq`, verifying exit code 0 and non-empty stdout.

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/test_cli.py`
Expected: FAIL on invalid `--benchmark` choice.

- [ ] **Step 3: Implement Nasdaq 100 support in `run_backtest.py`**

1. Update `build_argument_parser`:
   Add `"nasdaq_100"`, `"nasdaq 100"`, `"nasdaq100"`, `"qqq"` to `--benchmark` choices.
2. Normalize `bmk_filter = getattr(args, "benchmark", "all").lower().replace(" ", "_")` (mapping `"qqq"` and `"nasdaq100"` to `"nasdaq_100"`).
3. Pre-calculate Nasdaq 100 Annual & Quarterly series across all horizons.
4. Update `bench_configs` unpacking to 5-tuple: `(freq_tag, s_bm, m_bm, f_bm, n_bm)`.
5. Add `Nasdaq 100` rows to terminal table if `include_nasdaq`.
6. Append pre-tax and after-tax `StrategyResult` records to `all_results`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests/test_cli.py`
Expected: PASS

- [ ] **Step 5: Commit Task 4 changes**

```bash
git add run_backtest.py tests/test_cli.py
git commit -m "feat(cli): add Nasdaq 100 benchmark option and table output (#19)"
```

---

### Task 5: Google Sheets / Apps Script Templates

**Files:**
- Modify: `engine/templates/gas/02_executive_summary.js`
- Modify: `engine/templates/gas/03_performance_tradeoffs.js`
- Modify: `tests/test_exporters.py`

**Interfaces:**
- Consumes: Scenario matrix keys from `engine/scenarios.py`.
- Produces: Valid Google Apps Script templates supporting `"Nasdaq 100"` in Control 6 dropdown and dynamic formulas.

- [ ] **Step 1: Update existing assertion and add Nasdaq 100 test in `tests/test_exporters.py`**

1. In `tests/test_exporters.py` line 413, update:
   ```python
   self.assertIn("['S&P 500', 'MSCI World', 'FBGRX', 'Nasdaq 100']", code)
   ```
2. Add assertion verifying `IF($D$3="Nasdaq 100", "Nasdaq 100_Nasdaq 100", ...)` is present in generated code.

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/test_exporters.py`
Expected: FAIL

- [ ] **Step 3: Update `02_executive_summary.js` and `03_performance_tradeoffs.js`**

1. In `02_executive_summary.js`:
   - Update D3 validation list: `['S&P 500', 'MSCI World', 'FBGRX', 'Nasdaq 100']`.
   - Update B12 formula: `IF($D$3="Nasdaq 100", "US Large Tech", ...)`.
   - Update `benchKeyExpr` formula: `IF($D$3="Nasdaq 100", "Nasdaq 100_Nasdaq 100", ...)`.
2. In `03_performance_tradeoffs.js`:
   - Update `annKey` and `qtrKey` formulas with `IF('Executive Summary'!$D$3="Nasdaq 100", "Nasdaq 100_Nasdaq 100_Annual_", ...)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_exporters.py`
Expected: PASS

- [ ] **Step 5: Commit Task 5 changes**

```bash
git add engine/templates/gas/ tests/test_exporters.py
git commit -m "feat(gas): integrate Nasdaq 100 into Google Sheets templates (#19)"
```

---

### Task 6: Full Verification & Export Validation

**Files:**
- All modified files across the repo.
- Generated: `scripts/google_apps_script.js`, `outputs/summary_metrics.csv`, `outputs/annual_breakdown.csv`, `outputs/trade_log.csv`.

- [ ] **Step 1: Run full test suite**

Run: `python3 -m unittest discover tests`
Expected: All tests pass with 0 failures and 0 errors.

- [ ] **Step 2: Test CLI runs across multiple parameter configurations**

1. `python3 run_backtest.py --benchmark nasdaq_100`
2. `python3 run_backtest.py --benchmark qqq`
3. `python3 run_backtest.py --compare-frequencies --benchmark all`
Verify terminal ASCII table renders cleanly with `"Nasdaq 100"` rows.

- [ ] **Step 3: Verify output CSV files and generated Apps Script bundle**

Verify `outputs/summary_metrics.csv` contains `Nasdaq 100` records for all horizons and frequencies.
Verify `scripts/google_apps_script.js` contains the updated scenario rows (480 rows) and trajectory matrices.

- [ ] **Step 4: Commit all final outputs and artifacts**

```bash
git add outputs/ scripts/google_apps_script.js
git commit -m "chore: regenerate export outputs with Nasdaq 100 benchmark (#19)"
```
