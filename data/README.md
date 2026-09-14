# S&P 500 Top N Strategy Datasets

This directory contains the point-in-time constituent snapshots, split-adjusted prices, and dividend histories used by the backtest engine across the 31-year evaluation period (1994–2024).

For full details on sources, formulas, corporate actions, and rebuild instructions, see:
[`docs/DATA_PROVENANCE.md`](../docs/DATA_PROVENANCE.md)

## Directory Structure

- `raw/`: **Immutable Raw API Data**
  - `benchmarks/`: Raw JSON chart responses for `^GSPC`, `^SP500TR`, `^MSCIWORLD_PR`, `^MSCIWORLD_TR`, `FBGRX`, `URTH`, `^NDX`, `^NDXT`, and `QQQ`.
  - `tickers/`: Raw JSON chart responses for all equity constituents with exact distribution timestamps and amounts for corporate actions.
  - `constituents/`: Point-in-time constituent rankings and historical index weights.
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
- **Official Total Return (`^NDXT`, 2006–2024)**: Sourced directly from official Nasdaq-100 Total Return Index closes in `data/raw/benchmarks/NDXT.json`.
- **QQQ Distribution Bridge (1999-Q2 to 2006-Q1)**: Synthesized backwards from 2006-Q1 using actual unadjusted cash dividends and quarter-end closes from the Invesco QQQ Trust (`data/raw/benchmarks/QQQ.json`):
  $$y_t = \frac{\text{Div}_{\text{QQQ}, t}}{P_{\text{QQQ}, t-1}}$$
  QQQ launched on March 10, 1999, so 1999-Q1 dividend yield is set to $y_t = 0.0$.
- **Nominal Yield Bridge (1993-Q1 to 1998-Q4)**: Synthesized backwards using an annualized 0.25% nominal dividend yield ($y_t = \frac{0.0025}{4} = 0.000625$ per quarter), reflecting the historical low-dividend environment of Nasdaq-100 technology leaders prior to QQQ's launch.
- **Continuous Backward Chaining**:
  $$TR_{t-1} = \frac{TR_t}{1 + r_{\text{tr}, t}}, \quad \text{where } r_{\text{tr}, t} = r_{\text{pr}, t} + y_t \text{ and } r_{\text{pr}, t} = \frac{NDX_t - NDX_{t-1}}{NDX_{t-1}}$$
  Keeping raw float precision during recursion and rounding to 2 decimal places in export datasets. Annual closes are extracted directly as $TR_{\text{year}} = TR_{\text{year-Q4}}$.

## Rebuilding Datasets

All datasets (annual and quarterly) can be rebuilt deterministically from raw files at any time:
```bash
python3 scripts/build_datasets_from_raw.py
```
