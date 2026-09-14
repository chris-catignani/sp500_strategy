# Design Specification: Nasdaq 100 Benchmark Integration

## 1. Overview
This specification details the addition of the **Nasdaq 100** index to the benchmark comparison suite (GitHub Issue #19). The benchmark provides both pre-tax and after-tax total return tracking, basis adjustment, quarterly vs. annual dividend taxation, and terminal liquidation tax modeling across 10-year, 20-year, and 30-year horizons (1994–2024).

The benchmark is displayed under the primary name **"Nasdaq 100"** (without requiring an explicit ticker symbol in the UI), consistent with existing benchmarks ("S&P 500", "MSCI World", and "FBGRX").

## 2. Background & Motivation
GitHub Issue #19 requests adding QQQ / Nasdaq-100 as a benchmark option matching the pattern of existing benchmarks, including quarterly vs. annual dividends.

In the existing architecture:
- **S&P 500**: Tracks Price Return (`^GSPC`) and Total Return (`^SP500TR`). Implied dividend yield is derived as $\max(0, r_{\text{TR}} - r_{\text{PR}})$.
- **MSCI World**: Tracks Price Return (`^MSCIWORLD_PR`) and Total Return (`^MSCIWORLD_TR`). Calibrated against official MSCI historical index returns.
- **FBGRX**: Tracks NAV close (`FBGRX`) and Total Return (`FBGRX_TR` via split- and dividend-adjusted close).

For the Nasdaq 100:
- The official Price Return index (`^NDX`) has continuous trading data back to 1985.
- The official Total Return index (`^NDXT`) was launched in February 2006.
- The Invesco QQQ Trust (`QQQ`) launched on March 10, 1999, providing exact dividend and total return data from 1999 to 2005.
- Prior to 1999 (1993–1998), Nasdaq-100 companies paid negligible dividends (~0.2%–0.3%), which offset QQQ's expense ratio.

To support all three standard backtest horizons (10y, 20y, 30y from 1994 to 2024 with 1993 base year), we construct a continuous 31-year series combining `^NDX` (Price Return) and a composite Total Return series (`^NDXT`) anchored to official `^NDXT` (2006–2024), QQQ distributions (1999–2005), and `^NDX` price return (1993–1998).

## 3. Data Pipeline & Provenance

### 3.1 Raw Data Fetching (`scripts/fetch_raw_market_data.py`)
- Add `^NDX`, `^NDXT`, and `QQQ` to the benchmark fetch list.
- Store raw unmanipulated JSON responses in:
  - `data/raw/benchmarks/NDX.json`
  - `data/raw/benchmarks/NDXT.json`
  - `data/raw/benchmarks/QQQ.json`
- Commit raw JSON fixtures directly into Git so offline and sandboxed environments can build datasets deterministically without external network access.

### 3.2 Dataset Build & Mathematical Splicing (`scripts/build_datasets_from_raw.py`)
- Extract annual year-end closes and quarterly closes (Q1–Q4) for `^NDX` (Price Return).
- Build the composite Total Return series `^NDXT` using continuous backward chaining to prevent level jumps at boundary dates (e.g. 2005-Q4 / 2006-Q1):
  - **2006–2024**: Official `^NDXT` year-end and quarterly closes.
  - **Backward Chaining Formula (1993–2005)**:
    $$TR_{t-1} = \frac{TR_t}{1 + r_{\text{tr}, t}}$$
    where quarterly total return is defined linearly to match the engine's yield decomposition:
    $$r_{\text{tr}, t} = r_{\text{pr}, t} + y_t$$
    with:
    - $r_{\text{pr}, t} = \frac{NDX_t - NDX_{t-1}}{NDX_{t-1}}$
    - For 1999-Q2 to 2005-Q4: $y_t = \frac{\text{Div}_t}{P_{t-1}}$ using historical QQQ cash distributions. (QQQ launched March 10, 1999, so 1999-Q1 dividend yield is $0.0$).
    - For 1993-Q1 to 1999-Q1: nominal dividend yield $y_t = \frac{0.0025}{4} = 0.000625$ (0.25% annualized).
  - Annual levels are extracted directly from the corresponding Q4 closes: $TR_{\text{year}} = TR_{\text{year-Q4}}$.
- Add `"^NDX"` and `"^NDXT"` to `BENCHMARK_PRICE_KEYS` whitelist in `scripts/build_datasets_from_raw.py` so they are exported to:
  - `data/sp500_prices.json` (keys `^NDX`, `^NDXT`)
  - `data/sp500_quarterly_prices.json` (keys `^NDX`, `^NDXT`)
  - `data/world_prices.json` (keys `^NDX`, `^NDXT`)
  - `data/world_quarterly_prices.json` (keys `^NDX`, `^NDXT`)
- Document data sources, methodology, and rationale in `data/README.md`.

## 4. Engine Architecture & Integration

### 4.1 Data Loader (`engine/data_loader.py`)
- Add mappings in `DataLoader.BENCHMARK_KEY_MAP`:
  ```python
  "nasdaq_100": ("^NDX", "^NDXT"),
  "nasdaq 100": ("^NDX", "^NDXT"),
  "nasdaq100": ("^NDX", "^NDXT"),
  "^ndx": ("^NDX", "^NDXT"),
  "ndx": ("^NDX", "^NDXT"),
  "^ndxt": ("^NDX", "^NDXT"),
  "ndxt": ("^NDX", "^NDXT"),
  "qqq": ("^NDX", "^NDXT"),
  ```
- Implement benchmark accessor methods following canonical naming:
  - `get_nasdaq_level(year: int) -> float`
  - `get_nasdaq_tr_level(year: int) -> float`
  - `get_nasdaq_quarterly_level(year: int, quarter: int) -> float`
  - `get_nasdaq_tr_quarterly_level(year: int, quarter: int) -> float`
  - `get_nasdaq_quarterly_tr_level(year: int, quarter: int) -> float` (alias for backward compatibility)
  - `get_nasdaq_dividend_yield(year: int) -> float`

### 4.2 Quantitative Scenarios Matrix (`engine/scenarios.py`)
- In `compute_scenario_grid`:
  - Compute `nasdaq_benchmarks` (Annual) and `nasdaq_q_benchmarks` (Quarterly) for each `(tax_rate, horizon)` tuple.
  - Calculate metrics via `calculate_benchmark_annual_series`:
    - Pre-tax and after-tax CAGR
    - Post-liquidation CAGR and terminal wealth
    - Cumulative return and discrete maximum drawdown
    - Cumulative dividend taxes paid and tax drag
    - Alpha relative to S&P 500 after-tax return
  - Construct scenario row matrix keys:
    - Annual: `{h_label}_Nasdaq 100_Nasdaq 100_Annual_{rate_str}`
    - Quarterly: `{h_label}_Nasdaq 100_Nasdaq 100_Quarterly_{rate_str}`
  - Tag asset category as `"Index"`.
- In `build_default_scenario_data`:
  - Compute 30-year cumulative annual trajectory `nasdaq_traj_ann` and quarterly trajectory `nasdaq_traj_q`.
  - Append `("Nasdaq 100", nasdaq_traj_ann, nasdaq_traj_q)` to the `benchmarks` list.
  - This ensures `trajectory_matrix` and `drawdown_matrix` contain the keys required by the Google Sheets **Performance & Tradeoffs** tab (e.g. `S&P 500_Nasdaq 100_Annual`, `All World_Nasdaq 100_Quarterly`).

### 4.3 CLI Runner (`run_backtest.py`)
- Update `--benchmark` argument:
  ```python
  parser.add_argument(
      "--benchmark",
      type=str,
      choices=["all", "sp500", "msci_world", "fbgrx", "nasdaq_100", "nasdaq 100", "nasdaq100", "qqq"],
      default="all",
      help="Benchmark comparison display ('all', 'sp500', 'msci_world', 'fbgrx', 'nasdaq_100').",
  )
  ```
  Normalize benchmark filter so `nasdaq 100`, `nasdaq100`, and `qqq` map cleanly to `"nasdaq_100"`.
- Update `bench_configs` loop unpacking from a 4-tuple to a 5-tuple:
  `(freq_tag, s_bm, m_bm, f_bm, n_bm)`.
- Format Nasdaq 100 benchmark rows for terminal output tables when `--benchmark` matches `"all"` or `"nasdaq_100"`, labeling the universe column as `"Nasdaq 100"`.
- Generate pre-tax and after-tax `StrategyResult` records and output them into `outputs/summary_metrics.csv`.

### 4.4 Google Apps Script Templates (`engine/templates/gas/`)
- **`02_executive_summary.js`**:
  - Control 6 dropdown validation in cell `D3`: `['S&P 500', 'MSCI World', 'FBGRX', 'Nasdaq 100']`.
  - Cell `D7:F7`: `=IF($D$3="FBGRX", "Active mutual fund", "Passive buy & hold")`.
  - Cell `B12` (Asset Class): `=IF($D$3="MSCI World", "All World", IF($D$3="FBGRX", "US Large Growth", IF($D$3="Nasdaq 100", "US Large Tech", "S&P 500")))`.
  - Lookup formula `benchKeyExpr`:
    `$H$2 & "_" & IF($D$3="MSCI World", "All World_MSCI World", IF($D$3="FBGRX", "FBGRX_FBGRX", IF($D$3="Nasdaq 100", "Nasdaq 100_Nasdaq 100", "S&P 500_S&P 500"))) & "_" & $B$3 & "_" & ...`
- **`03_performance_tradeoffs.js`**:
  - Update `annKey` and `qtrKey` formulas to support `"Nasdaq 100_Nasdaq 100_Annual_"` and `"Nasdaq 100_Nasdaq 100_Quarterly_"`.

## 5. Invariants & Constraints
- **Zero External Dependencies**: Python standard library only (`urllib`, `json`, `math`, `unittest`, `dataclasses`).
- **Unleveraged Cash & Dual Tax Decoupling**: Dual tax settlement and FIFO lot rules remain unchanged.
- **Deterministic Offline Data**: Once datasets are generated, the engine executes 100% offline without external network access.

## 6. Verification Plan & Test Adjustments

### 6.1 Automated Unit Tests
- New test module `tests/test_nasdaq_benchmark.py`:
  - Verify `DataLoader` retrieval of annual and quarterly levels for `^NDX` and `^NDXT` (1993–2024).
  - Verify distribution yield calculations across all years are non-negative.
  - Verify pre-tax and after-tax series generation via `calculate_benchmark_annual_series`.
  - Verify CLI execution: `python3 run_backtest.py --benchmark nasdaq_100` and `--compare-frequencies`.

### 6.2 Existing Test Assertions Update
- Update `tests/test_scenarios.py`:
  - `test_default_scenario_data`: Total scenario rows increases from 450 to 480 (due to 30 additional rows: 5 tax rates $\times$ 3 horizons $\times$ 2 frequencies for Nasdaq 100).
  - Trajectory matrix rows:
    - 2 universes $\times$ 4 benchmarks $\times$ 2 frequencies $\times$ 31 years = 496 rows (was 372 with 3 benchmarks).
    - Single universe = 248 rows (was 186).
  - Drawdown matrix rows: same dimension update (496 and 248).
- Update `tests/test_cli.py`:
  - Extend benchmark option test loops to include `"nasdaq_100"` and aliases (`"qqq"`).
- Run full test suite: `python3 -m unittest discover tests` to verify 100% test pass.
