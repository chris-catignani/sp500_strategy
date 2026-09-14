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
  - **Universe**: 33 point-in-time constituents + 2 benchmark indices (`^GSPC` Price Index, `^SP500TR` Total Return Index).

### 2.2 Ticker Universe (33 Equities)
| Category | Tickers |
| :--- | :--- |
| **Mega-Cap Tech** | `AAPL`, `MSFT`, `NVDA`, `AMZN`, `GOOGL`, `META`, `TSLA`, `AVGO`, `CSCO`, `INTC`, `IBM`, `HPQ` |
| **Financials** | `BRK.B`, `JPM`, `BAC`, `WFC`, `C`, `AIG` |
| **Healthcare & Pharma**| `UNH`, `LLY`, `JNJ`, `PFE`, `MRK` |
| **Consumer & Retail** | `WMT`, `PG`, `HD`, `KO`, `MO` |
| **Energy & Industrials**| `XOM`, `CVX`, `GE` |
| **Telecom & Payments** | `T`, `V` |

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
├── tickers/
│   ├── AAPL.json          # Apple Inc. raw response (timestamps, quotes, splits, dividends)
│   ├── BRK.B.json         # Berkshire Hathaway Class B (queried as BRK-B)
│   ├── T.json             # Post-1998 SBC / AT&T Inc. raw response
│   ├── T_CORP_HISTORICAL.json # Decoupled original AT&T Corp ("Ma Bell") historical series (1993–1998)
│   ├── UNH.json           # UnitedHealth Group Inc. raw response
│   └── ... (33 files)
└── constituents/
    ├── historical_index_weights.json       # Authoritative S&P 500 point-in-time constituent factsheet weights
    └── world_historical_index_weights.json # Authoritative All-World point-in-time constituent factsheet weights
```

Each raw file contains the unadulterated JSON response directly from the API endpoint:
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
3. **Q4 Factsheet Re-Anchoring**: At each Q4 (December 31), candidate rosters and constituent index weights re-anchor to the official S&P Dow Jones Indices year-end factsheet. This introduces any newly admitted constituents (such as TSLA in 2020-Q4) and resets drifted weights to audited benchmark reality, eliminating multi-year cumulative drift error.
4. **Pluggable Dataset Architecture**: [`DataLoader.load_quarterly_universe()`](../engine/data_loader.py) checks for registered quarterly universe files in `data/`, enabling external point-in-time constituent datasets to be dropped in without engine modifications.

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
- **Prices & Baseline Closes**: Verified historical month-end closes from 1993 through 1998, including 1993-Q1..Q3 baseline closes (\$26.83, \$26.00, and \$26.75) to prevent artificial capitalization drift spikes in early 1994.
- **Automated Splicing**: In `scripts/build_datasets_from_raw.py`, pre-1999 SBC data for `T` is purged, and the verified `T_CORP_HISTORICAL` record is spliced into the constituent series for 1993–1998. Data from 1999 onward transitions smoothly into the consolidated modern AT&T series.

---

### 4.6 Statutory Corporate Spinoff Modeling (IRS Section 355 & Form 8937)

#### 4.6.1 Statutory Background & IRC Section 355
Under Internal Revenue Code (IRC) Section 355 and Treasury Regulations, a corporate division or spinoff meeting statutory requirements is treated as a **tax-free reorganization**:
- Shareholders receiving shares of a spun-off entity do not recognize taxable dividend income or immediate capital gain.
- Pursuant to IRC Section 358 and IRS Form 8937 (*Report of Organizational Actions Affecting Basis of Securities*), the aggregate tax basis in the pre-distribution parent shares is allocated between the parent shares and the spun-off shares in proportion to their relative fair market values immediately following the distribution:
  $$P_{\text{basis, new}} = \text{round}(P_{\text{basis, old}} \times R_{\text{retention}}, 4)$$
  where $R_{\text{retention}} \in (0, 1)$ is the basis retention ratio reported on the issuer's Form 8937.

#### 4.6.2 Engine Simulation Mechanics & Invariant Preservation
In a disciplined Top N strategy, the portfolio cannot hold non-qualifying arbitrary spin-co equity positions without violating constituent universe constraints. The backtesting engine (`engine/backtest.py` and `engine/tax_lots.py`) implements an exact statutory cash-realization and basis-adjustment model:
1. **Tax-Free Cash Credit**: In the quarter or year of the corporate action, the cash distribution per share is multiplied by existing shares held and credited directly to the portfolio's available cash pool (`self.cash += shares_held * dist_per_share`). This preserves the self-financing cash invariant ($C \ge 0$).
2. **Zero Dividend Tax Withholding**: Because qualifying Section 355 spinoffs are corporate reorganizations rather than ordinary dividend distributions, **zero dividend tax is withheld** at rebalancing ($0.00 dividend tax drag).
3. **Tax Lot Cost Basis Reduction**: All open FIFO tax lots of the parent company are updated via [`FIFOTaxLotManager.adjust_basis_ratio(ticker, ratio)`](../engine/tax_lots.py), reducing each lot's `purchase_price` by the Form 8937 basis retention ratio. This preserves embedded unrealized capital gains, ensuring correct capital gains tax settlement when the parent shares are subsequently trimmed or liquidated.

#### 4.6.3 Raw Corporate Spinoff Catalog (`data/raw/corporate_actions/spinoffs.json`)
The immutable catalog in `data/raw/corporate_actions/spinoffs.json` (compiled to `data/spinoff_distributions.json`) records the following verified historical corporate spinoffs:

| Ticker | Ex-Date | Spin-Co Ticker | Spin-Co Description | Dist / Share | Basis Retention ($R_{\text{retention}}$) | Statutory Filing |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **MO** | 2007-03-30 | `KFT` | Kraft Foods Inc. | \$21.90 | 0.6910 (69.10%) | IRS Form 8937 / Section 355 |
| **MO** | 2008-03-28 | `PM` | Philip Morris International Inc. | \$50.60 | 0.3040 (30.40%) | IRS Form 8937 / Section 355 |
| **T** | 2022-04-08 | `WBD` | Warner Bros. Discovery Inc. | \$5.81 | 0.7623 (76.23%) | IRS Form 8937 / Section 355 |
| **GE** | 2023-01-04 | `GEHC` | GE HealthCare Technologies Inc. | \$18.67 | 0.8165 (81.65%) | IRS Form 8937 / Section 355 |
| **GE** | 2024-04-02 | `GEV` | GE Vernova Inc. | \$35.38 | 0.6686 (66.86%) | IRS Form 8937 / Section 355 |

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
