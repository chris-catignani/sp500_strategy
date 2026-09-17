"""Archive Vanguard Index Trust's June 30 semi-annual reports from SEC EDGAR.

Zero external dependencies - Python 3 standard library only.

Why: the December 31 annual reports archived by download_vanguard_annual_filings.py anchor
Q4 only, so constituents priced from them have no Q2 observation and drop out of the
quarterly universe entirely (issue #63). Vanguard Index Trust files a semi-annual report at
June 30 in the same Schedule of Investments format, with unbroken coverage 1994-2006, which
yields implied closes at Q2 by the same value/shares quotient.

These are SEMI-ANNUAL reports and are therefore UNAUDITED, where the December 31 annuals
carry a Report of Independent Accountants. That difference is recorded per observation
rather than assumed away; see docs/DATA_PROVENANCE.md.

Accessions are pinned rather than discovered, following the annual archiver: the set was
enumerated once from the submissions API and does not change.

Note FY2003, which files as N-CSR - the same form Vanguard used for that year's December 31
annual report (0000932471-04-000399). Only CONFORMED PERIOD OF REPORT separates them, which
is exactly the confusion the period guard below exists to catch.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.download_vanguard_annual_filings import fetch_bytes, filing_url
from scripts.extract_ground_truth_from_sec import ScheduleParseError, read_filing_period

OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sec_filings"
MANIFEST_PATH = OUTPUT_DIR / "vanguard_semiannual_filings_manifest.json"

# (fiscal_year, form, accession). Every entry is a June 30 period; the download asserts
# that against each filing's own SEC header rather than trusting this table.
SEMIANNUAL_FILINGS = [
    (1994, "N-30D", "0000893220-94-000389"),
    (1995, "N-30D", "0000893220-95-000545"),
    (1996, "N-30D", "0000893220-96-001508"),
    (1997, "N-30D", "0000893220-97-001476"),
    (1998, "N-30D", "0000893220-98-001414"),
    (1999, "N-30D", "0000893220-99-001016"),
    (2000, "N-30D", "0000893220-00-001034"),
    (2001, "N-30D", "0000932471-01-500324"),
    (2002, "N-30D", "0000932471-02-000769"),
    (2003, "N-CSR", "0000932471-03-000714"),
    (2004, "N-CSRS", "0000932471-04-000761"),
    (2005, "N-CSRS", "0000932471-05-001231"),
    (2006, "N-CSRS", "0000932471-06-001224"),
]


def archive_semiannual_reports() -> dict:
    """Download each pinned filing, asserting its period before it is kept."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {}
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    for year, form, accession in SEMIANNUAL_FILINGS:
        file_name = f"VG500_{year}_Q2_{form.replace('/', '')}_{accession}.txt"
        destination = OUTPUT_DIR / file_name

        if destination.exists():
            print(f"FY{year} Q2 already archived: {file_name}")
        else:
            print(f"FY{year} Q2 downloading {accession} ...")
            destination.write_bytes(fetch_bytes(filing_url(accession)))

        # A December 31 annual report filed under the same form would otherwise land in a
        # Q2 slot and be read as a mid-year snapshot. FY2003 files as N-CSR under both
        # periods, so the form cannot be trusted to tell them apart.
        period = read_filing_period(destination)
        expected = f"{year}-06-30"
        if period != expected:
            destination.unlink()
            raise ScheduleParseError(
                f"{file_name}: SEC header reports period {period}, expected {expected}. "
                "Refusing to archive; this is not the June 30 semi-annual report."
            )

        manifest[str(year)] = {
            "fiscal_year": year,
            "quarter": "Q2",
            "form": form,
            "accession_number": accession,
            "report_date": period,
            "audited": False,
            "sec_url": filing_url(accession),
            "file_path": str(destination.relative_to(PROJECT_ROOT)),
            "file_size_bytes": destination.stat().st_size,
        }
        print(f"  {file_name}  period={period}  {manifest[str(year)]['file_size_bytes']:,} bytes")

    return manifest


def main() -> None:
    manifest = archive_semiannual_reports()
    ordered = {k: manifest[k] for k in sorted(manifest, key=int)}
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2)
        f.write("\n")
    total = sum(e["file_size_bytes"] for e in ordered.values())
    print(f"\n{len(ordered)} semi-annual filings archived, {total / 1e6:.1f} MB")
    print(f"Manifest: {MANIFEST_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
