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

        # Prefer N-CSR or N-30D (annual reports)
        preferred = None
        for q_year, q_num, m in filings_found:
            if m["form"] in ["N-CSR", "N-30D", "10-K"]:
                preferred = (q_year, q_num, m)
                break
        if not preferred:
            preferred = filings_found[0]

        q_year, q_num, m = preferred
        file_url = f"https://www.sec.gov/Archives/{m['file']}"
        raw_name = m['file'].split('/')[-1]
        save_name = f"SPY_{y}_{m['form']}_{raw_name}"
        save_path = OUTPUT_DIR / save_name

        print(f"  Found {m['form']} filed on {m['date']} ({file_url})")
        print(f"  Downloading to {save_name}...")
        try:
            content = fetch_url(file_url)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            # Extract accession number from file path or text
            acc_match = re.search(r"(\d{10}-\d{2}-\d{6})", m['file'])
            acc_num = acc_match.group(1) if acc_match else raw_name

            existing_manifest[y_str] = {
                "year": y,
                "form": m["form"],
                "filing_date": m["date"],
                "accession_number": acc_num,
                "sec_url": file_url,
                "file_path": str(save_path.relative_to(PROJECT_ROOT)),
                "file_size_bytes": len(content)
            }
            print(f"  Successfully archived {y} ({len(content):,} bytes)")
        except Exception as e:
            print(f"  Error downloading {file_url}: {e}")

    # Save manifest
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(existing_manifest, f, indent=2)
    print(f"\nArchived manifest saved to {manifest_file}")
    print(f"Total historical years in manifest: {len(existing_manifest)}")

if __name__ == "__main__":
    main()
