# S&P 500 Top N Strategy Datasets

This directory contains the point-in-time constituent snapshots, split-adjusted prices, and dividend histories used by the backtest engine across the 31-year evaluation period (1994–2024).

For full details on sources, formulas, corporate actions, and rebuild instructions, see:
[`docs/DATA_PROVENANCE.md`](../docs/DATA_PROVENANCE.md)

## Directory Structure

- `raw/`: **Immutable Raw API Data**
  - `benchmarks/`: Raw JSON chart responses for `^GSPC`, `^SP500TR`, `^MSCIWORLD_PR`, and `^MSCIWORLD_TR`.
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

## Rebuilding Datasets

All datasets (annual and quarterly) can be rebuilt deterministically from raw files at any time:
```bash
python3 scripts/build_datasets_from_raw.py
```
