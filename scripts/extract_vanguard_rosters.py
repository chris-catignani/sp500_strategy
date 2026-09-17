"""Derive audited December 31 S&P 500 rosters from Vanguard 500 Index Fund schedules.

Zero external dependencies - Python 3 standard library only.

`data/raw/constituents/historical_index_weights.json` labels 208 rows
`Unverified Estimate (No Primary Source)` for ranks 13-20 across 1994-2019: no primary
source in this repository reported a point-in-time capitalization for those positions.

The Vanguard Index Trust filings archived under #59 do. The 500 Index Fund tracks the
S&P 500, so its Schedule of Investments at each December 31 is an audited point-in-time
roster of the index, with every constituent's market value. Ranking that schedule yields
year-end ranks and weights that are read rather than estimated.

Each filing contains several Vanguard funds. The 500 Index Fund's schedule is the first
in the document, ending at the first total-common-stocks marker, and the parsed positions
are required to sum to the total the filing itself states.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.extract_ground_truth_from_sec import (
    ScheduleParseError,
    _extract_n30d_positions,
    _html_schedule_rows,
)
from scripts.extract_vanguard_prices import _primary_document

FILINGS_DIR = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sec_filings"
MANIFEST_PATH = FILINGS_DIR / "vanguard_annual_filings_manifest.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "vanguard_audited_rosters.json"

# The schedule footer. Matched case-sensitively: a lower-case "Total Common Stocks"
# appears earlier in the filing's explanatory prose describing how net assets are
# computed, and matching it would bound the schedule to zero rows.
_TEXT_TOTAL = re.compile(r"^\s*TOTAL COMMON STOCKS")
_HTML_TOTAL = re.compile(r"Total Common Stocks", re.IGNORECASE)
_MONEY = re.compile(r"^[\d,]+$")

# An S&P 500 tracker holds roughly five hundred stocks. The bound is wide enough for
# dual-class issuers and index turnover, and narrow enough that no other fund in these
# filings satisfies it.
_PLAUSIBLE_SP500_COUNT = (450, 540)


def _clean_name(name: str) -> str:
    """Strip position markers and absorbed rule characters from an issuer name.

    Fixed-width schedules separate sections with dashed rules, and a rule adjacent to a
    wrapped name is absorbed as a leading fragment, producing names such as
    "- - Microsoft Corp".
    """
    return re.sub(r"^[\s*^\-]+", "", name).strip().rstrip(".").strip() or name.strip()


def _figure(cell: str) -> str:
    """Strip a leading currency marker so the first row of a section is not dropped.

    The topmost position in each HTML section carries its value as "$ 99,997" while the
    rows beneath it carry a bare number. Treating the dollar sign as part of the text
    silently drops one position per section, which the reconciliation check then reports
    as a short read.
    """
    return cell.replace("$", "").replace("\xa0", " ").strip()


def _text_roster(text: str) -> Tuple[List[Dict[str, Any]], float]:
    """Select the 500 Index Fund's schedule from among the several a filing contains.

    Selection is by position count, not document order. The 500 Index Fund is not always
    the first schedule -- in the FY2002 filing the first is a far smaller fund holding
    148 stocks, which reconciles perfectly against its own total and is simply the wrong
    fund. Holding roughly five hundred stocks is the property that identifies an S&P 500
    tracker, and it cannot be satisfied by accident.
    """
    lines = text.split("\n")
    markers = [i for i, line in enumerate(lines) if _TEXT_TOTAL.match(line)]
    if not markers:
        raise ScheduleParseError("no schedule marker found")

    headers = [
        i for i, line in enumerate(lines) if "STATEMENT OF NET ASSETS" in line.upper()
    ]

    best: Tuple[List[Dict[str, Any]], float] = None
    previous_marker = 0
    for end in markers:
        # Each schedule begins at its own statement header. Bounding from the preceding
        # marker instead would sweep in the financial-highlights tables that sit between
        # two funds and inflate the position count past recognition.
        # The earliest filings carry no statement header in this form, so the preceding
        # schedule's total serves as the boundary instead.
        preceding = [h for h in headers if h < end]
        start = max(preceding[-1] if preceding else 0, previous_marker)
        positions = _extract_n30d_positions(lines, start, end)
        previous_marker = end
        if not _PLAUSIBLE_SP500_COUNT[0] <= len(positions) <= _PLAUSIBLE_SP500_COUNT[1]:
            continue
        stated = None
        for line in lines[end : end + 4]:
            figures = re.findall(r"([\d,]{6,})", line.replace("(COST $", "(COST "))
            if figures:
                stated = float(figures[-1].replace(",", ""))
                break
        if stated is None:
            continue
        # Where more than one schedule is S&P-500-sized, the 500 Index Fund is the
        # largest; the others are sector or style slices of the same universe.
        if best is None or stated > best[1]:
            best = (positions, stated)

    if best is None:
        raise ScheduleParseError(
            "no schedule held a plausible S&P 500 position count "
            f"{_PLAUSIBLE_SP500_COUNT}"
        )
    return best


def _html_roster(text: str) -> Tuple[List[Dict[str, Any]], float]:
    rows = _html_schedule_rows(text)
    end = next(
        (i for i, row in enumerate(rows) if any(_HTML_TOTAL.search(c) for c in row)), None
    )
    if end is None:
        raise ScheduleParseError("no total-common-stocks row found")

    positions: List[Dict[str, Any]] = []
    pending = ""
    for row in rows[:end]:
        cells = [c for c in row if c not in {"*", "(1)", "^"}]
        if not cells:
            continue

        # A long issuer name is split across rows, the first carrying no figures. The
        # fragment is held and prepended to the row that completes it; dropping it would
        # lose the position and the schedule would no longer reconcile.
        if len(cells) == 1 and not _MONEY.match(_figure(cells[0])):
            pending = (pending + " " + cells[0]).strip()
            continue
        if len(cells) < 3:
            pending = ""
            continue

        name = cells[0]
        shares_cell, value_cell = _figure(cells[1]), _figure(cells[2])
        if not _MONEY.match(shares_cell) or not _MONEY.match(value_cell):
            pending = ""
            continue
        shares = float(shares_cell.replace(",", ""))
        value = float(value_cell.replace(",", ""))
        if shares > 0 and value > 0:
            full = re.sub(r"\s+", " ", f"{pending} {name}").strip()
            positions.append({"name": full, "shares": shares, "val": value})
        pending = ""

    # The figure sits on the marker row in some years and on the row beneath it in
    # others, where the marker row carries only the label and the next carries the cost
    # basis and the total.
    stated = None
    for row in rows[end : end + 3]:
        figures = [_figure(c) for c in row if _MONEY.match(_figure(c))]
        if figures:
            stated = float(figures[-1].replace(",", ""))
            break
    if stated is None:
        raise ScheduleParseError("no figure on or after the total-common-stocks row")
    return positions, stated


def build_roster(path: Path) -> Dict[str, Any]:
    text = _primary_document(path.read_text(encoding="utf-8", errors="replace"))
    positions, stated = (_html_roster if "<TD" in text or "<td" in text else _text_roster)(text)
    if not positions:
        raise ScheduleParseError(f"{path.name}: schedule parsed to zero positions")

    parsed = sum(p["val"] for p in positions)
    # Dollar-exact reconciliation against the filing's own figure. A schedule that reads
    # short is indistinguishable from one that read completely unless this is enforced,
    # which is how a previous parser silently dropped rows (docs/DATA_PROVENANCE.md 4.3.6).
    if round(parsed) != round(stated):
        raise ScheduleParseError(
            f"{path.name}: parsed {parsed:,.0f} against stated {stated:,.0f} "
            f"(difference {parsed - stated:,.0f}). Refusing to publish a short read."
        )

    ranked = sorted(positions, key=lambda p: -p["val"])
    return {
        "position_count": len(ranked),
        "stated_total_usd_thousands": stated,
        "parsed_total_usd_thousands": parsed,
        "holdings": [
            {
                "rank": i,
                "name": _clean_name(p["name"]),
                "shares": int(p["shares"]),
                "value_usd_thousands": int(p["val"]),
                "weight": round(p["val"] / parsed, 6),
            }
            for i, p in enumerate(ranked, 1)
        ],
    }


def extract_all() -> Dict[str, Any]:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    rosters = {}
    unreconciled = {}
    for year_key in sorted(manifest, key=int):
        entry = manifest[year_key]
        try:
            roster = build_roster(PROJECT_ROOT / entry["file_path"])
        except ScheduleParseError as exc:
            # A roster that will not reconcile is withheld, not published with a caveat.
            # A short read is indistinguishable from a complete one once it is in a
            # dataset, so the year is recorded as unresolved instead.
            unreconciled[year_key] = str(exc)
            continue
        roster.update(
            {
                "report_date": entry["report_date"],
                "accession_number": entry["accession_number"],
                "form": entry["form"],
                "source_file": entry["file_path"],
            }
        )
        rosters[year_key] = roster

    return {
        "description": (
            "Audited December 31 rosters of the S&P 500, derived by ranking the Vanguard "
            "500 Index Fund's Schedule of Investments by market value. Ranks and weights "
            "are read from a primary filing rather than estimated."
        ),
        "source_entity": "Vanguard Index Trust, 500 Index Fund (CIK 0000036405)",
        "derivation": "weight = position market value / sum of all position market values",
        "validation": (
            "Every roster reconciles dollar-exact to the total stated on the face of its "
            "filing; a schedule that reads short raises rather than publishes."
        ),
        "caveat": (
            "These are the fund's holdings, not the index's published constituent weights. "
            "A full-replication index fund tracks the index closely but its weights reflect "
            "its own positions, including any sampling or cash drag, and the fund's total "
            "is its equity holdings rather than the index's float-adjusted capitalization."
        ),
        "unreconciled_years": unreconciled,
        "coverage": (
            "Rosters are published for 1996-2003. The 1994 and 1995 filings lay their "
            "schedules out differently and no candidate span yields a plausible S&P 500 "
            "position count; the 2004-2006 HTML filings drop a small number of positions "
            "whose name and share cells render empty, leaving an orphaned value. Both are "
            "recorded in unreconciled_years rather than published with a caveat."
        ),
        "coverage_note": (
            "Rosters are published only for years whose schedule reconciles dollar-exact. "
            "The HTML-era filings (2004-2006) drop a small number of positions whose name "
            "and share cells render empty, leaving an orphaned value; those years are "
            "listed in unreconciled_years and are NOT published. Every year a constituent "
            "missing from data/raw/tickers/ reaches a filing's Top 20 falls in the "
            "reconciled range, with the exception of SBC and DELL in 2004-2005 and BLS in "
            "2006, all at ranks 18-19."
        ),
        "rosters_by_year": rosters,
    }


def main() -> None:
    data = extract_all()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    for year, roster in data["rosters_by_year"].items():
        top = ", ".join(h["name"][:16] for h in roster["holdings"][:3])
        print(f"  {year}: {roster['position_count']:>4} positions  top3: {top}")
    for year, why in data["unreconciled_years"].items():
        print(f"  {year}: WITHHELD - {why.split(': ', 1)[-1][:90]}")
    print(f"\n{len(data['rosters_by_year'])} rosters written to {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
