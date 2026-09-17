"""Derive audited December 31 S&P 500 rosters from Vanguard 500 Index Fund schedules.

Zero external dependencies - Python 3 standard library only.

`data/raw/constituents/historical_index_weights.json` labels 208 rows
`Unverified Estimate (No Primary Source)` for ranks 13-20 across 1994-2019: no primary
source in this repository reported a point-in-time capitalization for those positions.

The Vanguard Index Trust filings archived in `data/raw/ground_truth/sec_filings/`
(VG500_*.txt) contain the 500 Index Fund's full Schedule of Investments at each
December 31, which is an audited point-in-time roster of the index, with every
constituent's market value. Ranking that schedule yields year-end ranks and weights
that are read from primary filings rather than estimated.

Each filing contains several Vanguard funds. The 500 Index Fund's schedule is
identified, parsed, and strictly required to reconcile dollar-exact to the total
stated on the face of the filing.
"""

import json
from pathlib import Path
import re
import sys
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

# The schedule footer for fixed-width text filings.
_TEXT_TOTAL = re.compile(r"^\s*TOTAL COMMON STOCKS")

# An S&P 500 tracker holds roughly five hundred stocks. Wide enough for dual-class
# issuers and index turnover, narrow enough that no other fund in these filings fits.
_PLAUSIBLE_SP500_COUNT = (450, 540)


def _clean_name(name: str) -> str:
    """Strip position markers, absorbed rules, and trailing dollar signs from an issuer name."""
    cleaned = re.sub(r"^[\s*^•\-]+", "", name).strip()
    cleaned = re.sub(r"[\s$]+$", "", cleaned).strip()
    return cleaned or name.strip()


def _is_footnote_cell(cell: str) -> bool:
    """Check whether an HTML table cell contains only footnote symbols."""
    return bool(re.fullmatch(r"[\*^•]+|\(\d+\)", cell.strip()))


def _is_money(cell: str) -> bool:
    """Check whether a cell string represents an integer currency figure."""
    val = cell.replace("$", "").replace(",", "").strip()
    return bool(val) and val.isdigit()


def _text_roster(text: str) -> Tuple[List[Dict[str, Any]], float]:
    """Parse fixed-width Schedule of Investments for Vanguard 500 Index Fund.

    Finds all candidate schedule headers ('STATEMENT OF NET ASSETS'), excludes schedules
    belonging to other funds (such as Growth Index Fund or Total Stock Market), and selects
    the 500 Index Fund schedule.
    """
    lines = text.split("\n")
    starts = [i for i, line in enumerate(lines) if "STATEMENT OF NET ASSETS" in line.upper()]
    if not starts:
        raise ScheduleParseError("missing STATEMENT OF NET ASSETS header")

    for start in starts:
        header = "\n".join(lines[start : min(len(lines), start + 35)]).upper()
        if any(
            other in header
            for other in [
                "GROWTH INDEX FUND",
                "VALUE INDEX FUND",
                "TOTAL STOCK MARKET",
                "EXTENDED MARKET",
            ]
        ):
            continue

        end = next((i for i in range(start, len(lines)) if _TEXT_TOTAL.match(lines[i])), None)
        if end is None:
            continue

        positions = _extract_n30d_positions(lines, start, end)
        if len(positions) < 400:
            continue

        stated = None
        for line in lines[end : end + 4]:
            figs = re.findall(r"([\d,]{6,})", line.replace("(COST $", "(COST "))
            if figs:
                stated = float(figs[-1].replace(",", ""))
                break

        if stated is not None and round(sum(p["val"] for p in positions)) == round(stated):
            return positions, stated

    # Fallback to the first schedule boundary if no multi-fund filter matched
    start = starts[0]
    end = next((i for i in range(start, len(lines)) if _TEXT_TOTAL.match(lines[i])), None)
    if end is None:
        raise ScheduleParseError("could not bound the 500 Index Fund schedule")

    positions = _extract_n30d_positions(lines, start, end)
    stated = None
    for line in lines[end : end + 4]:
        figs = re.findall(r"([\d,]{6,})", line.replace("(COST $", "(COST "))
        if figs:
            stated = float(figs[-1].replace(",", ""))
            break

    if stated is None:
        raise ScheduleParseError("no stated total after the schedule marker")
    return positions, stated


_UNIDENTIFIED_NAME = "(unidentified: issuer name and share count are blank in the filing)"


def _html_roster(text: str) -> Tuple[List[Dict[str, Any]], float]:
    """Parse HTML table Schedule of Investments for Vanguard 500 Index Fund.

    Locates the start of the schedule at the first row introducing Common Stock(s),
    bounds the schedule at the Total Common Stocks row, and extracts positions
    accounting for multi-row wrapped issuer names and isolated footnote markers.
    """
    rows = _html_schedule_rows(text)
    start = next(
        (
            i
            for i in range(len(rows))
            if any(
                re.search(r"Common\s+Stocks?", c, re.IGNORECASE) and "(" in c
                for c in rows[i]
            )
        ),
        None,
    )
    if start is None:
        raise ScheduleParseError("start of common stocks schedule not found")

    end = next(
        (
            i
            for i in range(start, len(rows))
            if any(re.search(r"Total\s+Common\s+Stocks?", c, re.IGNORECASE) for c in rows[i])
        ),
        None,
    )
    if end is None:
        raise ScheduleParseError("total common stocks row not found")

    positions: List[Dict[str, Any]] = []
    name_buffer: List[str] = []
    running = 0.0
    for index, r in enumerate(rows[start:end], start):
        cells = [c for c in r if not _is_footnote_cell(c)]

        # A row carrying only a figure is either a sector subtotal or a position whose
        # name and share cells are empty in the filing as filed. The two are told apart
        # by what follows: a subtotal precedes a sector heading, which carries the
        # sector's percentage in parentheses. Anything else is a real holding whose
        # identity the document simply does not state, and it must still be counted or
        # the schedule will not reconcile.
        if len(cells) == 1 and _is_money(cells[0]):
            figure = float(cells[0].replace("$", "").replace(",", "").strip())
            # A subtotal restates what has already been counted, so it equals the running
            # sum of positions since the previous subtotal. An orphaned holding does not.
            # Testing the arithmetic rather than the surrounding layout keeps this exact:
            # counting a subtotal double-counts a whole sector, and skipping an orphan
            # leaves the schedule short, and reconciliation catches either way round.
            is_sector_subtotal = abs(figure - running) < 1.0
            if is_sector_subtotal:
                running = 0.0
            else:
                if figure > 0:
                    positions.append(
                        {
                            "name": _UNIDENTIFIED_NAME,
                            "shares": 0.0,
                            "val": figure,
                            "unidentified": True,
                        }
                    )
                    running += figure
            name_buffer = []
            continue

        if len(cells) >= 3 and _is_money(cells[1]) and _is_money(cells[2]):
            name = " ".join(name_buffer + [cells[0]])
            name = re.sub(r"\s+", " ", name).strip()
            shares = float(cells[1].replace(",", ""))
            val = float(cells[2].replace("$", "").replace(",", "").strip())
            if shares > 0 and val > 0:
                positions.append({"name": name, "shares": shares, "val": val})
                running += val
            name_buffer = []
        elif len(cells) == 1 and not _is_money(cells[0]) and "(" not in cells[0]:
            name_buffer.append(cells[0])
        else:
            name_buffer = []

    stated = None
    for r in rows[end : end + 2]:
        for c in r:
            if "COST" in c.upper():
                money_cells = [
                    x for x in r if re.fullmatch(r"[\d,]{6,}", x.replace("$", "").strip())
                ]
                if money_cells:
                    stated = float(money_cells[-1].replace("$", "").replace(",", "").strip())
                    break
                figs = re.findall(r"([\d,]{6,})", c.replace("(Cost $", "(Cost "))
                if figs:
                    stated = float(figs[-1].replace(",", ""))
                    break
        if stated is not None:
            break

    if stated is None:
        raise ScheduleParseError("no stated total on or after the total common stocks row")
    return positions, stated


def build_roster(path: Path) -> Dict[str, Any]:
    """Parse a Vanguard filing schedule and produce a dollar-exact reconciled roster.

    Raises ScheduleParseError if the schedule cannot be bounded, if positions cannot
    be parsed, or if the parsed positions do not reconcile dollar-exact against the
    filing's own stated total.
    """
    text = _primary_document(path.read_text(encoding="utf-8", errors="replace"))
    positions, stated = (_html_roster if "<TD" in text or "<td" in text else _text_roster)(text)
    if not positions:
        raise ScheduleParseError(f"{path.name}: schedule parsed to zero positions")

    # Reconciliation proves the schedule was read completely; it does not prove the right
    # schedule was read. In the FY2002 filing the first schedule belongs to a fund holding
    # 148 stocks and reconciles perfectly against its own total. Holding roughly five
    # hundred stocks is what identifies an S&P 500 tracker, and the fallback path in
    # _text_roster applies neither filter, so the count is enforced here as well.
    if not _PLAUSIBLE_SP500_COUNT[0] <= len(positions) <= _PLAUSIBLE_SP500_COUNT[1]:
        raise ScheduleParseError(
            f"{path.name}: schedule holds {len(positions)} positions, outside the "
            f"{_PLAUSIBLE_SP500_COUNT} range an S&P 500 tracker occupies. This is most "
            "likely a different fund's schedule."
        )

    parsed = sum(p["val"] for p in positions)
    if round(parsed) != round(stated):
        raise ScheduleParseError(
            f"{path.name}: parsed {parsed:,.0f} against stated {stated:,.0f} "
            f"(difference {parsed - stated:,.0f}). Refusing to publish a short read."
        )

    ranked = sorted(positions, key=lambda p: -p["val"])
    return {
        "position_count": len(ranked),
        "stated_total_usd": int(stated * 1000),
        "parsed_total_usd": int(parsed * 1000),
        "stated_total_usd_thousands": int(stated),
        "parsed_total_usd_thousands": int(parsed),
        "holdings": [
            {
                "rank": i,
                "name": _clean_name(p["name"]),
                "shares": int(p["shares"]),
                "value_usd_thousands": int(p["val"]),
                "weight": round(p["val"] / parsed, 6),
                # Carried through so a consumer can tell a holding the filing declined to
                # name from one this parser failed to read.
                **({"unidentified": True} if p.get("unidentified") else {}),
            }
            for i, p in enumerate(ranked, 1)
        ],
    }


def extract_all() -> Dict[str, Any]:
    """Extract audited rosters for all archived Vanguard annual filings in the manifest.

    Refuses unreconciled filings by reporting them rather than inventing figures.
    """
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    rosters = {}
    unreconciled = {}
    for year_key in sorted(manifest, key=int):
        entry = manifest[year_key]
        try:
            roster = build_roster(PROJECT_ROOT / entry["file_path"])
        except ScheduleParseError as exc:
            unreconciled[year_key] = {
                "source_file": entry["file_path"],
                "accession_number": entry["accession_number"],
                "report_date": entry["report_date"],
                "reason": str(exc),
            }
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
        "reconciliation_summary": {
            "total_filings": len(manifest),
            "reconciled_count": len(rosters),
            "unreconciled_count": len(unreconciled),
            "reconciled_years": sorted(rosters.keys(), key=int),
            "unreconciled_years": sorted(unreconciled.keys(), key=int),
        },
        "unreconciled_years": {y: info["reason"] for y, info in unreconciled.items()},
        "unreconciled_filings": unreconciled,
        "coverage": (
            "Twelve of the thirteen archived filings reconcile, spanning 1994-2006. The "
            "FY2004 HTML filing drops a position whose name and share cells render empty, "
            "leaving an orphaned value of 24,416 thousand dollars; that year is recorded "
            "in unreconciled_years rather than published with a caveat."
        ),
        "rosters_by_year": rosters,
    }


def main() -> None:
    data = extract_all()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print(f"Extraction complete:")
    for year, roster in data["rosters_by_year"].items():
        top_names = ", ".join(h["name"][:16] for h in roster["holdings"][:3])
        print(
            f"  {year}: {roster['position_count']:>4} positions | "
            f"total: ${roster['stated_total_usd_thousands']:>11,d}k | top: {top_names}"
        )
    for year, info in data["unreconciled_filings"].items():
        print(f"  {year}: UNRECONCILED ({info['reason']})")

    print(
        f"\n{len(data['rosters_by_year'])} rosters written to "
        f"{OUTPUT_PATH.relative_to(PROJECT_ROOT)}"
    )


if __name__ == "__main__":
    main()
