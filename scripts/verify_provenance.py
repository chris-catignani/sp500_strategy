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
    python3 scripts/verify_provenance.py q2_rosters   # Vanguard semi-annual rosters
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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_doc_figures import ARCHIVE_DIR, classify_source_ref

HEADERS = {"User-Agent": "AcademicResearch sp500strategy@example.com"}

SPLITS_PATH = PROJECT_ROOT / "data" / "raw" / "corporate_actions" / "splits.json"
TERMINAL_PATH = PROJECT_ROOT / "data" / "raw" / "corporate_actions" / "terminal_actions.json"
ROSTERS_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "vanguard_audited_rosters.json"
SEMIANNUAL_ROSTERS_PATH = (
    PROJECT_ROOT / "data" / "raw" / "ground_truth" / "vanguard_semiannual_rosters.json"
)
MANIFEST_PATH = PROJECT_ROOT / "docs" / "doc_figure_manifest.json"

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


def _verify_cited_filing(
    result: Result, cik: str, accession: str, quote: str, figures: List[Any]
) -> Result:
    """Fetch the cited filing and re-check it, reporting a failed fetch rather than raising.

    Every claim in this script is "the document at this accession says this", so a claim
    that cannot be fetched is unsupported rather than fatal -- one unreachable filing must
    not stop the other sixty-eight from being checked.
    """
    try:
        document = _fetch(cik, accession)
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        result.check("fetch", False, type(exc).__name__)
        return result
    _verify_quote_and_figures(result, document, quote, figures)
    return result


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

        results.append(
            _verify_cited_filing(
                result, record["cik"], record["accession_number"],
                record.get("quoted_sentence", ""), [],
            )
        )

        # A registrant whose splits were stated in different filings carries a source on
        # the split itself. T_CORP is the case: the 1999 three-for-two is quoted from the
        # FY2001 report and the 2002 reverse split from FY2002, so one record-level
        # accession cannot stand behind both claims.
        for split in record["splits"]:
            if not split.get("quoted_sentence"):
                continue
            split_result = Result("splits", f"{ticker} {split['effective_date']}")
            results.append(
                _verify_cited_filing(
                    split_result, record["cik"], split["accession_number"],
                    split["quoted_sentence"], [],
                )
            )
    return results


def verify_terminal_actions(verbose: bool) -> List[Result]:
    with open(TERMINAL_PATH, "r", encoding="utf-8") as f:
        actions = json.load(f)["actions_by_ticker"]

    results = []
    for ticker, action in sorted(actions.items()):
        result = Result("terminal_actions", ticker)
        results.append(
            _verify_cited_filing(
                result,
                action["cik"],
                action["accession_number"],
                action.get("quoted_sentence", ""),
                [action.get("cash_per_share"), action.get("stock_exchange_ratio")],
            )
        )
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
        # SEI's September-30 report is its SEMI-ANNUAL, because its fiscal year ends March
        # 31. Same trust as the first row, opposite grade. Checking both here is the point:
        # a filer is not audited, a REPORT is, and this is the pair that proves the
        # distinction is being read from the document rather than assumed from the CIK.
        ("sei_q3_rosters.json", False, "stated_total_usd_thousands"),
    ]
    results = []
    for filename, expect_audited, total_field in sources:
        path = PROJECT_ROOT / "data" / "raw" / "ground_truth" / filename
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            rosters = json.load(f)["rosters_by_period"]
        for period, roster in sorted(rosters.items()):
            result = Result(filename.rsplit("_rosters", 1)[0], period)
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


def verify_q2_rosters(verbose: bool) -> List[Result]:
    """Re-read each Vanguard semi-annual roster's total AND its unaudited grade.

    Like verify_rosters and verify_q1_rosters, this reads archived filings from disk
    and requires no network. A semi-annual report is unaudited and carries no Report
    of Independent Accountants; this confirms the absence of an auditor's report from
    the document rather than assuming the grade from the fund.
    """
    if not SEMIANNUAL_ROSTERS_PATH.exists():
        return []

    with open(SEMIANNUAL_ROSTERS_PATH, "r", encoding="utf-8") as f:
        rosters = json.load(f)["rosters_by_period"]

    results = []
    for period, roster in sorted(rosters.items()):
        result = Result("vanguard_semiannual_rosters", period)
        path = PROJECT_ROOT / roster["source_file"]
        if not path.exists():
            result.check("archived filing present", False, str(path))
            results.append(result)
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        stated = int(roster["stated_total_usd_thousands"])
        printed = f"{stated:,}"
        result.check("stated total in filing", printed in text, printed)
        result.check(
            "positions reconcile",
            int(roster["parsed_total_usd_thousands"]) == stated,
            "",
        )
        has_opinion = "REPORT OF INDEPENDENT" in text.upper()
        result.check(
            "audit grade matches the filing",
            (not has_opinion) and (not roster["audited"]),
            f"auditor's report {'present' if has_opinion else 'absent'}",
        )
        results.append(result)
    return results


def generate_figure_variants(figure: str) -> Tuple[List[str], List[Tuple[float, int]]]:
    """Generate text variants and numeric targets for the three variant families (issue #105).

    Families:
      1. Percent <-> ratio: try figure divided by 100 whenever figure carries a %.
      2. Decimal precision: trailing-zero differences (69.10 vs 69.1) and thousands
         separators (3,170 vs 3170) in both directions.
      3. Scale suffix: $3.17B, $103.9bn. Try scaled by 1e3, 1e6, 1e9, and as written.
    """
    raw = figure.strip()
    s = raw.replace(r"\$", "$").replace(r"\%", "%").strip()
    text_variants = {raw, s}

    if s.startswith("$"):
        s = s[1:].strip()
        text_variants.add(s)

    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
        text_variants.add(s)

    is_percent = s.endswith("%")
    if is_percent:
        s = s[:-1].strip()
        text_variants.add(s)

    scale_suffix = None
    for suf in ("bn", "BN", "b", "B", "k", "K", "m", "M"):
        if s.endswith(suf):
            scale_suffix = suf.lower()
            s = s[:-len(suf)].strip()
            text_variants.add(s)
            break

    num_clean = s.replace(",", "")
    try:
        val = float(num_clean)
    except ValueError:
        return sorted(v for v in text_variants if v), []

    if "." in s:
        precision = len(s.split(".")[1])
    else:
        precision = 0

    numeric_targets = [(val, precision)]

    if is_percent:
        ratio_val = val / 100.0
        ratio_prec = precision + 2
        numeric_targets.append((ratio_val, ratio_prec))
        ratio_str = f"{ratio_val:.{ratio_prec}f}"
        text_variants.add(ratio_str)
        text_variants.add(ratio_str.rstrip("0").rstrip("."))

    if precision > 0:
        stripped = s.rstrip("0").rstrip(".")
        text_variants.add(stripped)
        text_variants.add(s + "0")
        if stripped:
            stripped_num = float(stripped.replace(",", ""))
            stripped_prec = len(stripped.split(".")[1]) if "." in stripped else 0
            numeric_targets.append((stripped_num, stripped_prec))
    else:
        text_variants.add(s + ".0")
        text_variants.add(s + ".00")

    if val >= 1000 or val <= -1000:
        if precision > 0:
            dec = s.split(".")[1]
            with_comma = f"{int(val):,}.{dec}"
        else:
            with_comma = f"{int(val):,}"
        text_variants.add(with_comma)
        text_variants.add(num_clean)
        if precision > 0:
            text_variants.add(with_comma.rstrip("0").rstrip("."))
            text_variants.add(num_clean.rstrip("0").rstrip("."))

    if scale_suffix is not None:
        for scale in (1e3, 1e6, 1e9):
            scaled_val = val * scale
            scaled_prec = max(0, precision - (3 if scale == 1e3 else 6 if scale == 1e6 else 9))
            numeric_targets.append((scaled_val, scaled_prec))
            if scaled_prec == 0 or scaled_val.is_integer():
                ival = int(round(scaled_val))
                text_variants.add(f"{ival:,}")
                text_variants.add(f"{ival}")
            else:
                text_variants.add(f"{scaled_val:,.{scaled_prec}f}")
                text_variants.add(f"{scaled_val:.{scaled_prec}f}")

    return sorted(v for v in text_variants if v), numeric_targets


def match_text(document_text: str, variants: List[str]) -> bool:
    """Check whether any variant string is a substring of normalised text."""
    norm_text = _normalise(document_text)
    return any(v in norm_text for v in variants if v)


def _parse_leaf_as_number(val: Any) -> Optional[float]:
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.strip().replace(",", ""))
        except ValueError:
            return None
    return None


def extract_numeric_leaves(data: Any) -> List[float]:
    """Recursively collect numeric leaves from parsed JSON structures."""
    leaves = []
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        else:
            n = _parse_leaf_as_number(item)
            if n is not None:
                leaves.append(n)
    return leaves


def match_numeric(leaves: List[float], targets: List[Tuple[float, int]]) -> bool:
    """Check if any JSON leaf matches any target rounded to printed precision."""
    if not targets:
        return False
    for target_val, prec in targets:
        target_rounded = round(target_val, prec)
        for leaf in leaves:
            if round(leaf, prec) == target_rounded:
                return True
    return False


_ACCESSION_MAP: Optional[Dict[str, Path]] = None
_NORMALIZED_TEXT_CACHE: Dict[Path, str] = {}
_JSON_LEAVES_CACHE: Dict[Path, List[float]] = {}


def _get_accession_file(accession: str) -> Optional[Path]:
    global _ACCESSION_MAP
    if _ACCESSION_MAP is None:
        _ACCESSION_MAP = {}
        if ARCHIVE_DIR.exists():
            for p in ARCHIVE_DIR.iterdir():
                m = re.search(r"\d{10}-\d{2}-\d{6}", p.name)
                if m:
                    _ACCESSION_MAP[m.group(0)] = p
    return _ACCESSION_MAP.get(accession)


def _get_cached_normalized_text(path: Path) -> str:
    if path not in _NORMALIZED_TEXT_CACHE:
        _NORMALIZED_TEXT_CACHE[path] = _normalise(
            path.read_text(encoding="utf-8", errors="replace")
        )
    return _NORMALIZED_TEXT_CACHE[path]


def _get_cached_json_leaves(path: Path) -> List[float]:
    if path not in _JSON_LEAVES_CACHE:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _JSON_LEAVES_CACHE[path] = extract_numeric_leaves(data)
    return _JSON_LEAVES_CACHE[path]


def verify_doc_figures(verbose: bool) -> List[Result]:
    """Re-check every sourced doc figure against the filing or dataset it cites (#105)."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)["entries"]

    results = []
    for entry in entries:
        if entry.get("verdict") != "sourced":
            continue

        section = entry.get("section", "")
        figure = entry.get("figure", "")
        source_ref = entry.get("source_ref", "")
        form = classify_source_ref(source_ref)
        subject = f"§{section} {figure}"

        result = Result("doc_figures", subject)
        text_variants, numeric_targets = generate_figure_variants(figure)

        result.section = section
        result.figure = figure
        result.form = form
        result.source_ref = source_ref
        result.variants = text_variants

        if form == "unarchived":
            result.skipped = source_ref.strip()
            result.outcome = "skipped-unarchived"
            results.append(result)
            continue

        if form == "accession":
            path = _get_accession_file(source_ref.strip())
            if not path or not path.exists():
                result.check("resolve source_ref", False, f"accession file missing on disk: {source_ref}")
                result.outcome = "unresolved"
            else:
                body = _get_cached_normalized_text(path)
                matched = match_text(body, text_variants)
                result.check("present in filing", matched, f"{figure} in {source_ref}")
                result.outcome = "hit" if matched else "miss"
            results.append(result)
            continue

        if form == "path":
            path = PROJECT_ROOT / source_ref.strip()
            if not path.exists():
                result.check("resolve source_ref", False, f"path missing on disk: {source_ref}")
                result.outcome = "unresolved"
            else:
                if source_ref.strip().endswith(".json"):
                    leaves = _get_cached_json_leaves(path)
                    matched = match_numeric(leaves, numeric_targets)
                    result.check("present in dataset", matched, f"{figure} in {source_ref}")
                    result.outcome = "hit" if matched else "miss"
                else:
                    body = _get_cached_normalized_text(path)
                    matched = match_text(body, text_variants)
                    result.check("present in file", matched, f"{figure} in {source_ref}")
                    result.outcome = "hit" if matched else "miss"
            results.append(result)
            continue

        result.check("resolve source_ref", False, f"unresolved {form}: {source_ref}")
        result.outcome = "unresolved"
        results.append(result)

    return results


def _report_doc_figures(results: List[Result], verbose: bool) -> Tuple[int, int, int, int]:
    hits = [r for r in results if getattr(r, "outcome", None) == "hit"]
    misses = [r for r in results if getattr(r, "outcome", None) == "miss"]
    unarchived = [r for r in results if getattr(r, "outcome", None) == "skipped-unarchived"]
    unresolved = [r for r in results if getattr(r, "outcome", None) == "unresolved"]

    if verbose:
        for r in results:
            if r.outcome == "hit":
                print(f"  {r.subject:17} ok    present ({r.source_ref})")
            elif r.outcome == "skipped-unarchived":
                print(f"  {r.subject:17} SKIP  {r.skipped}")
            elif r.outcome == "miss":
                print(f"  {r.subject:17} MISS  {r.source_ref} tried: {r.variants}")
            else:
                print(f"  {r.subject:17} FAIL  {r.source_ref}")

    if misses:
        print(f"\nMisses ({len(misses)}):")
        for r in misses:
            print(f"  §{r.section:<8} {r.figure:<24} {r.form:<10} {r.source_ref:<42} variants: {r.variants}")

    if unresolved:
        print(f"\nUnresolved ({len(unresolved)}):")
        for r in unresolved:
            print(f"  §{r.section:<8} {r.figure:<24} {r.form:<10} {r.source_ref}")

    print(f"\nCensus: hit={len(hits)} miss={len(misses)} unarchived={len(unarchived)} unresolved={len(unresolved)}")

    return len(hits), len(misses), len(unarchived), len(unresolved)


DATASETS = {
    "splits": verify_splits,
    "terminal": verify_terminal_actions,
    "rosters": verify_rosters,
    "q1_rosters": verify_q1_rosters,
    "q2_rosters": verify_q2_rosters,
    "doc_figures": verify_doc_figures,
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
        results = DATASETS[name](args.verbose)
        if name == "doc_figures":
            hits, misses, unarch, unres = _report_doc_figures(results, args.verbose)
            checked += hits + misses + unres
            skipped += unarch
            failures += unres
            continue

        for result in results:
            if result.skipped:
                skipped += 1
                print(f"  {result.subject:17} SKIP  {result.skipped}")
                continue
            checked += 1
            if result.ok:
                labels = ", ".join(label for label, _, _ in result.checks)
                print(f"  {result.subject:17} ok    {labels}")
            else:
                failures += 1
                print(f"  {result.subject:17} FAIL")
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
