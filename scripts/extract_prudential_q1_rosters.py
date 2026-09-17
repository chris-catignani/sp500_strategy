"""Derive unaudited March 31 (Q1) S&P 500 rosters from Prudential schedules.

Zero external dependencies - Python 3 standard library only.
Follows scripts/extract_vanguard_semiannual_rosters.py and scripts/extract_vanguard_rosters.py.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.extract_ground_truth_from_sec import ScheduleParseError
from scripts.extract_vanguard_rosters import _PLAUSIBLE_SP500_COUNT, _clean_name

FILINGS_DIR = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sec_filings"
MANIFEST_PATH = FILINGS_DIR / "prudential_q1_filings_manifest.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "prudential_q1_rosters.json"

PRU_ROW_DOTS = re.compile(
    r"^\s*(?P<shares>\d[\d,]*)\s+(?P<name>.+?)\.{2,}\s+\$?\s*(?P<value>\d[\d,]*)\s*$"
)
PRU_ROW_SPACES = re.compile(
    r"^\s*(?P<shares>\d[\d,]*)\s{2,}(?P<name>[A-Za-z0-9&.,'()/\- *]+?)\s{2,}\$?\s*(?P<value>\d[\d,]*)\s*$"
)
COLUMN_HEADER = re.compile(
    r"^\s*(?:Shares\s+Description|Shares\s+Value|Value\s*\(Note|<C>\s*<S>)", re.I
)


def _find_prudential_bounds(lines: List[str]) -> Tuple[int, int]:
    """Locate the bounds of the Stock Index Fund schedule in a Prudential filing."""
    headers = [
        i
        for i, l in enumerate(lines)
        if "STOCK INDEX FUND" in l.upper()
        and any(
            "PORTFOLIO OF INVESTMENTS" in lines[j].upper()
            for j in range(max(0, i - 5), min(len(lines), i + 5))
        )
    ]
    if not headers:
        raise ScheduleParseError("could not locate STOCK INDEX FUND schedule header")
    start = headers[0]

    ends = [
        i
        for i in range(start, len(lines))
        if "TOTAL COMMON STOCK" in lines[i].upper()
    ]
    if not ends:
        raise ScheduleParseError("could not locate TOTAL COMMON STOCKS footer")
    end = ends[0]

    return start, end


def parse_prudential_filing(path: Path) -> Dict[str, Any]:
    """Parse Prudential Stock Index Fund schedule and produce a dollar-exact reconciled roster."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start, end = _find_prudential_bounds(lines)

    stated = None
    for line in lines[end : end + 4]:
        figs = re.findall(
            r"([\d,]{6,})",
            line.replace("(cost $", "(cost ").replace("(Cost $", "(Cost "),
        )
        if figs:
            stated = float(figs[-1].replace(",", ""))
            break

    if stated is None:
        raise ScheduleParseError(f"{path.name}: missing stated total after schedule marker")

    positions: List[Dict[str, Any]] = []
    name_buffer: List[str] = []

    for idx in range(start + 1, end):
        l = lines[idx]
        if not l.strip() or l.strip().startswith("-") or l.strip().startswith("="):
            name_buffer = []
            continue
        upper = l.upper()
        if any(
            h in upper
            for h in [
                "<PAGE>",
                "<TABLE>",
                "</TABLE>",
                "PORTFOLIO OF INVESTMENTS",
                "STOCK INDEX FUND",
                "LONG-TERM INVESTMENTS",
                "COMMON STOCKS--",
            ]
        ):
            name_buffer = []
            continue
        if "--" in l and re.search(r"\d+\.\d+%", l):
            name_buffer = []
            continue
        if "CONT'D" in upper or "SEE NOTES" in upper or re.match(r"^\s*\d+\s*$", l):
            name_buffer = []
            continue
        if "<CAPTION>" in upper or COLUMN_HEADER.match(l):
            name_buffer = []
            continue

        m = PRU_ROW_DOTS.match(l) or PRU_ROW_SPACES.match(l)
        if m:
            shares = float(m.group("shares").replace(",", ""))
            frag_name = m.group("name").strip()
            full_name = " ".join(name_buffer + [frag_name]) if name_buffer else frag_name
            full_name = re.sub(r"\s+", " ", full_name).strip()
            val = float(m.group("value").replace(",", ""))
            if shares > 0 and val > 0:
                positions.append({"name": full_name, "shares": shares, "val": val})
            name_buffer = []
            continue

        frag = l.strip()
        if len(frag) <= 50 and not any(c.isdigit() for c in frag):
            name_buffer.append(frag)
        else:
            name_buffer = []

    if not positions:
        raise ScheduleParseError(f"{path.name}: schedule parsed to zero positions")

    if not _PLAUSIBLE_SP500_COUNT[0] <= len(positions) <= _PLAUSIBLE_SP500_COUNT[1]:
        raise ScheduleParseError(
            f"{path.name}: schedule holds {len(positions)} positions, outside the "
            f"{_PLAUSIBLE_SP500_COUNT} range an S&P 500 tracker occupies."
        )

    parsed = sum(p["val"] for p in positions)
    if round(parsed) != round(stated):
        raise ScheduleParseError(
            f"{path.name}: parsed ${parsed:,.0f} against stated ${stated:,.0f} "
            f"(difference ${parsed - stated:,.0f}). Refusing to publish a short read."
        )

    ranked = sorted(positions, key=lambda p: -p["val"])
    return {
        "position_count": len(ranked),
        "stated_total_usd": int(stated),
        "parsed_total_usd": int(parsed),
        # Prudential reports EXACT DOLLARS. Truncating to whole thousands here would
        # publish a value that no longer sums to the stated total, and would round the
        # smallest positions to zero -- an implied price of $0.00 wearing the same field
        # name the Vanguard and SEI rosters use for a figure read straight off a filing.
        "stated_total_usd_thousands": round(stated / 1000.0, 3),
        "parsed_total_usd_thousands": round(parsed / 1000.0, 3),
        "holdings": [
            {
                "rank": i,
                "name": _clean_name(p["name"]),
                "shares": int(p["shares"]),
                "value_usd": int(p["val"]),
                "value_usd_thousands": round(p["val"] / 1000.0, 3),
                "weight": round(p["val"] / parsed, 6),
            }
            for i, p in enumerate(ranked, 1)
        ],
    }


def extract_all() -> Dict[str, Any]:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    rosters: Dict[str, Any] = {}
    refused: Dict[str, str] = {}

    for key in sorted(manifest, key=lambda x: (int(x.split("_")[0]), x)):
        entry = manifest[key]
        year = entry["fiscal_year"]
        path = PROJECT_ROOT / entry["file_path"]
        try:
            roster = parse_prudential_filing(path)
        except ScheduleParseError as exc:
            refused[key] = str(exc)
            continue

        roster.update(
            {
                "period": f"{year}-Q1",
                "report_date": entry["report_date"],
                "audited": False,
                "form": entry["form"],
                "accession_number": entry["accession_number"],
                "source_file": entry["file_path"],
                "identification": "Schedule named STOCK INDEX FUND under PORTFOLIO OF INVESTMENTS, holding ~500 common stocks tracking the S&P 500.",
            }
        )
        rosters[f"{year}-Q1"] = roster

    return {
        "description": (
            "March 31 (Q1) rosters of the S&P 500, derived by ranking Prudential / Dryden "
            "Stock Index Fund Portfolio of Investments by position market value."
        ),
        "source_entity": "The Prudential Institutional Fund / Prudential Dryden Fund, Stock Index Fund (CIK 0000887991)",
        "grade": (
            "UNAUDITED. Prudential shareholder reports carry no Report of Independent "
            "Accountants and mark the schedule (UNAUDITED). Every entry is stamped audited: false."
        ),
        "validation": (
            "Every roster reconciles dollar-exact to its filing's stated total, holds a "
            "position count consistent with an S&P 500 tracker (450-540), and is demonstrably "
            "the S&P 500 fund's schedule. Filings failing any check are refused and recorded."
        ),
        "coverage": (
            f"{len(rosters)} of {len(manifest)} archived Prudential Q1 filings produce a roster."
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
            f"total: ${roster['stated_total_usd']:>12,} | top: {top}"
        )
    print(f"\n{len(data['rosters_by_period'])} Prudential rosters written to {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    for k, reason in data["refused_filings"].items():
        print(f"REFUSED {k}: {reason}")


if __name__ == "__main__":
    main()
