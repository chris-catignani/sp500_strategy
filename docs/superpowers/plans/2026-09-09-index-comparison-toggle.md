# Index Comparison Toggle & MSCI World Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide an interactive show/hide index comparison toggle (`None`, `S&P 500`, `MSCI World`, `Both`) in Google Sheets, eliminate duplicate S&P 500 rows, integrate 1993–2024 MSCI World historical benchmark data, and enhance dashboard KPI cards and comparison tables.

**Architecture:** Extend `data/world_prices.json` with 1993–2024 MSCI World Price Return and Gross Total Return levels, update `DataLoader` with accessors, refactor `engine/scenarios.py` to output 16-column matrix data tagged with `RowType` (`"Strategy"` vs `"Index"`), update `google_apps_script.template.js` with the new dropdown, dynamic array filter formula, and dynamic KPI Card 2, and expose MSCI World across terminal and CSV reporting.

**Tech Stack:** Python 3 standard library (`json`, `csv`, `math`, `unittest`), Google Apps Script / Google Sheets dynamic array formulas.

## Global Constraints

- Zero external dependencies: Python 3 standard library only (`argparse`, `dataclasses`, `csv`, `json`, `math`, `unittest`).
- Unleveraged cash invariant: $cash \ge 0.0$ at all times.
- Decoupled dual tax model: annual dividend taxes settled separately from realized capital gains; FIFO lot accounting.
- Split-adjusted data convention: all index price and total return series split-adjusted to 2024-12-31.
- All single quotes inside template strings in `google_apps_script.template.js` must be escaped (`\'Scenario Data\'`).

---

### Task 1: Historical Benchmark Data & DataLoader Extensions

**Files:**
- Modify: `data/world_prices.json`
- Modify: `engine/data_loader.py:180-240`
- Test: `tests/test_data_loader.py`

**Interfaces:**
- Consumes: `^MSCIWORLD_TR` and `^MSCIWORLD_PR` year-end levels (1993–2024).
- Produces: `DataLoader.get_msci_world_level(year: int) -> float`, `DataLoader.get_msci_world_tr_level(year: int) -> float`, `DataLoader.get_msci_world_dividend_yield(year: int) -> float`.

- [ ] **Step 1: Write unit tests for MSCI World data loading in `tests/test_data_loader.py`**

```python
    def test_msci_world_benchmark_levels(self):
        loader = DataLoader()
        # Verify 1993 base and 2024 terminal levels exist and are positive
        pr_1993 = loader.get_msci_world_level(1993)
        tr_1993 = loader.get_msci_world_tr_level(1993)
        pr_2024 = loader.get_msci_world_level(2024)
        tr_2024 = loader.get_msci_world_tr_level(2024)

        self.assertEqual(pr_1993, 1000.00)
        self.assertEqual(tr_1993, 1000.00)
        self.assertGreater(pr_2024, pr_1993)
        self.assertGreater(tr_2024, pr_2024)

        # Verify annual dividend yield is non-negative and reasonable
        yield_2024 = loader.get_msci_world_dividend_yield(2024)
        self.assertGreaterEqual(yield_2024, 0.0)
        self.assertLess(yield_2024, 0.10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_data_loader.py`
Expected: FAIL with `AttributeError: 'DataLoader' object has no attribute 'get_msci_world_level'`

- [ ] **Step 3: Add `^MSCIWORLD_TR` and `^MSCIWORLD_PR` to `data/world_prices.json` and implement accessors in `engine/data_loader.py`**

Add compound levels starting at 1993 = 1000.00:
- PR levels: 1993: 1000.00, 1994: 1051.00, 1995: 1242.81, 1996: 1396.05, 1997: 1573.21, 1998: 1914.75, 1999: 2379.46, 2000: 2065.85, 2001: 1697.09, 2002: 1339.86, 2003: 1741.95, 2004: 1958.65, 2005: 2103.98, 2006: 2474.07, 2007: 2636.12, 2008: 1511.29, 2009: 1914.05, 2010: 2096.84, 2011: 1928.88, 2012: 2183.11, 2013: 2709.23, 2014: 2788.61, 2015: 2712.20, 2016: 2856.49, 2017: 3430.93, 2018: 3072.74, 2019: 3846.76, 2020: 4387.62, 2021: 5271.28, 2022: 4245.49, 2023: 5169.73, 2024: 6048.59.
- TR levels: 1993: 1000.00, 1994: 1076.40, 1995: 1302.77, 1996: 1496.62, 1997: 1738.18, 1998: 2161.60, 1999: 2711.29, 2000: 2365.60, 2001: 1975.75, 2002: 1580.99, 2003: 2108.89, 2004: 2430.49, 2005: 2677.19, 2006: 3229.99, 2007: 3546.53, 2008: 2116.22, 2009: 2767.79, 2010: 3109.62, 2011: 2955.69, 2012: 3444.56, 2013: 4387.34, 2014: 4628.64, 2015: 4613.83, 2016: 4989.85, 2017: 6141.01, 2018: 5637.45, 2019: 7238.48, 2020: 8432.83, 2021: 10317.57, 2022: 8488.27, 2023: 10561.10, 2024: 12587.77.

In `engine/data_loader.py`:
```python
    def get_msci_world_level(self, year: int) -> float:
        return self.get_price("^MSCIWORLD_PR", year)

    def get_msci_world_tr_level(self, year: int) -> float:
        return self.get_price("^MSCIWORLD_TR", year)

    def get_msci_world_dividend_yield(self, year: int) -> float:
        tr_prev = self.get_msci_world_tr_level(year - 1)
        tr_curr = self.get_msci_world_tr_level(year)
        pr_prev = self.get_msci_world_level(year - 1)
        pr_curr = self.get_msci_world_level(year)

        r_tr = (tr_curr - tr_prev) / tr_prev if tr_prev > 0.0 else 0.0
        r_pr = (pr_curr - pr_prev) / pr_prev if pr_prev > 0.0 else 0.0
        return max(0.0, r_tr - r_pr)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_data_loader.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add data/world_prices.json engine/data_loader.py tests/test_data_loader.py
git commit -m "feat(data): add MSCI World PR and TR series and DataLoader accessors"
```

---

### Task 2: Scenario Matrix & 16-Column Data Architecture

**Files:**
- Modify: `engine/scenarios.py:60-150`
- Modify: `tests/test_scenarios.py`

**Interfaces:**
- Consumes: `DataLoader.get_spx_level`, `get_spx_tr_level`, `get_msci_world_level`, `get_msci_world_tr_level`, `calculate_benchmark_annual_series`.
- Produces: `scenario_rows` with 16 columns ending with `RowType` (`"Strategy"` or `"Index"`), no duplicate S&P 500 rows, and MSCI World index benchmark rows with Alpha vs S&P 500.

- [ ] **Step 1: Update unit tests in `tests/test_scenarios.py` to expect 16 columns and distinct index rows**

In `tests/test_scenarios.py`:
- Expect `len(row) == 16` for all rows in `scenario_data`.
- Verify `row[-1]` is either `"Strategy"` or `"Index"`.
- Verify S&P 500 benchmark appears once per (tax_rate, horizon), and MSCI World benchmark appears once per (tax_rate, horizon).

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_scenarios.py`
Expected: FAIL with `AssertionError: 15 != 16`

- [ ] **Step 3: Update `engine/scenarios.py`**

In `build_scenario_and_apps_script_data`:
1. Generate strategy rows for each universe (`sp500`: `Top 3`, `Top 5`, `Top 10`, `world`: `Top 3`, `Top 5`, `Top 10`), append `"Strategy"` as the 16th column.
2. For S&P 500 benchmark: append `[spx_key, rate, "S&P 500", h_label, "S&P 500", ..., 0.0, "Index"]`.
3. For MSCI World benchmark: calculate series using `msci_pr_levels` and `msci_tr_levels` with `calculate_benchmark_annual_series`. Compute `msci_alpha = round(msci_post_liq_cagr - spx_post_liq_cagr, 6)`. Append `[msci_key, rate, "All World", h_label, "MSCI World", ..., msci_alpha, "Index"]`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_scenarios.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/scenarios.py tests/test_scenarios.py
git commit -m "feat(scenarios): add RowType column, eliminate duplicate SPX, and add MSCI World benchmark"
```

---

### Task 3: Google Apps Script Template & Executive Dashboard Controls

**Files:**
- Modify: `engine/templates/google_apps_script.template.js`
- Test: `tests/test_exporters.py`

**Interfaces:**
- Consumes: 16-column `SCENARIO_DATA` with `RowType`.
- Produces: Updated `google_apps_script.template.js` with `Compare Index` dropdown in `I2:J2`, cleaned `Strategy` dropdown, dynamic Card 2, properly escaped dynamic FILTER formula in `A10`, and index row conditional formatting.

- [ ] **Step 1: Update unit tests in `tests/test_exporters.py`**

Verify:
- `SCENARIO_HEADERS` contains 16 columns including `"RowType"`.
- `google_apps_script.js` contains the `Compare Index` dropdown logic and updated `A10` formula.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_exporters.py`
Expected: FAIL on header matching or script generation assertions.

- [ ] **Step 3: Update `engine/templates/google_apps_script.template.js`**

1. `SCENARIO_HEADERS`: Add `'RowType'` as 16th header.
2. In `buildExecutiveSummarySheet`:
   - Controls:
     - `E2:F2`: Strategy dropdown values `['All', 'Top 3', 'Top 5', 'Top 10']`.
     - `G2:H2`: Horizon dropdown `['All', '10y', '20y', '30y']`.
     - `I2`: Label `'Compare Index:'` right-aligned, bold.
     - `J2`: Value `'Both'`, styled `#FEFCBF`, bold, centered, validation `['None', 'S&P 500', 'MSCI World', 'Both']`.
     - `K2:M2`: Helper text.
   - Card 2:
     - Title: `='IF($D$2="All World Only", "MSCI World Wealth (30y)", "S&P 500 Wealth (30y)")'`
     - Formula: `='=IFERROR(INDEX(\'Scenario Data\'!$J:$J, MATCH("30y_" & IF($D$2="All World Only","All World_MSCI World","S&P 500_S&P 500") & "_" & TEXT($B$2, "0.0%"), \'Scenario Data\'!$A:$A, 0)), 0)'`
   - Row 10 Filter Formula:
     ```javascript
     var filterFormula = '=IFNA(FILTER(\'Scenario Data\'!$C$2:$O, (\'Scenario Data\'!$A$2:$A <> "") * (ROUND(\'Scenario Data\'!$B$2:$B, 4) = ROUND($B$2, 4)) * (($H$2 = "All") + (\'Scenario Data\'!$D$2:$D = $H$2)) * (((\'Scenario Data\'!$P$2:$P = "Strategy") * (($D$2 = "All") + (\'Scenario Data\'!$C$2:$C = SUBSTITUTE($D$2, " Only", ""))) * (($F$2 = "All") + (\'Scenario Data\'!$E$2:$E = $F$2))) + ((\'Scenario Data\'!$P$2:$P = "Index") * ((($J$2 = "Both") * 1) + ((\'Scenario Data\'!$E$2:$E = $J$2) * 1))))), "No matching records found")';
     ```
   - Conditional formatting: Add index benchmark rule (`#EDF2F7`, italic) before zebra striping.
   - Format Column 16 in `buildScenarioDataSheet`.

- [ ] **Step 4: Run test to verify it passes and validate JavaScript syntax**

Run: `python3 -m unittest tests/test_exporters.py`
Run: `python3 -c "from engine.exporters.pipeline import ReportExporter; from engine.scenarios import build_default_scenario_data; ReportExporter().export_apps_script({}, *build_default_scenario_data())"`
Run: `node -c scripts/google_apps_script.js`
Expected: PASS and valid JS syntax.

- [ ] **Step 5: Commit**

```bash
git add engine/templates/google_apps_script.template.js tests/test_exporters.py
git commit -m "feat(sheets): add Compare Index toggle, dynamic Card 2, and 16-col filter"
```

---

### Task 4: Terminal Display & CSV Export Integration

**Files:**
- Modify: `run_backtest.py:350-420`
- Modify: `engine/exporters/csv.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: Multi-horizon simulation results and benchmarks.
- Produces: Terminal table with S&P 500 and MSCI World, CSV summaries containing both benchmarks.

- [ ] **Step 1: Write CLI test checking for MSCI World benchmark in terminal/CSV outputs**

In `tests/test_cli.py`:
- Verify `run_backtest.py` produces `summary_metrics.csv` containing rows for `MSCI World` as well as `S&P 500`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_cli.py`
Expected: FAIL if checking for MSCI World presence.

- [ ] **Step 3: Update `run_backtest.py` to calculate and append MSCI World benchmark results**

Add MSCI World pre-tax and after-tax `StrategyResult` instances to `all_results`, and add MSCI World row to `table_rows` in terminal output.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_cli.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add run_backtest.py engine/exporters/csv.py tests/test_cli.py
git commit -m "feat(cli): add MSCI World benchmark to terminal table and summary metrics CSV"
```

---

### Task 5: End-to-End Execution & Full Verification

**Files:**
- Run: Full test suite (`tests/`)
- Run: `python3 run_backtest.py`
- Validate: `node -c scripts/google_apps_script.js`
- Verify: `outputs/summary_metrics.csv`, `scripts/google_apps_script.js`

- [ ] **Step 1: Run full unit test suite**

Run: `python3 -m unittest discover tests`
Expected: All tests pass without warnings or errors.

- [ ] **Step 2: Run full simulation and artifact export**

Run: `python3 run_backtest.py`
Expected: Successful execution, terminal table displaying both S&P 500 and MSCI World, clean exit code 0.

- [ ] **Step 3: Validate generated Google Apps Script syntax**

Run: `node -c scripts/google_apps_script.js`
Expected: Syntax OK.

- [ ] **Step 4: Commit all generated outputs and update documentation**

```bash
git add scripts/google_apps_script.js outputs/ docs/
git commit -m "chore: regenerate Google Apps Script and audit outputs with index comparison toggle"
```
