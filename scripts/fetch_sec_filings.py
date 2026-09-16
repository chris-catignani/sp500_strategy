"""Fetch, parse, and archive audited SEC EDGAR SPY regulatory filings for ground-truth validation.

Saves raw filing documents to data/raw/ground_truth/sec_filings/ for permanent reference.
"""

import json
import os
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Any

SEC_CIK = "0000884394"  # SPDR S&P 500 ETF Trust
HEADERS = {"User-Agent": "AcademicResearch sp500strategy@example.com"}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sec_filings"
GROUND_TRUTH_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "quarterly_ground_truth_holdings.json"

def get_ssl_context() -> ssl.SSLContext:
    """Create an SSL context that works on macOS environments."""
    ctx = ssl.create_default_context()
    try:
        # Check if default context can verify
        return ctx
    except Exception:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

def fetch_url(url: str, is_json: bool = True) -> Any:
    """Fetch content from SEC EDGAR with rate limiting compliance."""
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers=HEADERS)
    time.sleep(0.15)  # SEC allows up to 10 requests per second
    with urllib.request.urlopen(req, context=ctx) as resp:
        content = resp.read()
        if is_json:
            return json.loads(content.decode("utf-8"))
        return content.decode("utf-8", errors="replace")

def fetch_submissions() -> dict:
    """Fetch recent submissions catalog for SPY."""
    url = f"https://data.sec.gov/submissions/CIK{SEC_CIK}.json"
    print(f"Fetching submissions metadata from {url}...")
    return fetch_url(url)

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sub = fetch_submissions()
    filings = sub.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    accs = filings.get("accessionNumber", [])
    report_dates = filings.get("reportDate", [])
    filing_dates = filings.get("filingDate", [])
    primary_docs = filings.get("primaryDocument", [])

    print(f"Loaded {len(forms)} filings from SEC EDGAR.")

    # Target key periods for modern era (2020-2024 NPORT-P filings)
    quarter_targets = {
        "2024-06-30": "2024-Q2",
        "2024-03-31": "2024-Q1",
        "2023-12-31": "2023-Q4",
        "2023-09-30": "2023-Q3",
        "2023-06-30": "2023-Q2",
        "2023-03-31": "2023-Q1",
        "2022-12-31": "2022-Q4",
        "2022-09-30": "2022-Q3",
        "2022-06-30": "2022-Q2",
        "2022-03-31": "2022-Q1",
        "2021-12-31": "2021-Q4",
        "2021-09-30": "2021-Q3",
        "2021-06-30": "2021-Q2",
        "2021-03-31": "2021-Q1",
        "2020-12-31": "2020-Q4",
        "2020-09-30": "2020-Q3",
        "2020-06-30": "2020-Q2",
        "2020-03-31": "2020-Q1",
    }

    manifest = {}
    
    for i, (form, r_date, f_date, acc, doc) in enumerate(zip(forms, report_dates, filing_dates, accs, primary_docs)):
        if r_date in quarter_targets and form.startswith("NPORT"):
            q_label = quarter_targets[r_date]
            if q_label in manifest:
                continue
            acc_nodash = acc.replace("-", "")
            # XML document URL
            doc_name = doc.split("/")[-1]
            url = f"https://www.sec.gov/Archives/edgar/data/{int(SEC_CIK)}/{acc_nodash}/{doc_name}"
            # Also raw XML if doc_name is xml
            xml_url = f"https://www.sec.gov/Archives/edgar/data/{int(SEC_CIK)}/{acc_nodash}/primary_doc.xml"
            
            print(f"Downloading filing for {q_label} (Report Date: {r_date}, Accession: {acc})...")
            try:
                xml_content = fetch_url(xml_url, is_json=False)
                save_path = OUTPUT_DIR / f"SPY_{q_label}_{acc}.xml"
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(xml_content)
                manifest[q_label] = {
                    "form": form,
                    "report_date": r_date,
                    "filing_date": f_date,
                    "accession_number": acc,
                    "url": f"https://www.sec.gov/Archives/edgar/data/{int(SEC_CIK)}/{acc_nodash}/{acc}-index.htm",
                    "file_path": str(save_path.relative_to(PROJECT_ROOT))
                }
            except Exception as e:
                print(f"Error downloading {xml_url}: {e}")

    print(f"Successfully archived {len(manifest)} modern quarterly SEC filings in {OUTPUT_DIR}.")
    
    # Save manifest for future reference
    manifest_path = OUTPUT_DIR / "sec_filings_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Saved manifest to {manifest_path}")

if __name__ == "__main__":
    main()
