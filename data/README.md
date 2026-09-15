# S&P 500 Top N Strategy Datasets

This directory contains the point-in-time constituent snapshots, split-adjusted prices, and dividend histories used by the backtest engine across the 31-year evaluation period (1994–2024).

For full details on sources, formulas, corporate actions, and rebuild instructions, see:
[`docs/DATA_PROVENANCE.md`](../docs/DATA_PROVENANCE.md)

## Directory Structure

- `raw/`: **Source archives and reconstruction inputs**
  - `benchmarks/`: Raw JSON chart responses for `^GSPC`, `^SP500TR`, `^MSCIWORLD_PR`, `^MSCIWORLD_TR`, `FBGRX`, `URTH`, `^NDX`, `^NDXT`, and `QQQ`.
  - `tickers/`: Raw JSON chart responses for all equity constituents with exact distribution timestamps and amounts for corporate actions.
  - `constituents/`: Point-in-time constituent rankings and historical index weights.
  - `corporate_actions/att_1996_endpoint_valuations.json`: Cited AT&T package quotes used to derive parent-only September/December 1996 valuations after subtracting separately credited child proceeds. The builder applies these corrections once; the legacy ticker archive is preserved.
- **Annual Datasets**:
  - `sp500_prices.json` / `world_prices.json`: Split-adjusted year-end closing prices (1993–2024).
  - `sp500_dividends.json` / `world_dividends.json`: Split-adjusted annual cash dividends per share (1994–2024).
  - `sp500_constituents.json` / `world_constituents.json`: Point-in-time annual constituent rosters and weights.
- **Quarterly Datasets (124 Quarters, 1994-Q1 through 2024-Q4)**:
  - `sp500_quarterly_prices.json` / `world_quarterly_prices.json`: Quarter-end split-adjusted closing prices.
  - `sp500_quarterly_dividends.json` / `world_quarterly_dividends.json`: Actual cash dividends distributed per quarter (exact ex-dates, not averaged).
  - `sp500_quarterly_constituents.json` / `world_quarterly_constituents.json`: Quarterly constituent compositions (dynamic price drift for Q1–Q3; factsheet re-anchored for Q4).

## Nasdaq 100 (^NDX / ^NDXT) Benchmark Datasets

The Nasdaq 100 benchmark integration provides continuous 31-year price return (`^NDX`) and total return (`^NDXT`) series from 1993 to 2024 (annual) and 1993-Q1 through 2024-Q4 (quarterly):

- **Price Return (`^NDX`)**: Sourced directly from historical market closes in `data/raw/benchmarks/NDX.json` across 1993–2024.
- **Total Return Composite (`^NDXT`)**: Constructed directly from `^NDX` combined with continuous quarterly `QQQ` cash distributions (`data/raw/benchmarks/QQQ.json`) from 1999-Q2 to 2024-Q4 and nominal pre-1999 dividend yield. Base $TR_{\text{1993-Q4}} = NDX_{\text{1993-Q4}} = 398.28$:
  $$r_{\text{pr}, t} = \frac{NDX_t - NDX_{t-1}}{NDX_{t-1}}$$
  $$y_t = \begin{cases}
  \frac{\text{Div}_{\text{QQQ}, t}}{P_{\text{QQQ}, t-1}} & \text{for } 1999\text{-Q2} \le t \le 2024\text{-Q4} \\
  0.0 & \text{for } t = 1999\text{-Q1} \\
  \frac{0.0025}{4} = 0.000625 & \text{for } 1993\text{-Q1} \le t \le 1998\text{-Q4}
  \end{cases}$$
  $$r_{\text{tr}, t} = r_{\text{pr}, t} + y_t$$
  $$TR_t = TR_{t-1} \times (1 + r_{\text{tr}, t})$$
- **Continuous Compounding**: Forward chained from 1994-Q1 to 2024-Q4 (with backward chaining for 1993-Q1..Q3), keeping full raw float precision throughout the quarterly sequence and rounding to 2 decimal places in export dictionaries. Annual closes are extracted directly as $TR_{\text{year}} = TR_{\text{year-Q4}}$.

## Rebuilding Datasets

All datasets (annual and quarterly) can be rebuilt deterministically from raw files at any time:
```bash
python3 scripts/build_datasets_from_raw.py
```
