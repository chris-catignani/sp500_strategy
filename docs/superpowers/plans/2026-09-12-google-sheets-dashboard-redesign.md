# Google Sheets Dashboard Redesign ("Scenario Spotlight") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Google Sheets Executive Summary dashboard into a focused "Scenario Spotlight" featuring dynamic user-driven KPI cards, an exact 3-row Head-to-Head comparison table against the benchmark, and an immediately visible metric glossary at row 14 with zero `#SPILL!` risk.

**Architecture:** Update `engine/templates/google_apps_script.template.js` (`buildExecutiveSummarySheet` and `recalculateSheet`) to replace the legacy 68-row spilling `FILTER()` table with deterministic `INDEX/MATCH` lookups for a user-selected strategy and benchmark, moving the glossary and methodology cards up to row 14 to fit on a single desktop screen.

**Tech Stack:** Python 3 standard library only, Vanilla Google Apps Script (JavaScript), Node.js (for syntax validation), `unittest`.

## Global Constraints

- **Zero External Dependencies**: Standard Python library only (`argparse`, `dataclasses`, `csv`, `json`, `math`, `unittest`).
- **Unleveraged Cash & Scaling Invariant**: Seed Capital must remain anchored at cell `$N$2` to maintain downstream formula compatibility across `SCALE_EXPR` and `Scenario Data`.
- **Zero Spill Risk**: Use deterministic `INDEX/MATCH` lookups instead of dynamic `FILTER()` formulas so the glossary at Row 14 is never blocked by `#SPILL!`.
- **Clean Single-Screen Fit**: The entire layout (header, controls, KPI cards, table, glossary, methodology) must occupy rows 1 to 25 (~600px height) without requiring vertical scrolling.

---

### Task 1: Update Exporter Tests for the Scenario Spotlight Layout

**Files:**
- Modify: `tests/test_exporters.py`

**Interfaces:**
- Consumes: `engine.exporters.generate_google_apps_script`
- Produces: Updated unit test suite asserting new layout headers, labels, and formulas in the generated Google Apps Script.

- [ ] **Step 1: Write the failing tests in `tests/test_exporters.py`**

Update `test_generate_google_apps_script` in `tests/test_exporters.py` to assert that the generated JavaScript includes the new Spotlight layout components and does NOT include the old spilling `FILTER()` formula:

```python
        # Test new Scenario Spotlight elements
        self.assertIn("HEAD-TO-HEAD PERFORMANCE & TAX SPOTLIGHT", js_code)
        self.assertIn("Benchmark:", js_code)
        self.assertIn("Net Advantage (Strategy vs", js_code)
        self.assertIn("KEY METRIC DEFINITIONS & GLOSSARY", js_code)
        self.assertIn("METHODOLOGY NOTE — REBALANCING, TAXES & DIVIDENDS", js_code)
        self.assertNotIn("FILTER('Scenario Data'!$C$2:$P", js_code)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python3 -m unittest tests/test_exporters.py
```
Expected: FAIL (because `HEAD-TO-HEAD PERFORMANCE & TAX SPOTLIGHT` is not yet in the template).

- [ ] **Step 3: Commit the test expectation changes**

```bash
git add tests/test_exporters.py
git commit -m "test: add assertions for scenario spotlight executive summary dashboard"
```

---

### Task 2: Implement "Scenario Spotlight" Executive Summary Dashboard

**Files:**
- Modify: `engine/templates/google_apps_script.template.js`

**Interfaces:**
- Consumes: `SCENARIO_DATA`, `SCALE_EXPR`, `BASE_INITIAL_CAPITAL`
- Produces: Updated `buildExecutiveSummarySheet(ss)` and `recalculateSheet()` functions.

- [ ] **Step 1: Replace `buildExecutiveSummarySheet` in `engine/templates/google_apps_script.template.js`**

Implement the full Scenario Spotlight specification:
- **Row 1**: Header Banner (A1:N1 merged).
- **Row 2**: 7 Parameter Controls:
  - Universe ($B$2): `['S&P 500', 'All World']` (default `'S&P 500'`).
  - Strategy ($D$2): `['Top 3', 'Top 5', 'Top 10']` (default `'Top 5'`).
  - Horizon ($F$2): `['10y', '20y', '30y']` (default `'30y'`).
  - Rebalance ($H$2): `['Annual', 'Quarterly']` (default `'Annual'`).
  - Benchmark ($J$2): `['S&P 500', 'MSCI World']` (default `'S&P 500'`).
  - Tax Rate ($L$2): `['0.0%', '15.0%', '20.0%', '30.0%', '37.0%']` (default `0.30` formatted as `0.0%`).
  - Seed Capital ($N$2): Positive number input (default `BASE_INITIAL_CAPITAL` formatted as `$#,##0`).
- **Rows 4–6**: 5 Dynamic KPI Cards with string-resilient tax rate coercion:
  `TAX_STR = IF(ISNUMBER($L$2), TEXT($L$2, "0.0%"), $L$2)`
  - Card 1 (A4:C6, Mint `#E6FFFA`): Strategy Final Wealth
  - Card 2 (D4:F6, Slate `#EDF2F7`): Benchmark Wealth
  - Card 3 (G4:H6, Ice Blue `#EBF8FF`): Strategy Post-Liq CAGR
  - Card 4 (I4:K6, Forest Green `#F0FFF4`): Strategy Alpha vs Selected Benchmark
  - Card 5 (L4:N6, Coral `#FFF5F5`): Strategy Annual Tax Drag
- **Row 8**: Banner `HEAD-TO-HEAD PERFORMANCE & TAX SPOTLIGHT`.
- **Row 9**: 14 Table Column Headers.
- **Row 10**: Selected Strategy Row (`INDEX/MATCH` from `'Scenario Data'`, Cols G–P mapped to E–N).
- **Row 11**: Selected Benchmark Row (`INDEX/MATCH` from `'Scenario Data'`, Cols G–P mapped to E–N).
- **Row 12**: Net Advantage / Delta Row (`=(E10-E11)`, `=(I10-I11)`, `=(G10-G11)` for Alpha).
- **Row 14**: Banner `KEY METRIC DEFINITIONS & GLOSSARY`.
- **Rows 15–18**: 2-Column Glossary Grid (merged cells, height 22px each).
- **Row 20**: Banner `METHODOLOGY NOTE — REBALANCING, TAXES & DIVIDENDS`.
- **Rows 21–25**: Methodology bullet points (merged A:N, height 20px each).
- **Row heights and column widths**: Set exact widths for columns 1–14 and heights for rows 1–25.

- [ ] **Step 2: Update `recalculateSheet()` in `engine/templates/google_apps_script.template.js`**

Update cell references in `recalculateSheet()`:
- Tax Rate from `sheet.getRange('L2').getValue()`
- Universe from `sheet.getRange('B2').getValue()`
- Strategy from `sheet.getRange('D2').getValue()`
- Horizon from `sheet.getRange('F2').getValue()`

- [ ] **Step 3: Run exporter tests to verify they pass**

Run:
```bash
python3 -m unittest tests/test_exporters.py
```
Expected: PASS.

- [ ] **Step 4: Verify generated JavaScript syntax with Node.js**

Run:
```bash
python3 -c "from engine.exporters import export_google_apps_script; export_google_apps_script('scripts/google_apps_script.js')" && node -c scripts/google_apps_script.js
```
Expected: Exit code 0 (valid JS syntax).

- [ ] **Step 5: Commit the dashboard implementation**

```bash
git add engine/templates/google_apps_script.template.js scripts/google_apps_script.js
git commit -m "feat: implement scenario spotlight layout in google apps script template"
```

---

### Task 3: Full End-to-End Verification & Backtest Regeneration

**Files:**
- Output: `scripts/google_apps_script.js`
- Test: Full test suite

- [ ] **Step 1: Run full test suite**

Run:
```bash
python3 -m unittest discover tests
```
Expected: All tests pass.

- [ ] **Step 2: Run CLI backtest to regenerate outputs**

Run:
```bash
python3 run_backtest.py
```
Expected: Successful execution and regeneration of outputs with zero warnings.

- [ ] **Step 3: Commit any regenerated artifacts**

```bash
git add scripts/google_apps_script.js outputs/
git commit -m "chore: regenerate script and backtest outputs with new dashboard layout"
```
