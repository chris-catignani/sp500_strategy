"""Derive June 30 S&P 500 rosters from Vanguard 500 Index Fund semi-annual schedules.

Zero external dependencies - Python 3 standard library only.

These are the Q2 counterpart of extract_vanguard_rosters.py. The parsing is identical and
is reused wholesale; what differs is the grade of the result and one extra guard.

UNAUDITED. A semi-annual report carries no Report of Independent Accountants, where the
December 31 annual reports do. Every roster written here is stamped `audited: false` so a
consumer cannot mistake a Q2 observation for a Q4 one. See issue #63.

The extra guard: reconciling dollar-exact proves a schedule was read completely, not that
the right schedule was read - the point extract_vanguard_rosters.build_roster already makes
about FY2002. The position-count filter is not sufficient on its own here. In the FY2005
semi-annual the first schedule that parses holds 453 positions, inside the range an S&P 500
tracker occupies, and reconciles perfectly against its own stated total of $10.3 billion -
but the 500 Index Fund held $103.9 billion on that date. So the roster is additionally
required to be the LARGEST 'Total Common Stocks' figure in its filing, which the 500 Index
Fund is throughout 1994-2006 by a wide margin over every other fund in these documents.
FY2005 is refused by that check rather than published wrong.
"""

import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.extract_ground_truth_from_sec import ScheduleParseError
from scripts.extract_vanguard_prices import _primary_document
from scripts.extract_vanguard_rosters import build_roster

FILINGS_DIR = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sec_filings"
MANIFEST_PATH = FILINGS_DIR / "vanguard_semiannual_filings_manifest.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "vanguard_semiannual_rosters.json"

# Tolerance in thousands of dollars when comparing a parsed total against the largest
# total stated anywhere in the filing. They are the same figure read two ways, so this is
# a guard against text-extraction noise, not a reconciliation allowance.
_TOTAL_MATCH_TOLERANCE = 1.0


def _largest_stated_total(document: str) -> Optional[float]:
    """Largest 'Total Common Stocks' figure in the filing, in thousands of dollars."""
    flat = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", document)))
    values = []
    for match in re.finditer(r"Total\s+Common\s+Stocks?(.{0,120})", flat, re.IGNORECASE):
        figures = re.findall(r"([\d,]{7,})", match.group(1).replace("Cost $", "Cost "))
        values.extend(float(f.replace(",", "")) for f in figures)
    return max(values) if values else None


def extract_all() -> Dict[str, Any]:
    """Extract Q2 rosters for every archived semi-annual filing in the manifest."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    rosters: Dict[str, Any] = {}
    refused: Dict[str, str] = {}

    for year in sorted(manifest, key=int):
        entry = manifest[year]
        path = PROJECT_ROOT / entry["file_path"]
        try:
            roster = build_roster(path)
        except ScheduleParseError as exc:
            refused[year] = str(exc)
            continue

        document = _primary_document(path.read_text(encoding="utf-8", errors="replace"))
        largest = _largest_stated_total(document)
        parsed_total = roster["stated_total_usd_thousands"]
        if largest is None or abs(parsed_total - largest) > _TOTAL_MATCH_TOLERANCE:
            refused[year] = (
                f"{path.name}: parsed schedule totals {parsed_total:,.0f}k but the filing's "
                f"largest Total Common Stocks figure is {largest:,.0f}k. The 500 Index Fund "
                "is the largest fund in these filings, so this is a different fund's "
                "schedule. Refusing to publish it as a Q2 roster."
            )
            continue

        roster.update(
            {
                "period": f"{year}-Q2",
                "report_date": entry["report_date"],
                "audited": False,
                "form": entry["form"],
                "accession_number": entry["accession_number"],
                "source_file": entry["file_path"],
            }
        )
        rosters[f"{year}-Q2"] = roster

    return {
        "description": (
            "June 30 rosters of the S&P 500, derived by ranking the Vanguard 500 Index "
            "Fund's semi-annual Schedule of Investments by position market value."
        ),
        "source_entity": "Vanguard Index Trust, 500 Index Fund (CIK 0000036405)",
        "grade": (
            "UNAUDITED. These are semi-annual reports and carry no Report of Independent "
            "Accountants, unlike the December-31 annual rosters in "
            "vanguard_audited_rosters.json. Every entry is stamped audited: false."
        ),
        "validation": (
            "Every roster reconciles dollar-exact to its filing's stated total, holds a "
            "position count consistent with an S&P 500 tracker, and is the largest fund "
            "schedule in its filing. A filing failing any of the three is refused, not "
            "approximated."
        ),
        "coverage": (
            f"{len(rosters)} of {len(manifest)} archived semi-annual filings produce a "
            "roster, spanning 1994-2006."
        ),
        "refused_filings": refused,
        "rosters_by_period": rosters,
    }


def main() -> None:
    data = extract_all()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    for period, roster in data["rosters_by_period"].items():
        top = ", ".join(h["name"] for h in roster["holdings"][:3])
        print(
            f"  {period}: {roster['position_count']:4d} positions | "
            f"total: ${roster['stated_total_usd_thousands']:>11,}k | top: {top}"
        )
    print(f"\n{len(data['rosters_by_period'])} rosters written to {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    for year, reason in data["refused_filings"].items():
        print(f"REFUSED {year}: {reason}")


if __name__ == "__main__":
    main()
