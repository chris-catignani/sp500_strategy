"""Cross-check test guards against manifest figure claims (issue #91).

Zero external dependencies - Python standard library only.

For every manifest entry with a non-null `guard`, report whether the named test
plausibly touches what the figure is about. This is a heuristic cross-check on the
controller's judgment, not a proof: a passing guard check does not prove that a test
asserts a figure, nor does a lack of literal token overlap prove that a test fails to
constrain it. It exists to detect invisible defects -- such as guards that point to
tests asserting only trivial truths, guards pointing to extractor fixtures, or
mismatches between claimed guard kinds and the assertions performed.

It never imports engine/ or any test module. All checks resolve statically as text.
"""

import argparse
import ast
import json
from pathlib import Path
import re
import sys
import textwrap

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "docs" / "doc_figure_manifest.json"

EQUALITY_ASSERTIONS = (
    "assertEqual",
    "assertAlmostEqual",
    "assertSequenceEqual",
    "assertListEqual",
    "assertDictEqual",
    "assertSetEqual",
    "assertCountEqual",
    "assertMultiLineEqual",
)

TRIVIAL_ASSERT_NAMES = (
    "assertTrue",
    "assertIsNotNone",
)


def is_extractor_fixture(guard):
    """Whether the guard names a test in the extractor test suite.

    tests/test_doc_figures.py tests the figure extractor itself; fixtures in it
    mention doc strings to verify extraction, not to guard data claims.
    """
    if not guard or not isinstance(guard, str):
        return False
    return guard.startswith("tests/test_doc_figures.py::") or guard == "tests/test_doc_figures.py"


def extract_method_body(text, class_name, method_name):
    """Extract the method body text for class_name::method_name from text.

    Reads from the `def` line to the next `def` at the same indentation,
    or until the class is exited or EOF.
    """
    lines = text.splitlines()
    in_class = False
    class_indent = 0
    found_method = False
    method_indent = 0
    body_lines = []

    for line in lines:
        if not in_class:
            m_cls = re.match(r"^(\s*)class\s+" + re.escape(class_name) + r"\b", line)
            if m_cls:
                in_class = True
                class_indent = len(m_cls.group(1))
        else:
            if not found_method:
                # If we hit a non-blank line indented <= class_indent that is not a comment, we left the class
                if (
                    line.strip()
                    and not line.strip().startswith("#")
                    and (len(line) - len(line.lstrip())) <= class_indent
                    and not re.match(r"^(\s*)class\s+" + re.escape(class_name) + r"\b", line)
                ):
                    break
                m_met = re.match(r"^(\s+)def\s+" + re.escape(method_name) + r"\b", line)
                if m_met:
                    found_method = True
                    method_indent = len(m_met.group(1))
            else:
                prefix = " " * method_indent
                if line.startswith(prefix + "def ") or line.startswith(prefix + "async def "):
                    break
                if (
                    line.strip()
                    and not line.strip().startswith("#")
                    and (len(line) - len(line.lstrip())) <= class_indent
                ):
                    break
                body_lines.append(line)

    if not found_method:
        return False, None
    return True, "\n".join(body_lines)


def resolve_guard(guard, repo_root=REPO_ROOT):
    """Resolve a guard string to its test body as text without importing.

    guard format: tests/path/to/file.py::ClassName::method_name
    Returns (test_exists: bool, body_text: Optional[str]).
    """
    if not guard or not isinstance(guard, str):
        return False, None
    parts = guard.split("::")
    if len(parts) != 3:
        return False, None
    file_rel, class_name, method_name = parts
    target_file = (repo_root / file_rel).resolve()
    if not target_file.is_file():
        return False, None
    try:
        text = target_file.read_text(encoding="utf-8")
    except OSError:
        return False, None

    exists, body = extract_method_body(text, class_name, method_name)
    return exists, body


def _is_trivial_call(attr, node):
    """Whether an individual assertion call matches trivial shapes."""
    if attr in TRIVIAL_ASSERT_NAMES:
        return True
    if attr == "assertGreater":
        if len(node.args) >= 2:
            second = node.args[1]
            if isinstance(second, ast.Constant) and second.value == 0:
                return True
            if (
                isinstance(second, ast.UnaryOp)
                and isinstance(second.operand, ast.Constant)
                and second.operand.value == 0
            ):
                return True
        return False
    if attr == "assertEqual":
        if len(node.args) >= 2:
            return ast.dump(node.args[0]) == ast.dump(node.args[1])
        return False
    return False


def analyze_test_body(body_text):
    """Analyze assertions in a test body.

    Returns dict with asserts_at_all, assertion_kinds, and only_trivial.
    """
    if body_text is None:
        return {
            "asserts_at_all": False,
            "assertion_kinds": [],
            "only_trivial": False,
        }

    dedented = textwrap.dedent(body_text)
    try:
        tree = ast.parse(dedented)
    except SyntaxError:
        # Fallback if raw snippet lacks context
        # Try wrapping in dummy function
        try:
            tree = ast.parse(f"def _dummy():\n{textwrap.indent(dedented, '    ')}")
        except SyntaxError:
            return {
                "asserts_at_all": False,
                "assertion_kinds": [],
                "only_trivial": False,
            }

    assert_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "self"
                and func.attr.startswith("assert")
            ):
                assert_calls.append((func.attr, node))

    if not assert_calls:
        return {
            "asserts_at_all": False,
            "assertion_kinds": [],
            "only_trivial": False,
        }

    assertion_kinds = sorted(list(set(attr for attr, _ in assert_calls)))
    only_trivial = all(_is_trivial_call(attr, node) for attr, node in assert_calls)

    return {
        "asserts_at_all": True,
        "assertion_kinds": assertion_kinds,
        "only_trivial": only_trivial,
    }


def check_kind_matches(guard_kind, assertion_kinds):
    """Check whether guard_kind ('value' or 'claim') matches the assertions found.

    - 'value' requires at least one equality assertion (assertEqual, assertAlmostEqual).
    - 'claim' mismatches if all assertions are equalities.
    Returns (matches: bool, reason: Optional[str]).
    """
    has_equality = any(k in EQUALITY_ASSERTIONS for k in assertion_kinds)
    all_equalities = bool(assertion_kinds) and all(k in EQUALITY_ASSERTIONS for k in assertion_kinds)

    if guard_kind == "value":
        if not has_equality:
            return False, "guard_kind is 'value' but no equality-style assertion appears"
        return True, None
    elif guard_kind == "claim":
        if all_equalities:
            return False, "guard_kind is 'claim' but the only assertions are equalities"
        return True, None
    return True, None


def check_data_overlap(figure, note, body_text):
    """Check whether figure literals or note dataset paths appear in test body.

    Returns list of matched tokens.
    """
    if not body_text:
        return []

    tokens = set()
    fig = str(figure).strip() if figure else ""
    if fig:
        tokens.add(fig)
        norm = fig.replace("−", "-").strip()
        tokens.add(norm)
        # Strip outer punctuation / symbols: $, %, pp, bold
        sub_num = re.sub(r"^[^\d+-]+|[^\d]+$", "", norm)
        if sub_num:
            tokens.add(sub_num)
            if sub_num.startswith(("+", "-")):
                tokens.add(sub_num[1:])

    note_str = str(note) if note else ""
    if note_str:
        # Match dataset paths or file names
        path_matches = re.findall(r"(?:data/[\w/.-]+|\b[\w.-]+\.(?:json|csv|py|txt)\b)", note_str)
        for p in path_matches:
            tokens.add(p)
            tokens.add(p.split("/")[-1])

    # Filter out single character tokens unless digit
    candidates = [t for t in tokens if len(t) > 1 or (t and t.isdigit())]

    matched = [c for c in sorted(candidates, key=lambda x: (-len(x), x)) if c in body_text]
    return matched


def audit_guard(entry, repo_root=REPO_ROOT):
    """Audit a single manifest entry.

    Returns dict of computed signals.
    """
    guard = entry.get("guard")
    guard_kind = entry.get("guard_kind")
    figure = entry.get("figure")
    section = entry.get("section")
    note = entry.get("note", "")

    extractor_fixture = is_extractor_fixture(guard)
    test_exists, body_text = resolve_guard(guard, repo_root=repo_root)

    if not test_exists:
        return {
            "guard": guard,
            "guard_kind": guard_kind,
            "figure": figure,
            "section": section,
            "note": note,
            "test_exists": False,
            "asserts_at_all": False,
            "assertion_kinds": [],
            "only_trivial": False,
            "kind_matches": False,
            "kind_mismatch_reason": "test does not exist",
            "data_overlap": [],
            "is_extractor_fixture": extractor_fixture,
        }

    analysis = analyze_test_body(body_text)
    kind_match, reason = check_kind_matches(guard_kind, analysis["assertion_kinds"])
    overlap = check_data_overlap(figure, note, body_text)

    return {
        "guard": guard,
        "guard_kind": guard_kind,
        "figure": figure,
        "section": section,
        "note": note,
        "test_exists": True,
        "asserts_at_all": analysis["asserts_at_all"],
        "assertion_kinds": analysis["assertion_kinds"],
        "only_trivial": analysis["only_trivial"],
        "kind_matches": kind_match,
        "kind_mismatch_reason": reason,
        "data_overlap": overlap,
        "is_extractor_fixture": extractor_fixture,
    }


def audit_guard_body(
    body_text,
    guard_kind="value",
    figure="",
    note="",
    guard="tests/test_example.py::TestClass::test_method",
):
    """Helper for testing inline fixture bodies directly."""
    extractor_fixture = is_extractor_fixture(guard)
    analysis = analyze_test_body(body_text)
    kind_match, reason = check_kind_matches(guard_kind, analysis["assertion_kinds"])
    overlap = check_data_overlap(figure, note, body_text)

    return {
        "guard": guard,
        "guard_kind": guard_kind,
        "figure": figure,
        "note": note,
        "test_exists": True,
        "asserts_at_all": analysis["asserts_at_all"],
        "assertion_kinds": analysis["assertion_kinds"],
        "only_trivial": analysis["only_trivial"],
        "kind_matches": kind_match,
        "kind_mismatch_reason": reason,
        "data_overlap": overlap,
        "is_extractor_fixture": extractor_fixture,
    }


def load_manifest_entries(manifest_path=MANIFEST_PATH):
    """Load guarded entries from the manifest."""
    manifest_path = Path(manifest_path)
    if not manifest_path.is_file():
        return []
    with open(manifest_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return [e for e in data.get("entries", []) if e.get("guard")]


def audit_manifest(manifest_path=MANIFEST_PATH, repo_root=REPO_ROOT):
    """Audit all guarded entries from the manifest."""
    entries = load_manifest_entries(manifest_path)
    return [audit_guard(e, repo_root=repo_root) for e in entries]


def format_report(results):
    """Format plain-text report grouped by concern."""
    extractor_fixtures = [r for r in results if r["is_extractor_fixture"]]
    only_trivial = [r for r in results if r["only_trivial"]]
    kind_mismatches = [r for r in results if not r["kind_matches"]]
    no_overlap = [r for r in results if not r["data_overlap"]]

    clean = [
        r
        for r in results
        if (
            r["test_exists"]
            and not r["is_extractor_fixture"]
            and not r["only_trivial"]
            and r["kind_matches"]
            and r["data_overlap"]
        )
    ]

    lines = []
    lines.append("=== Guard Verification Audit Report ===")
    lines.append("")

    # 1. Extractor fixtures
    lines.append(f"1. Extractor Fixtures ({len(extractor_fixtures)}):")
    if extractor_fixtures:
        for r in extractor_fixtures:
            lines.append(f"   §{r['section']} {r['figure']!r} -> {r['guard']}")
    else:
        lines.append("   (none)")
    lines.append("")

    # 2. Only trivial
    lines.append(f"2. Only Trivial Assertions ({len(only_trivial)}):")
    if only_trivial:
        for r in only_trivial:
            lines.append(
                f"   §{r['section']} {r['figure']!r} -> {r['guard']} ({', '.join(r['assertion_kinds'])})"
            )
    else:
        lines.append("   (none)")
    lines.append("")

    # 3. Kind mismatches
    lines.append(f"3. Kind Mismatches ({len(kind_mismatches)}):")
    if kind_mismatches:
        for r in kind_mismatches:
            lines.append(
                f"   §{r['section']} {r['figure']!r} (kind={r['guard_kind']}) -> {r['guard']}: {r['kind_mismatch_reason']}"
            )
    else:
        lines.append("   (none)")
    lines.append("")

    # 4. No data overlap
    lines.append(f"4. No Data Overlap ({len(no_overlap)}):")
    if no_overlap:
        for r in no_overlap:
            lines.append(f"   §{r['section']} {r['figure']!r} -> {r['guard']}")
    else:
        lines.append("   (none)")
    lines.append("")

    # 5. Clean count
    lines.append(f"5. Clean ({len(clean)}):")
    lines.append(f"   {len(clean)} guarded entries passed all checks.")
    lines.append("")

    # Summary
    lines.append(f"Total guarded entries examined: {len(results)}")
    lines.append(
        f"FLAGGED: extractor_fixture={len(extractor_fixtures)} only_trivial={len(only_trivial)} "
        f"kind_mismatch={len(kind_mismatches)} no_overlap={len(no_overlap)}"
    )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--json", action="store_true", help="emit the audit data as JSON"
    )
    parser.add_argument(
        "--manifest",
        default=str(MANIFEST_PATH),
        help="path to manifest file (defaults to docs/doc_figure_manifest.json)",
    )
    args = parser.parse_args()

    results = audit_manifest(manifest_path=args.manifest)

    if args.json:
        extractor_count = sum(1 for r in results if r["is_extractor_fixture"])
        trivial_count = sum(1 for r in results if r["only_trivial"])
        kind_mismatch_count = sum(1 for r in results if not r["kind_matches"])
        no_overlap_count = sum(1 for r in results if not r["data_overlap"])
        clean_count = sum(
            1
            for r in results
            if (
                r["test_exists"]
                and not r["is_extractor_fixture"]
                and not r["only_trivial"]
                and r["kind_matches"]
                and r["data_overlap"]
            )
        )
        payload = {
            "summary": {
                "total_examined": len(results),
                "extractor_fixture": extractor_count,
                "only_trivial": trivial_count,
                "kind_mismatch": kind_mismatch_count,
                "no_overlap": no_overlap_count,
                "clean": clean_count,
            },
            "entries": results,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(format_report(results))

    sys.exit(0)


if __name__ == "__main__":
    main()
