"""Tests for guard verification tooling (issue #91)."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_doc_guards import (
    analyze_test_body,
    audit_guard,
    audit_guard_body,
    is_extractor_fixture,
)


class TestGuardVerification(unittest.TestCase):
    """Signals to detect guards that do not plausibly assert published claims."""

    def test_body_whose_only_assertion_is_assert_greater_zero_is_flagged_only_trivial(self):
        body = "self.assertGreater(shares, 0.0)"
        result = analyze_test_body(body)
        self.assertTrue(result["only_trivial"])

    def test_body_with_assert_almost_equal_is_not_flagged_only_trivial(self):
        body = "self.assertAlmostEqual(actual, expected, places=2)"
        result = analyze_test_body(body)
        self.assertFalse(result["only_trivial"])

    def test_value_guard_whose_body_has_no_equality_assertion_is_flagged_by_kind_matches(self):
        body = "self.assertGreater(val, 0.0)\nself.assertTrue(ok)"
        result = audit_guard_body(body, guard_kind="value")
        self.assertFalse(result["kind_matches"])

    def test_claim_guard_whose_body_has_only_assert_less_is_not_flagged(self):
        body = "self.assertLess(delta, 0.0)"
        result = audit_guard_body(body, guard_kind="claim")
        self.assertTrue(result["kind_matches"])

    def test_guard_in_test_doc_figures_is_flagged_is_extractor_fixture(self):
        guard = "tests/test_doc_figures.py::TestExtraction::test_bold_counts_are_caught"
        self.assertTrue(is_extractor_fixture(guard))

    def test_guard_naming_nonexistent_method_is_flagged_test_exists_false(self):
        guard = "tests/test_doc_guards.py::TestGuardVerification::test_nonexistent_method_xyz"
        result = audit_guard(
            {"guard": guard, "guard_kind": "claim", "figure": "1.0"},
            repo_root=ROOT,
        )
        self.assertFalse(result["test_exists"])


if __name__ == "__main__":
    unittest.main()
