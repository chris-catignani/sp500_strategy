# Design Document: Consolidate Dual-Class Issuers at the Issuer Level (Issue #38)

**Date**: 2026-09-16  
**Status**: Approved  
**Author**: chris-catignani / Antigravity  
**Issue**: GitHub #38 (Step 2 of 6 in Quarterly & Historical Data Provenance)  
**Dependencies**: Depends on #39 (merged in PR #42). Next: #36.

---

## 1. Context & Problem Statement

In SEC regulatory filings for SPY (Form NPORT-P and predecessor forms), Alphabet Inc. is held and reported as two separate equity positions:
- **Class A**: CUSIP `02079K305`, Ticker `GOOGL` (with voting rights)
- **Class C**: CUSIP `02079K107`, Ticker `GOOG` (non-voting)

Similarly, S&P Dow Jones Indices ranks them as two separate index lines.

In this strategy engine, Alphabet's two share classes are consolidated into a single `GOOGL` constituent with combined enterprise market capitalization. This design choice is **load-bearing**:
- At year-end 2023, the filing reports:
  - #1 `AAPL` (7.030%)
  - #2 `MSFT` (6.980%)
  - #3 `AMZN` (3.451%)
  - #4 `NVDA` (3.055%)
  - #5 `GOOGL` / Alphabet Class A (2.065%)
  - #6 `META` (1.962%)
  - #7 `GOOG` / Alphabet Class C (1.753%)
- **Consolidated**, Alphabet's weight is $2.065\% + 1.753\% = 3.818\% \approx 3.82\%$, which moves Alphabet to **#3**, ahead of Amazon and NVIDIA. This establishes the 2024 Top 3 book (`AAPL`, `MSFT`, `GOOGL`).
- **As filed**, the 2024 Top 3 book would be `AAPL`, `MSFT`, `AMZN`. As reported in #34, this choice explains most of the -2.39pp swing in 10-year `Top_3_MarketCap` return.

### Existing Deficiencies
1. **Ad-hoc implementation**: Consolidation currently lives as an Alphabet-specific `if/else` filter inside `parse_xml_filing()` in `scripts/extract_ground_truth_from_sec.py`. If another dual-class issuer enters the top candidate universe (or in older filings parsed in #36 and #40), the rule will fail silently.
2. **Inconsistent company labelling**:
   - `scripts/generate_historical_weights.py:41` uses `Alphabet Inc. (Class A & C)`
   - `scripts/build_datasets_from_raw.py:21` uses `Alphabet Inc. (Class A)`
   - `scripts/extract_ground_truth_from_sec.py:342` uses `Alphabet Inc. (Class A & C Combined)`
3. **Execution convention undocumented**: The engine combines A+C for index weight and capital allocation, but trades against Class A price and dividend series (`GOOGL`). The rationale and tracking error implications must be formalized.
4. **Unrecorded sensitivity**: The exact sensitivity of all strategy scenarios to as-filed vs. consolidated rankings has not been permanently published in `docs/DATA_PROVENANCE.md`.
5. **README contradiction**: `README.md` states selection is by "S&P 500 index weight", but the index lists classes separately, whereas the engine consolidates them at the company/issuer level.

---

## 2. Core Decisions & Invariants

1. **Maintain Issuer-Level Consolidation**:
   - The strategy concentrates in the largest *companies*, not individual voting classes.
   - Dual-class shares represent economic claims on the same underlying cash flows and earnings.
   - Prevents structural degeneracy: without consolidation, a Top 3 or Top 5 portfolio could allocate multiple slots to the same corporate entity (e.g. holding both `GOOGL` and `GOOG`).
2. **Universal Rule via Declarative Issuer Registry**:
   - Replace the Alphabet-specific branch with a generic, CUSIP-keyed consolidation engine applied uniformly to any multi-class issuer.
3. **Single Canonical Company Label**:
   - Standardize across all scripts, datasets, and documentation on: **`Alphabet Inc. (Class A & C)`**.
4. **Execution Convention**:
   - Combined market-cap weighting from both classes; portfolio trade execution and dividend accounting mapped to the primary Class A line (`GOOGL`).
   - Documented in `README.md` and `docs/DATA_PROVENANCE.md`.
5. **Permanent Sensitivity Publication**:
   - Measure once across all primary scenarios (Annual & Quarterly, MarketCap & Performance, Top 3/5/10, 10y/20y/30y horizons, Pre-Tax & 30% After-Tax).
   - Record the full comparison table in `docs/DATA_PROVENANCE.md`.
   - Remove ephemeral comparison scripts afterwards.
6. **Zero External Dependencies**:
   - All code remains 100% Python 3 standard library.

---

## 3. Detailed Component Design

### 3.1 Declarative Issuer Registry (`scripts/extract_ground_truth_from_sec.py`)

Define the multi-class registry and lookup index:

```python
CONSOLIDATED_ISSUERS: Dict[str, Dict[str, Any]] = {
    "GOOGL": {
        "primary_ticker": "GOOGL",
        "canonical_name": "Alphabet Inc. (Class A & C)",
        "primary_cusip": "02079K305",
        "member_cusips": {"02079K305", "02079K107"},
        "member_tickers": {"GOOGL", "GOOG"},
    },
}

# Fast lookup by CUSIP
CUSIP_TO_ISSUER: Dict[str, str] = {
    cusip: issuer_key
    for issuer_key, spec in CONSOLIDATED_ISSUERS.items()
    for cusip in spec["member_cusips"]
}

# Fallback lookup by ticker when CUSIP is unavailable (e.g. historical N-30D text filings)
TICKER_TO_ISSUER: Dict[str, str] = {
    ticker: issuer_key
    for issuer_key, spec in CONSOLIDATED_ISSUERS.items()
    for ticker in spec.get("member_tickers", set())
}
```

### 3.2 Pure Consolidation Function (`consolidate_holdings`)

Implement `consolidate_holdings` as a pure, standalone function:

```python
def consolidate_holdings(
    raw_holdings: List[Dict[str, Any]],
    issuers: Optional[Dict[str, Dict[str, Any]]] = None,
    cusip_map: Optional[Dict[str, str]] = None,
    ticker_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Consolidate multi-class equity holdings at the issuer level.
    
    Sums valuations across classes for registered issuers, mapping to the primary
    ticker, CUSIP, and canonical name. All other holdings pass through unchanged.
    """
    if issuers is None:
        issuers = CONSOLIDATED_ISSUERS
    if cusip_map is None:
        cusip_map = CUSIP_TO_ISSUER
    if ticker_map is None:
        ticker_map = TICKER_TO_ISSUER

    aggregated: Dict[str, Dict[str, Any]] = {}
    passthrough: List[Dict[str, Any]] = []

    for h in raw_holdings:
        cusip = h.get("cusip", "")
        ticker = h.get("ticker", "")
        
        # Identify issuer by CUSIP, fallback to ticker
        issuer_key = cusip_map.get(cusip) or ticker_map.get(ticker)
        
        if issuer_key and issuer_key in issuers:
            spec = issuers[issuer_key]
            if issuer_key not in aggregated:
                aggregated[issuer_key] = {
                    "name": spec["canonical_name"],
                    "ticker": spec["primary_ticker"],
                    "cusip": spec["primary_cusip"],
                    "val": 0.0,
                }
            aggregated[issuer_key]["val"] += float(h.get("val", 0.0))
        else:
            passthrough.append(dict(h))

    result = passthrough + list(aggregated.values())
    return result
```

In `parse_xml_filing(xml_path)`:
Replace the custom Alphabet summation block with `consolidate_holdings(raw_holdings)`.
Then sort descending by `val` and assign ranks and weights as before.

### 3.3 Harmonization of Company Labels

1. **`scripts/build_datasets_from_raw.py`**:
   - Update `SP500_NAMES["GOOGL"] = "Alphabet Inc. (Class A & C)"`
   - Re-run dataset builder: `python3 scripts/build_datasets_from_raw.py`
   - Updates `data/sp500_constituents.json` and `data/sp500_quarterly_constituents.json` to uniformly reflect `Alphabet Inc. (Class A & C)`.
2. **`scripts/extract_ground_truth_from_sec.py`**:
   - Update ground-truth documentation strings and canonical names to `Alphabet Inc. (Class A & C)`.
3. **`scripts/generate_historical_weights.py`**:
   - Verify `COMPANY_NAMES["GOOGL"] = "Alphabet Inc. (Class A & C)"` matches.

### 3.4 As-Filed vs. Consolidated Sensitivity Analysis

Create an ephemeral measurement script `scripts/measure_dual_class_sensitivity.py`:
1. Build an alternative "as-filed" weights dataset where NPORT-P filings (2020–2024) do not consolidate `GOOGL` and `GOOG`.
2. Map execution for `GOOG` to `GOOGL` prices/dividends if it enters a book.
3. Run simulations across all primary dimensions:
   - Frequencies: Annual, Quarterly
   - Selectors: MarketCap, Performance
   - Portfolios: Top 3, Top 5, Top 10
   - Horizons: 10y (2014–2024), 20y (2004–2024), 30y (1994–2024)
   - Tax Tiers: Pre-Tax (0%), After-Tax (30%)
4. Generate markdown table of CAGR deltas: `Consolidated CAGR - As-Filed CAGR`.
5. Append the formatted table and analysis to `docs/DATA_PROVENANCE.md` under section 4.3.
6. Delete `scripts/measure_dual_class_sensitivity.py` per acceptance criteria ("alternative path removed afterwards").

### 3.5 Documentation Updates

1. **`README.md`**:
   - In **Executive Summary & Strategy Logic**, clarify rule 1 & 2:
     - State explicitly: *"Selection operates at the company/issuer level: dual-class share structures (such as Alphabet Class A & Class C) are consolidated into a single enterprise holding based on aggregated market capitalization, with execution mapped to the primary liquid share class (e.g. `GOOGL`)."*
   - In **Methodology Note**: update note on Alphabet share-class aggregation to explain the general issuer rule and reference the sensitivity table.
2. **`docs/DATA_PROVENANCE.md`**:
   - Add comprehensive subsection detailing:
     - The issuer consolidation architecture (`consolidate_holdings`, CUSIP mapping).
     - Execution convention: why Class A (`GOOGL`) is chosen (highest liquidity, voting rights, consistent price history since 2004 IPO) and why tracking error vs holding both is negligible (<1%).
     - The complete As-Filed vs Consolidated sensitivity table.

---

## 4. Testing & Verification Plan

1. **Unit Test for Issuer Consolidation (`tests/test_raw_constituents.py`)**:
   - Test `consolidate_holdings` directly with:
     - Real-world Alphabet holdings: verify Class A (`02079K305`) + Class C (`02079K107`) consolidate into `GOOGL` with summed value and name `"Alphabet Inc. (Class A & C)"`.
     - Synthetic multi-class issuer: define a secondary test issuer with synthetic CUSIPs (`99999A101`, `99999B102`), verify they consolidate into `SYNTH_A` with combined valuation.
     - Single-class holdings: verify they pass through with original CUSIP, name, ticker, and valuation unchanged.
2. **Company Label Consistency Test**:
   - Verify `COMPANY_NAMES["GOOGL"]` in `generate_historical_weights.py` and `SP500_NAMES["GOOGL"]` in `build_datasets_from_raw.py` match exactly.
   - Verify all entries for `GOOGL` in `data/sp500_constituents.json` and `data/sp500_quarterly_constituents.json` use `"Alphabet Inc. (Class A & C)"`.
3. **Filing Parsing Regression Test**:
   - Verify that 2020–2024 XML filing parsed top 20 tickers and weights match `historical_index_weights.json` exactly (already existing in `test_raw_constituents.py`).
4. **Full Test Suite**:
   - Run `python3 -m unittest discover tests` — all 235+ tests must pass.
