"""Derive unaudited September 30 (Q3) S&P 500 rosters from SEI Index Funds semi-annual schedules.

Zero external dependencies - Python 3 standard library only.
Follows scripts/extract_sei_q1_rosters.py and scripts/extract_vanguard_semiannual_rosters.py.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.extract_ground_truth_from_sec import ScheduleParseError
from scripts.extract_sei_q1_rosters import _find_sei_bounds
from scripts.extract_vanguard_rosters import _PLAUSIBLE_SP500_COUNT, _clean_name

FILINGS_DIR = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sec_filings"
MANIFEST_PATH = FILINGS_DIR / "sei_q3_filings_manifest.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sei_q3_rosters.json"

SEI_ROW = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9&.,'\"()/\- *!+]+?)\s{1,}(?P<shares>\d[\d,]*)\s+\$?\s*(?P<value>\d[\d,]*)\s*$"
)
COLUMN_HEADER = re.compile(
    r"^\s*(?:Description\s+)?(?:Shares|SHARES|AMOUNT).*(?:Value|VALUE|Market|MARKET)", re.I
)


def parse_sei_filing(path: Path) -> Dict[str, Any]:
    """Parse SEI S&P 500 schedule and produce a dollar-exact reconciled roster."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start, end = _find_sei_bounds(lines)

    stated = None
    for line in lines[end : end + 4]:
        figs = re.findall(
            r"([\d,]{6,})",
            line.replace("(Cost $", "(Cost ").replace("(COST $", "(COST "),
        )
        if figs:
            stated = float(figs[-1].replace(",", ""))
            break

    if stated is None:
        raise ScheduleParseError(f"{path.name}: missing stated total after schedule marker")

    positions: List[Dict[str, Any]] = []
    name_buffer: List[str] = []

    for idx in range(start + 1, end):
        raw = lines[idx]
        l = raw.rstrip()
        if not l.strip():
            name_buffer = []
            continue

        if re.match(r"^\s*[\d,]+\s*$", l):
            name_buffer = []
            continue
        if l.strip().startswith("-") or l.strip().startswith("="):
            name_buffer = []
            continue
        upper = l.upper()
        if any(
            h in upper
            for h in [
                "<PAGE>",
                "<TABLE>",
                "</TABLE>",
                "STATEMENT OF NET ASSETS",
                "SEI INDEX FUNDS",
                "S&P 500 INDEX",
            ]
        ):
            name_buffer = []
            continue
        if "<CAPTION>" in upper or "<S>" in upper or "<C>" in upper:
            name_buffer = []
            continue
        if (
            "ANNUAL REPORT / MARCH 31," in upper
            or "MARCH 31," in upper
            or "SEPTEMBER 30," in upper
            or "SEMI-ANNUAL REPORT" in upper
        ):
            name_buffer = []
            continue
        if COLUMN_HEADER.match(l):
            name_buffer = []
            continue
        if "--" in l and re.search(r"\d+\.\d+%", l):
            name_buffer = []
            continue
        if l.strip().endswith("%") and len(l.strip()) <= 10:
            name_buffer = []
            continue

        # Zero value holding in 1995: JWP* 6,100
        if "JWP*" in l and "6,100" in l:
            positions.append({"name": "JWP*", "shares": 6100.0, "val": 0.0})
            name_buffer = []
            continue

        m = SEI_ROW.match(l)
        if m:
            frag_name = m.group("name").strip()
            full_name = " ".join(name_buffer + [frag_name]) if name_buffer else frag_name
            full_name = re.sub(r"\s+", " ", full_name).strip()
            shares = float(m.group("shares").replace(",", ""))
            val = float(m.group("value").replace(",", ""))
            positions.append({"name": full_name, "shares": shares, "val": val})
            name_buffer = []
            continue

        frag = l.strip()
        if len(frag) <= 45 and not any(c.isdigit() for c in frag):
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
            f"{path.name}: parsed {parsed:,.0f}k against stated {stated:,.0f}k "
            f"(difference {parsed - stated:,.0f}k). Refusing to publish a short read."
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
                **({"no_value_printed": True} if p["val"] <= 0 else {}),
            }
            for i, p in enumerate(ranked, 1)
        ],
    }


def extract_all() -> Dict[str, Any]:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    rosters: Dict[str, Any] = {}
    refused: Dict[str, str] = {}

    for key in sorted(manifest):
        entry = manifest[key]
        year = entry["fiscal_year"]
        path = PROJECT_ROOT / entry["file_path"]
        try:
            roster = parse_sei_filing(path)
        except ScheduleParseError as exc:
            refused[key] = str(exc)
            continue

        roster.update(
            {
                "period": f"{year}-Q3",
                "report_date": entry["report_date"],
                "audited": False,
                "form": entry["form"],
                "accession_number": entry["accession_number"],
                "source_file": entry["file_path"],
                "identification": (
                    "Schedule bounded by S&P 500 Index Portfolio/Fund header and Total Common Stocks "
                    "footer under Statement of Net Assets / Schedule of Investments (Unaudited), "
                    "distinguished from Bond Index Portfolio by S&P 500 heading and Common Stocks column layout."
                ),
            }
        )
        rosters[f"{year}-Q3"] = roster

    return {
        "description": (
            "September 30 (Q3) rosters of the S&P 500, derived by ranking SEI Index Funds "
            "S&P 500 Index Portfolio Schedule of Investments by position market value."
        ),
        "source_entity": "SEI Index Funds, S&P 500 Index Portfolio (CIK 0000766589)",
        "grade": (
            "UNAUDITED. These are semi-annual reports and carry no Report of Independent "
            "Accountants, unlike the March-31 annual rosters in sei_q1_rosters.json. Every entry is stamped audited: false."
        ),
        "validation": (
            "Every roster reconciles dollar-exact to its filing's stated total, holds a "
            "position count consistent with an S&P 500 tracker (450-540), and is demonstrably "
            "the S&P 500 fund's schedule. Filings failing any check are refused and recorded."
        ),
        "coverage": (
            f"{len(rosters)} of 12 archived SEI Q3 periods produce a roster, "
            "spanning 1995-2006."
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
    print(f"\n{len(data['rosters_by_period'])} SEI Q3 rosters written to {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    for year, reason in data["refused_filings"].items():
        print(f"REFUSED {year}: {reason}")


if __name__ == "__main__":
    main()
