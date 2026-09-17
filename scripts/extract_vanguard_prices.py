"""Derive December 31 implied share prices from Vanguard Index Trust filings.

Zero external dependencies - Python 3 standard library only.

A fund's Schedule of Investments reports, for every position, the share count held and
its market value at the period end. Their quotient is the security's closing price on
that date. SPY's fiscal year ends September 30, so its filings cannot anchor a year-end
price; Vanguard Index Trust's December 31 filings can (see docs/DATA_PROVENANCE.md 4.3.9).

Output is AS-TRADED. These prices are not split-adjusted and must not be read as a return
series until each registrant's split record is applied: Lucent 1997->1999 reads as a 20
percent decline as-traded where the split-adjusted move is a 219 percent rise. Issue #55.

Validation here is cross-schedule agreement rather than reconciliation to a stated fund
total. Each filing carries several Vanguard funds holding the same securities on the same
date, so a security's implied price is derivable independently from several different
share counts and dollar values. Requiring those to agree is a stronger check for price
extraction than a single fund's total, which guards roster completeness instead.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.extract_ground_truth_from_sec import (
    ScheduleParseError,
    _extract_n30d_positions,
    _html_schedule_rows,
)

FILINGS_DIR = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sec_filings"
MANIFEST_PATH = FILINGS_DIR / "vanguard_annual_filings_manifest.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "vanguard_implied_prices.json"

# Schedules report market value in THOUSANDS of dollars, so a published value carries up
# to +/-$500 of rounding. Per share that is 500/shares, which is negligible for a large
# position and material for a small one: 5,000 shares admits +/-$0.10. Agreement is
# therefore checked against each pair's own precision rather than a flat figure, with a
# small epsilon for share-count rounding. A disagreement beyond this is not rounding - it
# means the pattern matched two different securities.
VALUE_ROUNDING_USD = 500.0
AGREEMENT_EPSILON_USD = 0.01

# A position must be at least this fraction of the largest one to corroborate its price.
PEER_SHARE_FRACTION = 0.10

# (ticker, first_year, last_year, name_regex). Year bounds exist because a ticker's filed
# name is not stable: America Online and Time Warner were SEPARATE listed companies until
# the merger completed 2001-01-11, so one pattern spanning both eras conflates two
# securities. Anchoring is by issuer name at the start of a row.
NAME_PATTERNS: List[Tuple[str, int, int, str]] = [
    ("LU",   1994, 2006, r"Lucent Technologies"),
    ("RD",   1994, 2006, r"Royal Dutch Petroleum"),
    ("EMC",  1994, 2006, r"EMC Corp"),
    ("SBC",  1994, 2004, r"SBC Communications"),
    ("AOL",  1994, 2000, r"America Online"),
    ("AOL",  2001, 2006, r"(?:AOL Time Warner|Time Warner,? Inc)"),
    ("SUNW", 1994, 2006, r"Sun Microsystems"),
    ("MOB",  1994, 1999, r"Mobil Corp"),
    ("NT",   1994, 2006, r"Nortel Networks"),
    ("DD",   1994, 2006, r"(?:E\.?\s?I\.?\s+du\s?Pont|Du\s?Pont \(E\.I\.\))"),
    # Bounded at 2000: WorldCom split into WorldCom Group and MCI Group TRACKING STOCKS in
    # June 2001, which are separate securities at separate prices, and the company entered
    # bankruptcy in 2002. Neither year is required by the gap report.
    ("MCIC", 1994, 2000, r"(?:MCI WorldCom|WorldCom,? Inc)(?!.*Group)"),
    ("COP",  1994, 2006, r"(?:ConocoPhillips|Phillips Petroleum)"),
    ("BLS",  1994, 2006, r"BellSouth Corp"),
    ("DELL", 1994, 2006, r"Dell (?:Computer|Inc)"),
    ("SLB",  1994, 2006, r"Schlumberger"),
    ("GILD", 1994, 2006, r"Gilead Sciences"),
    ("GTE",  1994, 2000, r"GTE Corp"),
    # Viacom listed Class A and Class B separately at different prices. They are captured
    # per class and consolidated at issuer level downstream, following the Alphabet
    # precedent in #38; a single pattern spanning both conflates two securities.
    ("VIA.A", 1994, 2006, r"Viacom,? Inc\.? Class A"),
    ("VIA.B", 1994, 2006, r"Viacom,? Inc\.? Class B"),
]

# Securities whose absence from a filing is a corporate event, not a parse failure. Each
# ceased to exist before that year end, so a price for it would be fabricated.
KNOWN_EXITS = {
    ("MOB", 1999): "Merged into Exxon Corp. 1999-11-30, forming Exxon Mobil Corp.",
    ("GTE", 2000): "Merged into Bell Atlantic 2000-06-30, forming Verizon Communications.",
    ("SBC", 2005): "SBC acquired AT&T Corp. 2005-11-18 and adopted the AT&T Inc. name; "
                   "the continuing registrant files as AT&T Inc. from the 2005 year end.",
}


def _primary_document(text: str) -> str:
    """Return the first <DOCUMENT>'s <TEXT> body from a full SEC submission.

    A full submission concatenates the report with its exhibits and graphic attachments.
    The binary attachments contain byte sequences such as "<![" that an SGML parser reads
    as a malformed marked section, so the report body is isolated before parsing. It is
    always the first document in the submission.
    """
    start = text.find("<TEXT>")
    if start == -1:
        return text
    end = text.find("</TEXT>", start)
    return text[start + len("<TEXT>") : end if end != -1 else len(text)]


def _positions(path: Path) -> List[Dict[str, Any]]:
    """Read every schedule position in a filing, across all funds it contains.

    No fund-boundary detection: a position's implied price does not depend on which
    fund holds it, and agreement across funds is the validation (see module docstring).
    """
    text = _primary_document(path.read_text(encoding="utf-8", errors="replace"))

    if "<TD" in text or "<td" in text:
        out: List[Dict[str, Any]] = []
        for cells in _html_schedule_rows(text):
            cells = [c for c in cells if c not in {"*", "(1)"}]
            if len(cells) < 3:
                continue
            name, shares_cell, value_cell = cells[0], cells[1], cells[2]
            if not re.fullmatch(r"[\d,]+", shares_cell) or not re.fullmatch(r"[\d,]+", value_cell):
                continue
            shares = float(shares_cell.replace(",", ""))
            value = float(value_cell.replace(",", ""))
            if shares > 0 and value > 0:
                out.append({"name": re.sub(r"\s+", " ", name).strip(), "shares": shares, "val": value})
        return out

    lines = text.split("\n")
    return _extract_n30d_positions(lines, -1, len(lines))


def _price_for(positions: List[Dict[str, Any]], pattern: str) -> Optional[Dict[str, Any]]:
    """Implied price for the first issuer matching pattern, with its agreement spread."""
    anchored = re.compile(r"^[^A-Za-z]{0,14}" + pattern, re.IGNORECASE)
    matches = [p for p in positions if anchored.match(p["name"]) and p["shares"] >= 1000]
    if not matches:
        return None

    # Values are reported in thousands of dollars throughout these schedules.
    def implied(p: Dict[str, Any]) -> float:
        return p["val"] * 1000.0 / p["shares"]

    # The largest position carries the least rounding error in the published figures.
    best = max(matches, key=lambda p: p["shares"])
    price = implied(best)

    # Only positions of comparable size can corroborate the price. A holding a hundred
    # times smaller carries a hundred times the per-share rounding noise, so it cannot
    # confirm or contradict anything; it is reported but not used to validate.
    peers = [p for p in matches if p["shares"] >= best["shares"] * PEER_SHARE_FRACTION]

    def allowance(p: Dict[str, Any]) -> float:
        return (
            VALUE_ROUNDING_USD / p["shares"]
            + VALUE_ROUNDING_USD / best["shares"]
            + AGREEMENT_EPSILON_USD
        )

    # A majority of comparable positions must corroborate the price. Individual schedules
    # do occasionally carry a position valued away from the others; that is preserved as
    # an outlier rather than averaged away or silently tolerated, because a systematic
    # mismatch (two securities under one pattern) fails the majority test while a single
    # anomalous holding does not.
    agreeing = [p for p in peers if abs(implied(p) - price) <= allowance(p)]
    outliers = [
        {"shares": int(p["shares"]), "value_usd_thousands": int(p["val"]),
         "implied_usd": round(implied(p), 4)}
        for p in peers if p not in agreeing
    ]
    spread = max(abs(implied(p) - price) for p in peers)
    allowed = max(allowance(p) for p in peers)
    return {
        "price_usd": round(price, 2),
        "schedules": len(matches),
        "corroborating_schedules": len(peers),
        "agreement_spread_usd": round(spread, 4),
        "agreement_allowance_usd": round(allowed, 4),
        "corroborating_agreement": f"{len(agreeing)}/{len(peers)}",
        "outlier_rows": outliers,
        "matched_name": best["name"],
        "shares": int(best["shares"]),
        "value_usd_thousands": int(best["val"]),
    }


def extract_all() -> Dict[str, Any]:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    observations: Dict[str, Dict[str, Any]] = {}
    disagreements: List[str] = []

    for year_key in sorted(manifest, key=int):
        entry = manifest[year_key]
        year = int(year_key)
        positions = _positions(PROJECT_ROOT / entry["file_path"])
        if not positions:
            raise ScheduleParseError(f"{entry['file_path']}: no schedule positions read")

        for ticker, first, last, pattern in NAME_PATTERNS:
            if not (first <= year <= last):
                continue
            found = _price_for(positions, pattern)
            if found is None:
                continue
            agree, total = (int(x) for x in found["corroborating_agreement"].split("/"))
            if agree * 2 <= total:
                disagreements.append(
                    f"{ticker} {year}: only {found['corroborating_agreement']} comparable "
                    f"schedules corroborate ${found['price_usd']} "
                    f"(matched {found['matched_name']!r}). The pattern is matching more "
                    "than one security."
                )
            found.update({
                "report_date": entry["report_date"],
                "accession_number": entry["accession_number"],
                "form": entry["form"],
                "source_file": entry["file_path"],
            })
            observations.setdefault(ticker, {})[year_key] = found

    # Emitted unconditionally. An exit recorded only when a lookup happens to be attempted
    # would go unrecorded wherever the name pattern is already bounded to end before it,
    # which is exactly where the reader most needs to know a price is absent by event
    # rather than by omission.
    notes = [f"{t} {y}: {why}" for (t, y), why in sorted(KNOWN_EXITS.items())]

    return {
        "description": (
            "December 31 implied share prices derived from Vanguard Index Trust Schedules "
            "of Investments as market value divided by share count. AS-TRADED, not "
            "split-adjusted."
        ),
        "source_entity": "Vanguard Index Trust (CIK 0000036405)",
        "derivation": "price = value_usd_thousands * 1000 / shares",
        "validation": (
            "Cross-schedule agreement: each filing holds several Vanguard funds owning "
            "the same securities. Independently derived prices must agree within the "
            "rounding their published precision admits: value is reported in thousands, "
            "so +/-$500 per position, or 500/shares per share."
        ),
        "adjustment_status": "as_traded_unadjusted",
        "corporate_action_notes": sorted(set(notes)),
        "cross_schedule_disagreements": disagreements,
        "prices_by_ticker": observations,
    }


def main() -> None:
    data = extract_all()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    n = sum(len(v) for v in data["prices_by_ticker"].values())
    print(f"{n} observations across {len(data['prices_by_ticker'])} tickers")
    for note in data["corporate_action_notes"]:
        print(f"  note: {note}")
    d = data["cross_schedule_disagreements"]
    print(f"\ncross-schedule disagreements: {len(d)}")
    for x in d:
        print(f"  {x}")
    print(f"Written: {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
