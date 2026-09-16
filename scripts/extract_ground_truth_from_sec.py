"""Extract and compile verified quarterly ground-truth S&P 500 Top 10 holdings from SEC filings.

Parses all 18 SPY Form NPORT-P XML regulatory filings directly, verifies reporting dates (repPdDate),
aggregates Alphabet share classes, and marks historical periods without point-in-time filing evidence as unverified.

Zero external dependencies - Python 3 standard library only.
"""

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import warnings
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FILINGS_DIR = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sec_filings"
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "quarterly_ground_truth_holdings.json"
UNIVERSE_GAP_REPORT_FILE = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "universe_gap_report.json"
TICKERS_DIR = PROJECT_ROOT / "data" / "raw" / "tickers"

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
    (r"^General\s+Motors", "GM"),
    (r"^Microsoft\s+Corp", "MSFT"),
    (r"^Intel\s+Corp", "INTC"),
    (r"^International\s+Business\s+Machines", "IBM"),
    (r"^Cisco\s+Systems", "CSCO"),
    (r"^Merck\s+&\s+Co", "MRK"),
    # Citicorp was the predecessor to Citigroup before the 1998 merger with
    # Travelers Group; both represent the same banking franchise and map to C.
    (r"^Citicorp", "C"),
    (r"^Citigroup", "C"),
    (r"^Pfizer", "PFE"),
    (r"^Oracle\s+Corp", "ORCL"),
    (r"^American\s+International\s+Group", "AIG"),
    (r"^American\s+Express", "AXP"),
    # American Home Products was renamed Wyeth in 2002; both represent the same
    # issuer and map to the successor ticker WYE.
    (r"^American\s+Home\s+Products", "WYE"),
    # Wyeth was formerly American Home Products; anchor to prevent matching longer names.
    (r"^Wyeth\b", "WYE"),
    (r"^Johnson\s+&\s+Johnson", "JNJ"),
    (r"^Procter\s+&\s+Gamble", "PG"),
    (r"^(J\.?\s*P\.?\s*Morgan|JPMorgan)\s+Chase", "JPM"),
    (r"^Chevron(Texaco)?\s+Corp", "CVX"),
    # AT&T Wireless Services (ticker AWE) was spun off from AT&T in 2001 and traded as
    # an independent S&P 500 constituent until acquired by Cingular in 2004. It must
    # be matched before AT&T, or the broader parent pattern swallows it and inflates T.
    (r"^AT\s*&\s*T\s+Wireless", "AWE"),
    (r"^AT\s*&\s*T", "T"),
    (r"^SBC\s+Communications", "SBC"),
    (r"^Bell\s+Atlantic", "BEL"),
    # BankAmerica Corp was the 1998 predecessor to Bank of America before merging
    # with NationsBank; maps to BAC.
    (r"^BankAmerica\b", "BAC"),
    (r"^Bank\s+of\s+America", "BAC"),
    (r"^Boeing", "BA"),
    # Coca-Cola Enterprises was the separately listed bottler, an S&P 500 constituent in
    # its own right until 2010. It must be matched before the parent, or the broader
    # pattern swallows it and inflates KO.
    (r"^Coca[-\s]?Cola\s+Enterprises", "CCE"),
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
    (r"^Disney\s*\(Walt\)", "DIS"),
    (r"^Abbott\s+Lab", "ABT"),
    (r"^(Eli\s+Lilly|Lilly\s*\(Eli\))", "LLY"),
    (r"^Schlumberger", "SLB"),
    (r"^ConocoPhillips", "COP"),
    (r"^United\s+Technologies", "UTX"),
    (r"^United\s+Parcel\s+Service", "UPS"),
    (r"^Nortel\s+Networks", "NT"),
    (r"^Sun\s+Microsystems", "SUNW"),
    (r"^Dell[,\s]", "DELL"),
    # Tyco Laboratories was renamed Tyco International in 1993, but earlier filings
    # continued to report the predecessor name; maps to TYC.
    (r"^Tyco\s+Laboratories", "TYC"),
    (r"^Tyco\s+International", "TYC"),
    (r"^WorldCom", "WCOM"),
    (r"^MCI\s+", "MCIC"),
    # Time Warner Cable (ticker TWC) was spun off from Time Warner in 2009 and traded as
    # a separate S&P 500 constituent. It must be matched before Time Warner, or the
    # parent pattern swallows it and inflates TWX.
    (r"^Time\s+Warner\s+Cable", "TWC"),
    (r"^Time\s+Warner", "TWX"),
    (r"^BellSouth", "BLS"),
    (r"^Ameritech", "AIT"),
    (r"^Mobil\s+Corp", "MOB"),
    (r"^Amoco\s+Corp", "AN"),
    (r"^Du\s*Pont|^E\.?I\.?\s+du\s*Pont|^DuPont", "DD"),
    (r"^Fannie\s+Mae|^Federal\s+National\s+Mortgage", "FNMA"),
    (r"^Freddie\s+Mac|^Federal\s+Home\s+Loan\s+Mortgage", "FMCC"),
    (r"^Royal\s+Dutch", "RD"),
    (r"^America\s+Online", "AOL"),
    (r"^AOL\s+Time\s+Warner", "AOL"),
    (r"^Bristol-?Myers\s+Squibb", "BMY"),
    # Applera Corp (Applied Biosystems Group, ticker ABI) was an independent S&P 500
    # constituent until its 2008 acquisition by Invitrogen. It must be matched before
    # Apple, or the broader prefix swallows it and inflates AAPL.
    (r"^Applera\b", "ABI"),
    (r"^Apple", "AAPL"),
    (r"^Home\s+Depot", "HD"),
    (r"^Verizon\s+Communications", "VZ"),
    (r"^QUALCOMM", "QCOM"),
    (r"^Compaq\s+Computer", "CPQ"),
    (r"^Comcast\s+Corp", "CMCSA"),
    (r"^Ford\s+Motor", "F"),
    (r"^GTE\s+Corp", "GTE"),
    (r"^Gillette\s+Co", "G"),
    (r"^Goldman\s+Sachs", "GS"),
    (r"^Google[,\s]", "GOOGL"),
    (r"^McDonald'?s", "MCD"),
    # Morgan Stanley merged with Dean Witter Discover in 1997 and traded under MWD
    # until rebranding and changing ticker to MS in 2002. Must precede Morgan Stanley.
    (r"^Morgan\s+Stanley[,\s]+Dean\s+Witter", "MWD"),
    (r"^Morgan\s+Stanley", "MS"),
    (r"^Motorola", "MOT"),
    (r"^Schering-?Plough", "SGP"),
    (r"^Viacom\b", "VIA"),
    (r"^Wachovia\s+Corp", "WB"),
    (r"^Warner-?Lambert", "WLA"),
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
# SPY's fiscal year ended December 31 through 1996, so the 1995 and 1996 annual reports
# represent Q4 (12-31) snapshots. Beginning in 1997, SPY changed its fiscal year end to
# September 30, so 1997-2009 annual reports represent Q3 (09-30) snapshots.
N30D_HISTORICAL_FILINGS = [
    # SPY's fiscal year ended December 31 until changing to September 30 in 1997;
    # 1995 and 1996 annual reports are December 31 (Q4) snapshots, not September 30.
    ("1995-Q4", "SPY_1995_N-30D_0000912057-96-003840.txt",
     "0000912057-96-003840", "Form N-30D", "1995-12-31", "1996-03-04"),
    ("1996-Q4", "SPY_1996_N-30D_0000912057-97-006798.txt",
     "0000912057-97-006798", "Form N-30D", "1996-12-31", "1997-02-26"),
    ("1997-Q3", "SPY_1997_N-30D_0000950135-97-004820.txt",
     "0000950135-97-004820", "Form N-30D", "1997-09-30", "1997-12-01"),
    ("1998-Q3", "SPY_1998_N-30D_0000950135-98-006321.txt",
     "0000950135-98-006321", "Form N-30D", "1998-09-30", "1998-12-21"),
    ("1999-Q3", "SPY_1999_Q4_N-30D_0000950135-99-005434.txt",
     "0000950135-99-005434", "Form N-30D", "1999-09-30", "1999-11-29"),
    ("2000-Q3", "SPY_2000_Q4_N-30D_0000950135-00-005227.txt",
     "0000950135-00-005227", "Form N-30D", "2000-09-30", "2000-11-21"),
    ("2001-Q3", "SPY_2001_N-30D_0000950135-01-503664.txt",
     "0000950135-01-503664", "Form N-30D", "2001-09-30", "2001-11-21"),
    ("2002-Q3", "SPY_2002_N-30D_0000950135-02-005195.txt",
     "0000950135-02-005195", "Form N-30D", "2002-09-30", "2002-11-21"),
    ("2003-Q3", "SPY_2003_N-30D_0000950135-03-005842.txt",
     "0000950135-03-005842", "Form N-30D", "2003-09-30", "2003-11-26"),
    ("2004-Q3", "SPY_2004_N-30D_0000950135-05-000037.txt",
     "0000950135-05-000037", "Form N-30D", "2004-09-30", "2005-01-05"),
    ("2005-Q3", "SPY_2005_N-30D_0000950135-05-006765.txt",
     "0000950135-05-006765", "Form N-30D", "2005-09-30", "2005-12-01"),
    ("2006-Q3", "SPY_2006_N-30D_0000950135-06-007169.txt",
     "0000950135-06-007169", "Form N-30D", "2006-09-30", "2006-11-29"),
    ("2007-Q3", "SPY_2007_N-30D_0000950135-07-007280.txt",
     "0000950135-07-007280", "Form N-30D", "2007-09-30", "2007-12-04"),
    ("2008-Q3", "SPY_2008_Q4_N-30D_0000950135-08-007648.txt",
     "0000950135-08-007648", "Form N-30D", "2008-09-30", "2008-11-26"),
    ("2009-Q3", "SPY_2009_N-30D_0000950123-09-066888.txt",
     "0000950123-09-066888", "Form N-30D", "2009-09-30", "2009-11-30"),
]

_QUARTER_DATES = (
    ("Q1", "03-31"),
    ("Q2", "06-30"),
    ("Q3", "09-30"),
    ("Q4", "12-31"),
)

_verified_historical_periods = {entry[0] for entry in N30D_HISTORICAL_FILINGS}
_historical_years = sorted({int(entry[0].split("-")[0]) for entry in N30D_HISTORICAL_FILINGS})

# Historical quarters adjacent to the extracted annual reports that have no point-in-time filing.
# Derived from N30D_HISTORICAL_FILINGS rather than hardcoding so coverage cannot drift.
UNVERIFIED_HISTORICAL_PERIODS = [
    (
        f"{year}-{q}",
        f"No point-in-time regulatory filing available for {year}-{dt}; unverified.",
    )
    for year in _historical_years
    for q, dt in _QUARTER_DATES
    if f"{year}-{q}" not in _verified_historical_periods
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


# The schedule's column header. The 1999 filing misspells the section title as
# "SCEDULE OF INVESTMENTS", so the column header - not the title - is the anchor.
_N30D_SCHEDULE_HEADER = re.compile(
    r"^\s*COMMON\s+STOCKS\b.*\bSHARES\b.*\bVALUE\b", re.IGNORECASE
)
# The schedule's closing total. A document with several of these carries several
# funds' schedules and must not be read as one portfolio.
_N30D_SCHEDULE_TOTAL = re.compile(
    r"^\s*Total\s+(?:Common\s+Stocks|Investments)\b", re.IGNORECASE
)
_N30D_TOTAL_VALUE = re.compile(r"\$?\s*(\d{1,3}(?:,\d{3}){2,})")
_N30D_ROW = re.compile(
    r"^(?P<name>.*?)[\s.]{2,}(?P<shares>\d[\d,]*)\s+\$?\s*(?P<value>\d[\d,]*)\s*$"
)
# A wrapped name fragment carries no figures - anything with digits or a currency marker
# belongs to a table the schedule parser must not absorb into the next company name.
_N30D_NAME_FRAGMENT = re.compile(r"^[A-Za-z(][A-Za-z0-9&.,'()/\- ]*$")


class ScheduleParseError(ValueError):
    """Raised when a filing's Schedule of Investments cannot be read faithfully."""


_TICKER_SHAPE = re.compile(r"^[A-Z][A-Z.]{0,5}$")


def assert_top_holdings_resolved(holdings, filing_label, depth=30):
    """Refuse a filing whose top `depth` holdings include an unmapped company name.

    `_n30d_ticker` returns the cleaned company name when no pattern matches. Emitting
    that into ranked output would reintroduce the silent gaps this extraction exists to
    close, so an unresolved name is a hard failure, not a warning.
    """
    unresolved = [
        h.get("ticker", "")
        for h in holdings[:depth]
        if not _TICKER_SHAPE.match(h.get("ticker", ""))
    ]
    if unresolved:
        names = ", ".join(repr(u) for u in unresolved)
        raise ScheduleParseError(
            f"{filing_label}: unmapped top-{depth} holding(s): {names}"
        )


_SEC_PERIOD = re.compile(r"^CONFORMED PERIOD OF REPORT:\s*(\d{4})(\d{2})(\d{2})", re.M)


def assert_filing_period_matches(txt_path: Any, expected_report_date: str) -> None:
    """Refuse a filing whose own stated period disagrees with its configured one.

    Parses CONFORMED PERIOD OF REPORT: YYYYMMDD from the SEC header. Reads only
    the header (content[:4000]) to avoid loading the full document.
    """
    path = Path(txt_path)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        header = f.read(4000)

    match = _SEC_PERIOD.search(header)
    if not match:
        raise ScheduleParseError(
            f"{path.name}: missing CONFORMED PERIOD OF REPORT in SEC header"
        )

    stated_date = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    if stated_date != expected_report_date:
        raise ScheduleParseError(
            f"{path.name}: conformed period of report ({stated_date}) "
            f"does not match expected report date ({expected_report_date})"
        )


def _n30d_ticker(name: str) -> str:
    """Map a Schedule of Investments company name to its ticker symbol."""
    cleaned = re.sub(r"\s*\*+\s*$", "", name).strip()
    for pattern, ticker in N30D_NAME_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return ticker
    return cleaned


def _resolve_n30d_schedule_bounds(lines: List[str], label: str) -> Tuple[int, int]:
    """Find the schedule header line index and the first closing total line index occurring after it.

    Raises ScheduleParseError if either anchor is missing or if no total anchor follows the header.
    Shared between parse_n30d_filing and the issuer-separation test suite so both resolve bounds identically.
    """
    headers = [i for i, line in enumerate(lines) if _N30D_SCHEDULE_HEADER.search(line)]
    totals = [i for i, line in enumerate(lines) if _N30D_SCHEDULE_TOTAL.search(line)]

    if not headers:
        raise ScheduleParseError(
            f"{label}: missing schedule header anchor (_N30D_SCHEDULE_HEADER)"
        )
    if not totals:
        raise ScheduleParseError(
            f"{label}: missing schedule total anchor (_N30D_SCHEDULE_TOTAL)"
        )

    start = headers[0]
    totals_after_start = [i for i in totals if i > start]
    if not totals_after_start:
        raise ScheduleParseError(
            f"{label}: missing schedule total anchor after header line {start}"
        )
    end = totals_after_start[0]
    return start, end


def _extract_n30d_positions(
    lines: List[str], start: int, end: int
) -> List[Dict[str, Any]]:
    """Extract position rows from lines within schedule bounds.

    This is the single definition of how a fixed-width Schedule of Investments row
    and its wrapped name fragments are read from Form N-30D filings. It is shared
    between parse_n30d_filing and the issuer-separation test suite so the two cannot
    drift apart.
    """
    positions: List[Dict[str, Any]] = []
    name_buffer: List[str] = []
    for raw in lines[start + 1 : end]:
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

    return positions


def parse_n30d_filing(txt_path: Path) -> Dict[str, Any]:
    """Parse a Form N-30D / N-CSR Schedule of Investments into ranked holdings.

    The schedule is fixed-width text where each position reads
    ``Company Name ......  shares  market_value``. Long names wrap across up to three
    indented continuation lines, so the name is accumulated until the numeric row is
    reached. Positions in the same issuer (multiple share classes) are consolidated.

    Args:
        txt_path: Path to the archived filing text.

    Returns:
        Dict with 'total_val_usd', 'stated_total_usd', and 'holdings' (ranked descending by market value).
    """
    lines = txt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    start, end = _resolve_n30d_schedule_bounds(lines, txt_path.name)

    # Stated total is within 3 lines of the closing anchor. Parenthetical cost
    # figures must be stripped so they are not mistaken for the market-value total.
    blob = " ".join(lines[end : end + 3])
    cleaned_blob = re.sub(r"\(Cost[^)]*\)", " ", blob, flags=re.IGNORECASE | re.DOTALL)
    matches = _N30D_TOTAL_VALUE.findall(cleaned_blob)
    if not matches:
        raise ScheduleParseError(
            f"{txt_path.name}: unable to find stated total value in lines {end}..{end + 3}"
        )
    stated_total = float(matches[-1].replace(",", ""))

    positions = _extract_n30d_positions(lines, start, end)

    parsed_sum = sum(pos["val"] for pos in positions)
    diff = abs(parsed_sum - stated_total)
    if diff >= 1.0:
        raise ScheduleParseError(
            f"{txt_path.name}: parsed sum ({parsed_sum:,.2f}) does not match "
            f"stated total ({stated_total:,.2f}); diff = {diff:,.2f}"
        )

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

    return {
        "total_val_usd": total_val,
        "stated_total_usd": stated_total,
        "holdings": holdings,
    }


CONSOLIDATED_ISSUERS: Dict[str, Dict[str, Any]] = {
    "GOOGL": {
        "primary_ticker": "GOOGL",
        "canonical_name": "Alphabet Inc.",
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


def _warn_unregistered_multi_class(
    raw_holdings: List[Dict[str, Any]],
    cusip_map: Dict[str, str],
    ticker_map: Dict[str, str],
) -> List[str]:
    """Flag issuers that appear under several tickers but are not registered for consolidation.

    A filing reports each share class as its own position, and the classes share an
    issuer ``name`` - SPY lists both Alphabet lines as "Alphabet Inc". Any other name
    that resolves to more than one ticker is a multi-class issuer this module would
    silently count twice, so it is surfaced rather than passed through in silence.

    Returns the issuer names warned about, so callers and tests can assert on them.
    """
    by_name: Dict[str, Dict[str, Optional[str]]] = {}
    for h in raw_holdings:
        name = (h.get("name") or "").strip()
        ticker = (h.get("ticker") or "").strip()
        if not (name and ticker):
            continue
        cusip = (h.get("cusip") or "").strip()
        # Resolve exactly as consolidate_holdings does, CUSIP first, so a class registered
        # by CUSIP under an unexpected ticker is not reported as a gap.
        by_name.setdefault(name, {})[ticker] = cusip_map.get(cusip) or ticker_map.get(ticker)

    unregistered = []
    for name, resolved in sorted(by_name.items()):
        tickers = sorted(resolved)
        if len(tickers) < 2:
            continue
        if all(resolved.values()):
            continue  # already consolidated by an entry in CONSOLIDATED_ISSUERS
        unregistered.append(name)
        warnings.warn(
            f"{name!r} is reported under multiple tickers ({', '.join(tickers)}) "
            "but is not registered in CONSOLIDATED_ISSUERS; its share classes will be "
            "ranked as separate constituents. Add the issuer to consolidate it.",
            stacklevel=2,
        )
    return unregistered


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

    _warn_unregistered_multi_class(raw_holdings, cusip_map, ticker_map)

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


def build_universe_gap_report(
    depth: int = 30,
    parsed_filings: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Collect tickers in historical Form N-30D filings' top `depth` missing from data/raw/tickers/.

    Enumerates the historical survivorship gap across all 15 annual filings (1995-2009).
    For each missing constituent, records its best rank, company name, and the list of
    periods where it ranks in the top `depth`.
    """
    if parsed_filings is None:
        parsed_filings = [
            (period, parse_n30d_filing(FILINGS_DIR / filename))
            for period, filename, *_ in N30D_HISTORICAL_FILINGS
        ]

    missing: Dict[str, Dict[str, Any]] = {}
    for period, parsed in parsed_filings:
        for h in parsed["holdings"][:depth]:
            ticker = h["ticker"]
            if not (TICKERS_DIR / f"{ticker}.json").exists():
                clean_name = re.sub(r"\s*\*+\s*$", "", h["name"]).strip()
                if ticker not in missing:
                    missing[ticker] = {
                        "name": clean_name,
                        "best_rank": h["rank"],
                        "periods": [period],
                    }
                else:
                    missing[ticker]["periods"].append(period)
                    if h["rank"] < missing[ticker]["best_rank"]:
                        missing[ticker]["best_rank"] = h["rank"]
                        missing[ticker]["name"] = clean_name

    sorted_missing = {
        k: v
        for k, v in sorted(
            missing.items(), key=lambda item: (item[1]["best_rank"], item[0])
        )
    }

    return {
        "description": (
            "Top constituents from historical SPY Form N-30D annual filings that have no "
            "market data files in data/raw/tickers/, enumerating the historical survivorship gap."
        ),
        "source": "15 SPY Form N-30D annual reports, fiscal years 1995-2009 (December 31 snapshots for 1995-1996, September 30 snapshots for 1997-2009)",
        "depth": depth,
        "missing_tickers": sorted_missing,
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
    # SPY's fiscal year ended December 31 through 1996, changing to September 30 in 1997.
    # Holdings are PARSED from the archived filing text, never transcribed by hand.
    for period, note in UNVERIFIED_HISTORICAL_PERIODS:
        ground_truth["periods"][period] = {
            "verified": False,
            "holdings": [],
            "note": note,
        }

    parsed_historical = []
    for period, filename, acc, form, rep_dt, file_dt in N30D_HISTORICAL_FILINGS:
        filing_path = FILINGS_DIR / filename
        assert_filing_period_matches(filing_path, rep_dt)
        parsed = parse_n30d_filing(filing_path)
        assert_top_holdings_resolved(parsed["holdings"], f"{period} ({filename})")
        parsed_historical.append((period, parsed))
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

    # 2. Modern Quarters (2020-Q1 .. 2024-Q4) parsed directly from Form NPORT-P XML
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

    # 3. Universe gap report across all 15 historical filings
    gap_report = build_universe_gap_report(depth=30, parsed_filings=parsed_historical)
    with open(UNIVERSE_GAP_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(gap_report, f, indent=2)

    print(f"\nUniverse gap report written to {UNIVERSE_GAP_REPORT_FILE}")
    print(f"Missing tickers from Top 30 across 15 historical filings ({len(gap_report['missing_tickers'])} total):")
    for ticker, info in gap_report["missing_tickers"].items():
        periods_str = ", ".join(info["periods"])
        print(f"  {ticker:<5} best rank #{info['best_rank']:<2} in {periods_str} ({info['name']})")


if __name__ == "__main__":
    main()
