# Issue #10: Engine Metric Fixes, Benchmark Precision & HTML Deprecation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address calculation inconsistencies in the simulation engine, fix FBGRX 1.28 bps CAGR discrepancy, update PerformanceSelector to use dividend-inclusive trailing 1-year total returns, standardize tax drag and wealth metrics, document discrete drawdown sampling, and deprecate dead HTML visualization code.

**Architecture:** 
- In `engine/metrics.py`, update `calculate_benchmark_annual_series` to set $r_{\text{step}} = r_{\text{TR}}$ when `eff_tax_rate == 0.0`, and $r_{\text{step}} = r_{\text{TR}} - \text{yield}_t \times \text{eff\_tax\_rate}$ when after-tax, preventing NAV data noise from inflating pre-tax returns.
- In `scripts/build_datasets_from_raw.py`, update annual and quarterly constituent builders to factor in split-adjusted dividends for trailing 1-year returns, rebuild constituent datasets in `data/`, and clarify mega-cap selection scope in `engine/selector.py`.
- Reconcile `tax_drag` via `calculate_tax_drag` across `metrics.py`, `run_backtest.py`, `engine/scenarios.py`, and `engine/exporters/csv.py`, with explicit labels and docstrings for `pre_liquidation_wealth` vs `post_liquidation_wealth`.
- Document endpoint drawdown sampling in `calculate_max_drawdown`, `engine/terminal_view.py` table footer, and `engine/backtest.py`.
- Remove `scripts/build_dashboard_html.py` and its documentation references.

**Tech Stack:** Python 3 standard library only (`dataclasses`, `json`, `math`, `unittest`, `csv`, `pathlib`, `argparse`). Zero external dependencies.

## Global Constraints
- Zero external dependencies: Python 3 standard library only.
- Unleveraged cash invariant: `cash >= 0.0` at all times.
- Split-adjusted data invariant: 2024-12-31 baseline.
- Backward compatibility: All 154 existing unit tests must pass or be properly updated for total return consistency.

---

### Task 1: Delete Unused HTML Dashboard and Clean References

**Files:**
- Delete: `scripts/build_dashboard_html.py`
- Modify: `docs/superpowers/plans/2026-09-12-mutual-fund-fbgrx-comparison.md:224`

- [ ] **Step 1: Remove `scripts/build_dashboard_html.py`**
Remove the dead script `scripts/build_dashboard_html.py`.

- [ ] **Step 2: Clean documentation reference**
In `docs/superpowers/plans/2026-09-12-mutual-fund-fbgrx-comparison.md`, update line 224 to reference the main runner or Google Apps Script exporter instead of `build_dashboard_html.py`.

- [ ] **Step 3: Verify no other references exist**
Run `git grep "build_dashboard_html"` to ensure no remaining references.

---

### Task 2: Fix FBGRX Benchmark CAGR Discrepancy in `calculate_benchmark_annual_series`

**Files:**
- Modify: `engine/metrics.py:240-252`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: `pr_levels: Sequence[float]`, `tr_levels: Sequence[float]`, `tax_rate: float`, `is_after_tax: bool`
- Produces: `Dict[str, Any]` with `annual_returns`, `final_equity`, etc.

- [ ] **Step 1: Write failing test verifying exact pre-tax CAGR matches TR levels for FBGRX quarterly**
In `tests/test_metrics.py`, add `test_fbgrx_quarterly_pretax_cagr_discrepancy_zero`:
```python
    def test_fbgrx_quarterly_pretax_cagr_discrepancy_zero(self):
        """Verify mutual fund NAV data noise (r_TR < r_PR) produces 0 discrepancy with direct TR CAGR."""
        from engine.data_loader import DataLoader
        loader = DataLoader()
        s_yr, e_yr = 1994, 2024
        pr_levels = [loader.get_fbgrx_quarterly_level(s_yr, 4)]
        tr_levels = [loader.get_fbgrx_tr_quarterly_level(s_yr, 4)]
        for y in range(s_yr + 1, e_yr + 1):
            for q in (1, 2, 3, 4):
                pr_levels.append(loader.get_fbgrx_quarterly_level(y, q))
                tr_levels.append(loader.get_fbgrx_tr_quarterly_level(y, q))

        direct_cagr = calculate_cagr(tr_levels[0], tr_levels[-1], 30)
        bench_pre = calculate_benchmark_annual_series(
            pr_levels=pr_levels,
            tr_levels=tr_levels,
            tax_rate=0.0,
            initial_capital=10000.0,
            is_after_tax=False,
        )
        series_cagr = calculate_cagr(10000.0, bench_pre["final_equity"], 30)
        self.assertAlmostEqual(direct_cagr, series_cagr, places=7)
```

- [ ] **Step 2: Run test to verify it fails with the 1.28 bps difference**
Run: `python3 -m unittest tests/test_metrics.py -k test_fbgrx_quarterly_pretax_cagr_discrepancy_zero`
Expected: FAIL (difference is ~1.28 bps / 0.000128).

- [ ] **Step 3: Update `calculate_benchmark_annual_series` in `engine/metrics.py`**
In `engine/metrics.py`:
```python
        r_pr = (pr_curr - pr_prev) / pr_prev if pr_prev > 0.0 else 0.0
        r_tr = (tr_curr - tr_prev) / tr_prev if tr_prev > 0.0 else 0.0
        yield_t = max(0.0, r_tr - r_pr)

        if eff_tax_rate == 0.0:
            r_annual = r_tr
        else:
            r_annual = r_tr - yield_t * eff_tax_rate
        annual_returns.append(r_annual)
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests/test_metrics.py`
Expected: PASS.

---

### Task 3: Fix Performance Selector Total Return & Scope Clarification

**Files:**
- Modify: `scripts/build_datasets_from_raw.py:328-415, 498-555`
- Modify: `engine/selector.py:120-136`
- Modify: `tests/test_data_loader.py:191-208`
- Generate: `data/sp500_constituents.json`, `data/world_constituents.json`, `data/sp500_quarterly_constituents.json`, `data/world_quarterly_constituents.json`

- [ ] **Step 1: Update `scripts/build_datasets_from_raw.py` to calculate trailing 1-year total return including dividends**
- Update `extract_quarterly_dividends` to use `range(1993, 2025)` so 1993 quarterly dividends are available for 1994 rolling 4-quarter sums.
- In `build_quarterly_constituents`:
  Pass `quarterly_dividends: Dict[str, Dict[str, float]]`.
  For both dynamically drifted Q1–Q3 and re-anchored Q4:
  Compute the trailing 4 quarter dividend sum `div_1y`, and:
  `ret_1y = round((p_curr - p_1y_prior + div_1y) / p_1y_prior, 4) if (p_curr is not None and p_1y_prior is not None and p_1y_prior > 0) else 0.0`.
- In annual constituents for S&P 500 and World:
  `div_1y = all_dividends_data.get(ticker, {}).get(str_year, 0.0)`
  `ret_1y = round((p_curr - p_prev + div_1y) / p_prev, 4) if p_prev > 0 else 0.0`.

- [ ] **Step 2: Run `python3 scripts/build_datasets_from_raw.py` to regenerate constituent datasets**
Run offline dataset generation to update constituent files in `data/`.

- [ ] **Step 3: Update `tests/test_data_loader.py` consistency test**
Rename `test_price_return_consistency` to `test_total_return_consistency` and verify:
`expected_return = (p_curr - p_prev + div) / p_prev` matches `c.trailing_1y_return`.

- [ ] **Step 4: Clarify docstrings in `engine/selector.py`**
Update `PerformanceSelector` class and `select` method docstrings:
Clarify that it ranks constituents from the candidate mega-cap universe (the top market cap snapshot) by trailing 1-year total return (split-adjusted price appreciation plus cash dividends).

- [ ] **Step 5: Run unit tests**
Run: `python3 -m unittest tests/test_selector.py tests/test_data_loader.py`
Expected: PASS.

---

### Task 4: Standardize Tax Drag and Clarify Wealth Labels

**Files:**
- Modify: `engine/metrics.py:104-118, 120-172`
- Modify: `run_backtest.py:290, 345, 396, 453, 506, 563, 673`
- Modify: `engine/scenarios.py:134, 181, 303, 369, 443, 497`
- Modify: `engine/exporters/csv.py:14, 69-90`
- Modify: `engine/models.py:83-106`

- [ ] **Step 1: Standardize `calculate_tax_drag` usage across all runners and exporters**
In `engine/exporters/csv.py`:
Import `calculate_tax_drag` from `engine.metrics`.
Replace raw subtraction `pretax_cagr_map[key] - r.cagr` with `calculate_tax_drag(pretax_cagr_map[key], r.cagr)`.
In `run_backtest.py` and `engine/scenarios.py`:
Import and use `calculate_tax_drag` for all strategy tax drags and benchmark tax drags.

- [ ] **Step 2: Clarify docstrings and labels for `pre_liquidation_wealth` vs `post_liquidation_wealth`**
In `engine/models.py`, `engine/metrics.py`, and `engine/exporters/csv.py`:
Explicitly define:
- `pre_liquidation_wealth`: Portfolio valuation before final liquidation tax (matches `final_equity` in StrategyResult).
- `post_liquidation_wealth`: Cash remaining after full terminal liquidation of all held tax lots, netting embedded unrealized gains against unused loss carryforwards, and deducting terminal capital gains tax.
- `post_liquidation_cagr`: Compound annual growth rate based on `post_liquidation_wealth`.
- `tax_drag`: Difference between pre-tax CAGR and after-tax pre-liquidation CAGR.
- `terminal_tax_drag`: Difference between pre-liquidation CAGR and post-liquidation CAGR.

- [ ] **Step 3: Run exporter and metrics tests**
Run: `python3 -m unittest tests/test_metrics.py tests/test_exporters.py`
Expected: PASS.

---

### Task 5: Document Endpoint Drawdown Sampling

**Files:**
- Modify: `engine/metrics.py:56-70`
- Modify: `engine/backtest.py:646-657`
- Modify: `engine/terminal_view.py:120-128`
- Modify: `AGENTS.md`

- [ ] **Step 1: Document discrete sampling in `calculate_max_drawdown` docstring**
In `engine/metrics.py`, add explicit documentation in `calculate_max_drawdown`:
"Note: Drawdown is evaluated across the discrete periodic observations supplied in `series` (e.g. annual or quarterly rebalancing points), rather than continuous intra-period daily high/low valuations."

- [ ] **Step 2: Document discrete sampling in `engine/backtest.py`**
In `engine/backtest.py` near `valuation_series = ...` and `calculate_max_drawdown`, add explanatory comments documenting endpoint rebalance valuation sampling.

- [ ] **Step 3: Add footer notes in `format_terminal_table` in `engine/terminal_view.py`**
In `engine/terminal_view.py`, append informative footnotes below the ASCII table:
```
  * Note: Max Drawdown is measured at discrete rebalance observation dates (annual/quarterly).
  * Note: Pre-Tax and After-Tax CAGRs reflect pre-liquidation wealth; Post-Liq CAGR reflects full terminal liquidation.
```

- [ ] **Step 4: Update `tests/test_cli.py` for terminal view footnotes**
Ensure `tests/test_cli.py` checks for or tolerates the new footnotes.

- [ ] **Step 5: Run full test suite and backtest CLI**
Run `python3 -m unittest discover tests`
Run `python3 run_backtest.py`
Run `python3 run_backtest.py --frequency quarterly`
Run `python3 run_backtest.py --compare-frequencies`
Verify all exit successfully with clean outputs.

---
