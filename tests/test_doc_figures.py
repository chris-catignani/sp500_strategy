"""Enumerate and classify every numeric claim published in the documentation (#91)."""

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_doc_figures import (
    extract_from_text,
    key_of,
    mask,
)


class TestMasking(unittest.TestCase):
    """Numerals that are not claims about data must never reach the candidate list."""

    def test_mask_preserves_length_and_newlines(self):
        text = "a `code` b\n0001047469-04-007840\n"
        masked = mask(text)
        self.assertEqual(len(masked), len(text))
        self.assertEqual(masked.count("\n"), text.count("\n"))

    def test_accession_numbers_are_not_figures(self):
        entries = extract_from_text("Filed under 0001047469-04-007840 today.", "d.md")
        self.assertEqual(entries, [])

    def test_bare_years_are_not_figures(self):
        entries = extract_from_text("Covering 1994 through 2019 inclusive.", "d.md")
        self.assertEqual(entries, [])

    def test_section_references_are_not_figures(self):
        entries = extract_from_text("See section 4.3.16 and §4.3.20 for detail.", "d.md")
        self.assertEqual(entries, [])

    def test_code_spans_are_not_figures(self):
        entries = extract_from_text("The factor is `1.99487` in the table.", "d.md")
        self.assertEqual(entries, [])

    def test_a_bolded_date_is_not_a_figure(self):
        """**2020-12-31** is a date, and the ISO mask must run before the year mask.

        Masking the year first leaves "-12-31", which the bold alternative then catches.
        """
        entries = extract_from_text("- **2020-12-31**: Adobe enters.", "d.md")
        self.assertEqual(entries, [])

    def test_a_bolded_quarter_label_is_not_a_figure(self):
        entries = extract_from_text("- **1999-Q2** figures follow.", "d.md")
        self.assertEqual(entries, [])

    def test_a_wordy_date_is_not_a_figure(self):
        entries = extract_from_text("headed **as of March 31, 2004 (Unaudited)**", "d.md")
        self.assertEqual(entries, [])

    def test_the_index_name_is_not_a_figure(self):
        """Without this mask every bolded mention of the index becomes a candidate."""
        entries = extract_from_text("the **SPDR S&P 500 ETF Trust** holds it.", "d.md")
        self.assertEqual(entries, [])

    def test_a_bold_label_whose_digit_is_incidental_is_not_a_figure(self):
        """Deliberate trade: the bold alternative requires a LEADING digit.

        These three cost nothing to drop and were pulled in by the looser pattern.
        """
        for label in ("**Phase 1 (Provisional Exits & Trims)**",
                      "**Python 3.8+**",
                      "**Cell B2 on Executive Summary**"):
            with self.subTest(label=label):
                self.assertEqual(extract_from_text(label, "d.md"), [])

    def test_form_with_markdown_emphasis_is_not_a_figure(self):
        """Form **20-F** is a form name; the emphasis must not defeat the mask."""
        entries = extract_from_text("filed on Form **20-F** with the SEC.", "d.md")
        self.assertEqual(entries, [])


class TestExtraction(unittest.TestCase):
    """Over-catching costs a decision; under-catching is the defect #91 exists to fix."""

    def test_percent_and_pp_are_caught(self):
        text = "#### 4.3.7 Findings\n\nnegative, averaging -1.64% and moving +0.006pp overall.\n"
        figures = [e["figure"] for e in extract_from_text(text, "d.md")]
        self.assertIn("-1.64%", figures)
        self.assertIn("+0.006pp", figures)

    def test_bold_counts_are_caught(self):
        text = "#### 4.3.6 Archive\n\nAcross all **55 verified regulatory filing quarters** we agree.\n"
        figures = [e["figure"] for e in extract_from_text(text, "d.md")]
        self.assertIn("55 verified regulatory filing quarters", figures)

    def test_an_escaped_dollar_amount_is_caught_and_normalised(self):
        """The document escapes dollar signs for LaTeX; the key must not carry the slash."""
        text = "#### 4.5.4 Reconciliation\n\nclosing at \\$43.375 that day.\n"
        self.assertIn("$43.375", [e["figure"] for e in extract_from_text(text, "d.md")])

    def test_trailing_punctuation_is_not_part_of_the_key(self):
        text = "#### 4.3.6 Archive\n\npublished as $12,950,461,905; now corrected.\n"
        self.assertIn("$12,950,461,905", [e["figure"] for e in extract_from_text(text, "d.md")])

    def test_dollar_amounts_and_n_of_m_are_caught(self):
        text = "#### 4.3.14 Coverage\n\nParsed $2,275,051,856 across 13 of 19 constituents.\n"
        figures = [e["figure"] for e in extract_from_text(text, "d.md")]
        self.assertIn("$2,275,051,856", figures)
        self.assertIn("13 of 19", figures)

    def test_section_is_tracked_from_the_heading(self):
        text = "#### 4.3.7 Findings\n\naveraging -1.64% overall.\n"
        self.assertEqual(extract_from_text(text, "d.md")[0]["section"], "4.3.7")

    def test_a_top_level_heading_number_is_tracked(self):
        text = "## 5. Corporate Actions\n\nadjusted by 1.50% that year.\n"
        self.assertEqual(extract_from_text(text, "d.md")[0]["section"], "5")

    def test_an_unnumbered_heading_does_not_become_a_section(self):
        """"#### 1996 endpoint reconciliation" is prose, not section 1996.

        Its figures belong to the numbered section enclosing it.
        """
        text = ("#### 4.6.4 Valuation\n\nallocating 27.99% to Lucent.\n\n"
                "#### 1996 endpoint reconciliation\n\nclosing at 3.17% drift.\n")
        sections = {e["section"] for e in extract_from_text(text, "d.md")}
        self.assertEqual(sections, {"4.6.4"})

    def test_a_repeated_figure_is_disambiguated_by_occurrence(self):
        text = "#### 4.3.7 Findings\n\n-1.64% here.\n\nand -1.64% again.\n"
        entries = extract_from_text(text, "d.md")
        self.assertEqual([e["occurrence"] for e in entries], [1, 2])
        self.assertEqual(len({key_of(e) for e in entries}), 2)

    def test_n_over_m_ratio_is_caught(self):
        figures = [e["figure"] for e in extract_from_text("accuracy is 89.8% (494/550)", "d.md")]
        self.assertIn("494/550", figures)

    def test_spaced_share_count_table_cell_is_not_caught_as_ratio(self):
        """Four-digit cap and whitespace prohibition prevent share counts looking like ratios."""
        entries = extract_from_text("| 3,092,063 / 1,640,834 |", "d.md")
        self.assertEqual(entries, [])

    def test_spelled_count_with_no_digit_is_caught(self):
        figures = [e["figure"] for e in extract_from_text(
            "**Thirteen of the nineteen now carry a series.**", "d.md")]
        self.assertIn("Thirteen of the nineteen", figures)

    def test_spelled_count_against_digit_is_caught(self):
        figures = [e["figure"] for e in extract_from_text(
            "Eight of the 46 tickers have no price series", "d.md")]
        self.assertIn("Eight of the 46", figures)

    def test_range_keeps_its_hyphen(self):
        figures = [e["figure"] for e in extract_from_text(
            "raised every one of these figures by 0.006-0.056pp", "d.md")]
        self.assertEqual(figures, ["0.006-0.056pp"])

    def test_genuine_unicode_minus_negative_is_caught(self):
        figures = [e["figure"] for e in extract_from_text("−0.68pp", "d.md")]
        self.assertEqual(figures, ["−0.68pp"])

    def test_parenthesised_delta_is_caught(self):
        figures = [e["figure"] for e in extract_from_text(
            "| 10y Top 3 | 24.49% → **21.68%** (−2.81) |", "d.md")]
        self.assertIn("(−2.81)", figures)
        self.assertEqual(len(figures), 3)

    def test_dollar_followed_by_billion_does_not_absorb_letter_b(self):
        """Regression test for re.I trap: $16 billion extracts $16, not $16 b."""
        figures = [e["figure"] for e in extract_from_text("$16 billion", "d.md")]
        self.assertEqual(figures, ["$16"])

    def test_large_dollar_followed_by_billion_does_not_absorb_letter_b(self):
        """Regression test for re.I trap: $100,000 billion extracts $100,000, not $100,000 b."""
        figures = [e["figure"] for e in extract_from_text("$100,000 billion", "d.md")]
        self.assertEqual(figures, ["$100,000"])


class TestManifestCoverage(unittest.TestCase):
    """The ratchet. A figure added to either document fails the suite until classified."""

    @classmethod
    def setUpClass(cls):
        from scripts.audit_doc_figures import extract_all, load_manifest
        cls.extracted = extract_all()
        cls.manifest = load_manifest()

    def test_every_extracted_figure_has_a_manifest_entry(self):
        known = {key_of(entry) for entry in self.manifest["entries"]}
        missing = [key_of(entry) for entry in self.extracted if key_of(entry) not in known]
        self.assertEqual(
            missing, [],
            "figures published with no verdict; run "
            "`python3 scripts/audit_doc_figures.py --unclassified`",
        )

    def test_the_manifest_has_no_orphans(self):
        """A deleted figure must not leave a stale verdict behind."""
        live = {key_of(entry) for entry in self.extracted}
        orphans = [key_of(entry) for entry in self.manifest["entries"]
                   if key_of(entry) not in live]
        self.assertEqual(orphans, [], "manifest entries that no longer appear in any document")

    def test_every_entry_is_classified(self):
        """Reports a count and a sample, never the whole list.

        Asserting the list equals [] dumps a 28KB diff while the manifest is being
        filled in, which buries the actual worklist. Measured, not guessed.
        """
        from scripts.audit_doc_figures import VERDICTS
        unclassified = [key_of(e) for e in self.manifest["entries"] if e["verdict"] is None]
        self.assertEqual(
            len(unclassified), 0,
            f"{len(unclassified)} entries still carry a null verdict; first five: "
            f"{unclassified[:5]}",
        )
        bad = sorted({e["verdict"] for e in self.manifest["entries"]
                      if e["verdict"] not in VERDICTS})
        self.assertEqual(bad, [], f"verdicts outside {VERDICTS}")


class TestManifestWellFormedness(unittest.TestCase):
    """A verdict can rot without the figure changing - a named test can be deleted."""

    @classmethod
    def setUpClass(cls):
        from scripts.audit_doc_figures import load_manifest
        cls.manifest = load_manifest()

    def test_deleting_one_of_two_identical_numerals_is_reported_not_guessed(self):
        """`occurrence` is positional, so deleting the first of a pair renumbers the second.

        The entry that then looks orphaned is the LAST in the group, not the one deleted.
        Dropping it transfers the deleted figure's verdict onto the survivor. Issue #91 hit
        this twice -- section 5's AT&T `$0.33`, whose twin is the sourced Ma Bell dividend,
        and 4.3.7's `3.06%`, where the survivor is `decision-evidence` and the deleted one
        was `remove`.
        """
        from scripts.audit_doc_figures import reconciliation

        manifest = {"entries": [
            {"document": "d.md", "section": "5", "figure": "$0.33", "occurrence": 1,
             "verdict": "wrong"},
            {"document": "d.md", "section": "5", "figure": "$0.33", "occurrence": 2,
             "verdict": "sourced"},
        ]}
        shifted, vanished = reconciliation(manifest, {("d.md", "5", "$0.33"): 1})
        self.assertEqual(vanished, [], "one occurrence survives, so nothing vanished")
        self.assertEqual(len(shifted), 1, "the surviving occurrence must be reported")
        _, entries, surviving = shifted[0]
        self.assertEqual(surviving, 1)
        self.assertEqual(len(entries), 2)

    def test_a_group_with_no_occurrences_left_is_safe_to_read_as_orphaned(self):
        from scripts.audit_doc_figures import reconciliation

        manifest = {"entries": [
            {"document": "d.md", "section": "5", "figure": "$9.99", "occurrence": 1,
             "verdict": "remove"},
        ]}
        shifted, vanished = reconciliation(manifest, {})
        self.assertEqual(shifted, [])
        self.assertEqual(len(vanished), 1)

    def test_the_committed_manifest_needs_no_renumbering(self):
        """A ratchet: deleting a figure with a twin and not renumbering fails here."""
        from scripts.audit_doc_figures import reconciliation, extract_all
        import collections as _c

        live = _c.Counter(
            (e["document"], e["section"], e["figure"]) for e in extract_all()
        )
        shifted, _ = reconciliation(self.manifest, live)
        self.assertEqual(
            [(g[1], g[2]) for g, _e, _w in shifted], [],
            "occurrence numbering is stale; run audit_doc_figures.py --reconcile",
        )

    def test_no_pipeline_figure_is_left_unguarded(self):
        """The criterion issue #91 was opened to reach, as a test.

        A figure our code produces, published with nothing asserting the claim it
        evidences, is the whole defect. Pass 1 counted 498 such candidates and classified
        them; pass 2 removed the ones that had stopped earning their place and guarded the
        rest. This is what stops the set growing back.

        Adding a computed figure to either document now means one of three things: name a
        test that asserts its claim, write one, or state the claim qualitatively and point
        at the command that prints the number. The suite will not let a fourth option
        through.
        """
        unguarded = [
            (e["section"], e["figure"])
            for e in self.manifest["entries"]
            if e.get("rot_exposed") is True and not e.get("guard")
        ]
        self.assertEqual(
            unguarded, [],
            f"{len(unguarded)} pipeline figures are published with nothing asserting "
            f"them; first five: {unguarded[:5]}",
        )

    def test_a_guard_declares_which_promise_it_makes(self):
        """`guard_kind` separates "the claim stays true" from "the figure cannot move".

        Measured under #91: every test passed while 4.3.6's headline accuracy drifted from
        a published 89.8% to 92.9%. Nothing was broken -- the assertions behind it are
        floors with headroom, which is what AGENTS.md asks for and which cannot notice a
        cell moving inside the floor. So a guard protects the claim, not the figure, and
        the manifest has to record which of the two promises it holds.
        """
        from scripts.audit_doc_figures import GUARD_KINDS

        bad = [
            (key_of(e), e.get("guard_kind"))
            for e in self.manifest["entries"]
            if e.get("guard") and e.get("guard_kind") not in GUARD_KINDS
        ]
        self.assertEqual(bad, [], f"guarded entry without a kind in {GUARD_KINDS}")

    def test_only_a_guarded_entry_declares_a_guard_kind(self):
        """A kind without a guard is a claim about a test that was never named."""
        stray = [
            key_of(e)
            for e in self.manifest["entries"]
            if e.get("guard_kind") and not e.get("guard")
        ]
        self.assertEqual(stray, [], "guard_kind on an entry with no guard")

    def test_every_named_guard_exists(self):
        """Checked by reading the file as text, never by importing it.

        Importing a test module would drag the engine into a ratchet that must stay a
        sub-second text scan.
        """
        for entry in self.manifest["entries"]:
            guard = entry.get("guard")
            if not guard:
                continue
            with self.subTest(guard=guard):
                relative, _, qualified = guard.partition("::")
                path = ROOT / relative
                self.assertTrue(path.exists(), f"{relative} does not exist")
                method = qualified.rpartition("::")[2]
                self.assertIn(
                    f"def {method}(", path.read_text(encoding="utf-8"),
                    f"{relative} has no {method}",
                )

    def test_every_entry_carries_the_required_fields(self):
        for entry in self.manifest["entries"]:
            with self.subTest(entry=entry.get("figure")):
                for field in ("document", "section", "figure", "occurrence", "verdict",
                              "guard", "note"):
                    self.assertIn(field, entry)


class TestSourcedVerdictsAreGrounded(unittest.TestCase):
    """The gate on classification, which nothing else can re-run to check.

    Every other assertion in this file re-derives its answer: the extractor runs again,
    the figures are found again. A verdict cannot be re-derived. It is judgment, and a
    wrong `sourced` verdict is a false provenance claim published under a field name that
    asserts it is true.

    docs/SUBAGENTS.md records what that failure actually looks like here. Under #76 a
    third of 335 published figures were wrong, and none of it was invention - every value
    came from the right document and carried the right accession. They were real numbers
    read under the wrong label, which is worse than fabrication because the citation
    checks out and the first three you spot-check are correct. The conclusion drawn there
    is that the controller's check cannot be attentional; it has to be mechanical.

    So a `sourced` or `derivation` verdict must quote the attributing language it relies
    on, and the quote must literally appear in the document. The classifier has to find
    the attribution rather than assume it, and a substring test either passes or does not.

    The obvious alternative - require an accession in the same section - does not work.
    4.3.5, 4.3.8, 4.6.3, 4.6.4 and 4.3.14 contain no accessions at all, because the
    accessions live in the datasets rather than in the prose. Measured, not assumed.
    """

    GROUNDED = ("sourced", "derivation")

    @classmethod
    def setUpClass(cls):
        from scripts.audit_doc_figures import load_manifest
        cls.manifest = load_manifest()
        cls.documents = {}

    def _document(self, relative):
        if relative not in self.documents:
            self.documents[relative] = (ROOT / relative).read_text(encoding="utf-8")
        return self.documents[relative]

    def test_a_grounded_verdict_carries_a_quote(self):
        missing = [
            (e["section"], e["figure"]) for e in self.manifest["entries"]
            if e["verdict"] in self.GROUNDED and not e.get("evidence_quote")
        ]
        self.assertEqual(
            len(missing), 0,
            f"{len(missing)} sourced/derivation entries carry no evidence_quote; "
            f"first five: {missing[:5]}",
        )

    def test_every_quote_appears_in_its_document(self):
        """A quote that is not in the document is the whole failure mode, caught."""
        for entry in self.manifest["entries"]:
            quote = entry.get("evidence_quote")
            if not quote:
                continue
            with self.subTest(section=entry["section"], figure=entry["figure"]):
                # assertIn would print the whole 1,600-line document on failure, which
                # buries the one line that matters under 168KB of noise.
                self.assertTrue(
                    quote in self._document(entry["document"]),
                    f"evidence_quote for {entry['figure']!r} in section "
                    f"{entry['section']} does not appear in {entry['document']}: "
                    f"{quote!r}",
                )


class TestSourcedFiguresPointAtSomething(unittest.TestCase):
    """`sourced` is the strongest verdict in the manifest. It has to point somewhere.

    Pass 1 gave it the weakest evidence of any verdict. `sourced` asserts a filing backs
    the figure, and all that was required of it was an `evidence_quote` -- which
    TestSourcedVerdictsAreGrounded checks is IN the document, not that it ATTRIBUTES
    anything, so a quote restating the figure satisfied the gate. Measured before this
    changed: 126 accessions are archived under `data/raw/ground_truth/sec_filings/`, 2
    accessions were cited across all 181 `sourced` entries, and neither of those two was
    on disk. 179 of 181 verdicts pointed at nothing a reader could find.

    So every `sourced` entry now carries a `source_ref`, in exactly one of three forms:
    an archived accession, a repo-relative path, or an explicit `unarchived:` marker.

    THE THIRD FORM CARRIES THE WEIGHT. A figure read from a document this repository
    does not hold still passes -- but it says so, and it is counted. That is the move
    `refused_filings` and the sourced-zero-versus-unknown rule in AGENTS.md already
    make: an honest gap that is visible beats one that is silently absent. §4.6.4's
    `\\$45.875` is the worked example. Verdict `sourced`, quote "official NYSE closing
    price on September 30, 1996", no accession, no dataset row, and no `LU.json` at all,
    because §4.6.5 records that the 1996 spinoff series are unavailable from commercial
    APIs. Written this way in pass 1 it would have been obvious immediately.

    WHAT A RESOLVING REF PROVES, AND WHAT IT DOES NOT. That the pointer is good: the
    filing is on disk, or the file exists. NOT that the figure appears in the document
    it names. `scripts/verify_provenance.py` does that, by re-reading the cited filing.
    This is a findability guarantee and nothing more.
    """

    @classmethod
    def setUpClass(cls):
        from scripts.audit_doc_figures import load_manifest, SOURCE_REF_VERDICTS
        cls.sourced = [e for e in load_manifest()["entries"]
                       if e["verdict"] in SOURCE_REF_VERDICTS]

    def test_there_are_sourced_entries_to_check(self):
        """Guards the rest of this class against silently checking an empty list."""
        self.assertGreater(len(self.sourced), 100)

    def test_every_sourced_entry_carries_a_source_ref(self):
        missing = [key_of(e) for e in self.sourced if not (e.get("source_ref") or "").strip()]
        self.assertEqual(
            len(missing), 0,
            f"{len(missing)} sourced entries carry no source_ref; first five: "
            f"{missing[:5]}",
        )

    def test_every_source_ref_takes_one_of_the_three_permitted_forms(self):
        """A ref that resolves to nothing is worse than no ref: it reads as evidence."""
        from scripts.audit_doc_figures import classify_source_ref
        bad = [(e["section"], e["figure"], e.get("source_ref"),
                classify_source_ref(e.get("source_ref")))
               for e in self.sourced
               if classify_source_ref(e.get("source_ref"))
               not in ("accession", "path", "unarchived")]
        self.assertEqual(
            len(bad), 0,
            f"{len(bad)} source_refs are not an archived accession, an existing "
            f"repo-relative path, or an `unarchived:` marker; first five: {bad[:5]}",
        )

    def test_an_accession_ref_names_a_filing_on_disk(self):
        """The whole defect being fixed: the two accessions pass 1 cited were not held.

        Stated separately from the form check so a failure says which rule broke.
        """
        from scripts.audit_doc_figures import ACCESSION, archived_accessions
        held = archived_accessions()
        absent = [(e["section"], e["figure"], e["source_ref"]) for e in self.sourced
                  if ACCESSION.match((e.get("source_ref") or "").strip())
                  and e["source_ref"].strip() not in held]
        self.assertEqual(absent, [], "accession cited with no filing in the archive")

    def test_a_path_ref_resolves_on_disk(self):
        absent = [(e["section"], e["figure"], e["source_ref"]) for e in self.sourced
                  if "/" in (e.get("source_ref") or "")
                  and not (e.get("source_ref") or "").strip().startswith("unarchived:")
                  and not (ROOT / e["source_ref"].strip()).exists()]
        self.assertEqual(absent, [], "source_ref path does not exist")

    def test_nothing_reads_from_an_ignored_path(self):
        """`.superpowers/` is gitignored. A ref into it passes here and fails on a clone.

        docs/SUBAGENTS.md records this exact failure: a script and seven tests whose
        input lived under an ignored path, green locally and erroring in `setUpClass`
        anywhere else.
        """
        leaked = [(e["section"], e["figure"], e["source_ref"]) for e in self.sourced
                  if ".superpowers" in (e.get("source_ref") or "")]
        self.assertEqual(leaked, [], "source_ref points into a gitignored path")

    def test_the_gap_count_is_published_rather_than_buried(self):
        """The `unarchived:` total is pinned, so a change either way is deliberate.

        This is manifest bookkeeping, not a published figure: it counts rows in
        `docs/doc_figure_manifest.json`, which is the artifact this test governs, and
        `python3 scripts/audit_doc_figures.py --source-refs` prints the census and
        every marker. Adding a gap has to be argued for; closing one has to lower the
        number, which is the direction this should move.
        """
        from scripts.audit_doc_figures import (
            classify_source_ref, UNARCHIVED_SOURCE_REFS)
        gaps = [e for e in self.sourced
                if classify_source_ref(e.get("source_ref")) == "unarchived"]
        self.assertEqual(
            len(gaps), UNARCHIVED_SOURCE_REFS,
            f"{len(gaps)} sourced figures resolve only to an `unarchived:` marker, "
            f"against {UNARCHIVED_SOURCE_REFS} recorded in "
            f"scripts/audit_doc_figures.py; run "
            f"`python3 scripts/audit_doc_figures.py --source-refs`",
        )

    def test_a_gap_marker_says_what_is_missing(self):
        """A bare `unarchived:` is an excuse. The marker has to name the document."""
        from scripts.audit_doc_figures import UNARCHIVED_PREFIX
        terse = [(e["section"], e["figure"], e["source_ref"]) for e in self.sourced
                 if (e.get("source_ref") or "").strip().startswith(UNARCHIVED_PREFIX)
                 and len(e["source_ref"].strip()[len(UNARCHIVED_PREFIX):].split()) < 3]
        self.assertEqual(terse, [], "`unarchived:` marker does not say what is missing")

    def test_no_other_verdict_carries_a_source_ref(self):
        """The field means "this verdict claims a document". Only `sourced` does."""
        from scripts.audit_doc_figures import load_manifest, SOURCE_REF_VERDICTS
        stray = [key_of(e) for e in load_manifest()["entries"]
                 if e["verdict"] not in SOURCE_REF_VERDICTS and e.get("source_ref")]
        self.assertEqual(stray, [], "source_ref set on a verdict that does not take it")


class TestRotExposureIsDeclared(unittest.TestCase):
    """Whether a reader can verify a figure without running our code.

    This is the axis that predicts rot, and it cuts across the verdicts. 4.6.4's
    spinoff proceeds print a Form 8937 ratio times a filed close --
    `$0.324084 \times \$45.875 = \$14.86735 \approx \mathbf{\$14.87}$` -- so they are
    computed and cannot rot: a reader confirms them with a calculator and no change to
    our code can move them. `87.0%` in 4.3.6 is a match rate over our own parsing, and
    moves whenever the parser or the rosters change. The old sourced/computed binary
    called both "computed".

    An earlier revision of this docstring cited 4.5.3's `$1.32` as the archetype,
    "4 x $0.33". The document prints no such operation -- it says
    `\$0.33 quarterly dividend (\$1.32/year)` -- so the example was invented rather
    than read. It is recorded here because publishing an unsourced illustration is the
    same defect this file exists to prevent.

    WHAT THIS TEST CANNOT DO. It checks that a figure claiming to be stable carries a
    trace and prints an operation. It cannot check that the trace is CORRECT. 4.3.6
    publishes `89.8% (494/550)`, which prints an operation and passes every mechanical
    check here -- and is pipeline, because 494 is our own match count. Same surface
    form as 4.5.4's `(41.27 - 64.75 + 16.97) / 64.75`, opposite rot behaviour.

    So a passing suite is not evidence that the classification is right. Every
    `rot_exposed: false` verdict is controller-reviewed; this test only makes the
    reviewable set well-formed.
    """

    @classmethod
    def setUpClass(cls):
        from scripts.audit_doc_figures import load_manifest
        cls.manifest = load_manifest()

    def _rot_classified(self):
        from scripts.audit_doc_figures import ROT_CLASSIFIED_VERDICTS
        return [e for e in self.manifest["entries"]
                if e["verdict"] in ROT_CLASSIFIED_VERDICTS]

    def test_every_derivation_and_decision_evidence_declares_rot_exposure(self):
        missing = [key_of(e) for e in self._rot_classified()
                   if not isinstance(e.get("rot_exposed"), bool)]
        self.assertEqual(
            len(missing), 0,
            f"{len(missing)} entries do not declare rot_exposed; first five: "
            f"{missing[:5]}",
        )

    def test_nothing_else_declares_rot_exposure(self):
        """A `sourced` or `remove` entry has no business carrying this field."""
        from scripts.audit_doc_figures import ROT_CLASSIFIED_VERDICTS
        stray = [key_of(e) for e in self.manifest["entries"]
                 if e["verdict"] not in ROT_CLASSIFIED_VERDICTS
                 and e.get("rot_exposed") is not None]
        self.assertEqual(stray, [], "rot_exposed set on a verdict that does not take it")

    def test_a_stable_figure_carries_an_inputs_trace(self):
        """`rot_exposed: false` asserts the leaves are filings. Say which."""
        missing = [key_of(e) for e in self._rot_classified()
                   if e.get("rot_exposed") is False and not e.get("inputs_trace")]
        self.assertEqual(
            len(missing), 0,
            f"{len(missing)} stable entries carry no inputs_trace; first five: "
            f"{missing[:5]}",
        )

    def test_a_stable_figure_prints_its_operation(self):
        """Necessary, not sufficient. See this class's docstring for why."""
        from scripts.audit_doc_figures import PRINTS_AN_OPERATION
        silent = [
            (e["section"], e["figure"]) for e in self._rot_classified()
            if e.get("rot_exposed") is False
            and not PRINTS_AN_OPERATION.search(e.get("evidence_quote") or "")
        ]
        self.assertEqual(
            len(silent), 0,
            f"{len(silent)} entries claim to be self-checking without printing an "
            f"operation; first five: {silent[:5]}",
        )


class TestRegenerationAudit(unittest.TestCase):
    """Regeneration-command audit on markdown tables and sections (issue #91)."""

    def test_markdown_table_detection_finds_contiguous_tables(self):
        from scripts.audit_doc_figures import find_markdown_tables
        text = (
            "Some introduction\n\n"
            "| Header 1 | Header 2 |\n"
            "|---|---|\n"
            "| Val 1 | Val 2 |\n\n"
            "Middle prose\n\n"
            "| Col A | Col B |\n"
            "|---|---|\n"
            "| 1 | 2 |\n"
        )
        tables = find_markdown_tables(text)
        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[0]["start_line"], 3)
        self.assertEqual(tables[0]["end_line"], 5)
        self.assertEqual(tables[1]["start_line"], 9)
        self.assertEqual(tables[1]["end_line"], 11)

    def test_markdown_table_detection_ignores_non_table_lines(self):
        from scripts.audit_doc_figures import find_markdown_tables
        text = "No tables here\nJust lines\n- bullet point\n"
        tables = find_markdown_tables(text)
        self.assertEqual(tables, [])

    def test_command_detection_finds_inline_command(self):
        from scripts.audit_doc_figures import find_section_commands
        text = "Regenerate this with `python3 scripts/audit_quarterly_expansion.py` easily."
        commands = find_section_commands(text)
        self.assertEqual(commands, ["python3 scripts/audit_quarterly_expansion.py"])

    def test_command_detection_finds_fenced_command(self):
        from scripts.audit_doc_figures import find_section_commands
        text = (
            "Run the following:\n"
            "```bash\n"
            "python3 run_backtest.py --compare-frequencies\n"
            "python3 -m unittest discover tests\n"
            "```\n"
        )
        commands = find_section_commands(text)
        self.assertIn("python3 run_backtest.py --compare-frequencies", commands)
        self.assertIn("python3 -m unittest discover tests", commands)

    def test_command_detection_ignores_unrelated_code(self):
        from scripts.audit_doc_figures import find_section_commands
        text = "Run `git status` or `echo hello` or `python3 other_script.py`."
        commands = find_section_commands(text)
        self.assertEqual(commands, [])


if __name__ == "__main__":
    unittest.main()
