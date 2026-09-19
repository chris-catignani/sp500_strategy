"""Enumerate every numeric claim published in the documentation (issue #91).

Zero external dependencies - Python standard library only.

This script does not classify, and cannot. The Top 20 weights in 4.3.5 and the pool-depth
deltas in 4.3.7 are both bare percentages, and no regular expression separates a figure
read from a filing from one the engine computed. Judgment supplies the verdict; this
script only guarantees that nothing escapes review.

Under-catching is the defect #91 exists to fix, so the filter runs generous: a candidate
that turns out to be sourced costs one decision, while a computed figure that never
reaches the manifest is exactly the silent rot this work removes.

It never imports engine/. The ratchet in tests/test_doc_figures.py runs on every suite
invocation, and a text scan keeps it under a second.
"""

import argparse
import json
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent

DOCUMENTS = ("docs/DATA_PROVENANCE.md", "README.md")
MANIFEST_PATH = REPO_ROOT / "docs" / "doc_figure_manifest.json"

VERDICTS = ("sourced", "derivation", "decision-evidence", "remove", "wrong",
            "not-a-claim")

# "not-a-claim" was added after classification began, because the other five all assume
# the candidate IS a claim and several candidates are not. The filter is generous by
# design, so it catches structural subheading numerals, table header units ($000), the
# subscript in W_{i,0}, and worked-example CLI parameters. Forcing those into "remove"
# would tell pass 2 to delete a section heading and corrupt a formula. They stay in the
# document and need no guard.

# The two verdicts that carry a rot-exposure decision. `sourced` cannot rot because a
# filing cannot change; `remove` is leaving; `not-a-claim` was never a claim; `wrong` is
# corrected in place. Only these two need the question asked.
ROT_CLASSIFIED_VERDICTS = ("derivation", "decision-evidence")

# The verdict that asserts a document backs the figure, and therefore owes a pointer to
# it. `sourced` was the strongest verdict pass 1 assigned and carried the weakest
# evidence: an `evidence_quote`, which the gate checks is IN the document rather than
# that it ATTRIBUTES anything, so a quote restating the figure satisfied it. Measured
# before this changed: 126 accessions are archived under `sec_filings/`, 2 were cited
# across all 181 `sourced` entries, and neither of those two is on disk.
SOURCE_REF_VERDICTS = ("sourced",)

# Where the archived filings live. The filename carries the accession, so the directory
# listing IS the set of resolvable accessions; nothing is parsed or opened.
ARCHIVE_DIR = REPO_ROOT / "data" / "raw" / "ground_truth" / "sec_filings"

# An SEC accession number, which is the filename's distinguishing part.
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")

# The honest-gap marker. It is the form that carries the weight: a figure read from a
# document this repository does not hold passes, but says so, and is counted. This is
# the same move `refused_filings` and the sourced-zero-versus-unknown rule already make
# -- a gap that is visible and countable beats one that is silently absent.
UNARCHIVED_PREFIX = "unarchived:"

# How many `sourced` entries resolve only to that marker. Pinned so that a change in
# either direction is deliberate: a new unarchived figure has to be argued for, and a
# figure that gains a real source has to lower the number. Not a published figure --
# this is manifest bookkeeping, and `scripts/audit_doc_figures.py --source-refs` prints
# the census that produces it.
UNARCHIVED_SOURCE_REFS = 46


_ARCHIVED = None


def archived_accessions():
    """The accessions on disk, read from the filenames of the archived filings.

    The manifests in that directory carry no accession in their name and are skipped by
    the pattern rather than by an exclusion list. Cached: the ratchet asks this once per
    `sourced` entry and must stay a sub-second scan.
    """
    global _ARCHIVED
    if _ARCHIVED is None:
        found = set()
        for path in ARCHIVE_DIR.iterdir():
            match = re.search(r"\d{10}-\d{2}-\d{6}", path.name)
            if match:
                found.add(match.group(0))
        _ARCHIVED = found
    return _ARCHIVED


def classify_source_ref(ref):
    """Which of the three permitted forms a `source_ref` takes, or why it takes none.

    WHAT A RESOLVING REF PROVES. That the pointer is good -- the filing is on disk, or
    the dataset file exists. NOT that the figure appears in what it points at.
    `scripts/verify_provenance.py` is what checks the latter, by re-reading the cited
    document. This field is a findability guarantee and must not be described as more.
    """
    if not ref or not isinstance(ref, str) or not ref.strip():
        return "missing"
    ref = ref.strip()
    if ref.startswith(UNARCHIVED_PREFIX):
        return "unarchived" if ref[len(UNARCHIVED_PREFIX):].strip() else "missing"
    if ACCESSION.match(ref):
        return "accession" if ref in archived_accessions() else "unresolved-accession"
    if "/" in ref:
        return "path" if (REPO_ROOT / ref).exists() else "unresolved-path"
    return "unrecognised"


# Does the document print the arithmetic? A figure claiming to be self-checking must show
# its work, so a reader can confirm it without running anything of ours.
#
# NECESSARY, NOT SUFFICIENT. 4.3.6's `89.8% (494/550)` matches this and is pipeline: 494
# is our own match count, so the figure rots however much arithmetic is shown. No regex
# decides this; the controller reviews every `rot_exposed: false`.
#
# The archetype it must catch is 4.6.4's spinoff proceeds, which print a Form 8937 ratio
# times a filed close:
#     $0.324084 \times \$45.875 = \$14.86735 \approx \mathbf{\$14.87}$
#
# Every part of this pattern was forced by a real line in the document:
#   - LaTeX `\times` and `\cdot`, because 4.6.4 writes multiplication that way. An
#     earlier version matched only unicode and silently blocked thirteen genuinely
#     self-checking figures, which had to be marked rot-exposed to keep the suite green.
#   - Escaped `\$`, because the document escapes dollar signs for LaTeX.
#   - Bold markers between operand and operator, because 4.5.4 writes
#     `**\$43.50** - **\$2.10** = **\$41.40**`.
#   - An ASCII hyphen counts as subtraction ONLY with real whitespace either side.
#     Without that, "2014-2019" reads as digit-minus-digit and every year range in the
#     document looks like printed arithmetic.
#   - An en dash is never an operator; it is how this document writes ranges.
PRINTS_AN_OPERATION = re.compile(
    r"\d[*\s]*(?:[×x*/+−]|\\times|\\cdot)[*\s]*\\?[\d$]"
    r"|\d[*\s]*\s-\s[*\s]*\\?[\d$]"
    r"|=[*\s]*\\?[\d$(]"
)

_MONTH = (r"(?:January|February|March|April|May|June|July|August|September|October"
          r"|November|December)")

# Each of these hides a numeral that is not a claim about data. ORDER MATTERS: dates and
# periods are blanked before bare years, and everything is blanked before figures are
# matched, so that a bolded date such as **2020-12-31** is emptied of digits and no
# longer looks like a bold count. This ordering was established empirically - masking
# years first leaves "-12-31" behind, which the bold pattern then catches.
_MASKS = (
    re.compile(r"```.*?```", re.S),                     # fenced code blocks
    re.compile(r"`[^`\n]*`"),                           # inline code spans
    re.compile(r"\b\d{10}-\d{2}-\d{6}\b"),              # SEC accession numbers
    re.compile(r"\bCUSIP\s+\S+"),                       # CUSIPs
    re.compile(r"^\|[\s:|-]+\|$", re.M),                # table alignment rows
    re.compile(r"§+\s?\d+(?:\.\d+)+"),                  # section refs carrying the sign
    # A section reference without the sign is masked by word, because bare "4.3.16" is
    # indistinguishable from a decimal figure without the preceding noun.
    re.compile(r"\bsections?\s+\d+(?:\.\d+)+", re.I),
    # Proper nouns that merely contain a numeral. Without these, every bolded mention of
    # the index ("**SPDR S&P 500 ETF Trust**") enters the candidate list as a figure.
    re.compile(r"S&P\s?\d+(?:\s?TR)?"),
    re.compile(r"\bTop\s?\d+"),
    re.compile(r"\bForm\s+\d+[A-Za-z-]*"),
    re.compile(r"\b(?:IRC\s+)?Section\s+\d+"),
    re.compile(r"\bN-30D\b|\bN-CSRS?\b|\bNPORT-P\b|\bSP500TR\b|\bGSPC\b|\bRule\s+\S+"),
    # Dates and periods, before bare years.
    re.compile(r"\bQ[1-4]\s+(?:19|20)\d{2}\b"),         # "Q1 2004"
    re.compile(r"\b(?:19|20)\d{2}-(?:Q[1-4]|\d{2}(?:-\d{2})?)\b"),  # 2020-12-31, 1999-Q2
    re.compile(rf"\b{_MONTH}\s+\d{{1,2}},?\s*(?:19|20)?\d{{0,4}}\b"),  # "March 31, 2004"
    re.compile(r"(?<![\d.\-])(?:19|20)\d{2}(?![\d.%])"),  # bare years
)

# The bold alternative requires the span to BEGIN with a digit. This is a deliberate
# trade against the generous-filter principle, made after measuring: matching any bold
# span containing a digit pulled in "**Phase 1 (Provisional Exits & Trims)**",
# "**Python 3.8+**" and "**Cell B2 on Executive Summary**" - labels whose numeral is
# incidental. Requiring a leading digit keeps every real bold count ("**208 rows**",
# "**55 verified regulatory filing quarters**", "**36 missing constituents**") and drops
# the labels. Percentages and dollar amounts inside a bold span are still caught by their
# own alternatives regardless of where they sit, so nothing numeric is lost.
_FIGURE = re.compile(
    r"[−+-]?\d[\d,]*(?:\.\d+)?\s?(?:%|pp\b)"            # percent and pp
    r"|\*\*\s*[−+-]?\d[^*\n]*\*\*"                      # bold beginning with a digit
    r"|\\?\$\s?\d[\d,]*(?:\.\d+)?\s?(?:bn|B|m|M|k|K)?"  # dollars, escaped or not
    r"|\b\d[\d,]* of \d[\d,]*\b"                        # "N of M"
)

# A heading number counts only if it is dotted ("4.3.7") or followed by a period
# ("1. Executive Summary"). Without the second condition, "#### 1996 endpoint
# reconciliation" reads as section "1996" and its fourteen figures are filed under a
# year instead of under 4.6.4, where they belong.
_HEADING = re.compile(r"^#{1,6}\s+(?:(\d+(?:\.\d+)+)|(\d+)\.)\s+(.*)$")


def _blank(match):
    """Replace a span with spaces, preserving length and newlines so offsets hold."""
    return "".join("\n" if char == "\n" else " " for char in match.group(0))


def mask(text):
    """Blank every numeral that is not a claim about data."""
    for pattern in _MASKS:
        text = pattern.sub(_blank, text)
    return text


def _normalise(figure):
    """Strip bold markers, escapes and trailing punctuation so the key is stable.

    The document escapes dollar signs for LaTeX (`\\$43.375`) and figures routinely end a
    clause, so without this the same figure keys differently in two places.
    """
    collapsed = " ".join(figure.replace("**", "").replace("\\", "").split())
    return collapsed.strip(" ,.;:")


def extract_from_text(text, document):
    """Enumerate candidate figures, tagged with the section heading above them.

    Headings are read from the raw text and figures from the masked text. Masking would
    otherwise destroy the section numbers in the headings themselves, because a heading
    number and a decimal figure look identical.
    """
    raw_lines = text.split("\n")
    masked_lines = mask(text).split("\n")

    entries = []
    counts = {}
    section = "preamble"

    for raw, masked_line in zip(raw_lines, masked_lines):
        heading = _HEADING.match(raw)
        if heading:
            section = heading.group(1) or heading.group(2)
        for match in _FIGURE.finditer(masked_line):
            figure = _normalise(match.group(0))
            if not any(char.isdigit() for char in figure):
                continue
            counts[(section, figure)] = counts.get((section, figure), 0) + 1
            entries.append({
                "document": document,
                "section": section,
                "figure": figure,
                "occurrence": counts[(section, figure)],
            })
    return entries


def extract_document(relative_path):
    """Enumerate one document, named by its repository-relative path."""
    text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    return extract_from_text(text, relative_path)


def extract_all():
    """Enumerate every document under the rule, in DOCUMENTS order."""
    entries = []
    for relative_path in DOCUMENTS:
        entries.extend(extract_document(relative_path))
    return entries


def key_of(entry):
    """The manifest key: section plus literal numeral, disambiguated by occurrence."""
    return (entry["document"], entry["section"], entry["figure"], entry["occurrence"])


def load_manifest():
    """Read the manifest, or an empty one if it does not exist yet."""
    if not MANIFEST_PATH.exists():
        return {"entries": []}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _tally():
    """Print a per-section count, which is how the classification work is sized."""
    counts = {}
    for entry in extract_all():
        counts[(entry["document"], entry["section"])] = counts.get(
            (entry["document"], entry["section"]), 0) + 1
    for (document, section), count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"{count:5d}  {document}  section {section}")
    print(f"\nTOTAL {sum(counts.values())} across {len(counts)} sections")


def _emit_skeleton():
    """Print a manifest whose entries are all unclassified, for filling in by hand."""
    manifest = {
        "description": (
            "Every numeric claim published in docs/, classified. A figure earns its place "
            "when the explanation collapses without it. See AGENTS.md and issue #91."
        ),
        "generated_by": "scripts/audit_doc_figures.py",
        "verdicts": list(VERDICTS),
        "entries": [
            dict(entry, verdict=None, guard=None, note="")
            for entry in extract_all()
        ],
    }
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


def _unclassified():
    """List candidates the manifest does not yet account for."""
    known = {tuple(key) for key in (
        key_of(entry) for entry in load_manifest()["entries"])}
    for entry in extract_all():
        if key_of(entry) not in known:
            print(f"{entry['document']}  section {entry['section']}  {entry['figure']!r}"
                  f"  #{entry['occurrence']}")


def _source_refs():
    """Print the `source_ref` census, and every gap marker in full.

    The point of the marker is that the gap is countable, so the count is printed rather
    than left to be derived by whoever next wonders. Each marker is listed with its
    figure, because a list of 54 reasons is the actual worklist for closing them.
    """
    counts = {}
    gaps = []
    for entry in load_manifest()["entries"]:
        if entry["verdict"] not in SOURCE_REF_VERDICTS:
            continue
        ref = entry.get("source_ref")
        form = classify_source_ref(ref)
        counts[form] = counts.get(form, 0) + 1
        if form == "unarchived":
            gaps.append((entry["section"], entry["figure"], ref.strip()))

    total = sum(counts.values())
    print(f"{total} entries carry a verdict in {SOURCE_REF_VERDICTS}")
    for form, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"{count:5d}  {form}")
    print(f"\n{len(archived_accessions())} accessions are archived under "
          f"{ARCHIVE_DIR.relative_to(REPO_ROOT)}")
    print(f"\n{len(gaps)} gap markers:")
    for section, figure, ref in gaps:
        print(f"  §{section:<8} {figure:<24} {ref}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--emit-skeleton", action="store_true",
                        help="print an unclassified manifest for every candidate")
    parser.add_argument("--unclassified", action="store_true",
                        help="list candidates missing from the manifest")
    parser.add_argument("--source-refs", action="store_true",
                        help="census the source_ref forms and list every gap marker")
    args = parser.parse_args()

    if args.emit_skeleton:
        _emit_skeleton()
    elif args.unclassified:
        _unclassified()
    elif args.source_refs:
        _source_refs()
    else:
        _tally()


if __name__ == "__main__":
    main()
