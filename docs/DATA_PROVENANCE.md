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
│   └── SP500TR.json       # S&P 500 Total Return Index (^SP500TR) raw response
├── tickers/
│   ├── AAPL.json          # Apple Inc. raw response (timestamps, quotes, splits, dividends)
│   ├── BRK.B.json         # Berkshire Hathaway Class B (queried as BRK-B)
│   ├── UNH.json           # UnitedHealth Group Inc. raw response
│   └── ... (33 files)
└── constituents/
    └── historical_index_weights.json  # Point-in-time constituent rankings and S&P 500 weights
```

Each raw file contains the unadulterated JSON response directly from the API endpoint:
- `timestamp`: Unix epoch seconds for each monthly observation.
- `indicators.quote[0].close`: Month-end closing price, normalized for splits as of the query date.
- `events.splits`: Dictionary of every stock split event, with timestamp `date`, `numerator`, `denominator`, and `splitRatio`.
- `events.dividends`: Dictionary of every cash dividend distribution, with ex-dividend `date` and split-adjusted `amount`.

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

### 4.3 Quarterly Pricing & Point-in-Time Constituent Composition
- **Quarterly Prices (`data/sp500_quarterly_prices.json` & `world_quarterly_prices.json`)**: Extracted from March, June, September, and December month-end candles. Q4 prices align with year-end closes.
- **Dynamic Weight Drift (Q1–Q3)**: Weights and rankings update dynamically based on price performance relative to the index:
  $$W_{i, q} = W_{i, 0} \times \frac{P_{i, q} / P_{i, 0}}{P_{\text{index}, q} / P_{\text{index}, 0}}$$
- **Q4 Factsheet Re-Anchoring**: At each Q4 (December 31), constituent rosters and weights re-anchor to official index factsheets, eliminating multi-year cumulative drift error.
- **Pluggable Dataset Architecture**: [`DataLoader.load_quarterly_universe()`](../engine/data_loader.py) checks for registered quarterly universe files in `data/`, enabling external point-in-time constituent datasets to be dropped in without engine modifications.

### 4.4 Benchmark Total Return & Synthetic Yield
- Pre-tax benchmark returns are tracked directly via `^SP500TR` (S&P 500) and `^MSCIWORLD_TR` (MSCI World).
- For after-tax benchmark comparisons, the dividend yield $y_t$ is determined dynamically from the relationship between Total Return and Price Return:
  $$r_{\text{tr}, t} = \frac{\text{TR}_t - \text{TR}_{t-1}}{\text{TR}_{t-1}}, \quad r_{\text{pr}, t} = \frac{\text{PR}_t - \text{PR}_{t-1}}{\text{PR}_{t-1}}$$
  $$y_t = \max(0, r_{\text{tr}, t} - r_{\text{pr}, t})$$
- For 1994, this yields:
  $$r_{\text{tr}, 1994} = \frac{575.71 - 568.20}{568.20} = +1.3216\%$$
  $$r_{\text{pr}, 1994} = \frac{459.27 - 466.45}{466.45} = -1.5393\%$$
  $$y_{1994} = 1.3216\% - (-1.5393\%) = 2.8609\% \approx 2.86\%$$

---

## 5. Major Corporate Actions & Adjustments Log

| Ticker | Action Date | Corporate Action | Impact & Adjustment |
| :--- | :--- | :--- | :--- |
| **UNH** | 1994, 2000, 2003, 2005 | Four 2-for-1 splits | Cumulative 16:1 split factor since 1993. Year-end 1993 split-adjusted close is \$5.34 (nominal unadjusted was \$75.88). |
| **AAPL** | 2000, 2005, 2014, 2020 | 2:1, 2:1, 7:1, 4:1 splits | Cumulative 56:1 split factor. 1994 split-adjusted close is \$0.33. |
| **NVDA** | 2000, 2001, 2006, 2007, 2021, 2024 | 2:1 (x3), 3:2, 4:1, 10:1 splits | Cumulative 480:1 split factor. 1999 split-adjusted close is \$0.10. |
| **C** | 2011-05-09 | 1-for-10 Reverse Split | Pre-2011 nominal prices scaled up by 10x. 2006 split-adjusted close is \$496.80. |
| **AIG** | 2009-07-01 | 1-for-20 Reverse Split | Pre-2009 nominal prices scaled up by 20x. 2007 split-adjusted close is \$1,166.00; crashed to \$31.40 in 2008 (-97.31%). |
| **GE** | 2021-08-02 | 1-for-8 Reverse Split | Pre-2021 nominal prices scaled up by 8x. Also spun off GEHC (2023) and GEV (2024). |
| **WMT** | 2024-02-26 | 3-for-1 Split | 2023 split-adjusted close is \$52.55; 2024 close is \$88.93 (+69.23% return). |
| **T** | 2022-04-08 | Spinoff of WarnerMedia | Spinoff accounted for via standard market price series. |
| **MO** | 2007, 2008 | Spinoff of Kraft & Philip Morris Int. | Spinoff distributions reflected in price index returns. |

---

## 6. Point-in-Time Constituent Selection & Weighting

In `data/sp500_constituents.json`, the top 12 constituents for each calendar year (1994–2024) are recorded in descending market cap rank order:
- **Index Weight Semantics**: Each constituent's `market_cap_weight` represents its actual point-in-time weight **in the entire S&P 500 index** (typically 1.0% to 7.5% per constituent, summing to ~20%–35% across the top 12).
- **Subset Normalization**: During backtest execution, [`engine/selector.py`](file:///Users/chriscatignani/Developer/sp500_strategy/engine/selector.py) dynamically normalizes any selected top $N \in \{3, 5, 10\}$ subset to sum strictly to 1.0:
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
