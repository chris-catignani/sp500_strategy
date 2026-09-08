# S&P 500 Top N Strategy Datasets

This directory contains the point-in-time constituent snapshots, split-adjusted prices, and dividend histories used by the backtest engine across the 31-year evaluation period (1994–2024).

For full details on sources, formulas, corporate actions, and rebuild instructions, see:
[`docs/DATA_PROVENANCE.md`](../docs/DATA_PROVENANCE.md)

## Directory Structure

- `raw/`: **Immutable Raw API Data**
  - `benchmarks/`: Raw JSON chart responses for `^GSPC` and `^SP500TR`.
  - `tickers/`: Raw JSON chart responses for all 33 equity constituents.
  - `constituents/`: Point-in-time constituent rankings and historical index weights.
- `sp500_prices.json`: Split-adjusted year-end closing prices (1993–2024) normalized to 2024-12-31 share terms.
- `sp500_dividends.json`: Split-adjusted annual cash dividends per share (1994–2024).
- `sp500_constituents.json`: Point-in-time Top 12 constituents per year (1994–2024) with actual S&P 500 market cap weights and verified trailing 1-year returns.

## Rebuilding Datasets

Datasets can be rebuilt deterministically from raw files at any time:
```bash
python3 scripts/build_datasets_from_raw.py
```
