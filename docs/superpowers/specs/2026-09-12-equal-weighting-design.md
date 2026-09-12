# Design Document: Equal Weighting Rebalancing & Google Sheets Integration

## Context & Motivation
Currently, the constituent selection and rebalancing algorithm in the S&P 500 Top N backtesting engine allocates portfolio capital based on the relative market capitalization weights of the top $N$ companies ($w_i = W_i / \sum_{j=1}^N W_j$).
While the underlying selector classes (`MarketCapSelector` and `PerformanceSelector` in `engine/selector.py`) already support `weight_by="equal"`, this capability is not exposed through `resolve_selector()`, the CLI runner (`run_backtest.py`), the multi-horizon scenario matrix generator (`engine/scenarios.py`), or the interactive Google Sheets dashboard (`engine/templates/google_apps_script.template.js`).

This design adds equal weighting ($1/N$ per constituent) as a first-class feature across the engine, CLI, scenario generator, and Google Sheets dashboard.

## 1. Engine & CLI Architecture
1. **`engine/selector.py`**:
   - Update `resolve_selector(strategy_name: str, n: int = 5, weight_by: str = "market_cap") -> BaseSelector` to accept and validate `weight_by in ("market_cap", "equal")`.
   - Pass `weight_by=weight_by` when instantiating `MarketCapSelector` and `PerformanceSelector`.
2. **`run_backtest.py`**:
   - Add CLI argument `--weight-by` with choices `["market_cap", "equal"]` (default: `"market_cap"`).
   - Pass `weight_by=args.weight_by` to `resolve_selector()` when setting up simulations.
   - Include weighting mode in summary outputs, table headers, and exported trade log metadata.

## 2. Scenario Matrix & Data Architecture
1. **`engine/scenarios.py`**:
   - Define weighting dimensions: `[("market_cap", "Market Cap"), ("equal", "Equal Weight")]`.
   - Expand `pretax_cache` to `(univ, n, weight_by, freq, start_year, end_year)`.
   - Simulate both Market Cap and Equal Weight variations across all horizons (10y, 20y, 30y), universes (S&P 500, All World), constituent counts (3, 5, 10), rebalance frequencies (Annual, Quarterly), and tax rates (0.0%, 15.0%, 20.0%, 30.0%, 37.0%).
   - Add `Weighting` column to `SCENARIO_HEADERS` (18 columns total):
     `["LookupKey", "TaxRate", "Universe", "Horizon", "Strategy", "Weighting", "Frequency", "PreTaxCAGR", "AfterTaxCAGR", "PostLiqCAGR", "CumReturn", "FinalEquity", "TotalDividends", "MaxDD", "TotalTaxes", "TaxDrag", "Alpha", "RowType"]`
   - Key format for active strategies:
     `"{h_label}_{univ_label}_{strat_label}_{weight_label}_{freq_str}_{rate_str}"`
     (e.g., `"30y_S&P 500_Top 5_Equal Weight_Annual_30.0%"`)
   - Benchmark keys remain invariant to constituent weighting:
     `"{h_label}_{bench_universe}_{bench_name}_{freq_str}_{rate_str}"`

## 3. Interactive Google Sheets Dashboard (`engine/templates/google_apps_script.template.js`)
1. **2-Row Parameter Control Bar**:
   - **Row 2**:
     - `A2:B2`: Universe (`S&P 500` / `All World`)
     - `C2:D2`: Strategy (`Top 3` / `Top 5` / `Top 10`)
     - `E2:F2`: Weighting (`Market Cap` / `Equal Weight`)
     - `G2:H2`: Horizon (`10y` / `20y` / `30y`)
     - `I2:N2`: Quick summary badge
   - **Row 3**:
     - `A3:B3`: Rebalance (`Annual` / `Quarterly`)
     - `C3:D3`: Benchmark (`S&P 500` / `MSCI World`)
     - `E3:F3`: Tax Rate (`0.0%`, `15.0%`, `20.0%`, `30.0%`, `37.0%`)
     - `G3:H3`: Seed Capital (`$10,000`)
     - `I3:N3`: Helper guidance text
2. **Formula & Lookup References**:
   - `SCALE_EXPR` updated to reference `$H$3` instead of `$N$2`.
   - `taxExpr`: `'IF(ISNUMBER($F$3), TEXT($F$3, "0.0%"), $F$3)'`
   - `stratKeyExpr`: `'$H$2 & "_" & $B$2 & "_" & $D$2 & "_" & $F$2 & "_" & $B$3 & "_" & ' + taxExpr`
   - `benchKeyExpr`: `'$H$2 & "_" & IF($D$3="MSCI World", "All World_MSCI World", "S&P 500_S&P 500") & "_" & $B$3 & "_" & ' + taxExpr`
3. **Layout Adjustment**:
   - KPI scorecards: Rows 5–7.
   - Head-to-head Spotlight table: Rows 9–13.
   - Glossary: Rows 15–19.
   - Frozen rows: Top 3 rows (`freezeRows(3)`).
4. **Scenario Data Column Alignment**:
   - Since `Weighting` is added at Column 6, metric columns shift by +1 (PreTaxCAGR is Col H, AfterTaxCAGR is Col I, FinalEquity is Col L, etc.).
   - Secondary matrices shift: Trajectory Matrix starts at Col T (20), Drawdown Matrix at Col AA (27), Era Matrix at Col AH (34).

## 4. Verification Plan
- Unit tests for selector resolution with `weight_by`.
- CLI execution test with `--weight-by equal`.
- Scenario generation verification across all weighting schemes and lookup keys.
- Apps script generation and template syntax verification.
- Full test suite execution: `python3 -m unittest discover tests`.
