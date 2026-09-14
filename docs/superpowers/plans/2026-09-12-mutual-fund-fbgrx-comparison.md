# Mutual Fund Comparison Framework & FBGRX Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate FBGRX (Fidelity Blue Chip Growth Fund) as an active mutual fund comparison benchmark across the data ingestion pipeline, calculation engine, scenario matrix, CLI output tables, and Google Sheets dashboard.

**Architecture:** Fetch historical FBGRX monthly prices and distributions (1993–2024); extract both NAV price return and distribution-adjusted total return into annual and quarterly dataset files; extend DataLoader with generic benchmark methods; generate decoupled scenario keys and benchmark-aware trajectory matrices in `engine/scenarios.py`; update Google Apps Script templates with dynamic dropdowns and decoupled lookups; and render FBGRX comparison rows in the CLI and CSV exporters.

**Tech Stack:** Python 3 standard library (`urllib`, `json`, `datetime`, `math`, `unittest`, `argparse`), Google Apps Script (JavaScript).

## Global Constraints
- Zero external dependencies: Python 3 standard library only (`argparse`, `dataclasses`, `csv`, `json`, `math`, `unittest`). No pandas, numpy, or third-party packages.
- Unleveraged cash invariant: `cash >= 0.0` at all times.
- Split-adjusted pricing and distributions: All prices and distributions adjusted to 2024-12-31.
- Exact decoupled dual tax model: Distribution drag taxed annually; terminal capital gains liquidation tax on unrealized gains.
- Rebalancing frequencies: Complete support for both Annual and Quarterly frequencies across 10y, 20y, and 30y horizons (1994–2024).

---

### Task 1: Market Data Ingestion & Dataset Building for FBGRX

**Files:**
- Modify: `scripts/fetch_raw_market_data.py:27-39`
- Modify: `scripts/build_datasets_from_raw.py:240-315, 410-435, 540-565`
- Outputs: `data/raw/benchmarks/FBGRX.json`, `data/sp500_prices.json`, `data/sp500_quarterly_prices.json`, `data/world_prices.json`, `data/world_quarterly_prices.json`

**Interfaces:**
- Consumes: Yahoo Finance Chart API JSON response for FBGRX.
- Produces: `"FBGRX"` (NAV price return) and `"FBGRX_TR"` (distribution-adjusted total return) keys in annual and quarterly price datasets.

- [ ] **Step 1: Update `scripts/fetch_raw_market_data.py`**
Add `"FBGRX"` to `BENCHMARKS` and `BENCHMARK_FILE_MAP`:
```python
BENCHMARKS = ["^GSPC", "^SP500TR", "URTH", "FBGRX"]
BENCHMARK_FILE_MAP = {
    "^GSPC": "GSPC.json",
    "^SP500TR": "SP500TR.json",
    "URTH": "URTH.json",
    "FBGRX": "FBGRX.json",
}
```

- [ ] **Step 2: Fetch raw FBGRX data**
Run `python3 scripts/fetch_raw_market_data.py` (with network permission) to ensure `data/raw/benchmarks/FBGRX.json` is downloaded and contains valid monthly timestamps and quotes from 1993 to 2024.

- [ ] **Step 3: Parameterize price extractors in `scripts/build_datasets_from_raw.py` with safe list traversal**
Update `extract_year_end_closes` and `extract_quarterly_closes` to accept `source_field: str = "close"`:
```python
def extract_year_end_closes(chart_data: dict, source_field: str = "close") -> Dict[str, float]:
    timestamps = chart_data.get("timestamp", [])
    if source_field == "adjclose":
        adjclose_list = chart_data.get("indicators", {}).get("adjclose")
        closes = adjclose_list[0].get("adjclose", []) if adjclose_list else []
    else:
        quote_list = chart_data.get("indicators", {}).get("quote")
        closes = quote_list[0].get("close", []) if quote_list else []
    # ... process December closes
```
And similarly for `extract_quarterly_closes`.

- [ ] **Step 4: Ingest FBGRX and update dataset export filters**
In `main()` of `scripts/build_datasets_from_raw.py`:
```python
fbgrx_raw = RAW_DIR / "benchmarks" / "FBGRX.json"
if fbgrx_raw.exists():
    fbgrx_chart = load_raw_chart(fbgrx_raw)
    all_prices_data["FBGRX"] = extract_year_end_closes(fbgrx_chart, source_field="close")
    all_prices_data["FBGRX_TR"] = extract_year_end_closes(fbgrx_chart, source_field="adjclose")
    all_quarterly_prices_data["FBGRX"] = extract_quarterly_closes(fbgrx_chart, source_field="close")
    all_quarterly_prices_data["FBGRX_TR"] = extract_quarterly_closes(fbgrx_chart, source_field="adjclose")
```
Update `sp500_prices` and `sp500_quarterly_prices` filters to include `"FBGRX"` and `"FBGRX_TR"`:
```python
BENCHMARK_PRICE_KEYS = ["^GSPC", "^SP500TR", "^MSCIWORLD_PR", "^MSCIWORLD_TR", "FBGRX", "FBGRX_TR"]
```

- [ ] **Step 5: Run dataset builder and verify**
Run `python3 scripts/build_datasets_from_raw.py` and verify that `"FBGRX"` and `"FBGRX_TR"` exist in `data/sp500_prices.json` and `data/sp500_quarterly_prices.json` with 32 annual points (1993–2024) and 125 quarterly points (1993-Q4 to 2024-Q4).

---

### Task 2: DataLoader Generic Benchmark Architecture & Unit Tests

**Files:**
- Modify: `engine/data_loader.py:245-350`
- Create: `tests/test_mutual_funds.py`

**Interfaces:**
- Consumes: Price datasets containing `"FBGRX"` and `"FBGRX_TR"`.
- Produces: `get_benchmark_level`, `get_benchmark_tr_level`, `get_benchmark_quarterly_level`, `get_benchmark_quarterly_tr_level`, `get_benchmark_dividend_yield`.

- [ ] **Step 1: Write the failing tests in `tests/test_mutual_funds.py`**
Test DataLoader benchmark methods for FBGRX and test `calculate_benchmark_annual_series` against FBGRX price levels.
Verify tests fail with `AttributeError` or missing method.

- [ ] **Step 2: Implement generic benchmark methods in `engine/data_loader.py`**
Add:
```python
def get_benchmark_level(self, benchmark: str, year: int) -> float:
    key_map = {"sp500": "^GSPC", "msci_world": "^MSCIWORLD_PR", "fbgrx": "FBGRX"}
    ticker = key_map.get(benchmark.lower(), benchmark)
    return self.get_price(ticker, year)

def get_benchmark_tr_level(self, benchmark: str, year: int) -> float:
    key_map = {"sp500": "^SP500TR", "msci_world": "^MSCIWORLD_TR", "fbgrx": "FBGRX_TR"}
    ticker = key_map.get(benchmark.lower(), f"{benchmark}_TR")
    return self.get_price(ticker, year)

def get_benchmark_quarterly_level(self, benchmark: str, year: int, quarter: int) -> float:
    key_map = {"sp500": "^GSPC", "msci_world": "^MSCIWORLD_PR", "fbgrx": "FBGRX"}
    ticker = key_map.get(benchmark.lower(), benchmark)
    return self.get_quarterly_price(ticker, year, quarter)

def get_benchmark_quarterly_tr_level(self, benchmark: str, year: int, quarter: int) -> float:
    key_map = {"sp500": "^SP500TR", "msci_world": "^MSCIWORLD_TR", "fbgrx": "FBGRX_TR"}
    ticker = key_map.get(benchmark.lower(), f"{benchmark}_TR")
    return self.get_quarterly_price(ticker, year, quarter)

def get_benchmark_dividend_yield(self, benchmark: str, year: int) -> float:
    tr_curr = self.get_benchmark_tr_level(benchmark, year)
    tr_prev = self.get_benchmark_tr_level(benchmark, year - 1)
    r_tr = (tr_curr - tr_prev) / tr_prev if tr_prev > 0.0 else 0.0
    pr_curr = self.get_benchmark_level(benchmark, year)
    pr_prev = self.get_benchmark_level(benchmark, year - 1)
    r_pr = (pr_curr - pr_prev) / pr_prev if pr_prev > 0.0 else 0.0
    return max(0.0, r_tr - r_pr)

# Aliases for convenience and caller compatibility
get_quarterly_benchmark_level = get_benchmark_quarterly_level
get_quarterly_benchmark_tr_level = get_benchmark_quarterly_tr_level
get_fbgrx_level = lambda self, y: self.get_benchmark_level("fbgrx", y)
get_fbgrx_tr_level = lambda self, y: self.get_benchmark_tr_level("fbgrx", y)
```

- [ ] **Step 3: Run unit tests to verify they pass**
Run `python3 -m unittest tests/test_mutual_funds.py`.
Expected: PASS.

---

### Task 3: Scenario Matrix Engine & Trajectory Multi-Benchmark Integration

**Files:**
- Modify: `engine/scenarios.py:260-350, 500-600, 830-885`
- Modify: `tests/test_scenarios.py:20-75`

**Interfaces:**
- Consumes: DataLoader benchmark methods.
- Produces: Decoupled scenario rows `{h}_FBGRX_FBGRX_{freq}_{tax}` and multi-benchmark trajectory keys `f"{u}_{b}_{f}"` in `TRAJECTORY_MATRIX` and `DRAWDOWN_MATRIX`.

- [ ] **Step 1: Write test for scenario keys and trajectory matrix in `tests/test_scenarios.py`**
Add assertions that FBGRX scenario entries exist across 10y, 20y, 30y, and that `trajectory_matrix` contains entries for `S&P 500_FBGRX_Annual`, etc. Run to verify failure.

- [ ] **Step 2: Generate FBGRX scenario rows in `engine/scenarios.py`**
Add FBGRX pre-tax and after-tax scenario rows:
- `lookup_key = f"{h_label}_FBGRX_FBGRX_{f_label}_{rate_str}"`
- Universe: `"FBGRX"`
- Strategy: `"FBGRX"`
- Weighting: `"Market Cap"` (aligns with test row[5] contract)
- RowType: `"Mutual Fund"`
- CAGR, wealth, drawdown, and annual history from `calculate_benchmark_annual_series`.

- [ ] **Step 3: Multi-benchmark trajectory matrices**
In `build_scenario_and_apps_script_data`:
Update the trajectory and drawdown matrix generator loops:
For each universe `u` in `("sp500", "all_world")`:
  For each benchmark `b` in `("S&P 500", "MSCI World", "FBGRX")`:
    For each frequency `f` in `("annual", "quarterly")`:
      `lookup_key = f"{u_label}_{b}_{f_label}"`
      Populate rows with strategy trajectories and the chosen benchmark trajectory.

- [ ] **Step 4: Update `tests/test_scenarios.py` contract checks**
Update contract assertions:
- `self.assertIn(row[17], ("Strategy", "Index", "Mutual Fund"))`
- In `test_build_default_scenario_data`: Update length assertions to **372 rows** (2 universes $\times$ 3 benchmarks $\times$ 2 frequencies $\times$ 31 years = 372).
- In `test_build_scenario_single_universe`: Update length assertions to **186 rows** (1 universe $\times$ 3 benchmarks $\times$ 2 frequencies $\times$ 31 years = 186).

- [ ] **Step 5: Run tests**
Run `python3 -m unittest tests/test_scenarios.py tests/test_mutual_funds.py`.
Expected: PASS.

---

### Task 4: Google Apps Script Dashboard Templates

**Files:**
- Modify: `engine/templates/gas/02_executive_summary.js:125-142, 190-200, 270-280`
- Modify: `engine/templates/gas/03_performance_tradeoffs.js:135-150, 220-265`
- Regenerate: `scripts/google_apps_script.js`

**Interfaces:**
- Consumes: Scenario data keys and multi-benchmark trajectory matrices.
- Produces: Interactive Google Sheets dashboard script with dynamic FBGRX benchmark dropdown and decoupled formulas.

- [ ] **Step 1: Update `02_executive_summary.js`**
Update Control 6 data validation to `['S&P 500', 'MSCI World', 'FBGRX']`.
Update `benchKeyExpr`:
```javascript
var benchKeyExpr = '$H$2 & "_" & IF($D$3="MSCI World", "All World_MSCI World", IF($D$3="FBGRX", "FBGRX_FBGRX", "S&P 500_S&P 500")) & "_" & $B$3 & "_" & ' + taxExpr;
```
Update Cell `B12` universe label:
```javascript
sheet.getRange('B12').setFormula('=IF($D$3="MSCI World", "All World", IF($D$3="FBGRX", "US Large Growth", "S&P 500"))');
```

- [ ] **Step 2: Update `03_performance_tradeoffs.js`**
Update Frequency Tradeoff Section 2 benchmark rows to resolve `$D$3`.
Update table header labels (lines 227 & 239):
```javascript
sheet.getRange('E42').setFormula('="Benchmark (" & \'Executive Summary\'!$D$3 & ")"');
sheet.getRange('K42').setFormula('="Benchmark (" & \'Executive Summary\'!$D$3 & ") Drawdown"');
```
Update Tab 2 chart filter formulas with open ranges:
```javascript
sheet.getRange('A43').setFormula(
  '=FILTER(\'Scenario Data\'!$U$2:$Y, \'Scenario Data\'!$T$2:$T = (\'Executive Summary\'!$B$2 & "_" & \'Executive Summary\'!$D$3 & "_" & \'Executive Summary\'!$B$3))'
);
sheet.getRange('G43').setFormula(
  '=FILTER(\'Scenario Data\'!$AB$2:$AF, \'Scenario Data\'!$AA$2:$AA = (\'Executive Summary\'!$B$2 & "_" & \'Executive Summary\'!$D$3 & "_" & \'Executive Summary\'!$B$3))'
);
```

- [ ] **Step 3: Rebuild dashboard HTML & Apps Script bundle**
Run `python3 scripts/build_dashboard_html.py` to regenerate `scripts/google_apps_script.js`.
Verify syntax and absence of syntax errors.

---

### Task 5: CLI Runner (`run_backtest.py`)

**Files:**
- Modify: `run_backtest.py:235-285, 350-390, 570-695`

**Interfaces:**
- Consumes: FBGRX benchmark series.
- Produces: Single unified FBGRX row in CLI terminal table and dual Pre-Tax/After-Tax `StrategyResult` records in CSV export.

- [ ] **Step 1: Add FBGRX series calculation to `run_backtest.py`**
Calculate `fbgrx_bench_pre` and `fbgrx_bench_post` for both Annual and Quarterly horizons.
Store in `fbgrx_metrics_by_horizon` and `quarterly_fbgrx_metrics_by_horizon`.

- [ ] **Step 2: Render single unified FBGRX row in CLI terminal output table**
In the benchmark rows section of `run_backtest.py`:
Append a single unified row for FBGRX to `table_rows` (e.g. labeled `"FBGRX"` or `"FBGRX (Annual)"`), displaying Pre-Tax CAGR, After-Tax CAGR, Post-Liq CAGR, Max Drawdown, Tax Drag, and Alpha vs SPX side-by-side, exactly matching S&P 500 and MSCI World benchmark rows.

- [ ] **Step 3: Include dual FBGRX entries in CSV export**
Create `StrategyResult` synthetic entries for `FBGRX (Pre-Tax)` and `FBGRX (After-Tax)` and append to `all_results` so they are exported into `summary_metrics.csv`.

---

### Task 6: Verification & Test Suite Execution

**Files:**
- Verify: Full test suite, CLI runs, CSV exports, Google Apps Script.

- [ ] **Step 1: Run full unit test suite**
Run: `python3 -m unittest discover tests`
Expected: ALL PASS.

- [ ] **Step 2: Run CLI backtest (Annual)**
Run: `python3 run_backtest.py`
Verify terminal table displays unified FBGRX row with valid CAGR and drawdown.

- [ ] **Step 3: Run CLI backtest (Quarterly)**
Run: `python3 run_backtest.py --frequency quarterly`
Verify quarterly metrics for FBGRX.

- [ ] **Step 4: Run side-by-side comparison**
Run: `python3 run_backtest.py --compare-frequencies`
Verify dual-frequency tables render without errors.
