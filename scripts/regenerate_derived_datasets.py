#!/usr/bin/env python3
"""Regenerate every derived dataset from the archived filings, in dependency order.

Zero external dependencies - Python 3 standard library only.

A derived dataset can fall behind its inputs without anything noticing. Each file stays
internally consistent, every test that reads one file at a time keeps passing, and the
drift is only visible to somebody who happens to re-run a generator and look at
`git status`. That is how it has been found every time so far, which is to say by
accident:

- `vanguard_implied_prices.json` sat five commits behind `splits.json`, carrying
  BellSouth's 1994 price adjusted by 2.0 where the recovered 1995 split makes 4.0
  correct (#114).
- `derived_quarterly_constituent_series.json` sat two readings behind its own script,
  and the terminal action reading its last price was wrong in consequence (#112).
- `derived_constituent_series.json` was left behind when #112 regenerated only its
  quarterly twin, so one event carried two stock-leg prices differing by about a factor
  of two (#115).

The exports drift the same way and matter more directly: the README tells a reader to paste
`scripts/google_apps_script.js` into Google Sheets, and that file embeds a snapshot of the
results rather than fetching them, so a stale copy builds a dashboard from figures the
engine no longer produces. They are regenerated and checked here too.

Running this script and finding a diff in any generated path means something is behind its
inputs. `--check` does exactly that and exits non-zero, which is what CI runs.

    python3 scripts/regenerate_derived_datasets.py           # regenerate everything
    python3 scripts/regenerate_derived_datasets.py --check   # regenerate, then fail on drift

`--check` reports any modified file under `data/`, so run it from a clean tree: it cannot
tell a dataset that is behind its inputs from one you are part-way through editing. CI
runs it on a fresh checkout, where that ambiguity does not arise.

Order matters. The extractors read the archived filings, the derivations read what the
extractors publish, and `build_datasets_from_raw.py` reads both. Running them out of order
produces a tree that is clean only by luck.

Network-dependent scripts are deliberately absent. `extract_issuer_dividend_tables.py`
re-reads its 168 filings from EDGAR rather than from the archive, so it cannot run in CI
and cannot be part of a reproducibility check; `verify_provenance.py` is the tool for the
claims it publishes. The `download_*` and `fetch_*` families populate the archive and are
not derivations at all.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Everything generated and committed. The datasets the engine reads, and the exports the
# README hands to a reader: `scripts/google_apps_script.js` is the file it tells people to
# paste into Google Sheets, and it embeds a snapshot of the results rather than fetching
# them, so an engine or data change that is not re-exported ships a dashboard computing
# figures this repository no longer produces.
CHECKED_PATHS: List[str] = [
    "data/",
    "outputs/",
    "scripts/google_apps_script.js",
]

# Dependency order, not alphabetical. Each entry reads what the entries above it publish.
PIPELINE: List[str] = [
    # Rosters and prices, read from the archived filings.
    "extract_vanguard_rosters.py",
    "extract_vanguard_semiannual_rosters.py",
    "extract_sei_q1_rosters.py",
    "extract_sei_q3_rosters.py",
    "extract_prudential_q1_rosters.py",
    "extract_ground_truth_from_sec.py",
    "extract_vanguard_prices.py",
    "generate_historical_weights.py",
    # Series derived from those rosters, the issuer map and the corporate-action records.
    "derive_constituent_series.py",
    "derive_quarterly_constituent_series.py",
    "derive_issuer_dividend_series.py",
    # The compiled datasets the engine reads, built from everything above.
    "build_datasets_from_raw.py",
]

# The exports, which read the compiled datasets and so must run last. This is the one step
# that is not a script under scripts/, and the only reason to run the backtest WITH exports.
EXPORT_COMMAND: List[str] = ["run_backtest.py", "--compare-frequencies"]


def _run(argv: List[str]) -> float:
    """Run one generator, raising SystemExit with its output if it fails."""
    started = time.monotonic()
    entry = PROJECT_ROOT / ("scripts" if argv[0] != EXPORT_COMMAND[0] else "") / argv[0]
    result = subprocess.run(
        [sys.executable, str(entry), *argv[1:]],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(f"{argv[0]} failed with exit code {result.returncode}")
    return elapsed


def _modified_datasets() -> List[str]:
    """Generated paths that differ from HEAD, as git reports them."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", *CHECKED_PATHS],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"git status failed: {result.stderr.strip()}")
    return [line[3:] for line in result.stdout.splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if regenerating changes any generated file",
    )
    args = parser.parse_args()

    total = 0.0
    for argv in [[script] for script in PIPELINE] + [EXPORT_COMMAND]:
        elapsed = _run(argv)
        total += elapsed
        print(f"  {' '.join(argv):<45} {elapsed:5.1f}s")
    print(f"\n{len(PIPELINE) + 1} generators in {total:.1f}s")

    if not args.check:
        return

    drifted = _modified_datasets()
    if not drifted:
        print("\nEvery generated file matches what its inputs produce.")
        return

    print(f"\n{len(drifted)} generated file(s) are behind their inputs:")
    for path in drifted:
        print(f"  {path}")
    raise SystemExit(
        "\nRegenerating changed a committed file, so at least one of them no longer "
        "matches what it is derived from. Commit the regenerated files once you have "
        "checked what moved and why -- a value that changes rather than appears is a "
        "correction, and worth understanding before it ships."
    )


if __name__ == "__main__":
    main()
