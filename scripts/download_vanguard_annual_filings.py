"""Archive Vanguard Index Trust's December 31 annual reports from SEC EDGAR.

Zero external dependencies - Python 3 standard library only.

Why a second filer at all: SPY's fiscal year ended September 30 from 1997 onward, so
no SPY filing anchors a December 31 price for 1997-2019. Vanguard Index Trust
(CIK 0000036405) has a December 31 fiscal year end and files a Schedule of
Investments in the same shares-and-value format, which yields exact year-end implied
closes (value / shares) for constituents absent from data/raw/tickers/. See issue #55.

Unlike download_all_historical_sec_filings.py, which discovers SPY filings by scanning
EDGAR master indexes, every accession here is pinned. The set was enumerated once from
the submissions API and does not change, so discovery would add failure modes without
adding information.

Full submission documents are archived (not the inner document) because only the full
submission carries the SEC header, and CONFORMED PERIOD OF REPORT is the single field
that separates a December 31 annual report from a June 30 semi-annual one. Both file as
the same form under the same filer name. This is the check whose absence once placed a
March 31 snapshot in an annual slot (see docs/DATA_PROVENANCE.md 4.3.6).
"""

import json
import ssl
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.extract_ground_truth_from_sec import ScheduleParseError, read_filing_period

SEC_CIK = "36405"
HEADERS = {"User-Agent": "AcademicResearch sp500strategy@example.com"}
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sec_filings"
MANIFEST_PATH = OUTPUT_DIR / "vanguard_annual_filings_manifest.json"

# (fiscal_year, form, accession). Every entry is a December 31 period; the download
# asserts that against each filing's own SEC header rather than trusting this table.
# FY1993 (0000893220-94-000129) exists but no missing constituent requires it.
ANNUAL_FILINGS = [
    (1994, "N-30D", "0000893220-95-000088"),
    (1995, "N-30D", "0000893220-96-000339"),
    (1996, "N-30D", "0000893220-97-000517"),
    (1997, "N-30D", "0000893220-98-000471"),
    (1998, "N-30D", "0000893220-99-000267"),
    (1999, "N-30D", "0000893220-00-000244"),
    (2000, "N-30D", "0000893220-01-000239"),
    (2001, "N-30D", "0000932471-02-000460"),
    (2002, "N-30D", "0000932471-03-000327"),
    (2003, "N-CSR", "0000932471-04-000399"),
    (2004, "N-CSR", "0000932471-05-000480"),
    (2005, "N-CSR", "0000932471-06-000510"),
    (2006, "N-CSR", "0000932471-07-000538"),
]

# Amendments are recorded, not archived. Both differ from their parent only in the
# EDGAR header (26 and 7 bytes respectively) and carry an identical Schedule of
# Investments, so storing them would add ~8MB to record a 33-byte difference. This
# follows the SPY FY2004 precedent, where N-30D/A 0000950135-05-000099 is noted in the
# manifest rather than archived.
AMENDMENTS = {
    2001: ("N-30D/A", "0000932471-02-000470", "2002-03-11"),
    2005: ("N-CSR/A", "0000932471-06-000605", "2006-03-16"),
}


def filing_url(accession: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{SEC_CIK}/{accession}.txt"


def fetch_bytes(url: str) -> bytes:
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers=HEADERS)
    time.sleep(0.15)  # Respect SEC rate limits (<10 req/sec)
    with urllib.request.urlopen(req, context=ctx, timeout=180) as resp:
        return resp.read()


def archive_annual_reports() -> dict:
    """Download each pinned filing, asserting its period before it is kept."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {}
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    for year, form, accession in ANNUAL_FILINGS:
        key = str(year)
        file_name = f"VG500_{year}_{form.replace('/', '')}_{accession}.txt"
        destination = OUTPUT_DIR / file_name

        if destination.exists():
            print(f"FY{year} already archived: {file_name}")
        else:
            url = filing_url(accession)
            print(f"FY{year} downloading {accession} ...")
            destination.write_bytes(fetch_bytes(url))

        # The filing must state the period this table claims for it. A June 30
        # semi-annual report filed as the same form would otherwise land in an
        # annual slot and be read as a year-end snapshot.
        period = read_filing_period(destination)
        expected = f"{year}-12-31"
        if period != expected:
            destination.unlink()
            raise ScheduleParseError(
                f"{file_name}: SEC header reports period {period}, expected {expected}. "
                "Refusing to archive; this is not the December 31 annual report."
            )

        entry = {
            "fiscal_year": year,
            "form": form,
            "accession_number": accession,
            "report_date": period,
            "sec_url": filing_url(accession),
            "file_path": str(destination.relative_to(PROJECT_ROOT)),
            "file_size_bytes": destination.stat().st_size,
        }

        if year in AMENDMENTS:
            amend_form, amend_accession, amend_filed = AMENDMENTS[year]
            entry["note"] = (
                f"Amended by {amend_form} {amend_accession} (filed {amend_filed}), which "
                "carries an identical Schedule of Investments and differs from this "
                "document only in the EDGAR header. Recorded rather than archived."
            )

        manifest[key] = entry
        print(f"  {file_name}  period={period}  {entry['file_size_bytes']:,} bytes")

    return manifest


def main() -> None:
    manifest = archive_annual_reports()
    ordered = {k: manifest[k] for k in sorted(manifest, key=int)}
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2)
        f.write("\n")
    total = sum(e["file_size_bytes"] for e in ordered.values())
    print(f"\n{len(ordered)} filings archived, {total / 1e6:.1f} MB")
    print(f"Manifest: {MANIFEST_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
