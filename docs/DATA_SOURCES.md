# Historical Data Sources, Provenance & Corporate Action Methodology

This document details the data lineage, normalization conventions, corporate action adjustments, and quantitative modeling assumptions governing the datasets in `data/` (`sp500_prices.json`, `sp500_dividends.json`, and `sp500_constituents.json`).

---

## 1. Primary Benchmark Indices (1993–2024)

### 1.1 S&P 500 Price Return (`^GSPC`)
* **Description**: The official benchmark price index tracking the market-cap-weighted performance of 500 leading U.S. public companies, excluding cash dividend distributions.
* **Coverage**: Year-end closing levels for 32 consecutive years (1993 to 2024).
* **Source & Verification**: S&P Dow Jones Indices / Federal Reserve Economic Data (FRED) / market close records. All 32 year-end levels (e.g., 1993: 466.45, 2007: 1,468.36, 2008: 903.25, 2024: 5,881.63) match official historical closing values to the penny.

### 1.2 S&P 500 Total Return (`^SP500TR`)
* **Description**: Tracks the cumulative total return of the S&P 500 universe assuming gross daily reinvestment of all cash distributions.
* **Coverage**: Year-end closing index levels for 1993–2024.
* **Base Year (1993)**: Normalized to `744.04`, reflecting the 1994 year-end close of `753.86` and the actual 1994 market total return of $+1.32\%$ and dividend yield of $2.86\%$.
* **Application in Backtest**:
  - In **Pre-Tax** runs: `^SP500TR` serves as the primary benchmark. Annual return is $R_{\text{TR}, t} = (\text{SP500TR}_t / \text{SP500TR}_{t-1}) - 1$.
  - In **After-Tax** runs: Serves alongside `^GSPC` to derive the synthetic annual dividend yield:
    $$y_t = \max\left(0.0, R_{\text{TR}, t} - R_{\text{PR}, t}\right)$$
    used to compute annual taxable index distributions and tax drag.

---

## 2. Constituent Universe & Point-in-Time Selection

### 2.1 Selection Universe
* **History**: Point-in-time annual constituent rankings from 1994 to 2024 (31 years).
* **Methodology**: At each year-end $t$, the top 12 companies in the S&P 500 by market capitalization are selected. The top $N$ ($N \in \{3, 5, 10\}$) form the investment portfolio for the subsequent calendar year.
* **Historical Accuracy**: Captures major historical leadership regimes:
  - 1990s: General Electric (`GE`), AT&T (`T`), Exxon (`XOM`), Coca-Cola (`KO`), Merck (`MRK`).
  - 2000s: ExxonMobil (`XOM`), General Electric (`GE`), Microsoft (`MSFT`), Citigroup (`C`), Pfizer (`PFE`).
  - 2010s: Apple (`AAPL`), ExxonMobil (`XOM`), Google (`GOOGL`), Berkshire Hathaway (`BRK.B`), Microsoft (`MSFT`).
  - 2020s: Apple (`AAPL`), Microsoft (`MSFT`), NVIDIA (`NVDA`), Amazon (`AMZN`), Alphabet (`GOOGL`), Meta (`META`).

### 2.2 Market Capitalization Weights (4-Era Stylized Templates)
In live markets, index constituent weights fluctuate daily based on price movements and share issuances. To preserve zero external dependencies and fast simulation speeds, market cap weights are represented via four stylized 12-rank concentration templates reflecting historical regime concentration:
* **`early` (1994–1999)**: Moderate concentration; top constituent $\approx 3.2\%$ (`[0.032, 0.028, 0.025, ...]`).
* **`mid` (2000–2006)**: Balanced mega-cap era; top constituent $\approx 3.8\%$ (`[0.038, 0.032, 0.029, ...]`).
* **`late` (2007–2017)**: Emerging tech concentration; top constituent $\approx 4.4\%$ (`[0.044, 0.036, 0.031, ...]`).
* **`modern` (2018–2024)**: Mega-cap tech dominance; top constituent $\approx 7.1\%$ (`[0.071, 0.065, 0.061, ...]`).

Target portfolio weights normalize relative to selected constituents:
$$w_i = \frac{W_i}{\sum_{j=1}^N W_j}$$

---

## 3. Equity Prices & Corporate Action Normalization

All constituent stock prices (`data/sp500_prices.json`) are maintained on a split-adjusted basis normalized to **December 31, 2024**.

### 3.1 Mega-Cap Tech Split Adjustments
Mega-cap tech equities reflect all cumulative historical forward stock splits:
* **Apple (`AAPL`)**: Normalized for 2:1 (2000), 2:1 (2005), 7:1 (2014), and 4:1 (2020) splits (cumulative $112\times$ adjustment factor).
* **NVIDIA (`NVDA`)**: Normalized for 2:1 (2000), 2:1 (2001), 2:1 (2006), 3:2 (2007), 4:1 (2021), and 10:1 (2024) splits (cumulative $480\times$ adjustment factor).
* **Amazon (`AMZN`)**: Normalized for 2:1 (1998), 3:1 (1999), 2:1 (1999), and 20:1 (2022) splits (cumulative $240\times$ adjustment factor).
* **Alphabet (`GOOGL`)**: Normalized for 2:1 (2014) and 20:1 (2022) splits.

### 3.2 Corporate Action Corrections for Legacy Constituents
Specific multi-year normalizations are enforced in `scripts/generate_datasets.py` to prevent phantom split returns:
1. **Walmart (`WMT`)**:
   - Walmart executed a 3-for-1 stock split on February 26, 2024.
   - Prices and dividends for 2000–2023 are normalized to the current post-split basis (e.g. 2023 price is $\$52.55$, dividend is $\$0.76$; 2024 price is $\$88.93$, dividend is $\$0.83$).
2. **General Electric (`GE`)**:
   - Normalized across historical splits (May 1994 2:1, May 1997 2:1, and May 2000 3:1) and the August 2021 1-for-8 reverse split.
   - The 1993–1999 series is normalized to the consistent pre-May 2000 share basis (1998: $\$102.00$, 1999: $\$154.75$, 2000: $\$143.81$), accurately preserving the $+51.7\%$ gain in 1999 and the $-7.07\%$ return in 2000.
3. **American International Group (`AIG`)**:
   - AIG executed a 1-for-20 reverse stock split on June 30, 2009.
   - Pre-2009 prices and dividends are normalized by $20\times$ (2007: $\$878.80$, 2008: $\$23.60$, 2009: $\$29.15$), preserving the authentic $-97.3\%$ collapse during the 2008 financial crisis and $+23.5\%$ rebound in 2009.
4. **UnitedHealth Group (`UNH`)**:
   - Normalized for historical 2:1 stock splits (1992, 1994, 2000, 2003, and 2005). Note: UNH was not held in the Top 10 prior to 2021, but pre-2006 price levels are adjusted for universe consistency.

---

## 4. Cash Dividend Accounting & Timing Conventions

### 4.1 Dividend History (`data/sp500_dividends.json`)
* Split-adjusted annual cash dividends per share (`DPS`) are provided for every constituent across 1994–2024.
* Non-dividend payers (e.g., `AMZN`, `TSLA`, `BRK.B`, and `GOOGL`/`META` prior to 2024) strictly record `0.0`.
* Companies initiating dividends (e.g. `MSFT` in 2003, `CSCO` in 2011, `AAPL` in 2012, `GOOGL` and `META` in 2024) record accurate initiation amounts.

### 4.2 Annual Discrete Timing Convention
* **Model Convention**: Cash dividends earned throughout year $t$ are calculated based on positions held during year $t$ and credited into portfolio cash once annually at year-end immediately prior to rebalancing:
  $$\text{DivIncome}_t = \sum_{i} S_i^{\text{held}} \times \text{DPS}_{i, t}$$
* **Live Trading Differences**: In reality, corporate dividends are distributed quarterly and held in cash or reinvested intra-year. The annual discrete convention is standard in long-term quantitative factor backtests because:
  1. It avoids arbitrary intra-year reinvestment timing assumptions.
  2. It preserves zero external library dependencies.
  3. It conservatively models after-tax drag by taxing all calendar year dividends in that tax year.
* **Special Dividends**: Extraordinary one-time non-recurring cash distributions (such as Microsoft's $\$3.00$ special dividend in November 2004) are excluded to reflect ongoing structural dividend yields.
