"""Archive SEI and Prudential March 31 (Q1) filings from SEC EDGAR.

Zero external dependencies - Python 3 standard library only.
Follows scripts/download_vanguard_semiannual_filings.py.
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
SEI_MANIFEST_PATH = OUTPUT_DIR / "sei_q1_filings_manifest.json"
PRUDENTIAL_MANIFEST_PATH = OUTPUT_DIR / "prudential_q1_filings_manifest.json"

SEI_CIK = "766589"
PRUDENTIAL_CIK = "887991"

# SEI Index Funds (CIK 766589)
# (year, form, accession)
SEI_FILINGS = [
    (1995, "N-30D", "0000950109-95-002026"),
    (1996, "N-30D", "0000935069-96-000067"),
    (1997, "N-30D", "0000935069-97-000083"),
    (1998, "N-30D", "0000935069-98-000088"),
    (1999, "N-30D", "0000935069-99-000097"),
    (2000, "N-30D", "0000935069-00-000275"),
    (2001, "N-30D", "0000935069-01-500170"),
    (2002, "N-30D", "0000935069-02-000435"),
    (2003, "N-30D", "0000935069-03-000686"),
    (2004, "N-CSR", "0000935069-04-000812"),
    (2005, "N-CSR", "0000935069-05-001458"),
    (2006, "N-CSR", "0000935069-06-001685"),
]

# Prudential / Dryden (CIK 887991)
# Note: 1997 has two accessions.
PRUDENTIAL_FILINGS = [
    (1994, "N-30D", "0000887991-94-000003"),
    (1995, "N-30D", "0000887991-95-000003"),
    (1996, "N-30D", "0000887991-96-000003"),
    (1997, "N-30D", "0000887991-97-000004"),
    (1997, "N-30D", "0000887991-97-000005"),
    (1999, "N-30D", "0000355348-99-000173"),
    (2000, "N-30D", "0000898733-00-000438"),
    (2001, "N-30D", "0000898733-01-500154"),
    (2002, "N-30D", "0000898733-02-000362"),
    (2003, "N-30D", "0000898733-03-000279"),
    (2004, "N-CSRS", "0001193125-04-097446"),
    (2005, "N-CSRS", "0001193125-05-120909"),
    (2006, "N-CSRS", "0001193125-06-126134"),
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
    
    # If missing from .txt header (early 1995 submission), check .hdr.sgml
    hdr_data = fetch_bytes(hdr_url(cik, accession)).decode("utf-8", errors="replace")
    match_hdr = _SEC_PERIOD.search(hdr_data) or _IMS_PERIOD.search(hdr_data)
    if match_hdr:
        # Prepend header to .txt file so the archived file is self-contained with full SEC header
        txt_content = txt_path.read_text(encoding="utf-8", errors="replace")
        txt_path.write_text(hdr_data + "\n" + txt_content, encoding="utf-8")
        return f"{match_hdr.group(1)}-{match_hdr.group(2)}-{match_hdr.group(3)}"

    raise ScheduleParseError(f"{txt_path.name}: missing CONFORMED PERIOD OF REPORT in SEC header")


def archive_filings(filer_name: str, cik: str, filings: list, manifest_path: Path, audited: bool) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    for year, form, accession in filings:
        file_name = f"{filer_name}_{year}_Q1_{form.replace('/', '')}_{accession}.txt"
        destination = OUTPUT_DIR / file_name

        if destination.exists():
            print(f"{filer_name} {year} Q1 already archived: {file_name}")
        else:
            url = filing_url(cik, accession)
            print(f"{filer_name} {year} Q1 downloading {accession} ...")
            destination.write_bytes(fetch_bytes(url))

        # Period guard
        period = extract_period(destination, cik, accession)
        expected = f"{year}-03-31"
        if period != expected:
            destination.unlink()
            raise ScheduleParseError(
                f"{file_name}: SEC header reports period {period}, expected {expected}. "
                "Refusing to archive; conformed period mismatch."
            )

        key = f"{year}_{accession}" if filings == PRUDENTIAL_FILINGS and year == 1997 else str(year)
        manifest[key] = {
            "fiscal_year": year,
            "quarter": "Q1",
            "form": form,
            "accession_number": accession,
            "report_date": period,
            "audited": audited,
            "sec_url": filing_url(cik, accession),
            "file_path": str(destination.relative_to(PROJECT_ROOT)),
            "file_size_bytes": destination.stat().st_size,
        }
        print(f"  {file_name}  period={period}  {manifest[key]['file_size_bytes']:,} bytes")

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    return manifest


def main():
    print("Archiving SEI Index Funds Q1 filings...")
    sei_manifest = archive_filings("SEI", SEI_CIK, SEI_FILINGS, SEI_MANIFEST_PATH, audited=True)
    print(f"{len(sei_manifest)} SEI filings archived.\n")

    print("Archiving Prudential Q1 filings...")
    prudential_manifest = archive_filings("PRUDENTIAL", PRUDENTIAL_CIK, PRUDENTIAL_FILINGS, PRUDENTIAL_MANIFEST_PATH, audited=False)
    print(f"{len(prudential_manifest)} Prudential filings archived.\n")


if __name__ == "__main__":
    main()
