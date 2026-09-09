# Design Specification: Dynamic Index Comparison Toggle & MSCI World Benchmark Integration

**Date**: 2026-09-09  
**Status**: Approved with Amendments  
**Topic**: Google Sheets Interactive Index Comparison Toggle & MSCI World Benchmark  

---

## 1. Executive Summary & Problem Statement

Currently, in the Google Apps Script spreadsheet output:
1. S&P 500 is output as duplicate rows in `Scenario Data` under both universes (`Universe = "S&P 500"` and `Universe = "All World"`), causing duplicate S&P 500 rows to display alongside active strategies in the Executive Summary dashboard table.
2. The user has no way to toggle index benchmarks on or off: S&P 500 is mixed directly into the active strategy rows even when the user only wants to compare Top 3 vs Top 5 vs Top 10 portfolios.
3. The All-World universe (comprising global mega-caps from MSCI World represented by ADRs/US equities) lacks its own natural benchmark (MSCI World Index) for side-by-side performance, tracking error, and tax comparison.

### Objectives
- Remove hardcoded/duplicate S&P 500 strategy rows from the core strategy view.
- Add an interactive **Compare Index** dropdown in the Executive Summary dashboard (`None`, `S&P 500`, `MSCI World`, `Both`), allowing instant show/hide of benchmark rows. Default value set to `"Both"` for instant contextual comparison with KPI Cards.
- Remove `S&P 500` from the **Strategy** dropdown filter so it strictly filters active portfolio selections (`All`, `Top 3`, `Top 5`, `Top 10`).
- Incorporate full historical 1993–2024 annual total return and price return data for the **MSCI World Index** (USD).
- Model both S&P 500 and MSCI World dynamically across all tax tiers ($0\%, 15\%, 20\%, 30\%, 37\%$) and horizons ($10\text{y}, 20\text{y}, 30\text{y}$).
- Keep benchmark rows clearly distinguished in styling and allow them to remain visible as comparison points even when filtering to a specific universe.
- Enhance KPI Card 2 to dynamically switch between S&P 500 Wealth and MSCI World Wealth depending on the active Universe filter.

---

## 2. Architecture & Data Model

### 2.1 Benchmark Market Data (`data/world_prices.json`)
We enrich `data/world_prices.json` with historical year-end index levels for the MSCI World Index from 1993 to 2024 (USD):
- `^MSCIWORLD_TR`: Gross Total Return levels (starting at base 1000.00 at year-end 1993, compounded with official annual returns).
- `^MSCIWORLD_PR`: Price Return levels (starting at base 1000.00 at year-end 1993, compounded with official annual returns).

Official annual returns applied (with 1994 calibrated to official USD total return +7.64% and price return +5.10%, yielding standard dividend yield ~2.54%):
| Year | Gross TR (%) | Price Return (%) | Implied Div Yield (%) |
|------|--------------|------------------|-----------------------|
| 1994 | +7.64% | +5.10% | 2.54% |
| 1995 | +21.03% | +18.25% | 2.78% |
| 1996 | +14.88% | +12.33% | 2.55% |
| 1997 | +16.14% | +12.69% | 3.45% |
| 1998 | +24.36% | +21.71% | 2.65% |
| 1999 | +25.43% | +24.27% | 1.16% |
| 2000 | -12.75% | -13.18% | 0.43% |
| 2001 | -16.48% | -17.85% | 1.37% |
| 2002 | -19.98% | -21.05% | 1.07% |
| 2003 | +33.39% | +30.01% | 3.38% |
| 2004 | +15.25% | +12.44% | 2.81% |
| 2005 | +10.15% | +7.42% | 2.73% |
| 2006 | +20.65% | +17.59% | 3.06% |
| 2007 | +9.80% | +6.55% | 3.25% |
| 2008 | -40.33% | -42.67% | 2.34% |
| 2009 | +30.79% | +26.65% | 4.14% |
| 2010 | +12.35% | +9.55% | 2.80% |
| 2011 | -4.95% | -8.01% | 3.06% |
| 2012 | +16.54% | +13.18% | 3.36% |
| 2013 | +27.37% | +24.10% | 3.27% |
| 2014 | +5.50% | +2.93% | 2.57% |
| 2015 | -0.32% | -2.74% | 2.42% |
| 2016 | +8.15% | +5.32% | 2.83% |
| 2017 | +23.07% | +20.11% | 2.96% |
| 2018 | -8.20% | -10.44% | 2.24% |
| 2019 | +28.40% | +25.19% | 3.21% |
| 2020 | +16.50% | +14.06% | 2.44% |
| 2021 | +22.35% | +20.14% | 2.21% |
| 2022 | -17.73% | -19.46% | 1.73% |
| 2023 | +24.42% | +21.77% | 2.65% |
| 2024 | +19.19% | +17.00% | 2.19% |

### 2.2 Data Loader Extensions (`engine/data_loader.py`)
- `get_msci_world_level(year: int) -> float`: Returns MSCI World price return level.
- `get_msci_world_tr_level(year: int) -> float`: Returns MSCI World total return level.
- `get_msci_world_dividend_yield(year: int) -> float`: Returns synthetic annual dividend yield.

### 2.3 Scenario Matrix Generation (`engine/scenarios.py`)
In `build_scenario_and_apps_script_data`:
- Strategy rows generated:
  - `Universe: S&P 500`: `Top 3`, `Top 5`, `Top 10` (Tag `RowType: Strategy`)
  - `Universe: All World`: `Top 3`, `Top 5`, `Top 10` (Tag `RowType: Strategy`)
- Index benchmark rows generated:
  - `Universe: S&P 500`, `Strategy: S&P 500`, `RowType: Index`
  - `Universe: All World`, `Strategy: MSCI World`, `RowType: Index`, `Alpha_vs_SPX: msci_post_liq_cagr - spx_post_liq_cagr`
- Within each `(tax_rate, horizon)` block, active strategies are appended first, followed by Index benchmarks.
- Headers in `SCENARIO_HEADERS` (16 columns, retaining PascalCase):
  `["LookupKey", "TaxRate", "Universe", "Horizon", "Strategy", "PreTaxCAGR", "AfterTaxCAGR", "PostLiqCAGR", "CumReturn", "FinalEquity", "TotalDividends", "MaxDD", "TotalTaxes", "TaxDrag", "Alpha", "RowType"]`

---

## 3. Google Sheets User Interface & Formulas

### 3.1 Header Control Layout (Executive Summary, Row 2)
Columns A through M:
- **A2:B2**: `Tax Rate:` [Dropdown: `0.0%`, `15.0%`, `20.0%`, `30.0%`, `37.0%`] (Default: `30.0%`)
- **C2:D2**: `Universe:` [Dropdown: `All`, `S&P 500 Only`, `All World Only`] (Default: `All`)
- **E2:F2**: `Strategy:` [Dropdown: `All`, `Top 3`, `Top 5`, `Top 10`] (Default: `All`) — *`S&P 500` removed*
- **G2:H2**: `Horizon:` [Dropdown: `All`, `10y`, `20y`, `30y`] (Default: `All`)
- **I2:J2**: `Compare Index:` [Dropdown: `None`, `S&P 500`, `MSCI World`, `Both`] (Default: `Both`, styled with `#FEFCBF`, bold, centered)
- **K2:M2**: Helper text: *"Filter universe, strategy, horizon, and dynamically toggle benchmark comparisons."*

### 3.2 Dynamic Multi-Criteria Table Filter Formula (`Executive Summary!A10`)
JavaScript string-escaped template:
```javascript
var filterFormula = '=IFNA(FILTER(\'Scenario Data\'!$C$2:$O, (\'Scenario Data\'!$A$2:$A <> "") * (ROUND(\'Scenario Data\'!$B$2:$B, 4) = ROUND($B$2, 4)) * (($H$2 = "All") + (\'Scenario Data\'!$D$2:$D = $H$2)) * (((\'Scenario Data\'!$P$2:$P = "Strategy") * (($D$2 = "All") + (\'Scenario Data\'!$C$2:$C = SUBSTITUTE($D$2, " Only", ""))) * (($F$2 = "All") + (\'Scenario Data\'!$E$2:$E = $F$2))) + ((\'Scenario Data\'!$P$2:$P = "Index") * ((($J$2 = "Both") * 1) + ((\'Scenario Data\'!$E$2:$E = $J$2) * 1))))), "No matching records found")';
```

### 3.3 Visual Distinction for Index Rows
Add a conditional formatting rule on the comparison table range (`A10:M52`) before the zebra striping rules:
- Formula: `=AND($A10<>"", $A10<>"No matching records found", OR($C10="S&P 500", $C10="MSCI World"), OR($E10="S&P 500", $E10="MSCI World"))`
- Formatting: Subtle slate-tint background (`#EDF2F7`) and italic font style, making index benchmark rows instantly identifiable.

### 3.4 KPI Summary Cards (Cards 1–5)
- **Card 1**: Top 5 Final Wealth (30y) (unchanged)
- **Card 2 (Enhanced)**:
  - Title: `=IF($D$2="All World Only", "MSCI World Wealth (30y)", "S&P 500 Wealth (30y)")`
  - Formula: `=IFERROR(INDEX('Scenario Data'!$J:$J, MATCH("30y_" & IF($D$2="All World Only","All World_MSCI World","S&P 500_S&P 500") & "_" & TEXT($B$2, "0.0%"), 'Scenario Data'!$A:$A, 0)), 0)`
  - Subtitle: `Passive buy & hold`
- **Card 3**: Top 5 Annual Return (30y) (unchanged)
- **Card 4**: 30-Year Excess Return (unchanged)
- **Card 5**: 30-Year Tax Drag (unchanged)

---

## 4. Terminal & CSV Outputs

- **Terminal Comparison Table**: In `run_backtest.py`, both `S&P 500` and `MSCI World` benchmark rows are displayed cleanly at the bottom of each horizon group.
- **CSV Summaries**: `summary_metrics.csv` includes both `S&P 500` and `MSCI World` results across simulated horizons with `alpha_vs_spx` populated.

---

## 5. Verification Plan

1. **Unit Tests**:
   - Verify `DataLoader.get_msci_world_level` and `DataLoader.get_msci_world_tr_level` across 1993–2024.
   - Verify `build_scenario_and_apps_script_data` outputs 16 columns and correct `RowType` values (`Strategy` vs `Index`).
   - Update test assertions in `tests/test_scenarios.py` and `tests/test_exporters.py` to match the 16-column schema.
   - Verify all tests pass (`python3 -m unittest discover tests`).
2. **Spreadsheet Validation**:
   - Check `node -c scripts/google_apps_script.js` for syntax correctness.
   - Confirm all dropdowns, conditional format rules, and formulas match the approved design.
