"""Derive year-end price series for constituents that have no vendor price file.

Zero external dependencies - Python 3 standard library only.

Prices come from the audited December-31 rosters (docs/DATA_PROVENANCE.md 4.3.10), where
every position carries a share count and a market value, so the closing price is their
quotient. Issuer names are resolved through data/raw/constituents/issuer_ticker_map.json
because filed names are not stable across years (4.3.11).

This supersedes the name-pattern extraction in extract_vanguard_prices.py as the source of
constituent series. The rosters are strictly better to read from: each one reconciles
dollar-exact to its filing's stated total, so a missing position is caught rather than
silently skipped, and the map removes the per-ticker regexes that previously matched
Exxon Mobil for Mobil and DuPont Photomasks for DuPont. Where both methods produce a price
they agree on all 134 observations, which is asserted by test.

Output is split-adjusted only where a filing-cited split record exists in
data/raw/corporate_actions/splits.json. A ticker without one is published as-traded and
flagged, because a split inside the holding period would otherwise register as a price
collapse that never happened.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

ROSTERS_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "vanguard_audited_rosters.json"
MAP_PATH = PROJECT_ROOT / "data" / "raw" / "constituents" / "issuer_ticker_map.json"
SPLITS_PATH = PROJECT_ROOT / "data" / "raw" / "corporate_actions" / "splits.json"
TICKERS_DIR = PROJECT_ROOT / "data" / "raw" / "tickers"
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "derived_constituent_series.json"

# Footnote markers and trailing punctuation vary between filings and carry no meaning.
_MARKERS = re.compile(r"^[#*^\s]+")


def normalise(name: str) -> str:
    return _MARKERS.sub("", name).strip().rstrip(".").strip()


def _split_factor(splits, as_of: str) -> float:
    """Divisor converting an as-traded price at as_of into final share terms."""
    factor = 1.0
    for split in splits:
        if split["effective_date"] > as_of:
            factor *= split["ratio"]
    return factor


def derive() -> Dict[str, Any]:
    with open(ROSTERS_PATH, "r", encoding="utf-8") as f:
        rosters = json.load(f)["rosters_by_year"]
    with open(MAP_PATH, "r", encoding="utf-8") as f:
        issuer_map = {normalise(k): v for k, v in json.load(f)["map"].items()}
    with open(SPLITS_PATH, "r", encoding="utf-8") as f:
        split_records = json.load(f)["splits_by_ticker"]

    observations: Dict[str, Dict[str, Any]] = {}
    for year in sorted(rosters, key=int):
        roster = rosters[year]
        for holding in roster["holdings"]:
            if holding.get("unidentified") or holding["shares"] <= 0:
                continue
            ticker = issuer_map.get(normalise(holding["name"]))
            if ticker is None:
                continue
            # A vendor file is the authoritative source where one exists; deriving over it
            # would give one constituent two series adjusted to different bases.
            if (TICKERS_DIR / f"{ticker}.json").exists():
                continue

            price = holding["value_usd_thousands"] * 1000.0 / holding["shares"]
            entry = {
                "price_usd": round(price, 2),
                "matched_name": holding["name"],
                "rank": holding["rank"],
                "shares": holding["shares"],
                "value_usd_thousands": holding["value_usd_thousands"],
                "report_date": roster["report_date"],
                "accession_number": roster["accession_number"],
                "source_file": roster["source_file"],
            }
            record = split_records.get(ticker)
            if record is not None:
                factor = _split_factor(record["splits"], roster["report_date"])
                entry["split_factor"] = round(factor, 6)
                entry["split_adjusted_price_usd"] = round(price / factor, 4)
                entry["split_source_accession"] = record["accession_number"]
            observations.setdefault(ticker, {})[year] = entry

    unadjusted = sorted(t for t in observations if t not in split_records)
    return {
        "description": (
            "Year-end price series for S&P 500 constituents with no vendor price file, "
            "derived from the audited December-31 rosters as market value divided by "
            "share count."
        ),
        "source": "data/raw/ground_truth/vanguard_audited_rosters.json",
        "issuer_resolution": "data/raw/constituents/issuer_ticker_map.json",
        "split_records": "data/raw/corporate_actions/splits.json",
        "adjustment_status": (
            "price_usd is AS-TRADED. split_adjusted_price_usd is present only where a "
            "filing-cited split record exists, and is expressed in the share terms of "
            "that registrant's final observation rather than of 2024-12-31, so it is NOT "
            "directly comparable to the series in data/raw/tickers/."
        ),
        "tickers_without_a_split_record": unadjusted,
        "series_by_ticker": observations,
    }


def main() -> None:
    data = derive()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    series = data["series_by_ticker"]
    total = sum(len(v) for v in series.values())
    adjusted = sum(
        1 for v in series.values() for o in v.values() if "split_adjusted_price_usd" in o
    )
    print(f"{total} observations across {len(series)} tickers; {adjusted} split-adjusted")
    if data["tickers_without_a_split_record"]:
        print("  awaiting a split record: " + ", ".join(data["tickers_without_a_split_record"]))
    print(f"Written: {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
