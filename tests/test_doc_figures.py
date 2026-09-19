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


if __name__ == "__main__":
    unittest.main()
