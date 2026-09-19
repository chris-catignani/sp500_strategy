"""Derive unaudited March 31 (Q1) S&P 500 rosters from Prudential schedules.

Zero external dependencies - Python 3 standard library only.
Follows scripts/extract_vanguard_semiannual_rosters.py and scripts/extract_vanguard_rosters.py.
"""

import html
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


# --- The HTML era, 2004-2006 -------------------------------------------------------
#
# Prudential moved the schedule from a fixed-width block into a table. Nothing about the
# figures changed -- still exact dollars, still one fund -- so only the reading changes.

_TABLE_ROW = re.compile(r"<TR\b.*?</TR>", re.S | re.I)
_TABLE_CELL = re.compile(r"<T[DH]\b[^>]*>(.*?)</T[DH]>", re.S | re.I)
_TABLE_CELL_TAG = re.compile(r"<T[DH]\b", re.I)
_LINE_BREAK = re.compile(r"<BR[^>]*>", re.I)
_ANY_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
# A figure, not merely a cell made of figure characters: a bare separator is neither.
_NUMERIC_CELL = re.compile(r"\d[\d,]*")
_FOOTNOTE_CELL = re.compile(r"\(?[a-z]\)?")
_SECTION_PERCENT = re.compile(r"\s*[\d.]+%$")

# The fund whose schedule this is. Every page of it carries a running header naming the
# fund, which is what makes the third guard checkable rather than assumed: a schedule
# lifted from elsewhere in a combined filing would carry a different name here.
_STOCK_INDEX_FUND = "STOCK INDEX FUND"

# The section this reader is entitled to read. LONG-TERM INVESTMENTS is the wrapper
# around it, not a peer.
_COMMON_STOCKS = "COMMON STOCKS"
_LONG_TERM = "LONG-TERM INVESTMENTS"

# Each total is spelled from the section it totals, so the fallback below and the check
# guarding it cannot come to mean different sections.
_TOTAL_COMMON_STOCKS = f"TOTAL {_COMMON_STOCKS}"
_TOTAL_LONG_TERM = f"TOTAL {_LONG_TERM}"


def _cells(row_html: str) -> List[str]:
    """Flatten one table row into its cell texts."""
    out = []
    for match in _TABLE_CELL.finditer(row_html):
        text = _LINE_BREAK.sub(" ", match.group(1))
        text = html.unescape(_ANY_TAG.sub("", text)).replace("\xa0", " ")
        out.append(_WHITESPACE.sub(" ", text).strip())
    return out


def _is_html_filing(text: str) -> bool:
    """Whether the schedule is a table rather than a fixed-width block.

    Asks for the same tag _TABLE_CELL reads, so the detector and the parser cannot
    disagree about what a cell is.
    """
    return bool(_TABLE_CELL_TAG.search(text))


def _section_labels(body: str) -> List[str]:
    """The asset-class headings inside a schedule body.

    These are the all-capital rows -- COMMON STOCKS, PREFERRED STOCKS, SHORT-TERM
    INVESTMENTS. Industry headings are title case (Aerospace/Defense), so they do not
    appear here, and the trailing percentage a heading may carry is dropped.
    """
    labels = []
    for row in _TABLE_ROW.findall(body):
        for cell in _cells(row):
            if cell.upper() != cell or not re.search(r"[A-Z]{3}", cell):
                continue
            label = _SECTION_PERCENT.sub("", cell).strip()
            if label != _LONG_TERM and label not in labels:
                labels.append(label)
    return labels


def _html_schedule(text: str, name: str) -> Tuple[str, float]:
    """Return the schedule body and the total printed on the face of the filing.

    2004 prints a `Total common stocks` line. 2005 and 2006 print only `Total long-term
    investments`, their long-term section being entirely common stock -- so that total is
    an acceptable substitute only while that remains true, which is checked rather than
    assumed. A filing that also held preferred stock under the same heading would
    reconcile a common-stock roster against a total covering both: a short read wearing a
    passing guard, which is the failure mode the Vanguard FY2005 semi-annual demonstrated.
    """
    upper = text.upper()
    start = upper.find("PORTFOLIO OF INVESTMENTS")
    if start < 0:
        raise ScheduleParseError(f"{name}: could not locate PORTFOLIO OF INVESTMENTS")

    for marker in (_TOTAL_COMMON_STOCKS, _TOTAL_LONG_TERM):
        at = upper.find(marker, start)
        if at >= 0:
            break
    else:
        raise ScheduleParseError(f"{name}: could not locate a stated total after the schedule")

    row_start = upper.rfind("<TR", start, at)
    row_end = upper.find("</TR>", at)
    if row_start < 0 or row_end < 0:
        raise ScheduleParseError(f"{name}: the stated total is not inside a table row")
    body = text[start:row_start]

    if marker == _TOTAL_LONG_TERM:
        sections = _section_labels(body)
        if sections != [_COMMON_STOCKS]:
            raise ScheduleParseError(
                f"{name}: falling back to the long-term investments total, but that "
                f"section holds {', '.join(sections) or 'nothing recognisable'} rather "
                f"than common stock alone. Refusing to reconcile a common stock roster "
                f"against a total that covers more."
            )

    funds = {
        cell
        for row in _TABLE_ROW.findall(body)
        for cell in _cells(row)
        if re.search(r"\bFund\b", cell)
    }
    if not funds or any(_STOCK_INDEX_FUND not in f.upper() for f in funds):
        raise ScheduleParseError(
            f"{name}: the schedule's running header names {sorted(funds) or 'no fund'}, "
            f"which does not identify it as the Stock Index Fund's."
        )

    figures = [c for c in _cells(text[row_start:row_end]) if _NUMERIC_CELL.fullmatch(c)]
    if not figures:
        raise ScheduleParseError(f"{name}: the stated total row prints no figure")
    return body, float(figures[-1].replace(",", ""))


def _html_positions(body: str) -> List[Dict[str, Any]]:
    """Read the priced rows out of a schedule body.

    A position row is shares, then a description, then a value. Requiring a figure on
    both sides of the description is what separates it from the page furniture, which
    carries a page number on one side only.

    The description test is deliberately weak: it asks for a letter, not for a run of
    them. 3M Co. has no three consecutive letters, and a stricter filter drops it --
    taking $14,769,184 out of the 2004 schedule and leaving a shortfall that reconciles
    to nothing and names nothing.
    """
    positions = []
    for row in _TABLE_ROW.findall(body):
        cells = [c for c in _cells(row) if c and c != "$"]
        figures = [c for c in cells if _NUMERIC_CELL.fullmatch(c)]
        names = [
            c
            for c in cells
            if re.search(r"[A-Za-z]", c)
            and "%" not in c
            and not _FOOTNOTE_CELL.fullmatch(c)
        ]
        if len(figures) < 2 or not names:
            continue
        shares = float(figures[0].replace(",", ""))
        value = float(figures[-1].replace(",", ""))
        # A value of zero is kept. 2005-Q1 fair-values Seagate Technology at 0, and a
        # positive-value filter drops the row without disturbing the reconciliation --
        # the roster then reports one position fewer than the schedule lists and says
        # nothing about it. _reconciled_roster flags it instead, so the derivation skips
        # the row rather than dividing by its shares.
        if shares > 0 and value >= 0:
            positions.append({"name": names[0], "shares": shares, "val": value})
    return positions


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
    text = path.read_text(encoding="utf-8", errors="replace")
    if _is_html_filing(text):
        body, stated = _html_schedule(text, path.name)
        return _reconciled_roster(_html_positions(body), stated, path.name)

    lines = text.splitlines()
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

    return _reconciled_roster(positions, stated, path.name)


def _reconciled_roster(
    positions: List[Dict[str, Any]], stated: float, name: str
) -> Dict[str, Any]:
    """Apply the three guards to a set of parsed positions and publish the roster.

    Shared by both eras, so the fixed-width and HTML readers cannot drift into
    guarding different things -- or, worse, into one of them guarding a number other
    than the one it publishes.
    """
    if not positions:
        raise ScheduleParseError(f"{name}: schedule parsed to zero positions")

    if not _PLAUSIBLE_SP500_COUNT[0] <= len(positions) <= _PLAUSIBLE_SP500_COUNT[1]:
        raise ScheduleParseError(
            f"{name}: schedule holds {len(positions)} positions, outside the "
            f"{_PLAUSIBLE_SP500_COUNT} range an S&P 500 tracker occupies."
        )

    parsed = sum(p["val"] for p in positions)
    if round(parsed) != round(stated):
        raise ScheduleParseError(
            f"{name}: parsed ${parsed:,.0f} against stated ${stated:,.0f} "
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
