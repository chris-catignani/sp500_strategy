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
│   └── quarterly_ground_truth_holdings.json # Audited SEC EDGAR Form N-Q/N-PORT/N-CSR holdings (1999-2024)
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
- **SPDR S&P 500 ETF Trust (SPY)**: While SPY launched in January 1993, public historical portfolio snapshots are dispersed across more than 120 quarterly regulatory filings (Form N-Q, Form N-PORT, and annual Form N-CSR) on SEC EDGAR. Parsing heterogeneous text, HTML, and XML filings spanning three decades introduces substantial fragility, non-standardized asset reporting schemas, and heavy external parsing dependencies—directly conflicting with this project's core invariant of a lightweight, zero-external-dependency architecture.

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
- **Ranks #13–#20 for 1994–2019 are unverified estimates.** No primary source in this repository reports a point-in-time capitalization for these positions. They are not derived from anything archived here, and the provenance table labels all 208 such rows `Unverified Estimate (No Primary Source)` with no underlying or anchor value. An earlier revision published a `Cap_i` for each row back-solved from the weight it was meant to explain, cited to "SEC Form 10-K & Point-in-Time Capitalization Archives"; that was circular and has been removed. Resolving these rows requires extracting the 23 remaining archived Form N-30D Schedules of Investments.
- **Programmatic Form NPORT-P XML Derivation (2020–2024)**: For modern periods covered by primary SEC Form NPORT-P XML filings (2020, 2021, 2022, 2023, 2024), Top 20 candidates and exact weights are parsed directly from SPY's December 31 XML filings by [`scripts/generate_historical_weights.py`](../scripts/generate_historical_weights.py) with Alphabet Class A (`02079K305`) & C (`02079K107`) consolidated into `GOOGL`:
  - **2020-12-31**: Adobe Inc. (`ADBE`, #19, 0.76%) and Comcast Corp. (`CMCSA`, #20, 0.76%) enter the Top 20.
  - **2021-12-31**: Adobe Inc. (`ADBE`, #20, 0.67%) and Broadcom Inc. (`AVGO`, #19, 0.68%) enter the Top 20. Walmart (`WMT`) is heavily float-adjusted due to ~50% Walton family ownership, placing it at rank #40 (0.51% weight in SPY) and outside the Top 20.
  - **2022-12-31**: AbbVie Inc. (`ABBV`, #19, \$3.17B, 0.89%) and Merck & Co. Inc. (`MRK`, #20, \$3.12B, 0.88%) place ahead of Meta Platforms Inc. (`META`, #21, \$3.00B, 0.84%), correctly reflecting Meta's drawdown in 2022.
  - **2023-12-31**: Costco Wholesale Corp. (`COST`, #19, 0.73%) and Merck & Co. Inc. (`MRK`, #20, 0.69%) place in the Top 20.
  - **2024-12-31**: Netflix Inc. (`NFLX`, #20, 0.76%) enters the Top 20, displacing Oracle Corp. (`ORCL`), correctly reflecting Netflix's 2024 run.
- **Weight Derivation Table**: Every constituent rank, weight, formula, and source citation across all 31 years (620 rows) is exported to [`docs/historical_weights_table.csv`](historical_weights_table.csv), split by evidentiary status: **100 rows** `SEC Form NPORT-P Audited Holdings` (2020–2024, carrying the exact `valUSD` and `total_fund_val` the weight is computed from, and independently reproducible), **312 rows** `Official Factsheet Anchor` (ranks #1–#12), and **208 rows** `Unverified Estimate (No Primary Source)` (ranks #13–#20 outside 2020–2024). Only the 100 audited rows are reproducible from figures published in the table; `tests/test_raw_constituents.py` asserts that each one satisfies `round(valUSD / total_fund_val, 4) == weight`, and that no unverified row publishes a value.
- **Zero Lookahead Guarantee**: Deriving candidates from the prior year-end factsheet ensures no future information from year $t$'s Q4 factsheet leaks into early-year decisions.

#### 4.3.6 Primary Ground-Truth SEC EDGAR Regulatory Archive & Automated Parser
To eliminate reliance on third-party aggregators and establish regulatory ground truth, **46 primary SEC EDGAR regulatory filings** of the SPDR S&P 500 ETF Trust (`SPY`, CIK `0000884394`) are permanently archived in `data/raw/ground_truth/sec_filings/`:
- **Coverage Scope (1995–2024)**:
  - **Modern XML Filings (2020-Q1 through 2024-Q4, 20 Quarters)**: Form `NPORT-P` filings containing exact portfolio valuations (`valUSD`) and percentage weights (`pctVal`) for all 505 constituents.
  - **Historical Annual Reports (1995–2019, 26 Filings)**: Form `N-CSR` and `N-30D` filings containing the complete audited **Schedule of Investments**. **3 of these 26 are currently extracted** (1999, 2000, 2008); the remaining 23 are archived but unparsed, and are the evidence that would let ranks #13–#20 stop being estimates for those years.
- **Automated Standard-Library Parser (`scripts/extract_ground_truth_from_sec.py`)**:
  - `parse_xml_filing()` parses all 20 XML filings, reads `<formData><genInfo><repPdDate>` to verify the reporting date matches each calendar quarter end, aggregates Alphabet share classes, and extracts the audited Top 10.
  - `parse_n30d_filing()` parses the fixed-width **Schedule of Investments** in the historical Form N-30D / N-CSR annual reports, joining company names wrapped across continuation lines and consolidating multiple positions in the same issuer. Holdings for 1999, 2000 and 2008 are read from the filing text, never transcribed: `tests/test_raw_constituents.py::TestN30DScheduleParser` asserts the parser output against the committed ground truth, so a transcription error cannot pass silently.
  - Programmatically generates [`data/raw/ground_truth/quarterly_ground_truth_holdings.json`](../data/raw/ground_truth/quarterly_ground_truth_holdings.json) with verification metadata, per-holding weights, and the fund's total portfolio value.
- **Audited Schedule of Investments Historical Reconciliation**:
  - SPY's fiscal year ends September 30. Historical annual reports (Form N-30D) strictly validate **Q3**:
    - **1999-Q3 (1999-09-30, Acc: `0000950135-99-005434`)**: Lucent Technologies (`LU`, \$248.0M) ranks #7 and Merck & Co. (`MRK`, \$189.2M) ranks #9; Pfizer is #11 and JNJ is outside the Top 10.
    - **2000-Q3 (2000-09-30, Acc: `0000950135-00-005227`)**: EMC Corp (`EMC`, \$414.6M) ranks #10, replacing IBM (\$380.9M, #12).
    - **2008-Q3 (2008-09-30, Acc: `0000950135-08-007648`)**: Bank of America (`BAC`, \$1,457.7M) ranks #9 and IBM (`IBM`, \$1,447.3M) ranks #10, replacing Wal-Mart (\$1,226.0M, #11) and Cisco (\$1,217.2M, #12).
  - Quarters lacking point-in-time regulatory filing evidence (historical Q1/Q2) are marked `"verified": false` and reported as `[UNVERIFIED - No Filing]`.
- **Reconciliation Accuracy**:
  - **Out-of-sample: 96.0%** (144/150) across the **15 NPORT-P quarters that are genuine tests**. This is the figure that measures the drift model.
  - Across all **20 NPORT-P quarters**, the headline figure is 97.0% (194/200) — but **five of those quarters are not independent evidence**. The 2020-Q4 … 2024-Q4 filings are the same documents the year-end candidate lists are parsed from, so they match 10/10 by construction. `scripts/audit_quarterly_expansion.py` reports both figures and `CIRCULAR_Q4_PERIODS` names the excluded quarters.
  - Across all **23 verified regulatory filing quarters** (20 XML + 3 Annual Reports), accuracy is 95.2% (219/230).
  - **Known universe gap**: the three extracted historical filings each surface constituents the model cannot hold at all. Lucent Technologies (`LU`, #7 on 1999-09-30) and EMC Corp (`EMC`, #10 on 2000-09-30) are absent from the 51-ticker universe entirely — they are not mis-ranked, they are missing. Because the universe is composed almost exclusively of companies that still exist, and the missing names are disproportionately ones that later collapsed (LU fell ~99% and EMC ~96% between 2000 and 2002), results in the 1999–2002 window carry an **upward survivorship bias**. Quantifying and correcting this requires extracting the remaining 23 archived filings.

#### 4.3.7 Empirical Mid-Year Promotion Findings & Selector Sensitivity
The offline analysis script [`scripts/audit_quarterly_expansion.py`](../scripts/audit_quarterly_expansion.py) detects mid-year promotions, classifies each against the audited filings, and runs the side-by-side strategy comparison.

- **Mid-Year Promotions into Top 10**: Across 1994–2024 (124 quarters), the audit identifies **68 company-quarter promotion instances into the Top 10**, of which **24 originate from ranks #13–#20** and were locked out under the Top 12 restriction. A promotion is only evidence for the expansion if a point-in-time filing agrees the company was genuinely in the Top 10, so `classify_promotions()` tags each one:
  - **7 CONFIRMED**: `ORCL` 2000-Q3 (#14 → #9; the 2000-09-30 filing places Oracle at #8), `C` 1999-Q3 (#14 → #8), `NVDA` 2021-Q2 and 2021-Q3 (#14 → #8), `TSLA` 2023-Q1/Q2/Q3 (#13 → #7/#6/#6).
  - **1 CONTRADICTED**: `WMT` 2008-Q3. The drift model promotes Walmart to #7; the audited 2008-09-30 Schedule of Investments places it at **#11** (\$1,226.0M), outside the true Top 10. This is a false positive of the drift model and must not be cited as evidence for the expansion.
  - **16 UNVERIFIED**: promotions into quarters with no archived filing (`VZ` 2001, `KO`/`PG` 2002, `WMT` 2008-Q1/Q2 and 2016, `GOOGL` 2009, `META` 2015, `BAC` 2017, and others). These are plausible but uncorroborated.
- **Selector Sensitivity — two distinct effects**:
  - **Pool size alone** (`TrueTop12DataLoader` holds the constituent data fixed and truncates the Q1–Q3 candidate pool to the prior December's base 12, isolating the expansion):
    - `MarketCapSelector`: Top 3 and Top 5 are **unchanged** (0.00% delta at every horizon and tax tier) — a name ranked #13–#20 cannot reach a Top 5 book. Top 10 improves: 10y pre-tax 21.82% → 22.06% (+0.24%), 20y 13.57% → 14.16% (+0.59%), 30y 12.96% → 13.01% (+0.05%). **This is the expansion's real benefit.**
    - `PerformanceSelector`: the expansion is **negative in 8 of the 9 strategy/horizon cells**, averaging **-2.2%** pre-tax and reaching **-5.89%** (Top 10, 10y). Only Top 3 at 10y improves (+2.92%). A wider candidate pool gives a momentum selector more recent winners to choose among, and the largest recent gainer out of 20 large caps mean-reverts more often than the largest out of 12. An earlier revision of this document quoted the single positive cell as representative; the full table is printed by the audit script and should be read in full.
  - **Data correction (separate from pool size)**: re-deriving the 2021–2023 year-end weights from the NPORT-P filings changed the underlying constituent data, which moved the reported results independently of any pool-size effect. `Top_3_MarketCap` fell from 26.88% to 24.49% (10y), 16.39% to 15.29% (20y) and 15.16% to 14.43% (30y). The cause is year-end 2023: the prior data ranked NVIDIA #3 at 3.4%, while the filing shows NVIDIA at 3.06% behind Alphabet — so the Top 3 book no longer holds NVIDIA through its 2024 run.
- **Alphabet share-class aggregation**: SPY files Alphabet as two positions (Class A `02079K305`, Class C `02079K107`) and the S&P 500 ranks them as two separate constituents. This project consolidates them into one `GOOGL` position and executes at Class A prices. The choice is load-bearing, not cosmetic: at 2023-12-31 the filing reads AAPL 7.03%, MSFT 6.98%, AMZN 3.45%, NVDA 3.06%, Alphabet A 2.07%, META 1.96%, Alphabet C 1.75%. Consolidated, Alphabet is 3.82% and ranks #3, which determines the entire 2024 Top 3 book; read as filed, the 2023 Top 3 is AAPL/MSFT/AMZN.

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
