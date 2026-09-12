# Design Specification: Mutual Fund Comparison Framework & FBGRX Integration

**Date**: 2026-09-12  
**Status**: Revised & Approved for Implementation (Post-Architecture Review)  
**Topic**: Mutual Fund Comparative Benchmarking (FBGRX) across Engine, CLI, and Google Sheets Dashboard  

---

## 1. Executive Summary & Problem Statement

The S&P 500 Top N quantitative strategy currently evaluates concentrated mega-cap equity portfolios against passive market index benchmarks (the S&P 500 Total Return index `^SP500TR` and the MSCI World Total Return index `^MSCIWORLD_TR`).

However, long-term investors frequently evaluate systematic mega-cap momentum/cap-weighted strategies against **premier actively managed large-cap growth mutual funds**. The foremost active comparator is the **Fidelity Blue Chip Growth Fund (`FBGRX`)**, which has operated continuously since 1987.

### Objectives
1. **Incorporate Full Historical FBGRX Data (1993–2024)**:
   - Monthly split-adjusted NAV closes and distributions (dividends and capital gains) across all 31 backtest years (1994–2024, anchored at 1993-Q4).
   - Full support for both **Annual** and **Quarterly** rebalancing frequencies.
2. **Standardized After-Tax Benchmark Modeling**:
   - Model pre-tax total return (NAV growth + reinvested distributions).
   - Model after-tax performance with exact annual distribution tax drag ($0.0\%, 15.0\%, 20.0\%, 30.0\%, 37.0\%$) and terminal capital gains liquidation tax, exactly matching the S&P 500 and MSCI World after-tax modeling.
3. **Seamless Google Sheets Dashboard Integration**:
   - Add `FBGRX` to the interactive **Benchmark** dropdown in the Executive Summary dashboard (`['S&P 500', 'MSCI World', 'FBGRX']`).
   - Automatically update all dashboard KPI Cards (Ending Wealth, Alpha vs Benchmark, Max Drawdown, Tax Drag) and trajectory/drawdown charts when `FBGRX` is selected.
4. **CLI & Export Reporting**:
   - Include `FBGRX (Pre-Tax)` and `FBGRX (After-Tax)` rows in the CLI ASCII terminal output tables.
   - Include FBGRX metrics in generated CSV summary reports.
5. **Future-Proof Extensibility**:
   - Architect mutual fund ingestion and benchmark modeling so adding future mutual funds (e.g. `FCNTX`, `VFINX`, `TRBCX`) only requires adding the ticker to a registry.

---

## 2. Architecture & Data Model

### 2.1 Raw Data Fetching (`scripts/fetch_raw_market_data.py`)
- Add `"FBGRX"` to `BENCHMARKS` and `BENCHMARK_FILE_MAP`:
  ```python
  BENCHMARKS = ["^GSPC", "^SP500TR", "URTH", "FBGRX"]
  BENCHMARK_FILE_MAP = {
      "^GSPC": "GSPC.json",
      "^SP500TR": "SP500TR.json",
      "URTH": "URTH.json",
      "FBGRX": "FBGRX.json",
  }
  ```
- Yahoo Finance provides monthly closes, splits, dividends, and capital gains distributions for FBGRX from 1993 to 2024.
- Raw JSON response is saved to `data/raw/benchmarks/FBGRX.json`.

### 2.2 Dataset Generation (`scripts/build_datasets_from_raw.py`)
- Parameterize extraction helpers to extract from either `close` (NAV price return) or `adjclose` (distribution-adjusted total return):
  - `extract_year_end_closes(chart_data: dict, price_type: str = "close") -> Dict[str, float]`
  - `extract_quarterly_closes(chart_data: dict, price_type: str = "close") -> Dict[str, float]`
- Store two series:
  - `"FBGRX"`: Raw NAV close (`price_type="close"`).
  - `"FBGRX_TR"`: Adjusted NAV close (`price_type="adjclose"`).
- Explicitly include `"FBGRX"` and `"FBGRX_TR"` in the dataset export filter dictionaries:
  - `data/sp500_prices.json` and `data/world_prices.json` (annual year-end closes 1993–2024).
  - `data/sp500_quarterly_prices.json` and `data/world_quarterly_prices.json` (quarter-end closes 1993-Q1 to 2024-Q4).

### 2.3 Generic Benchmark Data Loader (`engine/data_loader.py`)
To avoid ticker-specific method explosion and ensure future mutual funds can be plugged in trivially, implement generic benchmark methods:
- `get_benchmark_level(benchmark: str, year: int) -> float`: Returns price return / NAV level.
- `get_benchmark_tr_level(benchmark: str, year: int) -> float`: Returns total return level.
- `get_benchmark_quarterly_level(benchmark: str, year: int, quarter: int) -> float`
- `get_benchmark_quarterly_tr_level(benchmark: str, year: int, quarter: int) -> float`
- `get_benchmark_dividend_yield(benchmark: str, year: int) -> float`

Backward compatibility aliases (`get_spx_level`, `get_spx_tr_level`, `get_msci_world_level`, `get_msci_world_tr_level`) delegate to these generic methods.
For convenience, add `get_fbgrx_level` and `get_fbgrx_tr_level` convenience aliases.

---

## 3. Calculation Engine & Scenarios (`engine/scenarios.py`)

### 3.1 Pre-Tax & After-Tax Series Generation
Using `calculate_benchmark_annual_series`:
```python
fbgrx_pre = calculate_benchmark_annual_series(
    pr_levels=fbgrx_pr_series,
    tr_levels=fbgrx_tr_series,
    tax_rate=rate,
    initial_capital=initial_capital,
    is_after_tax=False,
)
fbgrx_post = calculate_benchmark_annual_series(
    pr_levels=fbgrx_pr_series,
    tr_levels=fbgrx_tr_series,
    tax_rate=rate,
    initial_capital=initial_capital,
    is_after_tax=True,
)
```

### 3.2 Scenario Matrix Keys & Decoupling
In `engine/scenarios.py`, for every horizon ($H \in \{10\text{y}, 20\text{y}, 30\text{y}\}$), frequency ($F \in \{\text{Annual}, \text{Quarterly}\}$), and tax rate ($\tau \in \{0.0, 0.15, 0.20, 0.30, 0.37\}$):
- Generate scenario entries for FBGRX with:
  - Universe: `"FBGRX"`
  - Strategy: `"FBGRX"`
  - Description: `"Fidelity Blue Chip Growth Fund (FBGRX)"`
  - RowType: `"Mutual Fund"` (or `"Benchmark"`)
  - Lookup key format:
    `{horizon}_FBGRX_FBGRX_{frequency}_{tax_rate}`
    (e.g. `30y_FBGRX_FBGRX_Annual_30.0%`).
- Include annual trajectory values, drawdown series, CAGR, Max Drawdown, Tax Drag, and Alpha vs Strategy.

### 3.3 Trajectory & Drawdown Matrices (`TRAJECTORY_MATRIX` / `DRAWDOWN_MATRIX`)
To allow the interactive charts in Tab 2 to render the exact selected benchmark without label/data mismatches:
- Update `lookup_key` in `TRAJECTORY_MATRIX` and `DRAWDOWN_MATRIX` to include benchmark identification:
  `lookup_key = f"{u_label}_{b_label}_{f_label}"`
  For example:
  - `S&P 500_S&P 500_Annual`
  - `S&P 500_FBGRX_Annual`
  - `All World_MSCI World_Annual`
  - `All World_FBGRX_Annual`
  (and their quarterly equivalents).
- The 5th series column contains the specific benchmark trajectory (`S&P 500`, `MSCI World`, or `FBGRX`) corresponding to that key.

---

## 4. Google Apps Script Dashboard Updates (`engine/templates/gas/`)

### 4.1 Executive Summary Dropdown (`02_executive_summary.js`)
- Update Control 6 (Cell `D3`) data validation list:
  ```javascript
  var benchRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['S&P 500', 'MSCI World', 'FBGRX'], true)
    .setAllowInvalid(false)
    .build();
  d3.setDataValidation(benchRule);
  ```
- **Decoupled Key Expression** (avoids `#N/A` errors when cross-universe combinations are selected):
  ```javascript
  var benchKeyExpr = '$H$2 & "_" & IF($D$3="MSCI World", "All World_MSCI World", IF($D$3="FBGRX", "FBGRX_FBGRX", "S&P 500_S&P 500")) & "_" & $B$3 & "_" & ' + taxExpr;
  ```
- Spotlight Table Universe label (Cell `B12`):
  ```javascript
  sheet.getRange('B12').setFormula('=IF($D$3="MSCI World", "All World", IF($D$3="FBGRX", "US Large Growth", "S&P 500"))');
  ```
- KPI Card 2 dynamically displays:
  `= "Selected Benchmark Wealth (" & $D$3 & ")"`
- KPI Card 4 dynamically displays:
  `= "Annual Alpha vs Selected Benchmark (" & $D$3 & ")"`

### 4.2 Performance & Tradeoffs Sheet (`03_performance_tradeoffs.js`)
- Update Frequency Tradeoffs Section 2 (lines 139–141) to reference `$D$3` rather than hardcoding S&P 500 / MSCI World:
  ```javascript
  sheet.getRange('A' + trRow).setFormula('="Benchmark (" & \'Executive Summary\'!$D$3 & ")"');
  annKey = '\'Executive Summary\'!$H$2 & "_" & IF(\'Executive Summary\'!$D$3="MSCI World", "All World_MSCI World_Annual_", IF(\'Executive Summary\'!$D$3="FBGRX", "FBGRX_FBGRX_Annual_", "S&P 500_S&P 500_Annual_")) & ' + taxExpr;
  qtrKey = '\'Executive Summary\'!$H$2 & "_" & IF(\'Executive Summary\'!$D$3="MSCI World", "All World_MSCI World_Quarterly_", IF(\'Executive Summary\'!$D$3="FBGRX", "FBGRX_FBGRX_Quarterly_", "S&P 500_S&P 500_Quarterly_")) & ' + taxExpr;
  ```
- Dynamic Filter formulas for interactive charts (lines 251, 254):
  ```javascript
  sheet.getRange('A43').setFormula(
    '=FILTER(\'Scenario Data\'!$U$2:$Y, \'Scenario Data\'!$T$2:$T = (\'Executive Summary\'!$B$2 & "_" & \'Executive Summary\'!$D$3 & "_" & \'Executive Summary\'!$B$3))'
  );
  sheet.getRange('G43').setFormula(
    '=FILTER(\'Scenario Data\'!$AB$2:$AF, \'Scenario Data\'!$AA$2:$AA = (\'Executive Summary\'!$B$2 & "_" & \'Executive Summary\'!$D$3 & "_" & \'Executive Summary\'!$B$3))'
  );
  ```
  *(Uses open-ended ranges `$U$2:$Y` and `$AB$2:$AF` to prevent data truncation).*

---

## 5. CLI & Exporters (`run_backtest.py`, `engine/exporters/`)

### 5.1 Terminal Output Table
In `run_backtest.py`:
- In addition to S&P 500 and MSCI World, compute FBGRX annual and quarterly pre-tax and after-tax series.
- Render FBGRX rows in the terminal table:
  ```text
  │ FBGRX (Pre-Tax)                  │    ... │    ... │    ... │    ... │
  │ FBGRX (After-Tax)                │    ... │    ... │    ... │    ... │
  ```
- Expose CLI argument `--benchmark` with choices `['sp500', 'msci_world', 'fbgrx', 'all']` (defaulting to comprehensive display).

### 5.2 CSV Exporters (`engine/exporters/csv.py`, `pipeline.py`)
- Record FBGRX pre-tax and after-tax `StrategyResult` records in `summary_metrics.csv`.

---

## 6. Verification & Test Plan

1. **Data Ingestion Test**:
   - Verify `data/raw/benchmarks/FBGRX.json` contains valid monthly data from 1993 to 2024.
   - Verify `sp500_prices.json` and `sp500_quarterly_prices.json` include non-empty, strictly positive prices for `FBGRX` and `FBGRX_TR`.
2. **Unit Tests (`tests/test_mutual_funds.py` and `tests/test_scenarios.py`)**:
   - Test DataLoader methods for FBGRX annual and quarterly levels.
   - Verify `calculate_benchmark_annual_series` correctly computes pre-tax vs after-tax wealth, tax drag, and distributions for FBGRX.
   - Test `scenarios.py` builds correct keys and values for FBGRX across all 3 horizons and 5 tax tiers.
   - Update `tests/test_scenarios.py` row assertions (`RowType` in `("Strategy", "Index", "Mutual Fund")`, updated matrix lengths).
3. **Regression Tests**:
   - Run full existing test suite: `python3 -m unittest discover tests`.
   - Ensure all existing tests for S&P 500 and All-World continue to pass with zero regressions.
4. **End-to-End CLI Run**:
   - Execute `python3 run_backtest.py` and verify FBGRX displays correctly in terminal tables and exports without error.
   - Execute `python3 run_backtest.py --frequency quarterly` and verify quarterly metrics.
   - Generate `scripts/google_apps_script.js` and verify template syntax and dropdown definitions.
