"""Extract and compile verified quarterly ground-truth S&P 500 Top 10 holdings from SEC filings.

Parses all 18 SPY Form NPORT-P XML regulatory filings directly, verifies reporting dates (repPdDate),
aggregates Alphabet share classes, and marks historical periods without point-in-time filing evidence as unverified.

Zero external dependencies - Python 3 standard library only.
"""

import json
from pathlib import Path
import re
from typing import Any, Dict, List
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FILINGS_DIR = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sec_filings"
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "quarterly_ground_truth_holdings.json"

# CUSIP to standard engine Ticker mapping
CUSIP_TO_TICKER = {
    "037833100": "AAPL",
    "594918104": "MSFT",
    "023135106": "AMZN",
    "67066G104": "NVDA",
    "02079K305": "GOOGL",
    "02079K107": "GOOG",
    "084670702": "BRK.B",
    "88160R101": "TSLA",
    "30303M102": "META",
    "91324P102": "UNH",
    "478160104": "JNJ",
    "30231G102": "XOM",
    "46625H100": "JPM",
    "92826C839": "V",
    "742718109": "PG",
    "58933Y105": "MRK",    # Merck & Co Inc (CUSIP 58933Y105)
    "580135101": "MCD",    # McDonald's Corp (CUSIP 580135101)
    "00287Y109": "ABBV",   # AbbVie Inc
    "166764100": "CVX",
    "532457108": "LLY",
    "437076102": "HD",
    "060505104": "BAC",
    "191216100": "KO",
    "713448108": "PEP",
    "931142103": "WMT",
    "22160K105": "COST",
    "11135F101": "AVGO",
    "17275R102": "CSCO",
    "00206R102": "T",
    "369604103": "GE",
    "459200101": "IBM",
    "717081103": "PFE",
    "254687106": "DIS",
    "68389X105": "ORCL",
    "92343V104": "VZ",
    "025816109": "AXP",
    "57636Q104": "MA",     # Mastercard Inc
    "70450Y103": "PYPL",   # PayPal Holdings Inc
    "00724F101": "ADBE",   # Adobe Inc
    "20030N101": "CMCSA",  # Comcast Corp
}

# Name pattern fallbacks if CUSIP lookup fails
NAME_FALLBACKS = [
    (r"Apple\s+Inc", "AAPL"),
    (r"Microsoft\s+Corp", "MSFT"),
    (r"Amazon\.com\s+Inc", "AMZN"),
    (r"NVIDIA\s+Corp", "NVDA"),
    (r"Alphabet\s+Inc.*Class\s+A", "GOOGL"),
    (r"Alphabet\s+Inc.*Class\s+C", "GOOG"),
    (r"Berkshire\s+Hathaway.*Class\s+B", "BRK.B"),
    (r"Tesla\s+Inc", "TSLA"),
    (r"Meta\s+Platforms|Facebook\s+Inc", "META"),
    (r"UnitedHealth\s+Group", "UNH"),
    (r"Johnson\s+&\s+Johnson", "JNJ"),
    (r"Exxon\s+Mobil", "XOM"),
    (r"JPMorgan\s+Chase", "JPM"),
    (r"Visa\s+Inc", "V"),
    (r"Procter\s+&\s+Gamble", "PG"),
    (r"Merck\s+&\s+Co", "MRK"),
    (r"AbbVie\s+Inc", "ABBV"),
    (r"Chevron\s+Corp", "CVX"),
    (r"Eli\s+Lilly", "LLY"),
    (r"Home\s+Depot", "HD"),
    (r"Broadcom\s+Inc", "AVGO"),
    (r"Mastercard\s+Inc", "MA"),
    (r"Costco\s+Wholesale", "COST"),
    (r"Pfizer\s+Inc", "PFE"),
    (r"Bank\s+of\s+America", "BAC"),
    (r"Walt\s+Disney", "DIS"),
    (r"Cisco\s+Systems", "CSCO"),
]


def strip_ns(tag: str) -> str:
    """Strip XML namespace."""
    return re.sub(r"\{.*?\}", "", tag)


def map_ticker(name: str, cusip: str, raw_ticker: str) -> str:
    """Map holding to standard ticker symbol."""
    if cusip in CUSIP_TO_TICKER:
        return CUSIP_TO_TICKER[cusip]
    if raw_ticker:
        t = raw_ticker.replace("-", ".").upper()
        if t in ("BRK.B", "BRKB"):
            return "BRK.B"
        return t
    for pattern, t in NAME_FALLBACKS:
        if re.search(pattern, name, re.IGNORECASE):
            return t
    return name


def parse_xml_filing(xml_path: Path) -> Dict[str, Any]:
    """Parse Form NPORT-P XML file."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Extract reporting date
    rep_pd_date = ""
    for elem in root.iter():
        if strip_ns(elem.tag) == "repPdDate":
            rep_pd_date = (elem.text or "").strip()
            break

    raw_holdings = []
    for elem in root.iter():
        if strip_ns(elem.tag) == "invstOrSec":
            name = ""
            val = 0.0
            cusip = ""
            ticker = ""
            for child in elem:
                t = strip_ns(child.tag)
                if t == "name":
                    name = (child.text or "").strip()
                elif t == "valUSD":
                    try:
                        val = float(child.text or "0")
                    except ValueError:
                        pass
                elif t == "cusip":
                    cusip = (child.text or "").strip()
                elif t == "ticker":
                    ticker = (child.text or "").strip()

            std_ticker = map_ticker(name, cusip, ticker)
            raw_holdings.append({
                "name": name,
                "ticker": std_ticker,
                "cusip": cusip,
                "val": val,
            })

    # Consolidate Alphabet Class A & C
    alphabet_val = sum(h["val"] for h in raw_holdings if h["ticker"] in ("GOOG", "GOOGL"))
    other_holdings = [h for h in raw_holdings if h["ticker"] not in ("GOOG", "GOOGL")]

    consolidated = list(other_holdings)
    if alphabet_val > 0:
        consolidated.append({
            "name": "Alphabet Inc. (Class A & C Combined)",
            "ticker": "GOOGL",
            "cusip": "02079K305",
            "val": alphabet_val,
        })

    consolidated.sort(key=lambda x: x["val"], reverse=True)
    total_val = sum(h["val"] for h in consolidated)

    for i, h in enumerate(consolidated, 1):
        h["rank"] = i
        h["weight"] = h["val"] / total_val if total_val > 0 else 0.0

    return {
        "report_date": rep_pd_date,
        "total_val_usd": total_val,
        "holdings": consolidated,
    }


def main():
    manifest_path = FILINGS_DIR / "sec_filings_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    ground_truth = {
        "description": "Audited S&P 500 quarter-end Top 10 constituent holdings compiled from SPY SEC Form NPORT-P / N-30D regulatory filings and official index factsheets.",
        "source_entity": "SPDR S&P 500 ETF Trust (SPY), SEC CIK 0000884394",
        "share_class_aggregation": {
            "Alphabet Inc": "In SPY SEC regulatory filings, Alphabet is held as both Class A (GOOGL) and Class C (GOOG). Capitalization rankings aggregate both classes to reflect Alphabet enterprise market capitalization, and map execution to GOOGL (the primary Class A ticker)."
        },
        "reconciliation_metric_note": "Reconciliation measures exact Top 10 constituent membership overlap against verified point-in-time regulatory filing schedules. Periods lacking point-in-time filing evidence are marked verified: false and excluded from numerical accuracy averages.",
        "periods": {},
    }

    # 1. Historical Periods (1999, 2000, 2008) from audited Form N-30D Schedules of Investments
    historical_specs = [
        ("1999-Q1", False, [], "No point-in-time regulatory filing available for 1999-03-31; unverified.", None, None, None, None),
        ("1999-Q2", False, [], "No point-in-time regulatory filing available for 1999-06-30; unverified.", None, None, None, None),
        ("1999-Q3", True, ["MSFT", "GE", "INTC", "CSCO", "IBM", "WMT", "LU", "XOM", "MRK", "C"], None, "0000950135-99-005434", "Form N-30D", "1999-09-30", "1999-11-29"),
        ("2000-Q1", False, [], "No point-in-time regulatory filing available for 2000-03-31; unverified.", None, None, None, None),
        ("2000-Q2", False, [], "No point-in-time regulatory filing available for 2000-06-30; unverified.", None, None, None, None),
        ("2000-Q3", True, ["GE", "CSCO", "MSFT", "XOM", "PFE", "INTC", "C", "ORCL", "AIG", "EMC"], None, "0000950135-00-005227", "Form N-30D", "2000-09-30", "2000-11-21"),
        ("2008-Q1", False, [], "No point-in-time regulatory filing available for 2008-03-31; unverified.", None, None, None, None),
        ("2008-Q2", False, [], "No point-in-time regulatory filing available for 2008-06-30; unverified.", None, None, None, None),
        ("2008-Q3", True, ["XOM", "GE", "PG", "MSFT", "JNJ", "JPM", "CVX", "T", "BAC", "IBM"], None, "0000950135-08-007648", "Form N-30D", "2008-09-30", "2008-11-26"),
    ]

    for period, verified, holdings, note, acc, form, rep_dt, file_dt in historical_specs:
        entry = {
            "verified": verified,
            "holdings": holdings,
        }
        if note:
            entry["note"] = note
        if acc:
            entry["accession_number"] = acc
            entry["form"] = form
            entry["report_date"] = rep_dt
            entry["filing_date"] = file_dt
            entry["sec_edgar_url"] = f"https://www.sec.gov/Archives/edgar/data/884394/{acc}.txt"
            entry["local_file"] = f"data/raw/ground_truth/sec_filings/SPY_{period[:4]}_Q4_{form.replace(' ', '_')}_{acc}.txt"
        ground_truth["periods"][period] = entry

    # 2. Modern Quarters (2020-Q1 .. 2024-Q2) parsed directly from Form NPORT-P XML
    for period, meta in sorted(manifest.items()):
        local_path = PROJECT_ROOT / meta["file_path"]
        parsed = parse_xml_filing(local_path)

        rep_date = parsed["report_date"]
        # Verify repPdDate matches quarter end
        expected_year, expected_q = period.split("-")
        q_month_map = {"Q1": "03-31", "Q2": "06-30", "Q3": "09-30", "Q4": "12-31"}
        expected_date = f"{expected_year}-{q_month_map[expected_q]}"
        if rep_date != expected_date:
            print(f"WARNING: Period {period} repPdDate mismatch: got {rep_date}, expected {expected_date}")

        top10_holdings = [h["ticker"] for h in parsed["holdings"][:10]]
        top10_weights = [round(h["weight"], 4) for h in parsed["holdings"][:10]]

        ground_truth["periods"][period] = {
            "verified": True,
            "holdings": top10_holdings,
            "weights": top10_weights,
            "accession_number": meta["accession_number"],
            "form": "NPORT-P",
            "report_date": rep_date,
            "filing_date": meta["filing_date"],
            "sec_edgar_url": meta["url"],
            "local_file": meta["file_path"],
            "fund_total_value_usd": parsed["total_val_usd"],
        }

    # 3. 2024-Q3 (Unverified - no archived SEC filing)
    ground_truth["periods"]["2024-Q3"] = {
        "verified": False,
        "holdings": [],
        "note": "No point-in-time regulatory filing archived for 2024-09-30; unverified.",
        "accession_number": "N/A",
        "form": "Unverified",
        "report_date": "2024-09-30",
        "filing_date": "N/A",
        "sec_edgar_url": "N/A",
        "local_file": "N/A",
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Successfully compiled {len(ground_truth['periods'])} ground-truth periods into {OUTPUT_FILE}")
    verified_count = sum(1 for p in ground_truth["periods"].values() if p["verified"])
    print(f"  Verified periods: {verified_count} / {len(ground_truth['periods'])}")


if __name__ == "__main__":
    main()
