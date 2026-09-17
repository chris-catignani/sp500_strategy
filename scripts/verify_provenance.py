"""Re-check every sourced claim in the raw datasets against the filing it cites.

Zero external dependencies - Python 3 standard library only.

The datasets record where each figure came from: an accession number, and usually the
sentence the figure was read in. That is enough to find a source but not enough to know
anyone ever looked at it. A field reading "confirmed_at_source" is an assertion, and an
assertion is what this script exists to replace.

Run it when a figure is questioned, before relying on a dataset in new work, or after
editing one. It fetches each cited filing from SEC EDGAR and re-confirms that the quoted
sentence is present and that each recorded figure appears in the document.

NOT part of the test suite. It needs the network and reaches a third-party service, so it
cannot be a precondition for committing; the suite asserts the offline invariants instead
(that quotes are non-empty, that figures agree across datasets, that cross-filer prices
reconcile). This checks the one thing those cannot: that the filing still says what we
recorded it saying.

Usage:
    python3 scripts/verify_provenance.py              # every dataset
    python3 scripts/verify_provenance.py splits       # one dataset
    python3 scripts/verify_provenance.py --verbose    # show each filing's matched text
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HEADERS = {"User-Agent": "AcademicResearch sp500strategy@example.com"}

SPLITS_PATH = PROJECT_ROOT / "data" / "raw" / "corporate_actions" / "splits.json"
TERMINAL_PATH = PROJECT_ROOT / "data" / "raw" / "corporate_actions" / "terminal_actions.json"
ROSTERS_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "vanguard_audited_rosters.json"

# A quotation is compared on its opening words. Filings are re-flowed by the parser and by
# EDGAR itself, so requiring the whole sentence to match character for character produces
# failures that are about whitespace rather than about the claim.
QUOTE_PREFIX_CHARS = 60


def _normalise(text: str) -> str:
    """Reduce a filing to comparable prose.

    Markup is stripped and entities decoded before comparison, because a filing writes
    "December&nbsp;2000" where the recorded quotation reads "December 2000". Comparing raw
    source would report that as a missing sentence, which is a fact about the encoding
    rather than about the claim. Page-break furniture is removed for the same reason: a
    sentence spanning a page carries a page number in the middle of it.
    """
    text = re.sub(r"<PAGE>\s*\d*", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _fetch(cik: str, accession: str) -> str:
    url = f"https://www.sec.gov/Archives/edgar/data/{str(cik).lstrip('0')}/{accession}.txt"
    time.sleep(0.15)  # Respect SEC rate limits (<10 req/sec)
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read().decode("utf-8", errors="replace")


class Result:
    def __init__(self, dataset: str, subject: str):
        self.dataset = dataset
        self.subject = subject
        self.checks: List[Tuple[str, bool, str]] = []
        self.skipped: Optional[str] = None

    def check(self, label: str, passed: bool, detail: str = "") -> None:
        self.checks.append((label, passed, detail))

    @property
    def ok(self) -> bool:
        return all(passed for _, passed, _ in self.checks)


def _verify_quote_and_figures(
    result: Result, document: str, quote: str, figures: List[Any]
) -> None:
    """Confirm the recorded sentence is in the filing and each figure appears in its text."""
    body = _normalise(document)

    if quote.strip():
        prefix = _normalise(quote)[:QUOTE_PREFIX_CHARS]
        result.check("quote", prefix in body, prefix)

    for figure in figures:
        if figure in (None, ""):
            continue
        # A figure is searched as written. Trailing zeros differ between how a filing
        # prints a ratio and how JSON stores it, so both spellings are tried before the
        # claim is called unsupported.
        text = str(figure)
        variants = {text, text.rstrip("0").rstrip("."), f"{figure:,}" if isinstance(figure, (int, float)) else text}
        found = any(v in body for v in variants if v)
        result.check(f"figure {text}", found, "")


def verify_splits(verbose: bool) -> List[Result]:
    with open(SPLITS_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)["splits_by_ticker"]

    results = []
    for ticker, record in sorted(records.items()):
        result = Result("splits", ticker)
        source = record.get("source_type", "filing_quoted")

        if source != "filing_quoted":
            # A vendor-sourced or not-found record has no filing to re-read. The suite
            # checks these instead: RD's split is corroborated against SHEL.json there.
            result.skipped = f"{source}, corroborated offline by the test suite"
            results.append(result)
            continue

        try:
            document = _fetch(record["cik"], record["accession_number"])
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            result.check("fetch", False, type(exc).__name__)
            results.append(result)
            continue

        _verify_quote_and_figures(result, document, record.get("quoted_sentence", ""), [])
        results.append(result)
    return results


def verify_terminal_actions(verbose: bool) -> List[Result]:
    with open(TERMINAL_PATH, "r", encoding="utf-8") as f:
        actions = json.load(f)["actions_by_ticker"]

    results = []
    for ticker, action in sorted(actions.items()):
        result = Result("terminal_actions", ticker)
        try:
            document = _fetch(action["cik"], action["accession_number"])
        except Exception as exc:  # noqa: BLE001
            result.check("fetch", False, type(exc).__name__)
            results.append(result)
            continue

        _verify_quote_and_figures(
            result,
            document,
            action.get("quoted_sentence", ""),
            [action.get("cash_per_share"), action.get("stock_exchange_ratio")],
        )
        results.append(result)
    return results


def verify_rosters(verbose: bool) -> List[Result]:
    """Re-read each roster's stated total from the archived filing on disk.

    This one needs no network: the filings are archived, so the check is whether the
    total recorded in the dataset is still the total the document states.
    """
    with open(ROSTERS_PATH, "r", encoding="utf-8") as f:
        rosters = json.load(f)["rosters_by_year"]

    results = []
    for year, roster in sorted(rosters.items()):
        result = Result("audited_rosters", year)
        path = PROJECT_ROOT / roster["source_file"]
        if not path.exists():
            result.check("archived filing present", False, str(path))
            results.append(result)
            continue

        stated = int(roster["stated_total_usd_thousands"])
        text = path.read_text(encoding="utf-8", errors="replace")
        result.check("stated total in filing", f"{stated:,}" in text, f"{stated:,}")
        result.check(
            "positions reconcile",
            int(roster["parsed_total_usd_thousands"]) == stated,
            "",
        )
        results.append(result)
    return results


def verify_q1_rosters(verbose: bool) -> List[Result]:
    """Re-read each March-31 roster's total AND its audit grade from the filing on disk.

    The grade is checked here rather than trusted because it is the claim this issue got
    wrong twice, both times by reading something other than the document: first the
    submissions API's `fiscalYearEnd`, which reports 0930 for SEI and is wrong for that
    trust, and then the presence of an "(UNAUDITED)" string that sits on SEI's Notice to
    Shareholders rather than on its schedule.

    So the assertion is positive and negative at once. SEI must carry a Report of
    Independent Accountants and be flagged audited; Prudential must carry none and be
    flagged unaudited. A filing that changed sides would fail here rather than quietly
    re-grade a price.
    """
    sources = [
        ("sei_q1_rosters.json", True, "stated_total_usd_thousands"),
        ("prudential_q1_rosters.json", False, "stated_total_usd"),
    ]
    results = []
    for filename, expect_audited, total_field in sources:
        path = PROJECT_ROOT / "data" / "raw" / "ground_truth" / filename
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            rosters = json.load(f)["rosters_by_period"]
        for period, roster in sorted(rosters.items()):
            result = Result(filename.split("_")[0], period)
            filing = PROJECT_ROOT / roster["source_file"]
            if not filing.exists():
                result.check("archived filing present", False, str(filing))
                results.append(result)
                continue

            text = filing.read_text(encoding="utf-8", errors="replace")
            stated = roster[total_field]
            # SEI reports value in whole thousands, Prudential in exact dollars, so each
            # is looked for in the units its own filing prints.
            printed = f"{int(round(stated)):,}"
            result.check("stated total in filing", printed in text, printed)
            result.check(
                "positions reconcile",
                round(roster["parsed_total_usd"]) == round(roster["stated_total_usd"]),
                "",
            )
            has_opinion = "REPORT OF INDEPENDENT" in text.upper()
            result.check(
                "audit grade matches the filing",
                has_opinion == expect_audited == roster["audited"],
                f"auditor's report {'present' if has_opinion else 'absent'}",
            )
            results.append(result)
    return results


DATASETS = {
    "splits": verify_splits,
    "terminal": verify_terminal_actions,
    "rosters": verify_rosters,
    "q1_rosters": verify_q1_rosters,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", nargs="?", choices=sorted(DATASETS), help="one dataset")
    parser.add_argument("--verbose", action="store_true", help="show matched text")
    args = parser.parse_args()

    selected = [args.dataset] if args.dataset else sorted(DATASETS)
    failures, skipped, checked = 0, 0, 0

    for name in selected:
        print(f"\n== {name} ==")
        for result in DATASETS[name](args.verbose):
            if result.skipped:
                skipped += 1
                print(f"  {result.subject:8} SKIP  {result.skipped}")
                continue
            checked += 1
            if result.ok:
                labels = ", ".join(label for label, _, _ in result.checks)
                print(f"  {result.subject:8} ok    {labels}")
            else:
                failures += 1
                print(f"  {result.subject:8} FAIL")
                for label, passed, detail in result.checks:
                    if not passed:
                        print(f"           - {label} not found in the filing {detail}")
            if args.verbose:
                for label, passed, detail in result.checks:
                    if passed and detail:
                        print(f"           . {label}: {detail}")

    print(f"\n{checked} claims re-checked, {skipped} skipped, {failures} failed")
    if failures:
        print(
            "\nA failure means the filing no longer contains what the dataset records. "
            "Read the filing before changing the dataset: the recorded figure may be right "
            "and the quotation merely re-flowed."
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
