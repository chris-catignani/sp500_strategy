"""Locate and download audited SPY annual regulatory filings for all remaining historical years from SEC master indexes.

Covers:
  - 1994-1998 (Form N-30D)
  - 2001-2007 (Form N-30D / N-CSR)
  - 2009-2013 (Form N-CSR)
  - 2015-2019 (Form N-CSR)

Permanently stores all raw documents in data/raw/ground_truth/sec_filings/
and records full accession metadata in sec_annual_filings_manifest.json.
"""

import urllib.request
import ssl
import sys
import os
import re
import json
import time
from pathlib import Path

SEC_CIK = "884394"
HEADERS = {"User-Agent": "AcademicResearch sp500strategy@example.com"}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.extract_ground_truth_from_sec import parse_n30d_filing, ScheduleParseError

OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sec_filings"

TARGET_YEARS = list(range(1995, 2020))

def fetch_url(url: str) -> str:
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers=HEADERS)
    time.sleep(0.15)  # Respect SEC rate limits (<10 req/sec)
    with urllib.request.urlopen(req, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="replace")

def get_filings_for_quarter(year: int, qtr: int):
    url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{qtr}/company.idx"
    try:
        content = fetch_url(url)
    except Exception as e:
        print(f"  Error fetching index for {year}-Q{qtr}: {e}")
        return []
    
    matches = []
    for line in content.splitlines():
        if f" {SEC_CIK} " in line or line.startswith("SPDR S&P 500") or "SPDR S&P 500" in line:
            parts = [p.strip() for p in re.split(r"\s{2,}", line)]
            if len(parts) >= 5:
                # Company Name, Form, CIK, Date, File
                matches.append({
                    "company": parts[0],
                    "form": parts[1],
                    "cik": parts[2],
                    "date": parts[3],
                    "file": parts[4]
                })
    return matches

def is_valid_spy_annual_report(file_path: Path, year: int, content: str) -> bool:
    """Validate that a candidate filing is SPY's own annual report.

    Enforces:
    1. Positive filer identity: COMPANY CONFORMED NAME must match SPY's official
       filer names ('SPDR TRUST SERIES 1' for 1995-2009, or 'SPDR S&P 500 ETF TRUST'
       for 2010-2019).
    2. Document-level exclusion: co-filed trusts sharing CIK 0000884394 (such as
       Select Sector SPDR Trust) share the conformed filer identity, so candidate
       descriptions containing 'SELECT SECTOR' are rejected.
    3. Faithful-parse enforcement: for the fixed-width era (<= 2009), once filer identity
       and document exclusion pass, the candidate IS SPY's report. Any ScheduleParseError
       is a real reconciliation failure and must not be swallowed.
    """
    header_lines = content[:5000].splitlines()[:100]
    description = ""
    company_name = ""
    for line in header_lines:
        if "<DESCRIPTION>" in line:
            description = line.replace("<DESCRIPTION>", "").strip().upper()
        if "COMPANY CONFORMED NAME:" in line:
            company_name = line.split("COMPANY CONFORMED NAME:")[-1].strip().upper()

    # 1. Positive filer identity:
    # 1995-2009 filings use "SPDR TRUST SERIES 1"; 2010-2019 filings use
    # "SPDR S&P 500 ETF TRUST". Any other conformed name is not SPY.
    if company_name not in ("SPDR TRUST SERIES 1", "SPDR S&P 500 ETF TRUST"):
        return False

    # 2. Document-level exclusion for co-filed trusts:
    # Under shared CIK 0000884394, Select Sector SPDR filings also carry
    # COMPANY CONFORMED NAME "SPDR TRUST SERIES 1", so filer identity alone
    # cannot exclude them. The document description identifies Select Sector.
    if "SELECT SECTOR" in description:
        return False

    # 3. Faithful-parse enforcement for the fixed-width era:
    # For year <= 2009, candidates passing the above checks are SPY's own reports.
    # A ScheduleParseError indicates an extraction/reconciliation failure on SPY itself
    # and must be raised rather than swallowed so it does not silently drop the filing.
    if year <= 2009:
        try:
            parse_n30d_filing(file_path)
        except ScheduleParseError as err:
            raise ScheduleParseError(f"{Path(file_path).name}: {err}") from err

    return True

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_file = OUTPUT_DIR / "sec_annual_filings_manifest.json"
    
    existing_manifest = {}
    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            existing_manifest = json.load(f)

    print(f"Scanning SEC EDGAR master indexes for {len(TARGET_YEARS)} historical years...")
    
    for y in TARGET_YEARS:
        y_str = str(y)
        if y_str in existing_manifest:
            print(f"Year {y} already archived: {existing_manifest[y_str]['file_path']}")
            continue

        print(f"\nSearching for SPY Annual Report for year {y}...")
        # Check QTR4 of year Y, then QTR1 of year Y+1
        filings_found = []
        for q_year, q_num in [(y, 4), (y + 1, 1)]:
            matches = get_filings_for_quarter(q_year, q_num)
            for m in matches:
                form = m["form"]
                if form in ["N-CSR", "N-CSRS", "N-30D", "10-K", "N-Q"]:
                    filings_found.append((q_year, q_num, m))
        
        if not filings_found:
            print(f"  WARNING: No filing found for year {y}")
            continue

        # Annual report forms (N-CSR, N-30D, 10-K) take precedence over interim forms.
        annual_candidates = [c for c in filings_found if c[2]["form"] in ["N-CSR", "N-30D", "10-K"]]
        other_candidates = [c for c in filings_found if c[2]["form"] not in ["N-CSR", "N-30D", "10-K"]]
        candidates = annual_candidates + other_candidates

        archived = False
        for q_year, q_num, m in candidates:
            file_url = f"https://www.sec.gov/Archives/{m['file']}"
            raw_name = m["file"].split("/")[-1]
            save_name = f"SPY_{y}_{m['form']}_{raw_name}"
            save_path = OUTPUT_DIR / save_name

            print(f"  Evaluating candidate {m['form']} filed on {m['date']} ({file_url})...")
            try:
                content = fetch_url(file_url)
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(content)

                if not is_valid_spy_annual_report(save_path, y, content):
                    print(f"  Candidate {save_name} is not SPY's own report; falling through...")
                    save_path.unlink(missing_ok=True)
                    continue

                # Extract accession number from file path or text
                acc_match = re.search(r"(\d{10}-\d{2}-\d{6})", m["file"])
                acc_num = acc_match.group(1) if acc_match else raw_name

                entry = {
                    "year": y,
                    "form": m["form"],
                    "filing_date": m["date"],
                    "accession_number": acc_num,
                    "sec_url": file_url,
                    "file_path": str(save_path.relative_to(PROJECT_ROOT)),
                    "file_size_bytes": len(content),
                }
                if y_str in existing_manifest and "note" in existing_manifest[y_str]:
                    entry["note"] = existing_manifest[y_str]["note"]
                elif y == 2004:
                    entry["note"] = (
                        "Amended by N-30D/A 0000950135-05-000099 (filed 2005-01-07), "
                        "which carries an identical Schedule of Investments."
                    )

                existing_manifest[y_str] = entry
                print(f"  Successfully archived {y} ({len(content):,} bytes)")
                archived = True
                break
            except Exception as e:
                print(f"  Error downloading or validating {file_url}: {e}")
                save_path.unlink(missing_ok=True)

        if not archived:
            print(f"  WARNING: No valid filing found for year {y}")

    # Save manifest
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(existing_manifest, f, indent=2)
    print(f"\nArchived manifest saved to {manifest_file}")
    print(f"Total historical years in manifest: {len(existing_manifest)}")

if __name__ == "__main__":
    main()
