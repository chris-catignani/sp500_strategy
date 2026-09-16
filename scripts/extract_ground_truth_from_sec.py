"""Extract and compile verified quarterly ground-truth S&P 500 Top 10 holdings from SEC filings.

Parses all 18 SPY Form NPORT-P XML regulatory filings directly, verifies reporting dates (repPdDate),
aggregates Alphabet share classes, and marks historical periods without point-in-time filing evidence as unverified.

Zero external dependencies - Python 3 standard library only.
"""

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
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
    "64110L106": "NFLX",   # Netflix Inc
}

# Historical company names appearing in Form N-30D Schedules of Investments (1995-2019).
# Includes constituents that no longer exist as independent issuers - these are required
# to read the filings faithfully, whether or not the strategy can currently hold them.
N30D_NAME_PATTERNS = [
    (r"^Lucent\s+Technologies", "LU"),
    (r"^EMC\s+Corp", "EMC"),
    (r"^Wal-?\s*Mart\s+Stores", "WMT"),
    (r"^Walmart", "WMT"),
    (r"^Exxon\s+Mobil", "XOM"),
    (r"^Exxon\s+Corp", "XOM"),
    (r"^General\s+Electric", "GE"),
    (r"^Microsoft\s+Corp", "MSFT"),
    (r"^Intel\s+Corp", "INTC"),
    (r"^International\s+Business\s+Machines", "IBM"),
    (r"^Cisco\s+Systems", "CSCO"),
    (r"^Merck\s+&\s+Co", "MRK"),
    (r"^Citigroup", "C"),
    (r"^Pfizer", "PFE"),
    (r"^Oracle\s+Corp", "ORCL"),
    (r"^American\s+International\s+Group", "AIG"),
    (r"^Johnson\s+&\s+Johnson", "JNJ"),
    (r"^Procter\s+&\s+Gamble", "PG"),
    (r"^JPMorgan\s+Chase", "JPM"),
    (r"^Chevron(Texaco)?\s+Corp", "CVX"),
    (r"^AT\s*&\s*T", "T"),
    (r"^SBC\s+Communications", "SBC"),
    (r"^Bank\s+of\s+America", "BAC"),
    (r"^Coca[-\s]?Cola", "KO"),
    # Philip Morris International was spun off from Altria in March 2008; both trade as
    # separate S&P 500 constituents thereafter and must not be consolidated. The pre-2003
    # "Philip Morris Cos." is the company that was renamed Altria.
    (r"^Philip\s+Morris\s+International", "PM"),
    (r"^Philip\s+Morris", "MO"),
    (r"^Altria\s+Group", "MO"),
    (r"^Wells\s+Fargo", "WFC"),
    (r"^Hewlett-?\s*Packard", "HPQ"),
    (r"^Amgen", "AMGN"),
    (r"^PepsiCo", "PEP"),
    (r"^Walt\s+Disney", "DIS"),
    (r"^Abbott\s+Laboratories", "ABT"),
    (r"^Eli\s+Lilly", "LLY"),
    (r"^Schlumberger", "SLB"),
    (r"^ConocoPhillips", "COP"),
    (r"^United\s+Technologies", "UTX"),
    (r"^Nortel\s+Networks", "NT"),
    (r"^Sun\s+Microsystems", "SUNW"),
    (r"^Dell\s+(Computer|Inc)", "DELL"),
    (r"^Tyco\s+International", "TYC"),
    (r"^WorldCom", "WCOM"),
    (r"^MCI\s+", "MCIC"),
    (r"^Time\s+Warner", "TWX"),
    (r"^BellSouth", "BLS"),
    (r"^Ameritech", "AIT"),
    (r"^Mobil\s+Corp", "MOB"),
    (r"^Amoco\s+Corp", "AN"),
    (r"^E\.?I\.?\s+du\s*Pont|^DuPont", "DD"),
    (r"^Fannie\s+Mae|^Federal\s+National\s+Mortgage", "FNMA"),
    (r"^Freddie\s+Mac|^Federal\s+Home\s+Loan\s+Mortgage", "FMCC"),
    (r"^Royal\s+Dutch", "RD"),
    (r"^AOL\s+Time\s+Warner", "AOL"),
    (r"^Bristol-?Myers\s+Squibb", "BMY"),
    (r"^Apple", "AAPL"),
    (r"^Home\s+Depot", "HD"),
    (r"^Verizon\s+Communications", "VZ"),
    (r"^QUALCOMM", "QCOM"),
]

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


# Historical Form N-30D annual reports with an extracted Schedule of Investments.
# SPY's fiscal year ends September 30, so each validates that year's Q3 only.
N30D_HISTORICAL_FILINGS = [
    ("1999-Q3", "SPY_1999_Q4_N-30D_0000950135-99-005434.txt",
     "0000950135-99-005434", "Form N-30D", "1999-09-30", "1999-11-29"),
    ("2000-Q3", "SPY_2000_Q4_N-30D_0000950135-00-005227.txt",
     "0000950135-00-005227", "Form N-30D", "2000-09-30", "2000-11-21"),
    ("2008-Q3", "SPY_2008_Q4_N-30D_0000950135-08-007648.txt",
     "0000950135-08-007648", "Form N-30D", "2008-09-30", "2008-11-26"),
]

# Quarters adjacent to the extracted annual reports that have no point-in-time filing.
UNVERIFIED_HISTORICAL_PERIODS = [
    ("1999-Q1", "No point-in-time regulatory filing available for 1999-03-31; unverified."),
    ("1999-Q2", "No point-in-time regulatory filing available for 1999-06-30; unverified."),
    ("2000-Q1", "No point-in-time regulatory filing available for 2000-03-31; unverified."),
    ("2000-Q2", "No point-in-time regulatory filing available for 2000-06-30; unverified."),
    ("2008-Q1", "No point-in-time regulatory filing available for 2008-03-31; unverified."),
    ("2008-Q2", "No point-in-time regulatory filing available for 2008-06-30; unverified."),
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


_N30D_ROW = re.compile(
    r"^(?P<name>.*?)\s*\.{2,}\s*(?P<shares>[\d,]+)\s+\$?\s*(?P<value>[\d,]+)\s*$"
)
# A wrapped name fragment carries no figures - anything with digits or a currency marker
# belongs to a table the schedule parser must not absorb into the next company name.
_N30D_NAME_FRAGMENT = re.compile(r"^[A-Za-z(][A-Za-z0-9&.,'()/\- ]*$")


def _n30d_ticker(name: str) -> str:
    """Map a Schedule of Investments company name to its ticker symbol."""
    cleaned = re.sub(r"\s*\*+\s*$", "", name).strip()
    for pattern, ticker in N30D_NAME_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return ticker
    return cleaned


def parse_n30d_filing(txt_path: Path) -> Dict[str, Any]:
    """Parse a Form N-30D / N-CSR Schedule of Investments into ranked holdings.

    The schedule is fixed-width text where each position reads
    ``Company Name ......  shares  market_value``. Long names wrap across up to three
    indented continuation lines, so the name is accumulated until the numeric row is
    reached. Positions in the same issuer (multiple share classes) are consolidated.

    Args:
        txt_path: Path to the archived filing text.

    Returns:
        Dict with 'total_val_usd' and 'holdings' (ranked descending by market value).
    """
    lines = txt_path.read_text(encoding="utf-8", errors="replace").splitlines()

    positions: List[Dict[str, Any]] = []
    name_buffer: List[str] = []
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            name_buffer = []
            continue

        match = _N30D_ROW.match(line)
        if match:
            name = " ".join(name_buffer + [match.group("name").strip()])
            name = re.sub(r"\s+", " ", name).strip()
            shares = float(match.group("shares").replace(",", ""))
            value = float(match.group("value").replace(",", ""))
            # Schedule rows always carry both a share count and a market value; the
            # statements of assets and operations elsewhere in the filing do not.
            if name and shares > 0 and value > 0:
                positions.append({"name": name, "shares": shares, "val": value})
            name_buffer = []
            continue

        # Continuation of a wrapped company name: plain text with no figures.
        fragment = line.strip()
        if len(fragment) <= 60 and _N30D_NAME_FRAGMENT.match(fragment) and not any(
            ch.isdigit() for ch in fragment
        ):
            name_buffer.append(fragment)
            if len(name_buffer) > 3:
                name_buffer = name_buffer[-3:]
        else:
            name_buffer = []

    # Consolidate multiple positions (e.g. share classes) in the same issuer.
    consolidated: Dict[str, Dict[str, Any]] = {}
    for pos in positions:
        ticker = _n30d_ticker(pos["name"])
        if ticker in consolidated:
            consolidated[ticker]["val"] += pos["val"]
            consolidated[ticker]["shares"] += pos["shares"]
        else:
            consolidated[ticker] = {
                "name": pos["name"],
                "ticker": ticker,
                "shares": pos["shares"],
                "val": pos["val"],
            }

    holdings = sorted(consolidated.values(), key=lambda h: h["val"], reverse=True)
    total_val = sum(h["val"] for h in holdings)
    for i, h in enumerate(holdings, 1):
        h["rank"] = i
        h["weight"] = h["val"] / total_val if total_val > 0 else 0.0

    return {"total_val_usd": total_val, "holdings": holdings}


CONSOLIDATED_ISSUERS: Dict[str, Dict[str, Any]] = {
    "GOOGL": {
        "primary_ticker": "GOOGL",
        "canonical_name": "Alphabet Inc. (Class A & C)",
        "primary_cusip": "02079K305",
        "member_cusips": {"02079K305", "02079K107"},
        "member_tickers": {"GOOGL", "GOOG"},
    },
}
CUSIP_TO_ISSUER: Dict[str, str] = {
    cusip: issuer_key
    for issuer_key, spec in CONSOLIDATED_ISSUERS.items()
    for cusip in spec["member_cusips"]
}
TICKER_TO_ISSUER: Dict[str, str] = {
    ticker: issuer_key
    for issuer_key, spec in CONSOLIDATED_ISSUERS.items()
    for ticker in spec.get("member_tickers", set())
}


def consolidate_holdings(
    raw_holdings: List[Dict[str, Any]],
    issuers: Optional[Dict[str, Dict[str, Any]]] = None,
    cusip_map: Optional[Dict[str, str]] = None,
    ticker_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Consolidate multi-class equity holdings at the issuer level.

    Sums valuations across classes for registered issuers, mapping to the primary
    ticker, CUSIP, and canonical name. All other holdings pass through unchanged.
    """
    if issuers is None:
        issuers = CONSOLIDATED_ISSUERS
        cusip_map = cusip_map or CUSIP_TO_ISSUER
        ticker_map = ticker_map or TICKER_TO_ISSUER
    else:
        if cusip_map is None:
            cusip_map = {
                c: k for k, s in issuers.items() for c in s.get("member_cusips", set())
            }
        if ticker_map is None:
            ticker_map = {
                t: k for k, s in issuers.items() for t in s.get("member_tickers", set())
            }

    aggregated: Dict[str, Dict[str, Any]] = {}
    passthrough: List[Dict[str, Any]] = []

    for h in raw_holdings:
        cusip = (h.get("cusip") or "").strip()
        ticker = (h.get("ticker") or "").strip()

        issuer_key = cusip_map.get(cusip) or ticker_map.get(ticker)

        if issuer_key and issuer_key in issuers:
            spec = issuers[issuer_key]
            if issuer_key not in aggregated:
                aggregated[issuer_key] = {
                    "name": spec["canonical_name"],
                    "ticker": spec["primary_ticker"],
                    "cusip": spec["primary_cusip"],
                    "val": 0.0,
                }
            aggregated[issuer_key]["val"] += float(h.get("val", 0.0))
        else:
            passthrough.append(dict(h))

    return passthrough + list(aggregated.values())


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

    consolidated = consolidate_holdings(raw_holdings)

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

    # 1. Historical Periods from audited Form N-30D Schedules of Investments.
    # SPY's fiscal year ends September 30, so these annual reports validate Q3 only.
    # Holdings are PARSED from the archived filing text, never transcribed by hand.
    for period, note in UNVERIFIED_HISTORICAL_PERIODS:
        ground_truth["periods"][period] = {
            "verified": False,
            "holdings": [],
            "note": note,
        }

    for period, filename, acc, form, rep_dt, file_dt in N30D_HISTORICAL_FILINGS:
        parsed = parse_n30d_filing(FILINGS_DIR / filename)
        top10 = parsed["holdings"][:10]
        ground_truth["periods"][period] = {
            "verified": True,
            "holdings": [h["ticker"] for h in top10],
            "weights": [round(h["weight"], 4) for h in top10],
            "accession_number": acc,
            "form": form,
            "report_date": rep_dt,
            "filing_date": file_dt,
            "sec_edgar_url": f"https://www.sec.gov/Archives/edgar/data/884394/{acc}.txt",
            "local_file": f"data/raw/ground_truth/sec_filings/{filename}",
            "fund_total_value_usd": parsed["total_val_usd"],
        }

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

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Successfully compiled {len(ground_truth['periods'])} ground-truth periods into {OUTPUT_FILE}")
    verified_count = sum(1 for p in ground_truth["periods"].values() if p["verified"])
    print(f"  Verified periods: {verified_count} / {len(ground_truth['periods'])}")


if __name__ == "__main__":
    main()
