"""Derive quarter-end price series for constituents that have no vendor price file.

Zero external dependencies - Python 3 standard library only.

The Q4 counterpart is derive_constituent_series.py, which reads the audited December-31
rosters. This reads two quarters, from two filers, by the same value/shares quotient and
through the same issuer-to-ticker map:

  Q2  Vanguard 500 Index Fund semi-annual (June 30), via
      extract_vanguard_semiannual_rosters.py. Values in THOUSANDS. UNAUDITED.
  Q3  SPDR S&P 500 Trust annual (September 30), already archived, via
      extract_ground_truth_from_sec.parse_n30d_filing. Values in EXACT DOLLARS. AUDITED,
      because September 30 is SPY's fiscal year end from 1997, so its September report is
      the annual one and carries a Report of Independent Accountants.

The two differ in unit and in grade, and both differences are handled explicitly rather
than averaged over: the unit in the quotient, the grade in a per-observation flag.

Why this exists: constituents recovered from the audited rosters were priced from
December-31 filings only, so they had no Q1-Q3 observation and were dropped from the
quarterly universe entirely, leaving the quarterly path carrying a survivorship bias the
annual path no longer has. See issue #63.

GRADE. Every observation carries an `audited` flag. Q2 is false and Q3 is true, and a Q4
observation from derive_constituent_series.py is audited. The flag is recorded per
observation rather than per dataset, so a consumer reading a single price can tell which
grade it is holding without knowing which quarter it came from.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.derive_constituent_series import _split_factor, normalise
from scripts.extract_ground_truth_from_sec import (
    FILINGS_DIR,
    N30D_HISTORICAL_FILINGS,
    parse_n30d_filing,
)

ROSTERS_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "vanguard_semiannual_rosters.json"
MAP_PATH = PROJECT_ROOT / "data" / "raw" / "constituents" / "issuer_ticker_map.json"
SPLITS_PATH = PROJECT_ROOT / "data" / "raw" / "corporate_actions" / "splits.json"
TICKERS_DIR = PROJECT_ROOT / "data" / "raw" / "tickers"
OUTPUT_PATH = (
    PROJECT_ROOT / "data" / "raw" / "ground_truth" / "derived_quarterly_constituent_series.json"
)


def _q3_rosters() -> Dict[str, Dict[str, Any]]:
    """SPY September-30 schedules, normalised to the shape the Q2 rosters use.

    SPY reports position values in exact dollars where Vanguard reports thousands, so the
    value is divided back by 1000 here rather than special-casing the quotient below. That
    keeps one derivation path for both filers and puts the unit difference in one place.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for period, filename, accession, _form, report_date, _filed in N30D_HISTORICAL_FILINGS:
        if not period.endswith("-Q3"):
            continue
        parsed = parse_n30d_filing(FILINGS_DIR / filename)
        out[period] = {
            "report_date": report_date,
            "accession_number": accession,
            "source_file": f"data/raw/ground_truth/sec_filings/{filename}",
            "audited": True,
            "holdings": [
                {
                    "rank": h["rank"],
                    "name": h["name"],
                    "shares": h["shares"],
                    "value_usd_thousands": h["val"] / 1000.0,
                }
                for h in parsed["holdings"]
            ],
        }
    return out


def derive() -> Dict[str, Any]:
    with open(ROSTERS_PATH, "r", encoding="utf-8") as f:
        rosters = json.load(f)["rosters_by_period"]
    rosters = {**rosters, **_q3_rosters()}
    with open(MAP_PATH, "r", encoding="utf-8") as f:
        issuer_map = {normalise(k): v for k, v in json.load(f)["map"].items()}
    with open(SPLITS_PATH, "r", encoding="utf-8") as f:
        split_records = json.load(f)["splits_by_ticker"]

    observations: Dict[str, Dict[str, Any]] = {}
    for period in sorted(rosters):
        roster = rosters[period]
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
                "audited": roster["audited"],
            }
            record = split_records.get(ticker)
            if record is not None:
                factor = _split_factor(record["splits"], roster["report_date"])
                entry["split_factor"] = round(factor, 6)
                entry["split_adjusted_price_usd"] = round(price / factor, 4)
                entry["split_source_accession"] = record["accession_number"]
            observations.setdefault(ticker, {})[period] = entry

    unadjusted = sorted(t for t in observations if t not in split_records)
    return {
        "description": (
            "Quarter-end price series for S&P 500 constituents with no vendor price file, "
            "derived as market value divided by share count from the Vanguard June-30 "
            "semi-annual rosters (Q2) and the SPY September-30 annual filings (Q3)."
        ),
        "sources": {
            "Q2": "data/raw/ground_truth/vanguard_semiannual_rosters.json",
            "Q3": "SPY September-30 annual filings in data/raw/ground_truth/sec_filings/",
        },
        "issuer_resolution": "data/raw/constituents/issuer_ticker_map.json",
        "split_records": "data/raw/corporate_actions/splits.json",
        "grade": (
            "MIXED, recorded per observation in the audited flag. Q3 is audited: SPY's "
            "fiscal year ends September 30 from 1997, so its September report is the "
            "annual one. Q2 is unaudited: Vanguard's fiscal year ends December 31, so its "
            "June report is the semi-annual one. Do not read the two as one grade."
        ),
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
    audited = sum(1 for v in series.values() for o in v.values() if o["audited"])
    print(
        f"{total} observations across {len(series)} tickers "
        f"({audited} audited Q3, {total - audited} unaudited Q2)"
    )
    for ticker in sorted(series):
        periods = sorted(series[ticker])
        print(f"  {ticker:8s} {len(periods):2d}  {periods[0]} .. {periods[-1]}")
    print(f"Written: {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
