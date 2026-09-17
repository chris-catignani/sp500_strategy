"""Archive SEI September 30 (Q3) filings from SEC EDGAR.

Zero external dependencies - Python 3 standard library only.
Follows scripts/download_q1_filings.py.
"""

import json
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.extract_ground_truth_from_sec import ScheduleParseError

HEADERS = {"User-Agent": "AcademicResearch sp500strategy@example.com"}
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sec_filings"
SEI_MANIFEST_PATH = OUTPUT_DIR / "sei_q3_filings_manifest.json"

SEI_CIK = "766589"

# SEI Index Funds (CIK 766589) semi-annual filings (September 30)
# (year, form, accession)
SEI_Q3_FILINGS = [
    (1995, "N-30D",  "0000935069-95-000073"),
    (1996, "N-30D",  "0000935069-96-000144"),
    (1997, "N-30D",  "0000935069-97-000203"),
    (1998, "N-30D",  "0000935069-98-000205"),
    (1998, "N-30D",  "0000935069-98-000213"),
    (1999, "N-30D",  "0000935069-99-000261"),
    (2000, "N-30D",  "0000935069-00-000629"),
    (2001, "N-30D",  "0000935069-01-500670"),
    (2002, "N-30D",  "0000935069-02-001260"),
    (2003, "N-CSRS", "0000935069-03-001566"),
    (2004, "N-CSRS", "0000935069-04-002035"),
    (2005, "N-CSRS", "0000935069-05-003335"),
    (2006, "N-CSRS", "0000935069-06-003272"),
]


def filing_url(cik: str, accession: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{str(cik).lstrip('0')}/{accession}.txt"


def hdr_url(cik: str, accession: str) -> str:
    acc_clean = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{str(cik).lstrip('0')}/{acc_clean}/{accession}.hdr.sgml"


def fetch_bytes(url: str) -> bytes:
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers=HEADERS)
    time.sleep(0.15)  # Respect SEC rate limits (<10 req/sec)
    with urllib.request.urlopen(req, context=ctx, timeout=180) as resp:
        return resp.read()


_SEC_PERIOD = re.compile(r"^CONFORMED PERIOD OF REPORT:\s*(\d{4})(\d{2})(\d{2})", re.M)
_IMS_PERIOD = re.compile(r"^<PERIOD>(\d{4})(\d{2})(\d{2})", re.M)


def extract_period(txt_path: Path, cik: str, accession: str) -> str:
    with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
        header = f.read(4000)
    match = _SEC_PERIOD.search(header)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    # If missing from .txt header, check .hdr.sgml
    hdr_data = fetch_bytes(hdr_url(cik, accession)).decode("utf-8", errors="replace")
    match_hdr = _SEC_PERIOD.search(hdr_data) or _IMS_PERIOD.search(hdr_data)
    if match_hdr:
        # Prepend header to .txt file so the archived file is self-contained with full SEC header
        txt_content = txt_path.read_text(encoding="utf-8", errors="replace")
        txt_path.write_text(hdr_data + "\n" + txt_content, encoding="utf-8")
        return f"{match_hdr.group(1)}-{match_hdr.group(2)}-{match_hdr.group(3)}"

    raise ScheduleParseError(f"{txt_path.name}: missing CONFORMED PERIOD OF REPORT in SEC header")


def archive_q3_filings() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    if SEI_MANIFEST_PATH.exists():
        with open(SEI_MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    for year, form, accession in SEI_Q3_FILINGS:
        file_name = f"SEI_{year}_Q3_{form.replace('/', '')}_{accession}.txt"
        destination = OUTPUT_DIR / file_name

        if destination.exists():
            print(f"SEI {year} Q3 already archived: {file_name}")
        else:
            url = filing_url(SEI_CIK, accession)
            print(f"SEI {year} Q3 downloading {accession} ...")
            destination.write_bytes(fetch_bytes(url))

        # Period guard
        period = extract_period(destination, SEI_CIK, accession)
        expected = f"{year}-09-30"
        if period != expected:
            destination.unlink()
            raise ScheduleParseError(
                f"{file_name}: SEC header reports period {period}, expected {expected}. "
                "Refusing to archive; conformed period mismatch."
            )

        key = f"{year}_{accession}" if year == 1998 else str(year)
        manifest[key] = {
            "fiscal_year": year,
            "quarter": "Q3",
            "form": form,
            "accession_number": accession,
            "report_date": period,
            "audited": False,
            "sec_url": filing_url(SEI_CIK, accession),
            "file_path": str(destination.relative_to(PROJECT_ROOT)),
            "file_size_bytes": destination.stat().st_size,
        }
        print(f"  {file_name}  period={period}  {manifest[key]['file_size_bytes']:,} bytes")

    with open(SEI_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    return manifest


def main():
    print("Archiving SEI Index Funds Q3 filings...")
    manifest = archive_q3_filings()
    print(f"{len(manifest)} SEI Q3 filings archived.\n")


if __name__ == "__main__":
    main()
