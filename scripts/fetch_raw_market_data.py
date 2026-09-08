"""Fetch raw historical market data, splits, and dividends from Yahoo Finance.

Zero external dependencies - Python 3 standard library only.
Saves raw unmanipulated JSON responses into data/raw/.
"""

import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO",
    "BRK.B", "JPM", "LLY", "UNH", "V", "PG", "HD", "XOM",
    "JNJ", "WFC", "BAC", "C", "AIG", "IBM", "CVX", "WMT",
    "GE", "PFE", "CSCO", "INTC", "KO", "MRK", "MO", "T", "HPQ",
]

BENCHMARKS = ["^GSPC", "^SP500TR"]

# Symbol translations for Yahoo Finance API
SYMBOL_MAP = {
    "BRK.B": "BRK-B",
}

# Sanitized filename mappings for benchmarks
BENCHMARK_FILE_MAP = {
    "^GSPC": "GSPC.json",
    "^SP500TR": "SP500TR.json",
}

# 1993-01-01 to 2024-12-31 UTC
PERIOD1 = 725846400   # 1993-01-01 00:00:00 UTC
PERIOD2 = 1735689600  # 2024-12-31 00:00:00 UTC

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def fetch_symbol_chart(symbol: str, retries: int = 3) -> dict:
    """Fetch raw JSON chart response from Yahoo Finance with curl fallback."""
    query_symbol = SYMBOL_MAP.get(symbol, symbol)
    encoded_symbol = urllib.parse.quote(query_symbol)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?"
        f"period1={PERIOD1}&period2={PERIOD2}&interval=1mo&events=div%2Csplit"
    )

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except Exception:
            # Fallback to curl
            try:
                out = subprocess.check_output(
                    ["curl", "-s", "-A", USER_AGENT, url],
                    timeout=15,
                )
                data = json.loads(out.decode("utf-8"))
                if "chart" in data and data["chart"].get("result"):
                    return data
            except Exception as e2:
                if attempt == retries:
                    raise RuntimeError(f"Failed to fetch {symbol}: {e2}") from e2
            time.sleep(1.5 * attempt)


def main():
    root_dir = Path(__file__).resolve().parent.parent
    raw_tickers_dir = root_dir / "data" / "raw" / "tickers"
    raw_benchmarks_dir = root_dir / "data" / "raw" / "benchmarks"
    raw_constituents_dir = root_dir / "data" / "raw" / "constituents"

    raw_tickers_dir.mkdir(parents=True, exist_ok=True)
    raw_benchmarks_dir.mkdir(parents=True, exist_ok=True)
    raw_constituents_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching raw data for {len(TICKERS)} tickers and {len(BENCHMARKS)} benchmarks...")

    # Fetch benchmarks
    for bmk in BENCHMARKS:
        filename = BENCHMARK_FILE_MAP[bmk]
        target_path = raw_benchmarks_dir / filename
        print(f"Fetching benchmark: {bmk} -> {target_path.name}")
        data = fetch_symbol_chart(bmk)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        time.sleep(0.5)

    # Fetch tickers
    for idx, ticker in enumerate(TICKERS, 1):
        target_path = raw_tickers_dir / f"{ticker}.json"
        print(f"[{idx}/{len(TICKERS)}] Fetching ticker: {ticker} -> {target_path.name}")
        data = fetch_symbol_chart(ticker)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        time.sleep(0.5)

    print("Finished fetching all raw market data.")


if __name__ == "__main__":
    main()
