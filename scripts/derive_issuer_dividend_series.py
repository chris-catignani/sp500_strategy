"""Dividend series for the constituents priced from fund schedules (issue #76).

The nineteen constituents priced from audited rosters (docs/DATA_PROVENANCE.md 4.3.12)
carry no dividend series, because a Schedule of Investments reports holdings rather than
distributions. This script assembles one from the sources 4.3.15 established, converts
each figure into the basis the price series uses, and publishes the result with the
evidence attached.

Four routes, each with its own grade:

- `issuer_table`   -- a quarter published in `issuer_dividend_tables.json`, which has
                      already passed that dataset's reconcile-or-withhold gate.
- `issuer_pinned`  -- a figure read directly from a named filing, where the extractor's
                      annual-line reader mis-aligned the year and withheld a quarter it
                      should have kept. Each is re-read here and gated the same way: the
                      four quarters must sum to the annual per-share figure the same
                      filing states, or nothing is published for that year.
- `vendor`         -- `RD` and `SBC` through their verified successor series (`SHEL` and
                      `T`). This is the grade every row in `sp500_dividends.json` already
                      carries, so it is not a downgrade.
- `sourced_zero`   -- a registrant that states in its own filing that it has never paid.
                      Bounded by the filing dates of the statements, and voided entirely
                      if any later filing of the same registrant reports a payment.

**Basis.** Prices are split-adjusted to each registrant's final observation, not to
2024-12-31 (4.1). A dividend stated in a filing is in the share terms current at that
filing's date, so the conversion into the price basis is

    dividend_in_price_basis = dividend_as_filed / split_factor(filing_date)

AT&T confirms this arithmetic itself: $0.33 a quarter in 1994, filed in 1995 when the
factor is 1.5 x 0.2 = 0.3, converts to $4.40 a year -- and AT&T's FY2002 report restates
1996-1999 as exactly `4.40` after the same two splits. The conversion is not inferred.

The vendor route takes no conversion. Yahoo does not apply SBC's 2022 1324:1000 price
factor to dividend amounts, so scaling by 1.324 would be wrong; SBC's own filings settle
it, stating `$ 0.895 $ 0.86 $ 0.825 $ 0.79` against vendor sums of 0.887/0.851/0.816/0.781.

Run:  python3 scripts/derive_issuer_dividend_series.py
It reaches SEC EDGAR for the pinned reads and caches into the same directory the issuer
table extractor uses. Like `verify_provenance.py` it is not part of the test suite; the
suite asserts the published dataset's invariants offline.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.extract_issuer_dividend_tables import (
    DEFAULT_CACHE_DIR,
    clean_document_text,
    fetch_filing,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "data" / "raw"
TABLES_PATH = RAW / "ground_truth" / "issuer_dividend_tables.json"
SPLITS_PATH = RAW / "corporate_actions" / "splits.json"
MANIFEST_PATH = RAW / "ground_truth" / "issuer_filing_manifest.json"
PRICES_PATH = REPO_ROOT / "data" / "sp500_prices.json"
OUTPUT_PATH = RAW / "ground_truth" / "derived_dividend_series.json"

QUARTER_END = {"Q1": "-03-31", "Q2": "-06-30", "Q3": "-09-30", "Q4": "-12-31"}
CENT = 0.005

# A registrant whose dividends are recoverable from a vendor series for a successor whose
# identity is established by the factor method of 4.3.12. Both were verified against a
# filing-sourced payout before use; see the module docstring.
VENDOR_ROUTE = {"RD": "SHEL", "SBC": "T"}

# A registrant whose own filings contradict a never-paid statement it filed earlier. The
# statement is true for the years it was filed about and false afterwards, so the zero is
# bounded rather than discarded -- and it must never be extended forward by default.
CONTRADICTED_ZEROS = {
    "VIA": {
        "first_paid_period": "2003-Q3",
        "accession_number": "0001047469-04-007840",
        "quoted_sentence": (
            "Viacom Inc.'s Board of Directors declared a quarterly cash dividend of $.06 "
            "per share on its common stock during the third and fourth quarters of 2003."
        ),
        "note": (
            "Viacom filed never-paid statements for eight years and then began paying. A "
            "ticker-level sourced zero would have zero-filled 2003 onwards, which is why "
            "the zero carries a date bound and this contradiction is recorded beside it. "
            "The dividends themselves are not wired: VIA is never selected in any "
            "scenario, so sourcing them would move nothing and is left to a later pass."
        ),
    },
}

# Years the issuer-table extractor withheld because its annual-line reader took the wrong
# year's cell, not because the quarterly figures were unreadable. Each entry names the
# filing, the quarterly figures to look for and the annual figure they must sum to. The
# reconciliation is re-run here against the filing text -- the pin says where to look, it
# does not assert the number.
PINNED_READS = [
    {
        "ticker": "T_CORP",
        "years": [1995],
        "accession_number": "0000005907-96-000010",
        "filing_date": "1996-02-28",
        "quarterly_line": "Dividends declared .33 .33 .33 .33",
        "annual_per_share": 1.32,
        "note": (
            "Note 20, QUARTERLY INFORMATION (UNAUDITED). The filing states the quarterly "
            "row twice, for 1995 and 1994; both read .33 a quarter, and Selected Financial "
            "Data states 1.32 for each year."
        ),
    },
    {
        "ticker": "T_CORP",
        "years": [1996, 1997],
        "accession_number": "0000005907-98-000013",
        "filing_date": "1998-03-27",
        "quarterly_line": "Dividends declared .33 .33 .33 .33",
        "annual_per_share": 1.32,
        "note": (
            "QUARTERLY INFORMATION (UNAUDITED) carries 1997 and 1996, each at .33 a "
            "quarter; Selected Financial Data states 1.32 for both."
        ),
    },
]


def split_factor(record: Optional[Dict[str, Any]], as_of: str) -> float:
    """Divisor converting an as-traded figure at as_of into final share terms."""
    factor = 1.0
    for split in (record or {}).get("splits", []):
        if split["effective_date"] > as_of:
            factor *= split["ratio"]
    return factor


def _blank_series() -> Dict[str, Any]:
    return {"annual": {}, "quarterly": {}, "sourced_zero": None, "notes": []}


def from_issuer_tables(tables, splits, series):
    """Quarters already gated by the reconcile-or-withhold rule of 4.3.15."""
    published = 0
    for ticker, body in sorted(tables.items()):
        quarters = body.get("quarters") or {}
        by_year: Dict[str, List[float]] = {}
        for period, quarter in sorted(quarters.items()):
            as_filed = quarter.get("dividend_declared_per_share")
            if as_filed is None:
                continue
            factor = split_factor(splits.get(ticker), quarter["filing_date"])
            converted = round(as_filed / factor, 6)
            series.setdefault(ticker, _blank_series())["quarterly"][period] = {
                "dividend_per_share": converted,
                "as_filed": as_filed,
                "filing_basis_factor": round(factor, 6),
                "accession_number": quarter["accession_number"],
                "filing_date": quarter["filing_date"],
                "route": "issuer_table",
                "grade": "filing_quoted",
                "audited": quarter.get("audited", False),
            }
            by_year.setdefault(period.split("-")[0], []).append(converted)
            published += 1
        for year, values in by_year.items():
            # A year reaches the annual series only with all four quarters present: the
            # gate in 4.3.15 reconciles a whole year, and three quarters of one is not a
            # year's dividend under any reading.
            if len(values) != 4:
                series[ticker]["notes"].append(
                    f"{year}: {len(values)} quarters published, annual figure withheld"
                )
                continue
            series[ticker]["annual"][year] = {
                "dividend_per_share": round(sum(values), 6),
                "route": "issuer_table",
                "grade": "filing_quoted",
                "quarters_summed": 4,
            }
    return published


def from_pinned_reads(splits, series, cache_dir, cik_map):
    """Re-read a withheld year from its filing, gated by the same reconciliation."""
    published, refused = 0, []
    for pin in PINNED_READS:
        ticker = pin["ticker"]
        try:
            text = clean_document_text(
                fetch_filing(str(cik_map.get(ticker)), pin["accession_number"], cache_dir)
            )
        except Exception as exc:  # network or archive failure: publish nothing
            refused.append({**pin, "reason": f"fetch failure: {exc}"})
            continue

        if pin["quarterly_line"] not in text:
            refused.append({**pin, "reason": "quoted quarterly line absent from filing"})
            continue
        values = [float(v) for v in re.findall(r"\.\d+|\d+\.\d+", pin["quarterly_line"])]
        if len(values) != 4 or abs(sum(values) - pin["annual_per_share"]) > CENT:
            refused.append({
                **pin,
                "reason": f"quarters sum to {sum(values)}, annual states {pin['annual_per_share']}",
            })
            continue
        if f"{pin['annual_per_share']:.2f}" not in text:
            refused.append({**pin, "reason": "annual per-share figure absent from filing"})
            continue

        factor = split_factor(splits.get(ticker), pin["filing_date"])
        target = series.setdefault(ticker, _blank_series())
        for year in pin["years"]:
            for index, label in enumerate(("Q1", "Q2", "Q3", "Q4")):
                period = f"{year}-{label}"
                if period in target["quarterly"]:
                    continue
                target["quarterly"][period] = {
                    "dividend_per_share": round(values[index] / factor, 6),
                    "as_filed": values[index],
                    "filing_basis_factor": round(factor, 6),
                    "accession_number": pin["accession_number"],
                    "filing_date": pin["filing_date"],
                    "route": "issuer_pinned",
                    "grade": "filing_quoted",
                    "audited": False,
                    "quoted_line": pin["quarterly_line"],
                    "note": pin["note"],
                }
                published += 1
            target["annual"].setdefault(str(year), {
                "dividend_per_share": round(pin["annual_per_share"] / factor, 6),
                "as_filed": pin["annual_per_share"],
                "filing_basis_factor": round(factor, 6),
                "accession_number": pin["accession_number"],
                "route": "issuer_pinned",
                "grade": "filing_quoted",
            })
    return published, refused


def from_vendor(series, price_span):
    """RD and SBC, through the successor series their identity was established against.

    Bounded to the registrant's own price series. The successor keeps trading and keeps
    paying long after the registrant stops being priceable here, and a dividend recorded
    for a year this repository cannot price would read as Royal Dutch having paid it.
    """
    published = 0
    for ticker, vendor_ticker in sorted(VENDOR_ROUTE.items()):
        path = RAW / "tickers" / f"{vendor_ticker}.json"
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            chart = json.load(f)["chart"]["result"][0]
        events = (chart.get("events") or {}).get("dividends") or {}
        target = series.setdefault(ticker, _blank_series())
        annual: Dict[str, float] = {}
        quarterly: Dict[str, float] = {}
        for event in events.values():
            moment = datetime.datetime.utcfromtimestamp(event["date"])
            period = f"{moment.year}-Q{(moment.month - 1) // 3 + 1}"
            annual[str(moment.year)] = round(annual.get(str(moment.year), 0.0) + event["amount"], 6)
            quarterly[period] = round(quarterly.get(period, 0.0) + event["amount"], 6)
        first_year, last_year = price_span.get(ticker, (None, None))
        if first_year is None:
            continue
        annual = {y: a for y, a in annual.items() if first_year <= int(y) <= last_year}
        quarterly = {p: a for p, a in quarterly.items() if first_year <= int(p[:4]) <= last_year}
        for year, amount in sorted(annual.items()):
            target["annual"][year] = {
                "dividend_per_share": amount,
                "route": "vendor",
                "grade": "vendor",
                "vendor_ticker": vendor_ticker,
                # No basis conversion: see the module docstring. The vendor applies split
                # adjustment to dividend amounts but not the 2022 SBC share-exchange
                # factor, which is the trap #76's thread records hitting.
                "filing_basis_factor": 1.0,
            }
        for period, amount in sorted(quarterly.items()):
            target["quarterly"][period] = {
                "dividend_per_share": amount,
                "route": "vendor",
                "grade": "vendor",
                "vendor_ticker": vendor_ticker,
                "filing_basis_factor": 1.0,
            }
            published += 1
    return published


def from_sourced_zeros(tables, manifest, series):
    """A zero that is read rather than assumed, bounded by the dates it was read on."""
    recorded = []
    for ticker, body in sorted(tables.items()):
        statements = body.get("never_paid_statements") or []
        if not statements:
            continue
        paid = [
            period for period, quarter in (body.get("quarters") or {}).items()
            if (quarter.get("dividend_declared_per_share") or 0) > 0
        ]
        latest = max(s["filing_date"] for s in statements)
        earliest = min(s["filing_date"] for s in statements)
        # A statement filed in 2000 says nothing about 2003. Where the registrant's own
        # later filings are in the manifest but carry no statement, the zero stops at the
        # last filing that does -- and where a later filing reports a payment, the zero is
        # void rather than merely bounded. Viacom is the case that forces this: it filed
        # these statements for eight years and then declared $.06 a quarter in 2003-Q3.
        contradicted = sorted(f for f in manifest.get(ticker, []) if f[0] > latest)
        entry = series.setdefault(ticker, _blank_series())
        contradiction = CONTRADICTED_ZEROS.get(ticker)
        entry["sourced_zero"] = {
            "through_filing_date": latest,
            "earliest_filing_date": earliest,
            "statement_count": len(statements),
            "statements": statements[:3],
            "later_filings_without_a_statement": [f[2] for f in contradicted],
            "contradicted_by_a_later_filing": contradiction,
            "voided": bool(paid) or contradiction is not None,
        }
        if contradiction:
            entry["notes"].append(
                f"sourced zero bounded at {contradiction['first_paid_period']}: "
                f"{contradiction['accession_number']} reports a payment"
            )
        if paid:
            entry["notes"].append(
                f"sourced zero void: the same dataset publishes paid quarters {sorted(paid)[:4]}"
            )
        recorded.append(ticker)
    return recorded


def build(cache_dir: Path) -> Dict[str, Any]:
    with open(TABLES_PATH, "r", encoding="utf-8") as f:
        tables = json.load(f)["tickers"]
    with open(SPLITS_PATH, "r", encoding="utf-8") as f:
        splits = json.load(f)["splits_by_ticker"]
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)["filings_by_ticker"]

    with open(PRICES_PATH, "r", encoding="utf-8") as f:
        prices = json.load(f)
    price_span = {
        ticker: (int(min(years)), int(max(years)))
        for ticker, years in prices.items() if years
    }

    series: Dict[str, Dict[str, Any]] = {}
    table_quarters = from_issuer_tables(tables, splits, series)
    cik_map = {t: splits.get(t, {}).get("cik") for t in manifest}
    pinned_quarters, refused = from_pinned_reads(splits, series, cache_dir, cik_map)
    vendor_quarters = from_vendor(series, price_span)
    zeros = from_sourced_zeros(tables, manifest, series)

    return {
        "description": (
            "Dividend series for the constituents priced from fund Schedules of "
            "Investments, assembled from the sources docs/DATA_PROVENANCE.md 4.3.15 "
            "established and converted into the basis the price series uses."
        ),
        "basis": (
            "dividend_per_share is expressed in the share terms of the registrant's final "
            "price observation, matching data/sp500_prices.json. as_filed, where present, "
            "is the figure the filing states, in that filing's own share terms."
        ),
        "generated_by": "scripts/derive_issuer_dividend_series.py",
        "metadata": {
            "quarters_from_issuer_tables": table_quarters,
            "quarters_from_pinned_reads": pinned_quarters,
            "quarters_from_vendor": vendor_quarters,
            "sourced_zero_tickers": zeros,
            "pinned_reads_refused": refused,
            "tickers_with_a_series": sorted(
                t for t, v in series.items() if v["annual"] or v["quarterly"]
            ),
        },
        "series_by_ticker": {k: series[k] for k in sorted(series)},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    payload = build(args.cache_dir)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    meta = payload["metadata"]
    print(f"Wrote {args.output.relative_to(REPO_ROOT)}")
    print(
        f"  quarters: {meta['quarters_from_issuer_tables']} from issuer tables, "
        f"{meta['quarters_from_pinned_reads']} pinned, {meta['quarters_from_vendor']} vendor"
    )
    print(f"  sourced zeros: {', '.join(meta['sourced_zero_tickers']) or 'none'}")
    if meta["pinned_reads_refused"]:
        print(f"  REFUSED pinned reads: {len(meta['pinned_reads_refused'])}")
        for r in meta["pinned_reads_refused"]:
            print(f"    {r['ticker']} {r['years']}: {r['reason']}")


if __name__ == "__main__":
    main()
