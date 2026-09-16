# Dual-Class Issuer Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the special-cased Alphabet consolidation logic with a generic, declarative issuer-level consolidation registry (`CONSOLIDATED_ISSUERS` / `consolidate_holdings()`), harmonize company labelling across all datasets to `"Alphabet Inc. (Class A & C)"`, publish a comprehensive as-filed vs. consolidated sensitivity table in `docs/DATA_PROVENANCE.md`, and update documentation to reflect issuer-level weighting.

**Architecture:** A declarative CUSIP/ticker-mapped issuer registry and a pure function `consolidate_holdings()` decouple multi-class consolidation from XML parsing. Datasets are re-generated with unified naming, a temporary measurement script records the scenario sensitivity in `docs/DATA_PROVENANCE.md` before removal, and the selection model in `README.md` is corrected.

**Tech Stack:** Python 3 standard library only (`xml.etree.ElementTree`, `json`, `pathlib`, `unittest`). Zero external dependencies.

## Global Constraints
- Zero external dependencies: standard library only.
- Strict self-financing invariant: `cash >= 0.0`.
- All prices and dividends split-adjusted.
- Canonical label: `"Alphabet Inc. (Class A & C)"` everywhere.
- Decoupled dual tax model: dividend income taxed at $\tau$, capital gains offset by capital loss carryforwards.

---

### Task 1: Core Consolidation Function & Declarative Issuer Registry

**Files:**
- Modify: `scripts/extract_ground_truth_from_sec.py:20-65, 335-360`
- Modify: `tests/test_raw_constituents.py:100-160`

**Interfaces:**
- Produces:
  - `CONSOLIDATED_ISSUERS: Dict[str, Dict[str, Any]]`
  - `CUSIP_TO_ISSUER: Dict[str, str]`
  - `TICKER_TO_ISSUER: Dict[str, str]`
  - `consolidate_holdings(raw_holdings: List[Dict[str, Any]], issuers: Optional[Dict[str, Dict[str, Any]]] = None, cusip_map: Optional[Dict[str, str]] = None, ticker_map: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]`

- [ ] **Step 1: Write the failing tests for `consolidate_holdings`**

Add unit tests to `tests/test_raw_constituents.py`:
```python
    def test_consolidate_holdings_alphabet(self):
        from scripts.extract_ground_truth_from_sec import consolidate_holdings
        raw = [
            {"name": "Alphabet Inc. Cl A", "ticker": "GOOGL", "cusip": "02079K305", "val": 200.0},
            {"name": "Alphabet Inc. Cl C", "ticker": "GOOG", "cusip": "02079K107", "val": 180.0},
            {"name": "Apple Inc.", "ticker": "AAPL", "cusip": "037833100", "val": 500.0},
        ]
        consolidated = consolidate_holdings(raw)
        self.assertEqual(len(consolidated), 2)
        by_ticker = {h["ticker"]: h for h in consolidated}
        self.assertIn("GOOGL", by_ticker)
        self.assertIn("AAPL", by_ticker)
        self.assertEqual(by_ticker["GOOGL"]["val"], 380.0)
        self.assertEqual(by_ticker["GOOGL"]["name"], "Alphabet Inc. (Class A & C)")
        self.assertEqual(by_ticker["GOOGL"]["cusip"], "02079K305")
        self.assertEqual(by_ticker["AAPL"]["val"], 500.0)

    def test_consolidate_holdings_synthetic_dual_class(self):
        from scripts.extract_ground_truth_from_sec import consolidate_holdings
        synthetic_issuers = {
            "SYNTH": {
                "primary_ticker": "SYNTH.A",
                "canonical_name": "Synthetic Corp. (Class A & B)",
                "primary_cusip": "99999A101",
                "member_cusips": {"99999A101", "99999B102"},
                "member_tickers": {"SYNTH.A", "SYNTH.B"},
            }
        }
        raw = [
            {"name": "Synthetic Cl A", "ticker": "SYNTH.A", "cusip": "99999A101", "val": 150.0},
            {"name": "Synthetic Cl B", "ticker": "SYNTH.B", "cusip": "99999B102", "val": 100.0},
            {"name": "Solo Corp", "ticker": "SOLO", "cusip": "111111100", "val": 300.0},
        ]
        # Verify dynamic map derivation when cusip_map / ticker_map are None
        consolidated = consolidate_holdings(raw, issuers=synthetic_issuers)
        self.assertEqual(len(consolidated), 2)
        by_ticker = {h["ticker"]: h for h in consolidated}
        self.assertIn("SYNTH.A", by_ticker)
        self.assertEqual(by_ticker["SYNTH.A"]["val"], 250.0)
        self.assertEqual(by_ticker["SYNTH.A"]["name"], "Synthetic Corp. (Class A & B)")
        self.assertEqual(by_ticker["SYNTH.A"]["cusip"], "99999A101")
        self.assertEqual(by_ticker["SOLO"]["val"], 300.0)

    def test_consolidate_holdings_ticker_fallback(self):
        from scripts.extract_ground_truth_from_sec import consolidate_holdings
        raw = [
            {"name": "Alphabet Inc.", "ticker": "GOOG", "cusip": "", "val": 100.0},
            {"name": "Alphabet Inc.", "ticker": "GOOGL", "cusip": "", "val": 150.0},
        ]
        consolidated = consolidate_holdings(raw)
        self.assertEqual(len(consolidated), 1)
        self.assertEqual(consolidated[0]["ticker"], "GOOGL")
        self.assertEqual(consolidated[0]["val"], 250.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_raw_constituents.TestRawConstituents.test_consolidate_holdings_alphabet`  
Expected: FAIL with `ImportError: cannot import name 'consolidate_holdings' from 'scripts.extract_ground_truth_from_sec'`

- [ ] **Step 3: Implement `CONSOLIDATED_ISSUERS` and `consolidate_holdings()` in `scripts/extract_ground_truth_from_sec.py`**

In `scripts/extract_ground_truth_from_sec.py`:
1. Define `CONSOLIDATED_ISSUERS`, `CUSIP_TO_ISSUER`, and `TICKER_TO_ISSUER`.
2. Implement `consolidate_holdings()` with dynamic map resolution and defensive `strip()`.
3. In `parse_xml_filing()`, replace the custom Alphabet block with:
```python
    consolidated = consolidate_holdings(raw_holdings)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_raw_constituents.TestRawConstituents.test_consolidate_holdings_alphabet tests.test_raw_constituents.TestRawConstituents.test_consolidate_holdings_synthetic_dual_class tests.test_raw_constituents.TestRawConstituents.test_consolidate_holdings_ticker_fallback`  
Expected: PASS

- [ ] **Step 5: Run existing XML filing test to ensure zero regression**

Run: `python3 -m unittest tests.test_raw_constituents.TestRawConstituents.test_xml_filing_exact_derivation`  
Expected: PASS

- [ ] **Step 6: Commit Task 1**

```bash
git add scripts/extract_ground_truth_from_sec.py tests/test_raw_constituents.py
git commit -m "feat: replace ad-hoc Alphabet branch with generic issuer consolidation"
```

---

### Task 2: Harmonize Company Labels Across All Scripts and Datasets

**Files:**
- Modify: `scripts/build_datasets_from_raw.py:21`
- Modify: `scripts/extract_ground_truth_from_sec.py:340-380`
- Rebuild: `data/sp500_constituents.json`, `data/sp500_quarterly_constituents.json`, `data/world_constituents.json`, `data/world_quarterly_constituents.json`
- Modify: `tests/test_raw_constituents.py`

- [ ] **Step 1: Write test asserting label consistency**

Add `test_company_label_consistency` in `tests/test_raw_constituents.py`:
```python
    def test_company_label_consistency(self):
        import json
        from pathlib import Path
        from scripts.generate_historical_weights import COMPANY_NAMES
        from scripts.build_datasets_from_raw import SP500_NAMES
        from scripts.extract_ground_truth_from_sec import CONSOLIDATED_ISSUERS

        canonical = "Alphabet Inc. (Class A & C)"
        self.assertEqual(COMPANY_NAMES["GOOGL"], canonical)
        self.assertEqual(SP500_NAMES["GOOGL"], canonical)
        self.assertEqual(CONSOLIDATED_ISSUERS["GOOGL"]["canonical_name"], canonical)

        repo = Path(__file__).resolve().parent.parent
        datasets = [
            "sp500_constituents.json",
            "sp500_quarterly_constituents.json",
            "world_constituents.json",
            "world_quarterly_constituents.json",
        ]
        for ds in datasets:
            with open(repo / "data" / ds, "r", encoding="utf-8") as f:
                content = json.load(f)
            # Scan all entries for GOOGL
            items = []
            if isinstance(content, dict):
                for v in content.values():
                    if isinstance(v, list):
                        items.extend(v)
            for item in items:
                if item.get("ticker") == "GOOGL":
                    self.assertEqual(item.get("name"), canonical, f"Failed in {ds}")
```

- [ ] **Step 2: Run test to verify it fails on old datasets**

Run: `python3 -m unittest tests.test_raw_constituents.TestRawConstituents.test_company_label_consistency`  
Expected: FAIL (identifies `"Alphabet Inc. (Class A)"` in datasets and `build_datasets_from_raw.py`)

- [ ] **Step 3: Update `SP500_NAMES` and re-run dataset builders**

1. Update line 21 of `scripts/build_datasets_from_raw.py`:
   `"GOOGL": "Alphabet Inc. (Class A & C)",`
2. Run: `python3 scripts/build_datasets_from_raw.py`
3. Run: `python3 scripts/generate_historical_weights.py`

- [ ] **Step 4: Run test to verify all datasets match canonical name**

Run: `python3 -m unittest tests.test_raw_constituents.TestRawConstituents.test_company_label_consistency`  
Expected: PASS

- [ ] **Step 5: Commit Task 2**

```bash
git add scripts/build_datasets_from_raw.py scripts/extract_ground_truth_from_sec.py data/sp500_constituents.json data/sp500_quarterly_constituents.json data/world_constituents.json data/world_quarterly_constituents.json tests/test_raw_constituents.py
git commit -m "data: harmonize Alphabet company label to 'Alphabet Inc. (Class A & C)'"
```

---

### Task 3: Measure As-Filed Sensitivity & Update Documentation

**Files:**
- Create: `scripts/measure_dual_class_sensitivity.py` (ephemeral)
- Modify: `docs/DATA_PROVENANCE.md`
- Modify: `README.md`
- Delete: `scripts/measure_dual_class_sensitivity.py`

- [ ] **Step 1: Create ephemeral sensitivity measurement script**

Create `scripts/measure_dual_class_sensitivity.py`:
- Parses 2020–2024 XML filings without consolidation to construct as-filed year-end weights and quarterly drifted candidates.
- Maps `GOOG` execution to `GOOGL` price and dividend series if it enters a book.
- Runs simulation across:
  - Selectors: `market_cap`, `performance`
  - Portfolios: Top 3, Top 5, Top 10
  - Horizons: 10y, 20y, 30y
  - Tiers: Pre-Tax (0%), After-Tax (30%)
  - Frequencies: Annual, Quarterly
- Formats comparison markdown table showing Consolidated CAGR, As-Filed CAGR, and Delta.

- [ ] **Step 2: Run sensitivity script and capture output table**

Run: `python3 scripts/measure_dual_class_sensitivity.py`  
Record output markdown table.

- [ ] **Step 3: Update `docs/DATA_PROVENANCE.md`**

Add Section 4.3.8 "Dual-Class Share Aggregation Sensitivity & Execution Convention":
- Document the exact CAGR numbers across all scenarios.
- Detail the execution convention: weights reflect combined A+C enterprise capitalization; execution maps to Class A (`GOOGL`).
- Document why Class A is the chosen vehicle (primary liquidity, continuous 2004 IPO history, voting rights) and note that the trading spread between A and C is typically <1.0%.

- [ ] **Step 4: Update `README.md`**

In `README.md`:
- Under **Executive Summary & Strategy Logic**, update rule 1 and 2 to clarify that constituent ranking and weighting operates at the company/issuer level (aggregating dual-class shares such as Alphabet Class A & C) rather than unadjusted single-share-class index lines.
- Under **Methodology Note**, update the note referencing the sensitivity table in `docs/DATA_PROVENANCE.md`.

- [ ] **Step 5: Delete ephemeral sensitivity script**

Delete `scripts/measure_dual_class_sensitivity.py` so no alternative path remains in the repository.

- [ ] **Step 6: Commit Task 3**

```bash
git add docs/DATA_PROVENANCE.md README.md
git commit -m "docs: publish dual-class sensitivity analysis and document execution convention"
```

---

### Task 4: Full Regression Verification & Pipeline Integrity Check

**Files:**
- None (verification only)

- [ ] **Step 1: Run complete test suite**

Run: `python3 -m unittest discover tests`  
Expected: All tests pass (238+ tests, 0 failures).

- [ ] **Step 2: Run annual backtest CLI runner**

Run: `python3 run_backtest.py --no-export`  
Expected: Clean exit code 0 with complete terminal summary tables.

- [ ] **Step 3: Run quarterly backtest CLI runner**

Run: `python3 run_backtest.py --frequency quarterly --no-export`  
Expected: Clean exit code 0 with quarterly terminal tables.

- [ ] **Step 4: Run quarterly expansion audit**

Run: `python3 scripts/audit_quarterly_expansion.py`  
Expected: Clean exit code 0, 96.0% out-of-sample accuracy confirmed.

- [ ] **Step 5: Check git status and diff**

Run: `git status`  
Expected: Clean working tree.
