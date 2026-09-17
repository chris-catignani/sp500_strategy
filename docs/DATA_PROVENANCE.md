# Historical Data Provenance & Methodology Specification

## 1. Executive Summary

This document establishes the official data provenance, sourcing methodology, corporate action adjustments, and verification standards for the S&P 500 Top N quantitative backtesting engine.

All historical constituent price, split, dividend, and benchmark index datasets used in this repository are derived from primary live market feeds and archived point-in-time index records. The raw API responses are permanently stored in `data/raw/` to ensure full transparency, immutability, and third-party auditability.

---

## 2. Primary Data Sources & Endpoints

### 2.1 Individual Equities & Benchmark Series
- **Primary Source**: Yahoo Finance Historical Chart & Corporate Actions API (`query1.finance.yahoo.com/v8/finance/chart/{symbol}`).
- **Secondary / Cross-Verification Source**: S&P Dow Jones Indices Historical Factsheets, Siblis Research S&P 500 Year-End Archives, and SEC Form 10-K filings.
- **Coverage Scope**:
  - **Start Date**: 1993-12-31 (providing the base year-end level for 1994 return and yield calculations).
  - **End Date**: 2024-12-31.
  - **Temporal Granularity**: Monthly candles (`interval=1mo`) with daily event resolution for corporate actions (`events=div,split`).
  - **Universe**: 51 point-in-time constituents + 2 benchmark indices (`^GSPC` Price Index, `^SP500TR` Total Return Index).

### 2.2 Ticker Universe (51 Equities)
| Category | Tickers |
| :--- | :--- |
| **Mega-Cap Tech & Semis** | `AAPL`, `MSFT`, `NVDA`, `AMZN`, `GOOGL`, `META`, `TSLA`, `AVGO`, `CSCO`, `INTC`, `IBM`, `HPQ`, `ORCL`, `QCOM`, `ADBE`, `NFLX` |
| **Financials** | `BRK.B`, `JPM`, `BAC`, `WFC`, `C`, `AIG`, `FNMA` |
| **Healthcare & Pharma**| `UNH`, `LLY`, `JNJ`, `PFE`, `MRK`, `AMGN`, `BMY`, `ABBV` |
| **Consumer & Retail** | `WMT`, `PG`, `HD`, `KO`, `MO`, `COST`, `DIS`, `MCD`, `PEP`, `PM` |
| **Energy & Industrials**| `XOM`, `CVX`, `GE`, `UPS` |
| **Telecom & Payments** | `T`, `V`, `MA`, `PYPL`, `VZ`, `CMCSA` |

---

## 3. Raw Data Architecture (`data/raw/`)

To guarantee data integrity and eliminate dependency on volatile external web connections during testing or execution, the repository maintains an immutable raw data cache:

```
data/raw/
├── benchmarks/
│   ├── GSPC.json          # S&P 500 Price Return Index (^GSPC) raw response
│   ├── SP500TR.json       # S&P 500 Total Return Index (^SP500TR) raw response
│   ├── MSCIWORLD.json     # MSCI World raw historical quarterly chart response
│   ├── URTH.json          # iShares MSCI World ETF (URTH) raw response
│   └── FBGRX.json         # Fidelity Blue Chip Growth Fund (FBGRX) raw response
├── corporate_actions/
│   └── spinoffs.json      # Raw corporate spinoff catalog (IRS Form 8937 / Section 355)
├── ground_truth/
│   ├── quarterly_ground_truth_holdings.json # Audited SEC EDGAR Form N-30D / NPORT-P holdings (1995–2024, 55 verified quarters across 120 labeled periods)
│   ├── sec_filings/                         # Archive of 69 filings: 56 SPY (20 NPORT-P XML, 35 historical annual & semi-annual reports, superseded Select Sector doc) + 13 Vanguard Index Trust December-31 annual reports
│   └── universe_gap_report.json             # Historical survivorship gap report (39 missing constituents at depth 30)
├── tickers/
│   ├── AAPL.json          # Apple Inc. raw response (timestamps, quotes, splits, dividends)
│   ├── BRK.B.json         # Berkshire Hathaway Class B (queried as BRK-B)
│   ├── T.json             # Post-1998 SBC / AT&T Inc. raw response
│   ├── T_CORP_HISTORICAL.json # Decoupled original AT&T Corp ("Ma Bell") historical series (1993–1998)
│   ├── UNH.json           # UnitedHealth Group Inc. raw response
│   └── ... (51 S&P 500 constituents; 67 files including World/benchmark tickers)
└── constituents/
    ├── historical_index_weights.json       # Authoritative S&P 500 point-in-time constituent factsheet weights (Top 20)
    └── world_historical_index_weights.json # Authoritative All-World point-in-time constituent factsheet weights
```

Downloaded chart files contain API responses with the following fields. The constituent
catalogs, corporate-action catalog, legacy `T_CORP_HISTORICAL.json` reconstruction,
and `att_1996_endpoint_valuations.json` are separately compiled inputs, not untouched
API responses. The endpoint manifest records the observations and sources used for
the 1996 reconciliation below.
- `timestamp`: Unix epoch seconds for each monthly observation.
- `indicators.quote[0].close`: Month-end closing price, normalized for splits as of the query date.
- `events.splits`: Dictionary of every stock split event, with timestamp `date`, `numerator`, `denominator`, and `splitRatio`.
- `events.dividends`: Dictionary of every cash dividend distribution, with ex-dividend `date` and split-adjusted `amount`.

### 3.1 Factsheet Provenance Architecture & Elimination of Circular Code Generation

Previously, constituent rosters and historical factsheet weights were embedded as hardcoded Python dictionaries within `scripts/build_datasets_from_raw.py`, which then serialized them to `data/raw/constituents/historical_index_weights.json`. This introduced circular code generation where a raw data artifact was being created by code rather than serving as the upstream authoritative input.

This architecture was strictly inverted to establish an unassailable data provenance chain:
1. **Authoritative Raw Source of Truth**: `data/raw/constituents/historical_index_weights.json` and `data/raw/constituents/world_historical_index_weights.json` are now the immutable upstream source files. They record point-in-time constituent rosters and S&P Dow Jones Indices / Compustat factsheet weights directly compiled from primary archives.
2. **One-Way Ingestion Pipeline**: `scripts/build_datasets_from_raw.py` reads directly from these raw JSON files into memory at runtime to drive dataset compilation (`data/sp500_constituents.json`, `data/sp500_quarterly_constituents.json`, etc.).
3. **Auditability & Zero Circularity**: By eliminating hardcoded constituent arrays in code, the data compilation script functions purely as a deterministic transformer. Any update to historical constituent weights must be made in the raw factsheet catalog, where it is subjected to integrity checks (`tests/test_dataset_integrity.py`).

#### 3.1.1 Historical Weight Sources & Institutional Validation Boundaries
- **Source Compilation**: Point-in-time index constituent weights were compiled from official S&P Dow Jones Indices year-end factsheets and verified against historical archives maintained by Siblis Research and SEC Form 10-K disclosures.
- **Institutional Access Constraints**: Audited daily observation-level constituent weights dating back to 1994 are proprietary intellectual property of S&P Global and CRSP (Center for Research in Security Prices), requiring expensive commercial academic licenses.
- **Verification Guarantee**: While free public endpoints cannot independently recalculate daily float-adjusted shares for 1994–2005, isolating these weights into static upstream JSON files guarantees immutability, programmatic auditability, and reproducible backtest results without undocumented hidden code shifts.

---

## 4. Normalization & Transformation Methodology

### 4.1 Split Adjustment Standard (Normalized to 2024-12-31)
All share prices and dividend-per-share values are normalized to share counts as of **December 31, 2024**.
- For any corporate stock split $k$ with ratio $S_k = \frac{\text{numerator}}{\text{denominator}}$, prices prior to the split date $T_{\text{split}, k}$ are scaled by:
  $$P_{\text{adj}, t} = \frac{P_{\text{unadj}, t}}{\prod_{T_{\text{split}, k} > t} S_k}$$
- In Yahoo Finance's `/v8/finance/chart` engine, `indicators.quote[0].close` is already normalized to current share terms by this exact formula.
- Year-end prices in `data/sp500_prices.json` are extracted from the December monthly candle (reflecting the final active trading session of December) and rounded to 2 decimal places (or 4 decimal places for base prices under \$1.00).

#### 4.1.1 The `close` Column Is Split- *and Spinoff-* Adjusted
The normalization above describes splits only, which is incomplete. Yahoo also back-adjusts
`indicators.quote[0].close` for **spinoff distributions**, scaling the entire pre-distribution
history so the ex-date price drop does not register as a loss. Measured against AT&T's
as-traded year-end closes:

| Year | As-traded | `T.json` `close` | Ratio |
|---|---:|---:|---:|
| 2019 | \$39.08 | \$29.52 | **1.324** |
| 2020 | \$28.76 | \$21.72 | **1.324** |
| 2021 | \$24.60 | \$18.58 | **1.324** |
| 2022 | \$18.41 | \$18.41 | **1.000** |
| 2023 | \$16.78 | \$16.78 | **1.000** |
| 2024 | \$22.77 | \$22.77 | **1.000** |

The factor is exactly 1.324 through 2021 and exactly 1.000 from 2022. The break is the
**WarnerMedia / Warner Bros. Discovery spinoff of April 8, 2022** (§4.6.3), applied by Yahoo as
a uniform 1/1.324 = 0.7553 scaling of all prior closes. `GE.json` carries the same signature
from its GEHC (2023) and GEV (2024) spinoffs.

**This is not a defect, and it must not be "corrected" out.** An adjusted price series combined
with a separately credited distribution (§4.6.2) is the correct total-return treatment, exactly
as for dividends; removing the adjustment while retaining the credit would double-count. Yahoo's
price factor (0.7553) and the IRS basis retention ratio (0.7623 for `T` → `WBD`) are different
quantities and are not expected to agree.

Two consequences follow:
- **Stored prices are not as-traded quotes.** Reconciling any series in `data/raw/tickers/`
  against a contemporaneous quote from a filing or news source requires applying the cumulative
  spinoff factor. This is why `T.json` reads \$21.62 for December 1995 where SBC's audited
  schedules imply \$57.50 (2.660 = 1.324 × 2, the additional March 1998 two-for-one split).
- **The factor is constant across a security's pre-distribution history, so it cancels in return
  calculations.** A slice of such a series is usable for returns without correction, provided it
  is never mixed with as-traded prices.

### 4.2 Cash Dividend Aggregation (Annual and Quarterly)
- In Yahoo Finance's raw chart payload, `events.dividends[i].amount` records the exact cash dividend per share, normalized to 2024-12-31 share terms, with Unix epoch `date` indicating the ex-dividend date.
- **Quarterly Granularity (`data/sp500_quarterly_dividends.json` & `world_quarterly_dividends.json`)**:
  - For each constituent, dividend distributions are assigned to their precise quarter:
    $$q = \lfloor(\text{month} - 1) / 3\rfloor + 1, \quad \text{key} = \text{"YYYY-Q"}q$$
  - Dividends are **never** estimated or divided by 4; they capture exact distribution dates and mid-year dividend raises in the specific quarter they occurred.
- **Annual Granularity (`data/sp500_dividends.json` & `world_dividends.json`)**:
  - For each stock and calendar year $t \in [1994, 2024]$, the total annual cash dividend per share $\text{DPS}_t$ is computed by summing all distributions where the ex-dividend date falls within that calendar year:
    $$\text{DPS}_t = \sum_{i: \text{Year}(T_{\text{ex}, i}) = t} \text{Amount}_i$$
- Cash dividends are pooled into available portfolio cash prior to rebalancing, preserving the self-financing cash invariant ($C \ge 0$).

### 4.3 Quarterly Pricing, Point-in-Time Constituent Composition & Drift Methodology

- **Quarterly Prices (`data/sp500_quarterly_prices.json` & `world_quarterly_prices.json`)**: Extracted from March, June, September, and December month-end candles. Q4 prices precisely match official year-end closes.

#### 4.3.1 Public Sourcing Constraints & Institutional Data Landscape
Free financial APIs (such as Yahoo Finance) reliably provide point-in-time adjusted prices, volumes, splits, and dividend distributions, but do **not** supply 30-year historical quarterly index constituent rosters, historical float-adjusted shares outstanding, or official intra-year index constituent weights (1994–2024).

Audited historical daily or quarterly index constituent compositions dating back to 1994 are proprietary intellectual property of index providers (S&P Dow Jones Indices, MSCI) and require costly institutional academic or commercial subscriptions (such as CRSP, Compustat, or direct S&P Capital IQ feeds).

#### 4.3.2 ETF Proxy Limitations (VOO & SPY SEC Filings)
To reconstruct historical quarterly constituent holdings without proprietary database licenses, passive ETF proxy strategies were evaluated:
- **Vanguard S&P 500 ETF (VOO)**: Launched in September 2010, VOO covers less than half of the 31-year (1994–2024) backtest horizon, rendering it incapable of providing holdings for the 1994–2009 period (which encompasses both the 2000–2002 Dot-Com crash and the 2007–2009 Global Financial Crisis).
- **SPDR S&P 500 ETF Trust (SPY)**: While SPY launched in January 1993, public historical portfolio snapshots prior to 2020 were filed only annually on Form N-30D (later Form N-CSR) at SPY's fiscal year-end. SPY's fiscal year ended December 31 through 1996 and September 30 from 1997 onward, so the 1995 and 1996 annual reports **are** December 31 primary sources, and every other pre-2020 annual filing is a September 30 snapshot. The year-end rosters remain unvalidated for 1994 and for 1997–2019 — but no longer for 1995 and 1996. SPY has never filed Form N-Q quarterly reports, leaving pre-2020 intermediate calendar quarter-ends (such as June 30) without quarterly regulatory filings in this filer. Separately, EDGAR holds a semi-annual Form N-30D at period 03-31 for every year 2010–2019, and **all ten are now archived and extracted** as the `2010-Q1` through `2019-Q1` periods, so March 31 is a primary-sourced quarter-end for that decade rather than a modeled one. Quarterly point-in-time filings across all four calendar quarter-ends still began only with Form NPORT-P XML in 2020. To provide verifiable ground truth without external dependencies, the repository archives 56 primary SEC EDGAR filings (20 NPORT-P XML, 35 historical annual and semi-annual reports, plus the superseded Select Sector document retained for auditability) and parses them via a pure Python standard-library parser (§4.3.6) to establish 55 verified quarters (across 120 total labeled periods, as unverified coverage now explicitly tracks every quarter of every year a filing exists for) and quantify the historical survivorship gap.

#### 4.3.3 Exact Mathematical Drift Mechanics
Between index reconstitution dates, a capitalization-weighted index does not transact or rebalance constituent shares; instead, passive constituent holdings naturally float and drift with price movements. The proportion of stock $i$ in index $M$ at quarter $q$ relative to base date $0$ (the preceding year-end factsheet anchor) satisfies the exact mathematical identity of passive index holding:

$$W_{i, q} = \frac{\text{Shares}_i \times P_{i, q}}{\sum_j \text{Shares}_j \times P_{j, q}} = \frac{\text{Shares}_i \times P_{i, 0} \times (P_{i, q} / P_{i, 0})}{\sum_j \text{Shares}_j \times P_{j, 0} \times (P_{j, q} / P_{j, 0})} = W_{i, 0} \times \frac{P_{i, q} / P_{i, 0}}{P_{\text{index}, q} / P_{\text{index}, 0}}$$

Where:
- $W_{i, 0}$ is constituent $i$'s official weight in the index at the prior year-end ($t-1$ Q4) factsheet anchor.
- $P_{i, q} / P_{i, 0}$ is the cumulative price return of stock $i$ from the year-end anchor through quarter $q$.
- $P_{\text{index}, q} / P_{\text{index}, 0}$ is the benchmark price index return over the same intra-year period.

In the absence of intermediate corporate share issuances or secondary offerings, index weights naturally follow this price-return ratio. This identity accurately models passive capitalization drift between official annual factsheet releases.

#### 4.3.4 Zero-Lookahead Candidate Policy & Official Inclusion Date Enforcement
To eliminate lookahead bias and maintain strict point-in-time realism:
1. **Prior-Year Factsheet Candidate Basis**: For quarters Q1, Q2, and Q3 of calendar year $t$, candidate rosters derive strictly from the verified year-end ($t-1$ Q4) index factsheet. No constituents from year $t$'s future Q4 factsheet are injected into prior quarters, ensuring that quarterly candidate evaluation at Q1–Q3 uses only information observable at that historical point in time.
2. **Official Inclusion Date Enforcement (`EFFECTIVE_INCLUSION_DATES`)**: Even when a company achieves mega-cap valuation status intra-year, it cannot enter the index prior to the index committee's official effective inclusion date. An explicit calendar lookup (`EFFECTIVE_INCLUSION_DATES`) enforces this quarter-end eligibility. For example:
   - **Tesla Inc. (`TSLA`)**: Officially added to the S&P 500 on **December 21, 2020**. TSLA is strictly excluded from candidate consideration in 2020-Q1, 2020-Q2, and 2020-Q3, preventing premature selection during early 2020.
   - **Netflix, Inc. (`NFLX`)**: Officially added to the S&P 500 on **December 17, 2010**, well before its 2024 Top 20 entry, so no candidacy exclusion applies to it.
3. **Q4 Factsheet Re-Anchoring**: At each Q4 (December 31), candidate rosters and constituent index weights re-anchor to the official S&P Dow Jones Indices year-end factsheet. This introduces any newly admitted constituents (such as TSLA in 2020-Q4) and resets drifted weights to audited benchmark reality, eliminating multi-year cumulative drift error.
4. **Pluggable Dataset Architecture**: [`DataLoader.load_quarterly_universe()`](../engine/data_loader.py) checks for registered quarterly universe files in `data/`, enabling external point-in-time constituent datasets to be dropped in without engine modifications.

#### 4.3.5 Quarterly Candidate Roster Expansion (Top 20 Universe) & Evidentiary Status
Evaluating candidate constituents for quarters Q1–Q3 from the prior December's point-in-time roster with passive price drift relative to the benchmark index ($W_{i,0} \times \frac{P_{i,q}/P_{i,0}}{P_{\text{index},q}/P_{\text{index},0}}$) is an intentional, principled design decision:
- **Prior Architecture & Top 12 Limitation**: Previously, candidate pools were restricted to the prior year-end Top 12 constituents. While sufficient for Top 3 and Top 5 strategies, a Top 10 strategy suffered truncation when equities ranked #13–#20 experienced massive intra-year momentum (e.g., Tesla in 2023, Walmart in 2008, Oracle in 2000).
- **Expanded Top 20 Universe**: The candidate universe is expanded to the **Top 20** largest companies in the S&P 500 at each year-end (1994–2024). Ranks #1–#12 are compiled from official S&P Dow Jones Indices year-end factsheets.
- **Ranks #13–#20 for 1994–2019 are unverified estimates.** No primary source in this repository reports a point-in-time capitalization for these positions. They are not derived from anything archived here, and the provenance table labels all 208 such rows `Unverified Estimate (No Primary Source)` with no underlying or anchor value. An earlier revision published a `Cap_i` for each row back-solved from the weight it was meant to explain, cited to "SEC Form 10-K & Point-in-Time Capitalization Archives"; that was circular and has been removed. Extracting the 35 historical Form N-30D Schedules of Investments (1995–2019; §4.3.6) provides audited ground truth that bounds intra-year drift and enumerates the survivorship gap. Because SPY's fiscal year ended December 31 through 1996 and September 30 from 1997 onward, the 1995 and 1996 annual reports **are** December 31 primary sources (providing the project's first independent year-end checks against the estimated candidate rosters; §4.3.6), whereas every other pre-2020 annual filing is a September 30 snapshot. Consequently, while 1995 and 1996 have now been checked against primary filings, these historical reports do not replace the 208 December 31 `Unverified Estimate` rows in the anchor tables, and year-end candidate rosters remain unvalidated for 1994 and 1997–2019.
- **Programmatic Form NPORT-P XML Derivation (2020–2024)**: For modern periods covered by primary SEC Form NPORT-P XML filings (2020, 2021, 2022, 2023, 2024), Top 20 candidates and exact weights are parsed directly from SPY's December 31 XML filings by [`scripts/generate_historical_weights.py`](../scripts/generate_historical_weights.py) with Alphabet Class A (`02079K305`) & C (`02079K107`) consolidated into `GOOGL`:
  - **2020-12-31**: Adobe Inc. (`ADBE`, #19, 0.76%) and Comcast Corp. (`CMCSA`, #20, 0.76%) enter the Top 20.
  - **2021-12-31**: Adobe Inc. (`ADBE`, #20, 0.67%) and Broadcom Inc. (`AVGO`, #19, 0.68%) enter the Top 20. Walmart (`WMT`) is heavily float-adjusted due to ~50% Walton family ownership, placing it at rank #40 (0.51% weight in SPY) and outside the Top 20.
  - **2022-12-31**: AbbVie Inc. (`ABBV`, #19, \$3.17B, 0.89%) and Merck & Co. Inc. (`MRK`, #20, \$3.12B, 0.88%) place ahead of Meta Platforms Inc. (`META`, #21, \$3.00B, 0.84%), correctly reflecting Meta's drawdown in 2022.
  - **2023-12-31**: Costco Wholesale Corp. (`COST`, #19, 0.73%) and Merck & Co. Inc. (`MRK`, #20, 0.69%) place in the Top 20.
  - **2024-12-31**: Netflix Inc. (`NFLX`, #20, 0.76%) enters the Top 20, displacing Oracle Corp. (`ORCL`), correctly reflecting Netflix's 2024 run.
- **Weight Derivation Table**: Every constituent rank, weight, formula, and source citation across all 31 years (620 rows) is exported to [`docs/historical_weights_table.csv`](historical_weights_table.csv), split by evidentiary status: **100 rows** `SEC Form NPORT-P Audited Holdings` (2020–2024, carrying the exact `valUSD` and `total_fund_val` the weight is computed from, and independently reproducible), **312 rows** `Official Factsheet Anchor` (ranks #1–#12), and **208 rows** `Unverified Estimate (No Primary Source)` (ranks #13–#20 outside 2020–2024). Only the 100 audited rows are reproducible from figures published in the table; `tests/test_raw_constituents.py` asserts that each one satisfies `round(valUSD / total_fund_val, 4) == weight`, and that no unverified row publishes a value.
- **Zero Lookahead Guarantee**: Deriving candidates from the prior year-end factsheet ensures no future information from year $t$'s Q4 factsheet leaks into early-year decisions.

#### 4.3.6 Primary Ground-Truth SEC EDGAR Regulatory Archive & Automated Parser
To eliminate reliance on third-party aggregators and establish regulatory ground truth, **56 primary SEC EDGAR regulatory filings** of the SPDR S&P 500 ETF Trust (`SPY`, CIK `0000884394`) are permanently archived in `data/raw/ground_truth/sec_filings/`:
- **Coverage Scope (1995–2024)**:
  - **Modern XML Filings (2020-Q1 through 2024-Q4, 20 Quarters)**: Form `NPORT-P` filings containing exact portfolio valuations (`valUSD`) and percentage weights (`pctVal`) for all 505 constituents.
  - **Historical Annual & Semi-Annual Reports (1995–2019, 35 Filings)**: Form `N-CSR` and `N-30D` filings containing the complete audited **Schedule of Investments**. **All 35 of these historical filings are extracted** (1995 and 1996 are December 31 snapshots reflecting SPY's pre-1997 fiscal year-end; 1997–2019 annual reports are September 30 snapshots; and the ten 2010–2019 semi-annual reports are March 31 snapshots). The 2010–2019 reports are HTML rather than fixed-width text and are read by a separate parser (§4.3.6).
  - **Annual vs. Semi-Annual Discrimination**: Both report types are Form `N-30D` filed under the same `COMPANY CONFORMED NAME` (`SPDR S&P 500 ETF TRUST`), so neither form type nor filer identity separates them — only `CONFORMED PERIOD OF REPORT` (03-31 vs 09-30) does. The semi-annual reports are therefore keyed `{year}-semi-annual` in `sec_annual_filings_manifest.json`, never in a bare-year annual slot, and `is_valid_spy_semi_annual_report()` asserts the period rather than the form. This is the check whose absence once placed the March 31, 2014 snapshot in the FY2014 annual slot.
  - **2004 Archive Correction**: Accession `0000950135-04-005558` (Form `N-CSR`, filed 2004-12-03) was previously archived as the FY2004 report. When strict total validation was implemented, the parser detected multiple schedule totals across nine distinct series (the Select Sector SPDR Trust) and found no SPY schedule in the document. The filing is retained in the archive for provenance auditability with `"spy_schedule": false` and is not a SPY source; the authentic SPY FY2004 Form `N-30D` annual report (accession `0000950135-05-000037`, filed 2005-01-05; amended by N-30D/A `0000950135-05-000099` with an identical schedule) was archived to replace it, parsing to a dollar-exact match against the filing's stated \$45,686,953,816 portfolio total.
  - **Verified Quarters & Coverage Accounting**: Verified quarters stand at **55** (20 modern NPORT-P quarters + 35 historical Form N-30D filings: 2 December 31 snapshots for 1995–1996, 23 September 30 snapshots for 1997–2019, and 10 March 31 snapshots for 2010–2019). The dataset labels **65 unverified historical periods** (120 periods tracked in total: 55 verified, 65 unverified). Archiving the ten semi-annual reports moved nine periods from unverified to verified (2014-Q1 was already verified), so every year 2010–2019 now has both a Q1 and a Q3 primary source. Remaining historical Q1/Q2/Q4 calendar quarters (plus 1994) lack regulatory filings in this filer and are labeled `[UNVERIFIED - No Filing]`.
- **Automated Standard-Library Parser (`scripts/extract_ground_truth_from_sec.py`)**:
  - `parse_xml_filing()` parses all 20 XML filings, reads `<formData><genInfo><repPdDate>` to verify the reporting date matches each calendar quarter end, aggregates Alphabet share classes, and extracts the audited Top 10.
  - `parse_n30d_filing()` parses the fixed-width **Schedule of Investments** across the 15 Form N-30D annual reports of 1995–2009 using standard library regex, joining company names wrapped across continuation lines and consolidating multiple positions in the same issuer.
  - `parse_html_schedule_filing()` parses the 20 HTML-era filings of 2010–2019 (ten annual, ten semi-annual) with `html.parser.HTMLParser`, reading each table row's cells and bounding the read by the same two anchors — the `Common Stocks / Shares / Value` column header and the closing `Total Common Stocks` row. It also drops page-break repeats: the 2019 filing reprints its last three rows at the top of the following page, which would have double-counted United Rentals, United Technologies and UnitedHealth for \$3,619,448,116. All three parsers return the same holdings shape and share one consolidation, ranking and weighting path (`_rank_schedule_positions()`), so the downstream treatment is defined once rather than once per filing format.
  - **Schedule Bounds & Exact Dollar Validation**: The parser strictly bounds its read to a single fund's Schedule of Investments and refuses any filing whose parsed constituent sum does not equal the total the filing itself states (`ScheduleParseError`). A consequence of this validation is that the previous parser silently dropped rows that lacked dot leaders (`...`). Under the new exact-matching parser, the Top 10 rosters for the three previously published periods (1999-Q3, 2000-Q3, 2008-Q3) are completely **unchanged**, but two published `fund_total_value_usd` figures changed:
    - **1999-Q3**: published before as \$12,950,461,905; now **\$13,163,739,469** (+\$213.3M / +\$213,277,564 of rows the old row regex could not match).
    - **2000-Q3**: published before as \$24,177,352,952; now **\$24,277,778,819** (+\$100.4M / +\$100,425,867, same cause).
    - **2008-Q3**: **\$92,935,982,898** (unchanged; the 2008 filing's rows all carried dot leaders, so the old parser already read it completely).
    Each new figure now equals, to the dollar, the total the filing itself states.
  - Programmatically generates [`data/raw/ground_truth/quarterly_ground_truth_holdings.json`](../data/raw/ground_truth/quarterly_ground_truth_holdings.json) with verification metadata, per-holding weights, and the fund's total portfolio value. All 35 historical extractions and 20 XML extractions are asserted by `tests/test_raw_constituents.py`, and `TestArchivedFilingCoverage` additionally requires that every `SPY_*.txt` on disk is claimed by an extraction registry and reconciles to its stated total, so an archived filing cannot silently parse to zero rows.
- **First Year-End Regulatory Validation (1995 & 1996)**:
  - **Substantive gain from correct period labeling**: SPY's fiscal year ended December 31 through 1996 and September 30 from 1997 onward. The 1995 and 1996 Form N-30D annual reports **are** December 31 primary sources, providing the project's first opportunity to validate year-end rosters against primary regulatory filings. The year-end rosters remain unvalidated for 1994 and for 1997–2019 (where pre-2020 filings are September 30 snapshots or unarchived). These filings raise validation coverage and enumerate the survivorship gap, but do not replace the 208 `Unverified Estimate` rows in the historical anchor tables.
  - **Both 1995 and 1996 disagree with estimated factsheet anchors**: Relabelled, these are the only pre-2020 December 31 rosters the project can check against a primary source, and **both disagree with the estimates** in `data/raw/constituents/historical_index_weights.json`:

| Year | Filing top 10 (Dec 31) | In filing, absent from estimate | In estimate, absent from filing | Overlap |
|---|---|---|---|---|
| 1995 | `GE T XOM KO MRK MO RD PG JNJ IBM` | `IBM`, `JNJ`, `RD` | `INTC`, `MSFT`, `WMT` | 7/10 |
| 1996 | `GE KO XOM INTC MSFT MRK MO RD IBM PG` | `IBM`, `RD` | `JNJ`, `T` | 8/10 |

  - **Persistence of `IBM` and `RD` discrepancies**: In both years, `IBM` and `RD` appear in the filing Top 10 but were missed by the estimated anchors. In the estimates, IBM was placed just outside the Top 10 at rank #13 (in both 1995 and 1996), whereas the filings place IBM at #10 (1995) and #9 (1996). Royal Dutch Petroleum (`RD`) is absent entirely from the project's 51-ticker universe (holding rank #7 in 1995 and #8 in 1996 in the filings), directly tying into the historical universe gap and survivorship findings detailed below.
- **Reconciliation Accuracy**:
  - Across all **55 verified regulatory filing quarters** (20 XML + 35 N-30D reports), average Top 10 match accuracy is **89.8%** (494/550). This is down from the 90.4% (416/460) measured over 45 quarters: nothing in the drift model changed, but archiving the ten March 31 semi-annual reports widened the sample by ten quarters that reconcile at **87.0%** (87/100), which is below the 90.4% the earlier sample averaged. The lower headline figure is a broader measurement, not a regression.
  - Across the **35 historical Form N-30D quarters (1995–2019)**, accuracy is **85.7%** (300/350). Within the HTML era the two report types score almost identically — the ten September 30 annual quarters reach 88.0% (88/100) and the ten March 31 semi-annual quarters 87.0% (87/100) — so being one quarter closer to the year-end factsheet anchor confers no measurable advantage. Both are well above the 1995–2009 fixed-width average of 83.3% (125/150). Misses in the March quarters are concentrated at ranks 8–10 and involve the same names that miss in the September quarters (for example `PG` and `WFC` displaced by `JPM` and `WMT` in 2013), i.e. boundary noise in the drift model's tail rather than a defect specific to the new snapshots.
  - Across all **20 modern Form NPORT-P XML quarters (2020–2024)**, the headline figure is **97.0%** (194/200).
  - **Out-of-sample: 96.0%** (144/150) across the **15 NPORT-P quarters that are genuine tests**. This is the figure that measures the drift model.
  - **Circular-Q4 Caveat**: The five modern Q4 filings (2020-Q4 … 2024-Q4) match 10/10 by construction because the year-end candidate lists are themselves parsed from those exact filings. `scripts/audit_quarterly_expansion.py` reports both figures and `CIRCULAR_Q4_PERIODS` names the excluded quarters. (Note: 1995-Q4 and 1996-Q4 candidate lists derive from estimated factsheet anchors, not from these Form N-30D filings, so they are genuine independent tests and not circular.)
- **Historical Universe Gap & Survivorship Bias Analysis**:
  - The 26 extracted filings reveal a persistent historical universe gap: constituents appearing in the filings' Top 30 that have no price series in `data/raw/tickers/`.
  - An exhaustive gap audit is published at [`data/raw/ground_truth/universe_gap_report.json`](../data/raw/ground_truth/universe_gap_report.json), enumerating **39 missing constituents** across the 1995–2019 filings (depth 30). The 2010–2019 annual filings add only two (`GILD`, `DWDP`) — by that era the project's universe covers nearly all of the index's largest constituents — and the ten semi-annual 03-31 filings archived under #54 add one more (`OXY`, rank #30 at 2011-Q1).
  - Four missing constituents reached the Top 10 in audited filings:
    - `RD` (Royal Dutch Petroleum Co., #7 peak rank, present in Top 10 across 1995, 1996, and 1997; 7 filings total)
    - `LU` (Lucent Technologies Inc., #7 peak rank in 1999-Q3; present in Top 30 across 4 filings: 1997–2000)
    - `EMC` (EMC Corp., #10 peak rank in 2000-Q3)
    - `SBC` (SBC Communications Inc., #10 peak rank in 2001-Q3; present in Top 30 across 10 filings)
  - **Nuanced Survivorship Framing**: A claim must not outrun its sources. Rather than characterizing all missing constituents as companies that later collapsed, the full 26-filing evidence reveals that survivorship effects operated bidirectionally. While telecom and tech crash casualties like `LU` (fell ~99% from peak) and `EMC` (fell ~96%) create upward survivorship bias when omitted during the 2000–2002 crash, major blue chips like Royal Dutch Petroleum (`RD`) and SBC Communications (`SBC`) were stable mega-cap operating companies that did not collapse. The universe gap represents systematic universe selection truncation across the pre-2010 era, rather than a pure distressed-firm attrition pattern. Issue #37 tracks closing this gap, decomposed into #55 (deriving price series for the **17** of these constituents that reach a filing's Top 20) and #56 (modelling terminal value for constituents that stop trading mid-horizon).

#### 4.3.7 Empirical Mid-Year Promotion Findings & Selector Sensitivity
The offline analysis script [`scripts/audit_quarterly_expansion.py`](../scripts/audit_quarterly_expansion.py) detects mid-year promotions, classifies each against the audited filings, and runs the side-by-side strategy comparison.

- **Mid-Year Promotions into Top 10**: Across 1994–2024 (124 quarters), the audit identifies **68 company-quarter promotion instances into the Top 10**, of which **24 originate from ranks #13–#20** and were locked out under the Top 12 restriction. A promotion is only evidence for the expansion if a point-in-time filing agrees the company was genuinely in the Top 10, so `classify_promotions()` tags each one:
  - **9 CONFIRMED**: `C` 1999-Q3 (#14 → #8), `ORCL` 2000-Q3 (#14 → #9; filing places Oracle at #8), `KO` 2002-Q3 (#15 → #9), `PG` 2002-Q3 (#16 → #10), `NVDA` 2021-Q2 and 2021-Q3 (#14 → #8), `TSLA` 2023-Q1/Q2/Q3 (#13 → #7/#6/#6).
  - **3 CONTRADICTED**: `VZ` 2001-Q3 (the drift model promotes Verizon from #16 → #10; the audited 2001-09-30 filing places SBC at #10 and Verizon outside the Top 10), `WMT` 2008-Q3 (the drift model promotes Walmart to #7; the audited 2008-09-30 Schedule of Investments places it at **#11**, outside the true Top 10), `GOOGL` 2009-Q3 (the drift model promotes Google to #10; the audited 2009-09-30 filing places Apple, Bank of America, and AT&T in the Top 10, leaving Google outside). These are false positives of the drift model and must not be cited as evidence for the expansion.
  - **12 UNVERIFIED**: promotions into quarters with no archived filing (`C` 1999-Q2, `ORCL` 2000-Q1/Q2, `VZ` 2001-Q1, `KO` 2002-Q2, `WMT` 2008-Q1/Q2, `GOOGL` 2009-Q2, `META` 2015-Q3, `VZ` 2016-Q1, `WMT` 2016-Q2, `BAC` 2017-Q3). These are plausible but uncorroborated.
- **Selector Sensitivity — two distinct effects**:
  - **Pool size alone** (`TrueTop12DataLoader` holds the constituent data fixed and truncates the Q1–Q3 candidate pool to the prior December's base 12, isolating the expansion):
    - `MarketCapSelector`: Top 3 and Top 5 are **unchanged** (0.00% delta at every horizon and tax tier) — a name ranked #13–#20 cannot reach a Top 5 book. Top 10 improves: 10y pre-tax 21.82% → 22.06% (+0.24%), 20y 13.57% → 14.16% (+0.59%), 30y 12.96% → 13.01% (+0.05%). **This is the expansion's real benefit.**
    - `PerformanceSelector`: the expansion is **negative in 8 of the 9 strategy/horizon cells**, averaging **-2.2%** pre-tax and reaching **-5.89%** (Top 10, 10y). Only Top 3 at 10y improves (+2.92%). A wider candidate pool gives a momentum selector more recent winners to choose among, and the largest recent gainer out of 20 large caps mean-reverts more often than the largest out of 12. An earlier revision of this document quoted the single positive cell as representative; the full table is printed by the audit script and should be read in full.
  - **Data correction (separate from pool size)**: re-deriving the 2021–2023 year-end weights from the NPORT-P filings changed the underlying constituent data, which moved the reported results independently of any pool-size effect. `Top_3_MarketCap` fell from 26.88% to 24.49% (10y), 16.39% to 15.29% (20y) and 15.16% to 14.43% (30y). The cause is year-end 2023: the prior data ranked NVIDIA #3 at 3.4%, while the filing shows NVIDIA at 3.06% behind Alphabet — so the Top 3 book no longer holds NVIDIA through its 2024 run.
- **Alphabet share-class aggregation**: SPY files Alphabet as two positions (Class A `02079K305`, Class C `02079K107`) and the S&P 500 ranks them as two separate constituents. This project consolidates them into one `GOOGL` position and executes at Class A prices. The choice is load-bearing, not cosmetic: at 2023-12-31 the filing reads AAPL 7.03%, MSFT 6.98%, AMZN 3.45%, NVDA 3.06%, Alphabet A 2.07%, META 1.96%, Alphabet C 1.75%. Consolidated, Alphabet is 3.82% and ranks #3, which determines the entire 2024 Top 3 book; read as filed, the 2023 Top 3 is AAPL/MSFT/AMZN. The consolidation applies to the 2020-2024 filing-derived weights, and since the 2010-2019 extraction it also applies to the **September 30** ground truth for 2014-2019, whose filings list both classes explicitly ("Google, Inc. (Class A)"/"(Class C)" in 2014, "Alphabet, Inc. Class A"/"Class C" from 2015) and are aggregated through the same `CONSOLIDATED_ISSUERS` registry. This does **not** close the 2014-2019 gap, which concerns the **December** factsheet anchor rows: a September filing cannot establish what a December anchor's share-class basis was, so those rows remain unverified (§4.3.8). A registered issuer that contributed only one class keeps the name the filing gave it, so SPY's 2006-2013 single-class Google positions are not relabelled "Alphabet Inc." years before the rename. See section 4.3.8 for coverage and the open gap.

#### 4.3.8 Dual-Class Issuer Consolidation & Execution Convention

In capitalization-weighted benchmark construction, indices often track separate share classes of multi-class issuers as distinct constituents (e.g., S&P Dow Jones and SPDR S&P 500 ETF Trust separate Alphabet Inc. into Class A `GOOGL` and Class C `GOOG`). From an equity market microstructure standpoint, each share class carries a distinct CUSIP and trading symbol. However, from an economic enterprise perspective, both share classes represent undivided equity claims on the same corporate issuer, backed by identical underlying operating earnings and cash flows.

To prevent artificial portfolio distortion—where an issuer's enterprise weight is arbitrarily fragmented across multiple slots or double-counted in concentrated books—the simulation engine standardizes on **company/issuer-level consolidation**:

**1. Capitalization Consolidation**

All publicly traded share classes of a registered issuer are aggregated into a single enterprise weight ($W_{\text{issuer}} = \sum_k W_{\text{class}_k}$) via `CONSOLIDATED_ISSUERS` and `consolidate_holdings()` in [`scripts/extract_ground_truth_from_sec.py`](../scripts/extract_ground_truth_from_sec.py).

- In the audited 2023-12-31 SPY Form NPORT-P filing, Alphabet is reported as Class A (CUSIP `02079K305`, 2.065%) and Class C (CUSIP `02079K107`, 1.753%).
- Combined, Alphabet's aggregate 3.818% (~3.82%) weight ranks **#3** behind Apple (7.03%) and Microsoft (6.98%), establishing the 2024 Top 3 book as `['AAPL', 'MSFT', 'GOOGL']`.
- Unconsolidated, Alphabet fragments into rank #5 (`GOOGL`) and rank #7 (`GOOG`), so an uncombined selection would hold Amazon (#3, 3.45%) instead.
- In Top 10 portfolios, unconsolidated treatment creates portfolio degeneracy by allocating two distinct slots to the same corporate enterprise, displacing the authentic 10th distinct company.

Consolidation is keyed on CUSIP, with ticker as a fallback. Because the registry is explicit, an issuer filed under two tickers but absent from `CONSOLIDATED_ISSUERS` would otherwise be ranked twice in silence; `_warn_unregistered_multi_class()` detects that case by looking for one issuer `name` resolving to several tickers, and raises a warning rather than passing it through. All 20 archived NPORT-P filings are clean under this check: Alphabet is the only multi-class issuer they report.

**2. Coverage, and the 2014–2019 Gap**

Consolidation can only be applied where the underlying source reports each share class separately. That condition holds for the 2020–2024 year-end weights, which are derived from SPY Form NPORT-P filings. It does not hold uniformly before that, and the series is **not** consistent across its full span. Note that the September-30 ground truth extracted from the 2014–2019 annual reports *is* consolidated (§4.3.6) — but it is September-dated, so it cannot settle what the December anchor rows below are based on:

| Years | Source | Share-class basis |
|---|---|---|
| 1994–2013 | Year-end factsheet anchors | Single class. Alphabet Class C was created 2014-04-03 by stock dividend; before that date Alphabet had one listed class, so there is nothing to consolidate. |
| 2014–2019 | Year-end factsheet anchors | **Undetermined.** No December-dated primary source for these years is archived in this repository. |
| 2020–2024 | SPY Form NPORT-P (December) | Consolidated, verified — `consolidate_holdings()` sums both CUSIPs. |

The 2014–2019 rows are the open problem. SPY's archived annual reports (fiscal year end September 30) do carry both Alphabet classes, and they show the two classes at comparable size:

| Schedule date | Class A | Class C | C/A |
|---|---|---|---|
| 2014-09-30 | $1,714,698,526 | $1,682,324,270 | 0.981 |
| 2015-09-30 | $1,822,232,272 | $1,773,130,574 | 0.973 |
| 2016-09-30 | $2,497,461,820 | $2,406,998,965 | 0.964 |
| 2017-09-30 | $3,264,369,036 | $3,260,913,576 | 0.999 |
| 2018-09-30 | $4,098,642,554 | $4,174,606,489 | 1.019 |
| 2019-09-30 | $4,061,358,997 | $4,090,422,764 | 1.007 |

*(Source: `data/raw/ground_truth/sec_filings/SPY_{2014_Q4,2015,2016,2017,2018,2019}_N-30D_*.txt`, Schedule of Investments. Note that `SPY_2014_Q4_N-30D_0001193125-14-428689.txt` carries `CONFORMED PERIOD OF REPORT: 20130930` in its SEC header, but every Schedule of Investments page in the document body is dated September 30, 2014; the header value is a filing-agent error and the body date governs.)*

A consolidated Alphabet weight should therefore sit close to twice its Class A weight. The committed 2014–2019 figures match neither multiple consistently — 2019 reads 2.70%, against roughly 1.65% for Class A alone and 3.30% consolidated — so their composition cannot be inferred from the numbers themselves, and the September ratios above cannot be projected onto a December anchor without a December source to check them against.

Rather than assert a consolidation that is not evidenced, these rows are published as unverified: in [`historical_weights_table.csv`](historical_weights_table.csv) their `methodology` reads `Official Factsheet Anchor (Share-Class Composition Unverified)` and their `source_citation` records that the weight may understate the consolidated issuer weight. Closing the gap requires acquiring a December-dated primary source for 2014–2019 and is tracked in issue #45.

The practical consequence is that Alphabet may be under-ranked in those years. If the committed weights are Class A only, a consolidated Alphabet would enter Top 3 and Top 5 books it is currently excluded from, and reported returns for the affected horizons would change. This is a known limitation of the published 1994–2019 results, not a settled result.

**3. Execution Convention**

The simulation engine aggregates all registered share classes into a single constituent with the canonical issuer label **`Alphabet Inc.`** and executes entirely through **Alphabet Inc. Class A (`GOOGL`)**. The label names the issuer and deliberately makes no claim about which classes a given year's weight covers, because—as the table above shows—that varies by year and belongs in per-row provenance, not in a global constant.

- **Primary Voting Rights & Historical Continuity**: Class A shares carry standard 1-vote-per-share governance and maintain an unbroken price and corporate action record dating to Google's August 2004 initial public offering. Class C shares (`GOOG`) were created in April 2014 via a stock dividend as non-voting equity.
- **Institutional Liquidity**: Class A represents the standard primary equity line for benchmark replication and institutional order routing.
- **Single-line execution**: Routing through one class avoids dual-lot tax tracking and a second set of corporate actions for what is one economic claim.

**Limitation**: only `GOOGL` prices are archived (`data/raw/tickers/GOOGL.json`); no `GOOG` price series is held in this repository. Any realized price spread between Class A and Class C is therefore outside the model, and its effect on returns is neither measured nor bounded here. No claim is made that the spread is negligible — that would require a Class C price series this repository does not have.


#### 4.3.9 Second-Filer December-31 Archive (Vanguard Index Trust, CIK `0000036405`)
SPY's fiscal year ended September 30 from 1997 onward (§4.3.6), so **no SPY filing anchors a December 31 price for 1997–2019**. That is a property of the filer, not of the regulatory record: other S&P 500 index funds file on a December 31 fiscal year. **Vanguard Index Trust** does, and its Schedule of Investments carries the same shares-and-value columns, so an exact year-end implied close follows from `value / shares` for any constituent it holds.

- **Archive scope**: 13 annual reports, fiscal years 1994–2006 (`VG500_*.txt` in `data/raw/ground_truth/sec_filings/`, catalogued in `vanguard_annual_filings_manifest.json`). Form `N-30D` through FY2002 and Form `N-CSR` from FY2003; fixed-width text through FY2003 and HTML from FY2004, both already handled by the parsers in §4.3.6. The span covers every year a constituent missing from `data/raw/tickers/` is required. FY1993 (`0000893220-94-000129`) exists and is unarchived because nothing requires it.
- **Full submissions, not inner documents**: each archived file is the complete `{accession}.txt` submission, because only that carries the SEC header. **`CONFORMED PERIOD OF REPORT` is the single field separating a December 31 annual report from a June 30 semi-annual one** — Vanguard files both as Form `N-30D` under the same `COMPANY CONFORMED NAME`, so neither form type nor filer identity distinguishes them. `scripts/download_vanguard_annual_filings.py` refuses and deletes any download whose stated period is not `{year}-12-31`, and `TestVanguardArchiveCoverage` re-asserts it against the documents on disk. This is the same failure mode that once placed a March 31 snapshot in an annual slot (§4.3.6).
- **Pinned accessions**: unlike the SPY archiver, which discovers filings by scanning EDGAR master indexes, every Vanguard accession is pinned in the script. The set was enumerated once from the submissions API and is closed, so discovery would add failure modes without adding information.
- **Two manifests, one directory**: both manifests are keyed by bare year, so a Vanguard entry in the SPY manifest would collide with the SPY filing for that year and silently displace it. The separation is asserted by test.
- **Amendments recorded, not archived**: the FY2001 `N-30D/A` (`0000932471-02-000470`) and FY2005 `N-CSR/A` (`0000932471-06-000605`) differ from their parents by **26 and 7 bytes** respectively — EDGAR header only — and carry identical Schedules of Investments. Archiving them would add ~8MB to record a 33-byte difference. They are noted in the manifest, following the SPY FY2004 precedent (§4.3.6).

##### Independent cross-filer validation (1995-12-31)
SPY's fiscal year ended December 31 through 1996, so its FY1995 annual report covers **the same date** as Vanguard's. Two unrelated registrants, independently audited, filed on different dates, reporting the same securities:

| Constituent | Vanguard-implied | SPY-implied | Delta |
|---|---:|---:|---:|
| Mobil Corp. (`MOB`) | \$112.00 | \$112.00 | \$0.0002 |
| GTE Corp. (`GTE`) | \$44.00 | \$44.00 | \$0.0000 |
| BellSouth Corp. (`BLS`) | \$43.50 | \$43.50 | \$0.0001 |
| Royal Dutch Petroleum (`RD`) | \$141.13 | \$141.13 | \$0.0048 |
| SBC Communications (`SBC`) | \$57.50 | \$57.50 | \$0.0001 |

Agreement to under half a cent across five securities, with residuals attributable to share-count rounding in the published schedules rather than to method error. This is the strongest available check on the implied-price method, and it is repeatable for 1996, the other year SPY filed a December 31 snapshot.

##### Derived dataset (`data/raw/ground_truth/vanguard_implied_prices.json`)
`scripts/extract_vanguard_prices.py` reads every schedule position in each archived filing and publishes **186 December-31 implied prices across 18 securities** (the 17 gap constituents, with Viacom split into its Class A and Class B listings). Each observation carries the accession number, report date, source file, matched issuer name, share count and reported value, so any figure is checkable against the filing it came from.

- **Deliberately not written into `data/raw/tickers/`.** That directory holds raw Yahoo Finance chart responses. A derived series stored in that shape would be indistinguishable from a vendor-sourced one, which is the confusion this document exists to prevent. Downstream consumption is by explicit reference to this dataset.
- **Validation is cross-schedule agreement, not a fund total.** Each filing contains several Vanguard funds holding the same securities, so a price is derivable independently from several different share counts and values. A **majority of comparably-sized positions** must agree to within the rounding their published precision admits — value is reported in thousands, so ±\$500 per position, or 500/shares per share. A position an order of magnitude smaller carries correspondingly more per-share noise and is reported but not used to corroborate.
- **Outliers are preserved, not averaged away.** One observation (Viacom Class B, 2005) has a single fund valuing a 1,532,521-share position at \$32.32 where three others — including the two largest — agree exactly at \$32.60. The majority price is published and the dissenting row is retained in `outlier_rows`.
- **Absences are explained.** Where a security is missing because it ceased to exist rather than because extraction failed, the dataset records the event: Mobil (merged into Exxon 1999-11-30), GTE (merged into Bell Atlantic 2000-06-30) and SBC (renamed AT&T Inc. after acquiring AT&T Corp. 2005-11-18). Their terminal treatment is issue #56.
- **Issuer names are not stable across years.** America Online and Time Warner were **separate listed companies** until the merger completed 2001-01-11, so a single name pattern spanning both eras conflates two securities; the patterns are year-bounded. WorldCom is bounded at 2000 for the same reason, having issued two tracking stocks in June 2001.

##### Split records (`data/raw/corporate_actions/splits.json`)
Implied prices are as-traded, so a series spanning a split is discontinuous until adjusted. Split records for the twelve registrants whose prices are derived here are catalogued with the filing each was read in, following the citation discipline of `spinoffs.json`. Each entry carries the CIK, accession number, form type and the **verbatim sentence** stating the split.

- **Scope**: only registrants with no usable vendor series. `RD` (via `SHEL.json`) and `SBC` (via `T.json`) are absent by design — those series already carry Yahoo's adjustment (§4.1.1).
- **Basis**: each series is adjusted to the share terms of its **final observation**, not to 2024-12-31 (§4.1). The published dataset states plainly that the adjusted figures are therefore *not* directly comparable to `data/raw/tickers/`.
- **`GTE` has no splits, and that is a finding, not a gap.** Its FY1999 Form 10-K contains no stock split for 1994–2000; the only "two-for-one" language in the document describes a pension service credit. The observed price series shows no halving across those years, corroborating the absence.

##### How each split record was established
Every record names its source type, because a ratio is only as good as what stands behind it.

- **`filing_quoted`** — a verbatim sentence read in the cited filing. Eighteen of the twenty registrants.
- **`none_found`** — the registrant's own filings were searched and no split was found in the window. `GM` and `GTE` are recorded this way. This is a finding, not an absence of effort: `GTE`'s only "two-for-one" language describes a pension service credit, and neither registrant's price series shows a discontinuity.
- **`vendor_event`** — `RD` alone. Royal Dutch was a foreign private issuer filing Form **20-F** rather than 10-K, and EDGAR's 20-F listing for that filer does not reach 1997, so the four-for-one split of 1997-06-01 comes from a vendor corporate-action feed rather than a filing.

The one vendor-sourced record is corroborated independently rather than taken on trust. Yahoo's `SHEL` series **is** Royal Dutch before 2005 (§4.3.9), so applying the split to the filing-derived as-traded price must reproduce that vendor close:

| Year | Filing-derived, adjusted | `SHEL.json` close |
|---|---:|---:|
| 1995 | \$35.28 | \$35.28 |
| 1996 | \$42.69 | \$42.69 |
| 1997 | \$54.19 | \$54.19 |
| 1998 | \$47.88 | \$47.88 |
| 2000 | \$60.56 | \$60.56 |
| 2001 | \$49.02 | \$49.02 |

Six years agree to the cent. The remaining two, 1994 and 1999, differ by about 0.2% because the fund values at its own year-end business day while the vendor's December close is the month's last trade, which are not always the same session. A wrong ratio would be out by a factor of four, so the check is decisive despite the tolerance.

##### A record that is deliberately incomplete
`T_CORP` (the pre-2005 AT&T Corp.) carries its 2002 one-for-five reverse split, but the same filing records the **AT&T Wireless split-off of 2001** and the **AT&T Broadband distribution to Comcast in 2002**. Those are distributions, not splits, and are not modelled in `spinoffs.json`. The note on the record says so: this registrant's series **understates its return across 2001–2002** until they are added. Recorded rather than silently carried, because the series otherwise looks complete.

##### Validation of the adjustment against a second filer
SPY reports September 30 and Vanguard December 31. Expressed in the same share terms, their ratio is one quarter's price move; a split missing from the records would instead appear as a ratio near 2.0 or 0.5, because one side would remain in pre-split terms. Across **73 comparisons spanning 1995–2006, 71 fall inside a normal quarterly range**. The two that do not are both Q4 2000 and are genuine:

| Security | SPY 09-30 | Vanguard 12-31 | Move |
|---|---:|---:|---:|
| Lucent (`LU`) | \$30.56 | \$13.50 | −56% |
| Sun Microsystems (`SUNW`) | \$58.37 | \$27.87 | −52% |

Lucent's own Form 10-K405 reports that quarter's range as **\$12.19–\$34.63**, independently corroborating the fall. Both are the dot-com crash rather than an adjustment defect, and the test bound is set to admit them.

##### Consumption by the dataset builder
`scripts/build_datasets_from_raw.py` merges these series into `data/sp500_prices.json` from a second input, alongside the vendor series it reads from `data/raw/tickers/`. The `T_CORP_HISTORICAL` splice (§4.5.3) is the existing precedent for a conditional second source.

- **A constituent has exactly one price source.** The merge raises rather than overwrite a vendor series, and a test asserts no derived ticker also has a file in `data/raw/tickers/`. The two are adjusted to different bases — Yahoo to the present, a delisted series to its own final trading date — so silently preferring one would produce a series that is internally inconsistent without saying so.
- **Only split-adjusted issuers are merged.** An issuer whose split record could not be established from a filing is excluded rather than carried as-traded, because a split inside the holding period would otherwise register as a price collapse that never happened.
- **No dividends are derived.** A Schedule of Investments reports holdings, not distributions. The dividend series for these issuers is **empty, not zero**: total return is understated for them, and the dataset records the figure as unknown rather than nil.
- **Annual only.** These are December 31 observations, so no quarterly series exists and the quarterly path cannot select these constituents. Vanguard also files a June 30 semi-annual report, which would support a second observation per year, but that is not archived here.

**This merge changes no backtest result.** None of these constituents appears in `constituents_by_year` in `data/raw/constituents/historical_index_weights.json`, so none can be selected. Correcting those rosters — the step that actually removes the survivorship bias — remains outstanding; the prices are now available for it.

**Implied prices are as-traded.** They are not split-adjusted, and interpreting them without each registrant's split record inverts the reading: Lucent (`LU`) 1997→1999 reads as a 20% decline as-traded, where the split-adjusted move is a **219% rise** across its April 1998 and April 1999 two-for-one splits (both stated in Lucent's own Form 10-K405, accession `0000950117-01-501896`). Derivation of split-adjusted series from this archive is tracked in #55.

#### 4.3.10 Audited December-31 Rosters from the Vanguard 500 Index Fund
§4.3.5 records that ranks #13–#20 for 1994–2019 are `Unverified Estimate (No Primary Source)`: no primary source in this repository reported a point-in-time capitalization for those positions. For **1994–2006 that is no longer true.** The Vanguard 500 Index Fund tracks the S&P 500, so its Schedule of Investments at each December 31 is an audited point-in-time roster of the index, and ranking it by market value yields year-end ranks and weights that are **read rather than estimated**. Published to `data/raw/ground_truth/vanguard_audited_rosters.json` by `scripts/extract_vanguard_rosters.py`.

- **Selection is by position count, not document order.** Each filing contains several Vanguard funds. In the FY2002 filing the *first* schedule belongs to a fund holding **148** stocks, which reconciles perfectly against its own stated total and is simply the wrong fund — so dollar-exact reconciliation alone cannot establish that the right schedule was read. Holding roughly five hundred stocks is the property that identifies an S&P 500 tracker, and both conditions are asserted by test.
- **Dollar-exact reconciliation, or the year is withheld.** A roster that will not reconcile is **not published with a caveat**, because a short read is indistinguishable from a complete one once it is in a dataset.
- **Coverage is complete: all thirteen archived filings reconcile**, spanning 1994–2006.
- **One holding is counted but not named.** The FY2004 filing contains a row whose issuer and share cells are blank **in the document as filed**, stating only a market value of \$24,416 thousand. Dropping it leaves the schedule short of the total the filing itself states; naming it would be invention. It is counted at its stated value and flagged `unidentified`, so the year reconciles with nothing made up. At rank #471 of 506 and 0.023% of the fund it cannot reach the Top 20, and a test pins that.
- **Sector subtotals are told apart arithmetically, not by layout.** A subtotal also renders as a lone figure, and counting one would double-count an entire sector. A subtotal restates what has already been counted, so it equals the running sum of positions since the previous subtotal; an unnamed holding does not. Testing the arithmetic rather than the surrounding markup keeps the rule exact across all three HTML filings.
- **Fund identification is by name and by size.** A schedule is skipped when its heading names another Vanguard fund (Growth Index, Value Index, Total Stock Market, Extended Market), and the selected schedule must hold a plausible S&P 500 position count. Both filters matter: reconciliation proves a schedule was read completely, not that the right schedule was read.

##### What the audited roster says that the estimate does not
At **2000-12-31** the filing places three constituents inside the Top 20 that the estimated roster omits entirely:

| Rank | Constituent | Weight | In estimated roster? |
|---:|---|---:|---|
| 12 | SBC Communications (`SBC`) | 1.38% | **No** |
| 16 | EMC Corp. (`EMC`) | 1.24% | **No** |
| 19 | Royal Dutch Petroleum (`RD`) | 1.11% | **No** |

This is the survivorship gap evidenced at a December 31 date rather than inferred from a September snapshot. The same filing places **Lucent (`LU`) at rank #60**, already collapsed from its #7 standing in SPY's September 1999 filing — so Lucent's contribution to the bias runs through the 1997–1999 year-ends, not 2000.

The published dataset therefore covers **twelve December-31 rosters spanning 1994–2006**.

**These rosters are the fund's holdings, not the index's published constituent weights.** A full-replication fund tracks the index closely, but its weights reflect its own positions and its total is its equity holdings rather than the index's float-adjusted capitalization. They are a far stronger basis than an unsourced estimate; they are not the index itself.

#### 4.3.11 Issuer Identity Across Filings (`data/raw/constituents/issuer_ticker_map.json`)
Filed issuer names are not stable, so the audited rosters (§4.3.10) cannot be read by name alone. A registrant is renamed (Philip Morris to Altria, SBC to AT&T Inc.), merges under a new name (Exxon to ExxonMobil, Citicorp to Citigroup), or is punctuated differently between two filings. Matching on the name splits one issuer into several or conflates two, and **both errors are silent**: an unmapped issuer simply does not appear in the candidate universe, which reintroduces survivorship bias through a lookup miss rather than a missing download.

The map resolves all **58 filed name variants** appearing in any 1994–2006 Top 20 to **46 distinct tickers**, and a test asserts that no Top-20 name goes unmapped.

- **A rename keeps one series.** Where the same registrant continues under a new name, both names map to the ticker whose price series covers the whole period — `Bell Atlantic` and `Verizon` to `VZ`, `BankAmerica` and `Bank of America` to `BAC`.
- **Distinct registrants keep distinct tickers, which resolves the AT&T collision from primary evidence.** §4.5 records that `T` conflates two companies and decouples them with a hand-built series. The filings settle it directly: **`AT&T Corp` and `SBC Communications` are listed as separate issuers in the same years**, so they are priced separately rather than one standing in for the other. Mobil and GTE likewise remain distinct from the registrants that absorbed them.

**Eight of the 46 tickers have no price series yet**: `AN`, `COP`, `GM`, `MOT`, `RD`, `SBC`, `TYC` and `T_CORP`. Each is present in the rosters with shares and market value, so each is derivable by the method in §4.3.9, and each additionally requires a split record cited to a filing before its series can be read as a return.

#### 4.3.12 Constituent Series Derived from the Audited Rosters
`scripts/derive_constituent_series.py` publishes `data/raw/ground_truth/derived_constituent_series.json`: year-end price series for constituents with no vendor price file, read from the audited rosters (§4.3.10) as market value divided by share count, with issuers resolved through the map in §4.3.11.

This **supersedes the name-pattern extraction** of §4.3.9 as the source of constituent series. The rosters are strictly better to read from: each reconciles dollar-exact to its filing's stated total, so a missing position is caught rather than silently skipped, and the map removes the per-ticker regexes that previously matched *Exxon Mobil* for Mobil and *DuPont Photomasks* for DuPont. **Where both methods produce a price they agree on every shared observation**, which is asserted by test and is what justifies the replacement.

One constituent has one price source. A ticker with a file in `data/raw/tickers/` is never derived over, because the two are adjusted to different bases and a series carrying both would give returns that depend on which source a consumer read.

##### Verifying a vendor series belongs to the registrant the filings name
Yahoo recycles a delisted company's symbol, so a clean-looking series is not evidence of identity — fetching `LU` today returns Lufax Holding (§3). The filings settle it. A filing's implied price divided by the vendor's adjusted close is that year's cumulative corporate-action factor: it holds flat for years, then steps by a split ratio. An unrelated company produces no such structure.

`COP`, `SLB` and `GILD` were fetched on this basis and verified before use:

| Ticker | Factor by year | Reading |
|---|---|---|
| `SLB` | 4.000 (1994–96) → 2.000 (1997–2005) → 1.000 (2006) | two-for-one splits in 1997 and 2006 |
| `GILD` | 4.000 (2004–06) | two two-for-one splits after 2006 |
| `COP` | 2.624 (2003–04) → 1.312 (2005–06) | two-for-one split in 2005; the residual 1.312 is the 2012 Phillips 66 spinoff, exactly the adjustment described in §4.1.1 |

Adding these three closes them in the survivorship gap report: **36 missing constituents at depth 30, of which 14 reach a Top 20**, down from 39 and 17.

### 4.4 Benchmark Total Return, Synthetic Yield & Observed Quarterly Levels
- Pre-tax benchmark returns are tracked directly via `^SP500TR` (S&P 500) and `^MSCIWORLD_TR` (MSCI World).
- **Observed Historical Quarterly Benchmark Levels (MSCI World)**: Linear interpolation between annual year-end anchors was eliminated and replaced with observed historical quarterly index closes from `data/raw/benchmarks/MSCIWORLD.json`. Intra-year quarterly returns are scaled to match official annual Q4 anchors while preserving the observed quarterly trajectory—faithfully reflecting real intra-year market shocks (such as the Q1 2020 COVID crash or Q3 2008 Lehman collapse).
- For after-tax benchmark comparisons, the dividend yield $y_t$ is determined dynamically from the relationship between Total Return and Price Return:
  $$r_{\text{tr}, t} = \frac{\text{TR}_t - \text{TR}_{t-1}}{\text{TR}_{t-1}}, \quad r_{\text{pr}, t} = \frac{\text{PR}_t - \text{PR}_{t-1}}{\text{PR}_{t-1}}$$
  $$y_t = \max(0, r_{\text{tr}, t} - r_{\text{pr}, t})$$
- For 1994, this yields:
  $$r_{\text{tr}, 1994} = \frac{575.71 - 568.20}{568.20} = +1.3216\%$$
  $$r_{\text{pr}, 1994} = \frac{459.27 - 466.45}{466.45} = -1.5393\%$$
  $$y_{1994} = 1.3216\% - (-1.5393\%) = 2.8609\% \approx 2.86\%$$

#### 4.4.1 MSCI World Benchmark: Synthetic Quarterly Total Return & Institutional Paywall Constraints
Historical 31-year daily/quarterly Gross Total Return index series for MSCI World (1994–2024) are commercial intellectual property of MSCI Inc. and require costly institutional licenses (such as MSCI Index Metrics, Bloomberg, or FactSet). Public APIs provide price returns or modern ETF proxies (e.g. URTH starting only in 2012).
To provide an unassailable benchmark without third-party subscriptions:
1. Observed quarterly price index levels from `data/raw/benchmarks/MSCIWORLD.json` provide the intra-year quarterly shape and volatility dynamics.
2. Intra-year quarterly returns are rescaled so their compound annual product matches audited annual total return targets.
3. The synthetic annual dividend yield is spread evenly across quarters ($y_t / 4$).
This methodology faithfully reflects discrete quarterly market drawdowns (e.g., Q3 2008 Lehman, Q1 2020 COVID) while strictly guaranteeing exact adherence to audited annual benchmark targets.

### 4.5 Security Decoupling: AT&T Corp ("Ma Bell") vs. SBC Communications (1993–1998)

#### 4.5.1 The Telecommunications Merger & Retrospective Ticker Collision
In modern market datasets, historical equity series are frequently retroactively reassigned following corporate mergers and acquisitions. A prominent instance occurs with ticker **`T`**:
- In November 2005, **SBC Communications Inc.** (formerly Southwestern Bell Corporation, one of the seven Regional Bell Operating Companies created by the 1984 DOJ breakup of AT&T) acquired its former parent corporation, **AT&T Corp** ("Ma Bell"), for \$16 billion.
- Following the merger, SBC Communications rebranded the consolidated enterprise as **AT&T Inc.** and adopted the legacy single-letter ticker symbol **`T`** on the New York Stock Exchange.
- Modern automated APIs (including Yahoo Finance `/v8/finance/chart/T`) link the pre-2005 ticker history of `T` to the financial statements, stock splits, and dividend distributions of the surviving legal entity (**SBC Communications**), rather than the original AT&T Corp.

#### 4.5.2 Point-in-Time Impact on S&P 500 Constituent Selection
From 1994 through 1998, the authentic mega-cap constituent ranking in the S&P 500 Top 10 was the original **AT&T Corp** ("Ma Bell"), not SBC Communications:
- Relying on SBC Communications' historical series artificially distorts constituent price returns, capitalization weights, and dividend cash flows for the telecom holding.
- To resolve this collision, the repository decouples the two corporate entities.

#### 4.5.3 Verified Decoupled Series (`T_CORP_HISTORICAL.json`)
The authentic historical market record for original AT&T Corp is isolated in `data/raw/tickers/T_CORP_HISTORICAL.json`:
- **Cash Dividends**: Verified split-adjusted distributions of **\$0.33 per quarter (\$1.32 per year)** across 1994–1998, reflecting Ma Bell's consistent quarterly \$0.33 payout.
- **Prices & Baseline Closes**: Verified historical month-end closes from 1993 through 1998, including 1993-Q1..Q3 baseline closes (\$52.50, \$54.00, and \$56.25) to prevent artificial capitalization drift spikes in early 1994.
- **Automated Splicing**: In `scripts/build_datasets_from_raw.py`, pre-1999 SBC data for `T` is purged, and the verified `T_CORP_HISTORICAL` record is spliced into the constituent series for 1993–1998. Data from 1999 onward transitions smoothly into the consolidated modern AT&T series.
- **The purged slice is SBC's authentic series and is recoverable.** The pre-1999 data discarded
  by the splice above is not spurious — `T.json` carries `firstTradeDate` 1983-11-21, the
  continuing Southwestern Bell / SBC registrant that took the `T` ticker on acquiring AT&T Corp
  in 2005. It reconciles to SBC's audited fund-schedule prices on a known constant (§4.1.1:
  1.324 from the 2022 WBD spinoff, × 2 before the March 1998 split). Correct for the AT&T Corp
  collision, it is the primary source for `SBC` as a distinct historical constituent, which is
  why `SBC` requires no external data acquisition under #55.

#### 4.5.4 AT&T Corporate Timeline & 1998–2006 Top 12 Absence
A rigorous audit of `historical_index_weights.json` reveals that ticker **`T` was NOT in the S&P 500 Top 12 from 1998 through 2006**:
- Following the 1996 Lucent Technologies spinoff and 1996 NCR spinoff, legacy AT&T Corp shrank rapidly in market capitalization and dropped completely out of Top 10/12 consideration by year-end 1998.
- During 1994–1997, the legacy series comes from `T_CORP_HISTORICAL.json`, with the explicit 1996 endpoint reconciliation below. Other legacy observations remain subject to the source-validation work in issue #25.
- Transitioning to modern SBC Communications data in 1999 therefore had **zero effect** on portfolio constituent selection or performance during the 1998–2006 window.
- When `T` re-entered the Top 12 roster in 2007, SBC Communications had already completed its \$16 billion acquisition of AT&T Corp (November 2005) and adopted the consolidated **AT&T Inc.** identity, ensuring complete continuity with modern corporate reality.

---

### 4.6 Statutory Corporate Spinoff Modeling (IRS Section 355 & Form 8937)

#### 4.6.1 Statutory Background & IRC Section 355
Under Internal Revenue Code (IRC) Section 355 and Treasury Regulations, a corporate division or spinoff meeting statutory requirements is treated as a **tax-free reorganization**:
- Shareholders receiving shares of a spun-off entity do not recognize taxable dividend income or immediate capital gain upon distribution.
- Pursuant to IRC Section 358 and IRS Form 8937 (*Report of Organizational Actions Affecting Basis of Securities*), the aggregate tax basis in the pre-distribution parent shares is allocated between the parent shares and the spun-off shares in proportion to their relative fair market values immediately following the distribution:
  $$P_{\text{basis, new}} = \text{round}(P_{\text{basis, old}} \times R_{\text{retention}}, 4)$$
  where $R_{\text{retention}} \in (0, 1)$ is the basis retention ratio reported on the issuer's Form 8937.

#### 4.6.2 Engine Simulation Mechanics & Invariant Preservation
In a disciplined Top N strategy, the portfolio cannot hold non-qualifying arbitrary spin-co equity positions without violating constituent universe constraints. The backtesting engine (`engine/backtest.py` and `engine/tax_lots.py`) implements an exact statutory two-step cash-realization and basis-adjustment model:
1. **Tax-Free Corporate Distribution (IRC § 355 & § 358)**:
   - In the quarter or year of the corporate action, the cash distribution per share is credited directly to available cash (`self.cash += shares_held * dist_per_share`), maintaining self-financing cash neutrality ($C \ge 0$).
   - **Zero Dividend Tax Withholding**: Qualifying Section 355 reorganizations are not dividends; zero dividend tax is withheld ($0.00 dividend tax drag).
   - **Cost Basis Allocation**: All open FIFO tax lots of the parent company are reduced by $R_{\text{retention}}$ via [`FIFOTaxLotManager.adjust_basis_ratio(ticker, ratio)`](../engine/tax_lots.py), while the remaining basis $B_{\text{child}} = \sum_{\text{lots}} \text{shares} \times (\text{old\_price} - \text{new\_price})$ is apportioned to the child shares.
2. **Immediate Monetization & Capital Gains Tax Settlement (IRC § 1001)**:
   - Because the portfolio strategy immediately sells the non-qualifying child shares for cash proceeds $G = \text{shares\_held} \times \text{dist\_per\_share}$, this monetization constitutes a taxable disposition under IRC § 1001.
   - The realized capital gain is computed as $\text{Realized Gain}_{\text{child}} = G - B_{\text{child}}$.
   - This realized gain is recorded in `FIFOTaxLotManager.current_annual_realized_gain` and nets against capital loss carryforwards during annual/quarterly rebalancing tax settlement, paying tax at the capital gains rate $\tau$. This preserves the fundamental invariant that all lifecycle economic gains are taxed without escaping taxation.

#### 4.6.3 Raw Corporate Spinoff Catalog (`data/raw/corporate_actions/spinoffs.json`)
The immutable catalog in `data/raw/corporate_actions/spinoffs.json` (compiled to `data/spinoff_distributions.json`) records the following verified historical corporate spinoffs:

| Ticker | Ex-Date | Spin-Co Ticker | Spin-Co Description | Dist / Share | Basis Retention ($R_{\text{retention}}$) | Statutory Filing |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **T** | 1996-09-30 | `LU` | Lucent Technologies Inc. | \$14.87 | 0.7201 (72.01%) | IRS Form 8937 / Section 355 |
| **T** | 1996-12-31 | `NCR` | NCR Corporation | \$2.10 | 0.9523 (95.23%) | IRS Form 8937 / Section 355 |
| **MO** | 2007-03-30 | `KFT` | Kraft Foods Inc. | \$21.90 | 0.6910 (69.10%) | IRS Form 8937 / Section 355 |
| **MO** | 2008-03-28 | `PM` | Philip Morris International Inc. | \$50.60 | 0.3040 (30.40%) | IRS Form 8937 / Section 355 |
| **T** | 2022-04-08 | `WBD` | Warner Bros. Discovery Inc. | \$5.81 | 0.7623 (76.23%) | IRS Form 8937 / Section 355 |
| **GE** | 2023-01-04 | `GEHC` | GE HealthCare Technologies Inc. | \$18.67 | 0.8165 (81.65%) | IRS Form 8937 / Section 355 |
| **GE** | 2024-04-02 | `GEV` | GE Vernova Inc. | \$35.38 | 0.6686 (66.86%) | IRS Form 8937 / Section 355 |

#### 4.6.4 Valuation Provenance & Child-Share Liquidation Pricing
Following the engine's immediate-liquidation convention for non-qualifying Spin-Co equity, cash distributions per share represent the product of the **share distribution ratio** and the **child-share market price** on the distribution date:

1. **AT&T / Lucent Technologies (`LU`, 1996-09-30)**:
   - **Distribution Ratio**: 0.324084 shares of Lucent common stock per AT&T share.
   - **Statutory Basis Allocation**: AT&T retained **72.01%** (`0.7201`), allocating **27.99%** to Lucent (IRS Section 358; [AT&T Official Shareholder Cost Basis Guide](https://investors.att.com/stockholder-services/cost-basis-guide/worksheet/att-corp)).
   - **Market Liquidation Price**: **\$45.875** ($45\frac{7}{8}$), the official NYSE closing price on September 30, 1996.
   - **Proceeds per Share**: $0.324084 \times \$45.875 = \$14.86735 \approx \mathbf{\$14.87}$.
   - **Basis versus valuation**: The issuer basis allocation is retained independently. The former $38.25 parent-price cross-check was unsupported and is removed; a tax allocation ratio is not evidence of an endpoint execution price.
2. **AT&T / NCR Corporation (`NCR`, 1996-12-31)**:
   - **Distribution Ratio**: 0.0625 shares of NCR common stock per AT&T share (1 share of NCR for each 16 AT&T shares).
   - **Statutory Basis Allocation**: AT&T retained **95.23%** (`0.9523`), allocating **4.77%** to NCR (IRS Section 358; AT&T Shareholder Cost Basis Guide).
   - **Market Liquidation Price**: **\$33.625** ($33\frac{5}{8}$), when-issued valuation on December 31, 1996; regular trading began January 2, 1997.
   - **Proceeds per Share**: $0.0625 \times \$33.625 = \$2.10156 \approx \mathbf{\$2.10}$.
   - **Basis versus valuation**: Retain the issuer basis factor independently of the market valuation.
3. **Altria / Kraft Foods (`KFT`, 2007-03-30)**:
   - **Distribution Ratio**: 0.692024 shares of Kraft Foods Inc. per Altria share.
   - **Statutory Basis Allocation**: Altria retained **69.10%** (`0.6910`), allocating **30.90%** to Kraft (IRS Form 8937).
   - **Market Liquidation Price**: **\$31.65**, closing price on March 30, 2007.
   - **Proceeds per Share**: $0.692024 \times \$31.65 = \$21.902 \approx \mathbf{\$21.90}$.
4. **Altria / Philip Morris International (`PM`, 2008-03-28)**:
   - **Distribution Ratio**: 1.0 share of PMI common stock per Altria share.
   - **Statutory Basis Allocation**: Altria retained **30.40%** (`0.3040`), allocating **69.60%** to PMI (IRS Form 8937).
   - **Market Liquidation Price**: **\$50.60**, closing price on March 28, 2008.
   - **Proceeds per Share**: $1.0 \times \$50.60 = \mathbf{\$50.60}$.
5. **AT&T / WarnerMedia (`WBD`, 2022-04-08)**:
   - **Distribution Ratio**: 0.241917 shares of Warner Bros. Discovery per AT&T share.
   - **Statutory Basis Allocation**: AT&T retained **76.23%** (`0.7623`), allocating **23.77%** to WBD (IRS Form 8937).
   - **Market Liquidation Price**: **\$24.01**, closing price on April 8, 2022.
   - **Proceeds per Share**: $0.241917 \times \$24.01 = \$5.808 \approx \mathbf{\$5.81}$.
6. **General Electric / GE HealthCare (`GEHC`, 2023-01-04)**:
   - **Distribution Ratio**: 1 share of GEHC per 3 GE shares (0.333333 shares/GE share).
   - **Statutory Basis Allocation**: GE retained **81.65%** (`0.8165`), allocating **18.35%** to GEHC (IRS Form 8937).
   - **Market Liquidation Price**: **\$56.00**, closing price on January 4, 2023.
   - **Proceeds per Share**: $\frac{1}{3} \times \$56.00 = \$18.666 \approx \mathbf{\$18.67}$.
7. **General Electric / GE Vernova (`GEV`, 2024-04-02)**:
   - **Distribution Ratio**: 1 share of GEV per 4 GE shares (0.25 shares/GE share).
   - **Statutory Basis Allocation**: GE retained **66.86%** (`0.6686`), allocating **33.14%** to GEV (IRS Form 8937).
   - **Market Liquidation Price**: **\$141.50**, closing price on April 2, 2024.
   - **Proceeds per Share**: $0.25 \times \$141.50 = \$35.375 \approx \mathbf{\$35.38}$.

#### 1996 endpoint reconciliation (derived valuations)

The legacy archive's $56.50 Q3 and $43.50 Q4 entries are superseded by
`data/raw/corporate_actions/att_1996_endpoint_valuations.json` during dataset compilation.
Contemporaneous first-person portfolio statements value 130 AT&T shares at
[$6,792.50 on September 30](https://www.fool.com/archive/foolport/1996/09/30/fool-portfolio-report-monday-september-30-1996.aspx)
and [$5,638.75 on December 31](https://www.fool.com/archive/foolport/1996/12/31/fool-portfolio-report-tuesday-december-31-1996.aspx),
implying package quotes of $52.25 and $43.375. The September statement has no separate
Lucent position; the [October 1 statement](https://www.fool.com/archive/foolport/1996/10/01/fool-portfolio-report-tuesday-october-1-1996.aspx)
recognizes it separately. These observations are not post-distribution parent closes.

The engine recognizes each child at the distribution-date endpoint. To conserve
wealth under this convention, the builder deducts **only that endpoint's** separately
credited child proceeds from the package quote: Q3 = $52.25 - $14.87 = $37.38;
Q4 = $43.375 - $2.10, rounded to $41.27. Lucent must not be deducted again in Q4.
Annual 1996 uses the same Q4 valuation. These are **derived parent-only valuations**,
not observed exchange execution prices. This is an explicit approximation for
quarter-end trading immediately after a distribution, not a daily execution model.
The underlying source archive is preserved, and rebuilds apply the reconciliation once.
Legacy prices, dividends and distributions use contemporary legacy AT&T share units;
they are not mapped onto modern SBC/AT&T share counts.

[The transfer-agent historical guide](https://www.shareowneronline.com/FileHttphandler.ashx?filename=Historical&guid=131b40cd-f071-476d-8f86-1e6cd2b1edb5)
supports Lucent's $45.875 close. NCR's $33.625 when-issued quote is reported in
[contemporaneous coverage](https://www.latimes.com/archives/la-xpm-1997-01-01-fi-14389-story.html).
Basis allocation remains independently sourced from the issuer guide; it is not used
to reverse-engineer an alleged market close. Remaining legacy source validation is
tracked separately in issue #25.

#### 4.6.5 Absence of 1996 Spinoff Ticker Series on Modern Commercial APIs
Modern market data providers (e.g., Yahoo Finance) do not host clean, unadjusted historical equity ticker series for 1996 Lucent (`LU`) or 1996 NCR (`NCR`):
- Lucent merged with Alcatel in 2006 to form Alcatel-Lucent, which was acquired by Nokia (`NOK`) in 2016, extinguishing the standalone ticker history.
- NCR Corporation executed multiple spin-mergers and split in 2023 into NCR Voyix (`VYX`) and NCR Atleos (`NATL`).
Consequently, source data for these legacy transactions cannot be retrieved via raw ticker downloads and must be reconciled using verifiable issuer cost-basis worksheets, SEC filings, and contemporaneous NYSE transaction records.

#### 4.6.6 Rebalancing Entitlement Dynamics: Annual vs. Quarterly
Because quarterly rebalancing dynamically drifts constituent market-cap weights at quarter-ends, corporate action entitlement depends on whether the security was held at the distribution date:
- In 1996-Q3, `T` drifted to market cap rank #10.
- **Top 5 Annual**: Holds `T` across the entire 1996 calendar year $\implies$ receives Lucent (\$14.87) in Q3 and NCR (\$2.10) in Q4 (total \$16.97).
- **Top 5 Quarterly**: Holds `T` entering Q3 $\implies$ receives Lucent (\$14.87) in Q3, but is trimmed/exited at the 1996-Q3 rebalance upon slipping to rank #10 $\implies$ receives **\$0.00 from NCR in Q4**.
- **Top 10 Quarterly**: Holds `T` through all four quarters $\implies$ receives both Lucent and NCR.
- **Top 3 Quarterly**: Exits `T` at 1996-Q1 $\implies$ receives neither distribution.

---

## 5. Major Corporate Actions & Adjustments Log

| Ticker | Action Date | Corporate Action | Impact & Adjustment |
| :--- | :--- | :--- | :--- |
| **UNH** | 1994, 2000, 2003, 2005 | Four 2-for-1 splits | Cumulative 16:1 split factor since 1993. Year-end 1993 split-adjusted close is \$5.34 (nominal unadjusted was \$75.88). |
| **AAPL** | 2000, 2005, 2014, 2020 | 2:1, 2:1, 7:1, 4:1 splits | Cumulative 56:1 split factor. 1994 split-adjusted close is \$0.33. |
| **NVDA** | 2000, 2001, 2006, 2007, 2021, 2024 | 2:1 (x3), 3:2, 4:1, 10:1 splits | Cumulative 480:1 split factor. 1999 split-adjusted close is \$0.10. |
| **C** | 2011-05-09 | 1-for-10 Reverse Split | Pre-2011 nominal prices scaled up by 10x. 2006 split-adjusted close is \$496.80. |
| **AIG** | 2009-07-01 | 1-for-20 Reverse Split | Pre-2009 nominal prices scaled up by 20x. 2007 split-adjusted close is \$1,166.00; crashed to \$31.40 in 2008 (-97.31%). |
| **GE** | 2021-08-02 | 1-for-8 Reverse Split | Pre-2021 nominal prices scaled up by 8x. |
| **GE** | 2023, 2024 | Spinoff of GEHC & GEV | Modeled via Section 355 tax-free cash credit (\$18.67 and \$35.38) and Form 8937 basis retention ratios (0.8165 and 0.6686). |
| **WMT** | 2024-02-26 | 3-for-1 Split | 2023 split-adjusted close is \$52.55; 2024 close is \$88.93 (+69.23% return). |
| **T** | 1993–1998 | Decoupling of AT&T Corp ("Ma Bell") | Decoupled from SBC Communications (`T_CORP_HISTORICAL.json`) with verified \$0.33/quarter (\$1.32/year) dividends. |
| **T** | 1996-09-30 | Spinoff of Lucent Technologies (`LU`) | Modeled via Section 355 tax-free cash credit (\$14.87/sh; 0.324084 shares at \$45.875) and Form 8937 basis retention ratio (0.7201). |
| **T** | 1996-12-31 | Spinoff of NCR Corporation (`NCR`) | Modeled via Section 355 tax-free cash credit (\$2.10/sh; 0.0625 shares at \$33.625) and Form 8937 basis retention ratio (0.9523). |
| **T** | 2022-04-08 | Spinoff of WarnerMedia (`WBD`) | Modeled via Section 355 tax-free cash credit (\$5.81/sh) and Form 8937 basis retention ratio (0.7623). |
| **MO** | 2007, 2008 | Spinoff of Kraft (`KFT`) & Philip Morris (`PM`) | Modeled via Section 355 tax-free cash credits (\$21.90 and \$50.60) and Form 8937 basis retention ratios (0.6910 and 0.3040). |

---

## 6. Point-in-Time Constituent Selection & Weighting

In `data/sp500_constituents.json`, the top 12 constituents for each calendar year (1994–2024) are recorded in descending market cap rank order:
- **Index Weight Semantics**: Each constituent's `market_cap_weight` represents its actual point-in-time weight **in the entire S&P 500 index** (typically 1.0% to 7.5% per constituent, summing to ~20%–35% across the top 12).
- **Subset Normalization**: During backtest execution, [`engine/selector.py`](../engine/selector.py) dynamically normalizes any selected top $N \in \{3, 5, 10\}$ subset to sum strictly to 1.0:
  $$w_i = \frac{W_i}{\sum_{j=1}^N W_j}$$
- **Trailing 1-Year Return**: Sourced dynamically from split-adjusted closing prices:
  $$r_{t} = \frac{P_t - P_{t-1}}{P_{t-1}}$$
  ensuring 100% mathematical consistency between `data/sp500_prices.json` and `data/sp500_constituents.json`.

---

## 7. Deterministic Rebuild & Audit Instructions

The entire dataset can be rebuilt and verified offline at any time using the Python standard library:

```bash
# 1. Rebuild datasets from raw cached files
python3 scripts/build_datasets_from_raw.py

# 2. Run dataset integrity and regression test suite
python3 -m unittest tests/test_dataset_integrity.py
python3 -m unittest tests/test_data_loader.py

# 3. Run full project test suite
python3 -m unittest discover tests

# 4. Run strategy simulation
python3 run_backtest.py
```
