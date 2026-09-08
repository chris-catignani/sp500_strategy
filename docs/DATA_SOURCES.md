# Historical Data Sources, Provenance & Corporate Action Methodology

This document details the data lineage, normalization conventions, corporate action adjustments, and quantitative modeling assumptions governing the datasets in `data/` (`sp500_prices.json`, `sp500_dividends.json`, and `sp500_constituents.json`).

For full technical specifications, raw API schemas, and offline rebuild instructions, see:
[`docs/DATA_PROVENANCE.md`](DATA_PROVENANCE.md)

---

## 1. Primary Benchmark Indices (1993–2024)

### 1.1 S&P 500 Price Return (`^GSPC`)
* **Description**: The official benchmark price index tracking the market-cap-weighted performance of 500 leading U.S. public companies, excluding cash dividend distributions.
* **Coverage**: Year-end closing levels for 32 consecutive years (1993 to 2024).
* **Source & Verification**: S&P Dow Jones Indices / Yahoo Finance Market Feed. All 32 year-end levels (e.g., 1993: 466.45, 2007: 1,468.36, 2008: 903.25, 2024: 5,881.63) match official historical closing values to the penny.

### 1.2 S&P 500 Total Return (`^SP500TR`)
* **Description**: Tracks the cumulative total return of the S&P 500 universe assuming gross daily reinvestment of all cash distributions.
* **Coverage**: Year-end closing index levels for 1993–2024 (1993: 568.20, 1994: 575.71, 2024: 12,911.82).
* **Application in Backtest**:
  - In **Pre-Tax** runs: `^SP500TR` serves as the primary benchmark. Annual return is $R_{\text{TR}, t} = (\text{SP500TR}_t / \text{SP500TR}_{t-1}) - 1$.
  - In **After-Tax** runs: Serves alongside `^GSPC` to derive the synthetic annual dividend yield:
    $$y_t = \max\left(0.0, R_{\text{TR}, t} - R_{\text{PR}, t}\right)$$
    used to compute annual taxable index distributions and tax drag (e.g., 1994 yield is $\approx 2.86\%$).

---

## 2. Constituent Universe & Point-in-Time Selection

### 2.1 Selection Universe
* **History**: Point-in-time annual constituent rankings from 1994 to 2024 (31 years).
* **Methodology**: At each year-end $t$, the top 12 companies in the S&P 500 by market capitalization are selected. The top $N$ ($N \in \{3, 5, 10\}$) form the investment portfolio for the subsequent calendar year.
* **Historical Regimes**:
  - 1990s: General Electric (`GE`), AT&T (`T`), Exxon (`XOM`), Coca-Cola (`KO`), Merck (`MRK`).
  - 2000s: ExxonMobil (`XOM`), General Electric (`GE`), Microsoft (`MSFT`), Citigroup (`C`), Pfizer (`PFE`).
  - 2010s: Apple (`AAPL`), ExxonMobil (`XOM`), Google (`GOOGL`), Berkshire Hathaway (`BRK.B`), Microsoft (`MSFT`).
  - 2020s: Apple (`AAPL`), Microsoft (`MSFT`), NVIDIA (`NVDA`), Amazon (`AMZN`), Alphabet (`GOOGL`), Meta (`META`).

### 2.2 Point-in-Time Index Market Cap Weights
Each constituent's `market_cap_weight` in `data/sp500_constituents.json` represents its actual point-in-time weight **within the overall S&P 500 index** as of December 31 each year (sourced from archived S&P Dow Jones index factsheets and Compustat):
* Early era (1994–1999): Top constituent $\approx 2.7\%–4.9\%$ of index; top 12 sum to $\approx 21\%–28\%$.
* Modern era (2020–2024): Top constituent $\approx 6.3\%–7.1\%$ of index; top 12 sum to $\approx 31\%–39\%$.

During simulation execution, [`engine/selector.py`](../engine/selector.py) dynamically normalizes any chosen top $N$ subset:
$$w_i = \frac{W_i}{\sum_{j=1}^N W_j}$$

---

## 3. Equity Prices & Corporate Action Normalization

All constituent stock prices (`data/sp500_prices.json`) are maintained on a split-adjusted basis normalized to **December 31, 2024** share counts, derived from raw API chart data in `data/raw/tickers/`.

### 3.1 Corporate Action Adjustments Log
* **Apple (`AAPL`)**: Normalized for 2:1 (2000), 2:1 (2005), 7:1 (2014), and 4:1 (2020) splits (cumulative $56\times$ adjustment factor).
* **NVIDIA (`NVDA`)**: Normalized for three 2:1 splits (2000, 2001, 2006), 3:2 (2007), 4:1 (2021), and 10:1 (2024) splits (cumulative $480\times$ adjustment factor).
* **Amazon (`AMZN`)**: Normalized for 2:1 (1998), 3:1 (1999), 2:1 (1999), and 20:1 (2022) splits (cumulative $240\times$ adjustment factor).
* **Walmart (`WMT`)**: Normalized for 3:1 split on February 26, 2024. 2023 close is $\$52.55$; 2024 close is $\$88.93$.
* **Citigroup (`C`)**: Normalized for 1-for-10 reverse split in May 2011. Pre-2011 prices scaled by $10\times$.
* **American International Group (`AIG`)**: Normalized for 1-for-20 reverse split in July 2009. Pre-2009 prices scaled by $20\times$. 2007 close is $\$1,166.00$; 2008 close is $\$31.40$ ($-97.31\%$).
* **UnitedHealth Group (`UNH`)**: Normalized for four 2:1 splits (1994, 2000, 2003, 2005). 1993 close is $\$5.34$.
* **General Electric (`GE`)**: Normalized for 1-for-8 reverse split in August 2021.

---

## 4. Cash Dividend Accounting & Timing Conventions

### 4.1 Dividend History (`data/sp500_dividends.json`)
* Split-adjusted annual cash dividends per share (`DPS`) are computed by summing all cash dividend distributions whose ex-dividend dates fall within that calendar year.
* Non-dividend payers (e.g., `AMZN`, `TSLA`, `BRK.B`, and `GOOGL`/`META` prior to 2024) strictly record `0.0`.

### 4.2 Annual Discrete Timing Convention
* Cash dividends earned throughout year $t$ are calculated based on positions held during year $t$ and credited into portfolio cash once annually at year-end immediately prior to rebalancing:
  $$\text{DivIncome}_t = \sum_{i} S_i^{\text{held}} \times \text{DPS}_{i, t}$$
* Cash dividends are pooled into available cash and taxed under the decoupled dual tax model before secondary rebalancing.

---

## 5. Offline Deterministic Rebuild

Datasets can be verified and rebuilt from raw files at any time:
```bash
# Rebuild processed datasets from raw files
python3 scripts/build_datasets_from_raw.py

# Run all integrity tests
python3 -m unittest discover tests

# Run backtest simulation
python3 run_backtest.py
```
