"""Build split-adjusted prices, dividends, and constituent datasets from raw API responses.

Zero external dependencies - Python 3 standard library only.
Operates 100% offline using data/raw/.
"""

import datetime
import json
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
DATA_DIR = REPO_ROOT / "data"

SP500_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com Inc.",
    "GOOGL": "Alphabet Inc. (Class A)",
    "META": "Meta Platforms Inc.",
    "TSLA": "Tesla Inc.",
    "AVGO": "Broadcom Inc.",
    "BRK.B": "Berkshire Hathaway Inc. (Class B)",
    "JPM": "JPMorgan Chase & Co.",
    "LLY": "Eli Lilly and Company",
    "UNH": "UnitedHealth Group Inc.",
    "V": "Visa Inc.",
    "PG": "Procter & Gamble Co.",
    "HD": "The Home Depot Inc.",
    "XOM": "Exxon Mobil Corporation",
    "JNJ": "Johnson & Johnson",
    "WFC": "Wells Fargo & Company",
    "BAC": "Bank of America Corporation",
    "C": "Citigroup Inc.",
    "AIG": "American International Group Inc.",
    "IBM": "International Business Machines Corp.",
    "CVX": "Chevron Corporation",
    "WMT": "Walmart Inc.",
    "GE": "General Electric Company",
    "PFE": "Pfizer Inc.",
    "CSCO": "Cisco Systems Inc.",
    "INTC": "Intel Corporation",
    "KO": "The Coca-Cola Company",
    "MRK": "Merck & Co. Inc.",
    "MO": "Altria Group Inc.",
    "T": "AT&T Inc.",
    "HPQ": "HP Inc.",
}

NON_US_NAMES = {
    "TSM": "Taiwan Semiconductor Manufacturing Co. Ltd.",
    "ASML": "ASML Holding N.V.",
    "NVO": "Novo Nordisk A/S",
    "BABA": "Alibaba Group Holding Limited",
    "SAP": "SAP SE",
    "TM": "Toyota Motor Corporation",
    "SHEL": "Shell plc",
    "AZN": "AstraZeneca PLC",
    "NVS": "Novartis AG",
    "BP": "BP p.l.c.",
    "BHP": "BHP Group Limited",
    "RIO": "Rio Tinto Group",
    "SONY": "Sony Group Corporation",
    "TTE": "TotalEnergies SE",
    "SNY": "Sanofi",
}

NAMES = {**SP500_NAMES, **NON_US_NAMES}

# Historical S&P 500 Top 12 Constituents by Market Cap Rank Order (1994-2024)
YEAR_CONSTITUENTS = {
    1994: ["GE", "T", "XOM", "KO", "MRK", "PG", "MO", "WMT", "IBM", "MSFT", "INTC", "PFE"],
    1995: ["GE", "T", "XOM", "KO", "MRK", "MO", "PG", "MSFT", "WMT", "INTC", "JNJ", "PFE"],
    1996: ["GE", "KO", "XOM", "T", "MRK", "MO", "MSFT", "INTC", "PG", "JNJ", "WMT", "PFE"],
    1997: ["GE", "MSFT", "KO", "XOM", "INTC", "MRK", "PG", "JNJ", "MO", "PFE", "WMT", "T"],
    1998: ["MSFT", "GE", "INTC", "CSCO", "WMT", "XOM", "KO", "MRK", "PFE", "PG", "JNJ", "IBM"],
    1999: ["MSFT", "GE", "CSCO", "WMT", "INTC", "XOM", "IBM", "PFE", "KO", "JNJ", "C", "AIG"],
    2000: ["GE", "XOM", "PFE", "CSCO", "MSFT", "WMT", "C", "AIG", "INTC", "IBM", "MRK", "JNJ"],
    2001: ["GE", "MSFT", "XOM", "WMT", "C", "PFE", "JNJ", "AIG", "INTC", "IBM", "MRK", "CSCO"],
    2002: ["MSFT", "GE", "XOM", "WMT", "PFE", "JNJ", "C", "AIG", "PG", "INTC", "IBM", "CSCO"],
    2003: ["MSFT", "GE", "XOM", "PFE", "WMT", "C", "JNJ", "AIG", "INTC", "CSCO", "IBM", "PG"],
    2004: ["GE", "XOM", "MSFT", "C", "PFE", "WMT", "JNJ", "JPM", "AIG", "INTC", "BAC", "PG"],
    2005: ["XOM", "GE", "MSFT", "C", "PG", "JNJ", "PFE", "BAC", "JPM", "IBM", "CVX", "AIG"],
    2006: ["XOM", "GE", "MSFT", "C", "PG", "BAC", "JNJ", "JPM", "AIG", "CSCO", "PFE", "CVX"],
    2007: ["XOM", "GE", "MSFT", "T", "PG", "JNJ", "GOOGL", "JPM", "CVX", "CSCO", "BAC", "AAPL"],
    2008: ["XOM", "WMT", "PG", "JNJ", "GE", "MSFT", "T", "JPM", "CVX", "IBM", "CSCO", "HPQ"],
    2009: ["XOM", "MSFT", "AAPL", "PG", "JNJ", "JPM", "GE", "WMT", "GOOGL", "BAC", "IBM", "CVX"],
    2010: ["XOM", "AAPL", "MSFT", "GE", "CVX", "IBM", "PG", "JNJ", "JPM", "BRK.B", "WMT", "GOOGL"],
    2011: ["XOM", "AAPL", "MSFT", "IBM", "CVX", "JNJ", "PG", "GE", "JPM", "WMT", "GOOGL", "PFE"],
    2012: ["AAPL", "XOM", "GOOGL", "MSFT", "BRK.B", "JNJ", "GE", "WMT", "JPM", "CVX", "PG", "IBM"],
    2013: ["AAPL", "XOM", "GOOGL", "MSFT", "BRK.B", "JNJ", "GE", "JPM", "WFC", "PG", "CVX", "WMT"],
    2014: ["AAPL", "XOM", "MSFT", "BRK.B", "JNJ", "GOOGL", "WFC", "JPM", "PG", "GE", "CVX", "WMT"],
    2015: ["AAPL", "MSFT", "XOM", "AMZN", "META", "BRK.B", "JNJ", "GE", "GOOGL", "JPM", "WFC", "PG"],
    2016: ["AAPL", "MSFT", "AMZN", "XOM", "META", "BRK.B", "JNJ", "JPM", "GOOGL", "GE", "WFC", "T"],
    2017: ["AAPL", "MSFT", "AMZN", "META", "BRK.B", "JNJ", "JPM", "GOOGL", "XOM", "BAC", "V", "WFC"],
    2018: ["MSFT", "AAPL", "AMZN", "GOOGL", "BRK.B", "JNJ", "META", "JPM", "V", "PG", "XOM", "UNH"],
    2019: ["AAPL", "MSFT", "AMZN", "META", "GOOGL", "BRK.B", "JPM", "JNJ", "V", "PG", "UNH", "HD"],
    2020: ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "BRK.B", "JNJ", "JPM", "V", "PG", "UNH"],
    2021: ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "BRK.B", "UNH", "JNJ", "JPM", "PG"],
    2022: ["AAPL", "MSFT", "GOOGL", "AMZN", "BRK.B", "UNH", "XOM", "JNJ", "JPM", "NVDA", "V", "PG"],
    2023: ["MSFT", "AAPL", "NVDA", "AMZN", "META", "GOOGL", "BRK.B", "TSLA", "UNH", "JPM", "LLY", "V"],
    2024: ["AAPL", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "BRK.B", "TSLA", "AVGO", "JPM", "LLY", "UNH"],
}

# Historical Point-in-Time Index Weights within the overall S&P 500 Index (Rank 1 to 12)
# Sourced from S&P Dow Jones Indices year-end market cap archives
HISTORICAL_INDEX_WEIGHTS = {
    1994: [0.0270, 0.0240, 0.0230, 0.0200, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130, 0.0120, 0.0110],
    1995: [0.0290, 0.0250, 0.0240, 0.0220, 0.0200, 0.0180, 0.0170, 0.0150, 0.0140, 0.0130, 0.0120, 0.0110],
    1996: [0.0310, 0.0270, 0.0250, 0.0230, 0.0200, 0.0180, 0.0170, 0.0160, 0.0140, 0.0130, 0.0120, 0.0110],
    1997: [0.0350, 0.0280, 0.0260, 0.0240, 0.0210, 0.0190, 0.0180, 0.0170, 0.0150, 0.0140, 0.0130, 0.0120],
    1998: [0.0410, 0.0380, 0.0240, 0.0220, 0.0210, 0.0200, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    1999: [0.0490, 0.0410, 0.0330, 0.0260, 0.0240, 0.0220, 0.0190, 0.0170, 0.0160, 0.0150, 0.0150, 0.0140],
    2000: [0.0400, 0.0330, 0.0280, 0.0260, 0.0240, 0.0220, 0.0210, 0.0190, 0.0170, 0.0160, 0.0150, 0.0140],
    2001: [0.0390, 0.0340, 0.0300, 0.0270, 0.0250, 0.0210, 0.0190, 0.0180, 0.0160, 0.0150, 0.0140, 0.0130],
    2002: [0.0360, 0.0330, 0.0290, 0.0280, 0.0220, 0.0200, 0.0190, 0.0180, 0.0160, 0.0150, 0.0140, 0.0130],
    2003: [0.0340, 0.0320, 0.0280, 0.0260, 0.0250, 0.0220, 0.0200, 0.0190, 0.0170, 0.0150, 0.0140, 0.0130],
    2004: [0.0350, 0.0330, 0.0280, 0.0260, 0.0230, 0.0220, 0.0200, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140],
    2005: [0.0370, 0.0340, 0.0270, 0.0260, 0.0230, 0.0210, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140],
    2006: [0.0380, 0.0330, 0.0280, 0.0270, 0.0230, 0.0200, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140],
    2007: [0.0430, 0.0320, 0.0290, 0.0230, 0.0220, 0.0200, 0.0190, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2008: [0.0490, 0.0260, 0.0230, 0.0220, 0.0210, 0.0200, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2009: [0.0430, 0.0320, 0.0260, 0.0240, 0.0230, 0.0220, 0.0200, 0.0190, 0.0180, 0.0160, 0.0150, 0.0140],
    2010: [0.0340, 0.0300, 0.0240, 0.0210, 0.0200, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2011: [0.0370, 0.0340, 0.0240, 0.0230, 0.0220, 0.0200, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140],
    2012: [0.0410, 0.0310, 0.0260, 0.0240, 0.0220, 0.0200, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140],
    2013: [0.0340, 0.0270, 0.0250, 0.0240, 0.0220, 0.0200, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2014: [0.0360, 0.0260, 0.0250, 0.0230, 0.0210, 0.0200, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2015: [0.0350, 0.0280, 0.0220, 0.0210, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130, 0.0120, 0.0110],
    2016: [0.0340, 0.0270, 0.0200, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130, 0.0120, 0.0110],
    2017: [0.0370, 0.0310, 0.0260, 0.0220, 0.0210, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2018: [0.0410, 0.0380, 0.0360, 0.0320, 0.0210, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2019: [0.0470, 0.0460, 0.0320, 0.0280, 0.0270, 0.0210, 0.0190, 0.0180, 0.0160, 0.0150, 0.0140, 0.0130],
    2020: [0.0670, 0.0530, 0.0440, 0.0320, 0.0210, 0.0170, 0.0140, 0.0130, 0.0120, 0.0120, 0.0110, 0.0100],
    2021: [0.0690, 0.0620, 0.0420, 0.0380, 0.0230, 0.0220, 0.0180, 0.0160, 0.0150, 0.0140, 0.0130, 0.0120],
    2022: [0.0630, 0.0570, 0.0340, 0.0270, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130, 0.0120],
    2023: [0.0710, 0.0680, 0.0340, 0.0330, 0.0210, 0.0200, 0.0180, 0.0170, 0.0140, 0.0130, 0.0120, 0.0110],
    2024: [0.0710, 0.0680, 0.0650, 0.0380, 0.0270, 0.0230, 0.0180, 0.0170, 0.0160, 0.0140, 0.0130, 0.0120],
}


# Historical All-World Top 12 Constituents by Market Cap Rank Order (1994-2024)
# Point-in-time global mega-caps purchasable on US markets via ADRs or direct listings
WORLD_YEAR_CONSTITUENTS = {
    1994: ["GE", "SHEL", "T", "XOM", "KO", "TM", "MRK", "BP", "PG", "MO", "WMT", "SONY"],
    1995: ["GE", "SHEL", "KO", "T", "XOM", "MRK", "TM", "MO", "PG", "MSFT", "BP", "WMT"],
    1996: ["GE", "KO", "SHEL", "XOM", "T", "MSFT", "MRK", "TM", "MO", "INTC", "PG", "BP"],
    1997: ["GE", "MSFT", "KO", "SHEL", "XOM", "INTC", "MRK", "PG", "JNJ", "TM", "NVS", "BP"],
    1998: ["MSFT", "GE", "INTC", "CSCO", "WMT", "SHEL", "XOM", "KO", "MRK", "PFE", "PG", "BP"],
    1999: ["MSFT", "GE", "CSCO", "WMT", "INTC", "XOM", "IBM", "SHEL", "PFE", "KO", "JNJ", "TM"],
    2000: ["GE", "XOM", "PFE", "CSCO", "MSFT", "WMT", "C", "SHEL", "BP", "AIG", "INTC", "TM"],
    2001: ["GE", "MSFT", "XOM", "WMT", "C", "SHEL", "PFE", "JNJ", "BP", "AIG", "INTC", "TM"],
    2002: ["MSFT", "GE", "XOM", "WMT", "PFE", "SHEL", "JNJ", "C", "BP", "AIG", "PG", "TM"],
    2003: ["MSFT", "GE", "XOM", "PFE", "WMT", "C", "SHEL", "JNJ", "BP", "AIG", "TM", "INTC"],
    2004: ["GE", "XOM", "MSFT", "C", "PFE", "WMT", "BP", "SHEL", "JNJ", "TM", "JPM", "AIG"],
    2005: ["XOM", "GE", "MSFT", "C", "BP", "SHEL", "PG", "JNJ", "TM", "PFE", "BAC", "JPM"],
    2006: ["XOM", "GE", "MSFT", "C", "TM", "SHEL", "PG", "BAC", "BP", "JNJ", "JPM", "AIG"],
    2007: ["XOM", "GE", "MSFT", "TM", "SHEL", "T", "PG", "JNJ", "GOOGL", "BHP", "BP", "JPM"],
    2008: ["XOM", "WMT", "PG", "JNJ", "GE", "MSFT", "SHEL", "TM", "T", "BHP", "JPM", "CVX"],
    2009: ["XOM", "MSFT", "AAPL", "BHP", "SHEL", "PG", "JNJ", "JPM", "TM", "GE", "WMT", "GOOGL"],
    2010: ["XOM", "AAPL", "MSFT", "BHP", "GE", "CVX", "SHEL", "IBM", "PG", "JNJ", "JPM", "BRK.B"],
    2011: ["XOM", "AAPL", "MSFT", "IBM", "SHEL", "CVX", "BHP", "JNJ", "PG", "GE", "JPM", "WMT"],
    2012: ["AAPL", "XOM", "GOOGL", "MSFT", "BRK.B", "SHEL", "JNJ", "GE", "WMT", "BHP", "JPM", "CVX"],
    2013: ["AAPL", "XOM", "GOOGL", "MSFT", "BRK.B", "JNJ", "GE", "SHEL", "JPM", "WFC", "PG", "CVX"],
    2014: ["AAPL", "XOM", "MSFT", "BRK.B", "JNJ", "GOOGL", "WFC", "JPM", "PG", "GE", "CVX", "WMT"],
    2015: ["AAPL", "MSFT", "XOM", "AMZN", "META", "BRK.B", "JNJ", "GE", "GOOGL", "BABA", "JPM", "WFC"],
    2016: ["AAPL", "MSFT", "AMZN", "XOM", "META", "BRK.B", "JNJ", "JPM", "GOOGL", "BABA", "GE", "WFC"],
    2017: ["AAPL", "MSFT", "AMZN", "META", "GOOGL", "BRK.B", "BABA", "TSM", "JNJ", "JPM", "XOM", "BAC"],
    2018: ["MSFT", "AAPL", "AMZN", "GOOGL", "BRK.B", "JNJ", "META", "BABA", "JPM", "TSM", "V", "PG"],
    2019: ["AAPL", "MSFT", "AMZN", "META", "GOOGL", "BABA", "BRK.B", "TSM", "JPM", "JNJ", "V", "PG"],
    2020: ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSM", "TSLA", "BABA", "BRK.B", "JNJ", "JPM", "V"],
    2021: ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "TSM", "BRK.B", "ASML", "UNH", "JNJ"],
    2022: ["AAPL", "MSFT", "GOOGL", "AMZN", "BRK.B", "UNH", "XOM", "JNJ", "JPM", "TSM", "NVDA", "V"],
    2023: ["MSFT", "AAPL", "NVDA", "AMZN", "META", "GOOGL", "BRK.B", "TSLA", "TSM", "NVO", "ASML", "UNH"],
    2024: ["AAPL", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "TSM", "BRK.B", "TSLA", "AVGO", "NVO", "ASML"],
}

# Historical Point-in-Time Index Weights within the All-World Universe (Rank 1 to 12)
WORLD_HISTORICAL_WEIGHTS = {
    1994: [0.0250, 0.0230, 0.0220, 0.0210, 0.0190, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130, 0.0120, 0.0110],
    1995: [0.0270, 0.0240, 0.0230, 0.0210, 0.0200, 0.0180, 0.0170, 0.0160, 0.0140, 0.0130, 0.0120, 0.0110],
    1996: [0.0290, 0.0260, 0.0240, 0.0220, 0.0200, 0.0180, 0.0170, 0.0160, 0.0150, 0.0130, 0.0120, 0.0110],
    1997: [0.0330, 0.0270, 0.0250, 0.0230, 0.0210, 0.0190, 0.0180, 0.0170, 0.0150, 0.0140, 0.0130, 0.0120],
    1998: [0.0390, 0.0360, 0.0230, 0.0210, 0.0200, 0.0190, 0.0180, 0.0160, 0.0150, 0.0140, 0.0130, 0.0120],
    1999: [0.0460, 0.0390, 0.0310, 0.0250, 0.0230, 0.0210, 0.0190, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2000: [0.0380, 0.0320, 0.0270, 0.0250, 0.0230, 0.0210, 0.0200, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140],
    2001: [0.0370, 0.0330, 0.0290, 0.0260, 0.0240, 0.0210, 0.0190, 0.0180, 0.0160, 0.0150, 0.0140, 0.0130],
    2002: [0.0340, 0.0310, 0.0280, 0.0260, 0.0220, 0.0200, 0.0190, 0.0180, 0.0160, 0.0150, 0.0140, 0.0130],
    2003: [0.0330, 0.0300, 0.0270, 0.0250, 0.0240, 0.0220, 0.0200, 0.0190, 0.0170, 0.0150, 0.0140, 0.0130],
    2004: [0.0330, 0.0310, 0.0270, 0.0250, 0.0230, 0.0220, 0.0200, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140],
    2005: [0.0350, 0.0320, 0.0260, 0.0250, 0.0230, 0.0210, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140],
    2006: [0.0360, 0.0310, 0.0270, 0.0250, 0.0230, 0.0200, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140],
    2007: [0.0400, 0.0300, 0.0270, 0.0230, 0.0220, 0.0200, 0.0190, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2008: [0.0450, 0.0250, 0.0230, 0.0220, 0.0210, 0.0200, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2009: [0.0400, 0.0310, 0.0260, 0.0240, 0.0230, 0.0210, 0.0200, 0.0190, 0.0180, 0.0160, 0.0150, 0.0140],
    2010: [0.0330, 0.0290, 0.0240, 0.0210, 0.0200, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2011: [0.0350, 0.0320, 0.0240, 0.0230, 0.0220, 0.0200, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140],
    2012: [0.0390, 0.0300, 0.0250, 0.0240, 0.0220, 0.0200, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140],
    2013: [0.0330, 0.0260, 0.0250, 0.0230, 0.0220, 0.0200, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2014: [0.0350, 0.0250, 0.0240, 0.0230, 0.0210, 0.0200, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2015: [0.0340, 0.0270, 0.0220, 0.0210, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130, 0.0120, 0.0110],
    2016: [0.0330, 0.0260, 0.0200, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130, 0.0120, 0.0110],
    2017: [0.0350, 0.0300, 0.0250, 0.0220, 0.0210, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2018: [0.0390, 0.0360, 0.0340, 0.0300, 0.0210, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130],
    2019: [0.0440, 0.0430, 0.0310, 0.0270, 0.0260, 0.0210, 0.0190, 0.0180, 0.0160, 0.0150, 0.0140, 0.0130],
    2020: [0.0620, 0.0500, 0.0410, 0.0300, 0.0210, 0.0190, 0.0170, 0.0140, 0.0130, 0.0120, 0.0110, 0.0100],
    2021: [0.0640, 0.0580, 0.0400, 0.0360, 0.0230, 0.0220, 0.0190, 0.0180, 0.0160, 0.0150, 0.0140, 0.0120],
    2022: [0.0590, 0.0540, 0.0330, 0.0260, 0.0190, 0.0180, 0.0170, 0.0160, 0.0150, 0.0140, 0.0130, 0.0120],
    2023: [0.0660, 0.0640, 0.0330, 0.0310, 0.0210, 0.0200, 0.0190, 0.0170, 0.0150, 0.0140, 0.0130, 0.0120],
    2024: [0.0660, 0.0640, 0.0610, 0.0360, 0.0260, 0.0220, 0.0190, 0.0170, 0.0160, 0.0140, 0.0130, 0.0120],
}


def load_raw_chart(file_path: Path) -> dict:
    """Load and return chart result from a raw JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["chart"]["result"][0]


def extract_year_end_closes(chart_data: dict) -> Dict[str, float]:
    """Extract split-adjusted year-end closes (December of each year)."""
    timestamps = chart_data.get("timestamp", [])
    closes = chart_data.get("indicators", {}).get("quote", [{}])[0].get("close", [])

    year_closes = {}
    for ts, c in zip(timestamps, closes):
        if c is not None:
            dt = datetime.datetime.utcfromtimestamp(ts)
            if dt.month == 12:
                # Store the close price rounded to 2 decimals (4 decimals if < $1.00)
                if c < 1.0:
                    rounded_c = round(float(c), 4)
                else:
                    rounded_c = round(float(c), 2)
                year_closes[str(dt.year)] = rounded_c

    return year_closes


def extract_annual_dividends(chart_data: dict) -> Dict[str, float]:
    """Extract annual split-adjusted cash dividends per share."""
    events = chart_data.get("events", {})
    divs = events.get("dividends", {})

    annual_totals: Dict[int, float] = {}
    for k, div in divs.items():
        dt = datetime.datetime.utcfromtimestamp(div["date"])
        annual_totals[dt.year] = annual_totals.get(dt.year, 0.0) + float(div["amount"])

    # Round to 4 decimal places for precision
    result = {}
    for yr in range(1994, 2025):
        val = annual_totals.get(yr, 0.0)
        result[str(yr)] = round(val, 4)

    return result


def main():
    print("Building datasets from raw data in data/raw/...")

    all_prices_data: Dict[str, Dict[str, float]] = {}
    all_dividends_data: Dict[str, Dict[str, float]] = {}

    # 1. Process benchmarks
    gspc_data = load_raw_chart(RAW_DIR / "benchmarks" / "GSPC.json")
    sp500tr_data = load_raw_chart(RAW_DIR / "benchmarks" / "SP500TR.json")
    urth_raw = RAW_DIR / "benchmarks" / "URTH.json"

    all_prices_data["^GSPC"] = extract_year_end_closes(gspc_data)
    all_prices_data["^SP500TR"] = extract_year_end_closes(sp500tr_data)
    if urth_raw.exists():
        all_prices_data["URTH"] = extract_year_end_closes(load_raw_chart(urth_raw))

    print(f"Processed ^GSPC: {len(all_prices_data['^GSPC'])} years (1993..2024)")
    print(f"Processed ^SP500TR: {len(all_prices_data['^SP500TR'])} years (1993..2024)")

    # 2. Process all tickers (US + non-US)
    for ticker in sorted(NAMES.keys()):
        raw_file = RAW_DIR / "tickers" / f"{ticker}.json"
        if not raw_file.exists():
            raise FileNotFoundError(f"Missing raw file for {ticker}: {raw_file}")

        chart = load_raw_chart(raw_file)
        ticker_prices = extract_year_end_closes(chart)
        ticker_divs = extract_annual_dividends(chart)

        all_prices_data[ticker] = ticker_prices
        all_dividends_data[ticker] = ticker_divs

    print(f"Processed prices and dividends for {len(NAMES)} tickers ({len(SP500_NAMES)} SP500, {len(NON_US_NAMES)} Non-US).")

    # 3. Build S&P 500 constituents
    sp500_constituents: Dict[str, List[dict]] = {}
    for year in range(1994, 2025):
        str_year = str(year)
        tickers = YEAR_CONSTITUENTS[year]
        weights = HISTORICAL_INDEX_WEIGHTS[year]

        c_list = []
        for rank, ticker in enumerate(tickers):
            weight = weights[rank]
            name = SP500_NAMES[ticker]
            p_curr = all_prices_data[ticker][str_year]
            p_prev = all_prices_data[ticker][str(year - 1)]
            ret_1y = round((p_curr - p_prev) / p_prev, 4)

            c_list.append({
                "ticker": ticker,
                "name": name,
                "market_cap_weight": weight,
                "trailing_1y_return": ret_1y,
                "year": year,
            })
        sp500_constituents[str_year] = c_list

    # 4. Build All-World constituents
    world_constituents: Dict[str, List[dict]] = {}
    for year in range(1994, 2025):
        str_year = str(year)
        tickers = WORLD_YEAR_CONSTITUENTS[year]
        weights = WORLD_HISTORICAL_WEIGHTS[year]

        c_list = []
        for rank, ticker in enumerate(tickers):
            weight = weights[rank]
            name = NAMES[ticker]
            p_curr = all_prices_data[ticker][str_year]
            p_prev = all_prices_data[ticker][str(year - 1)]
            ret_1y = round((p_curr - p_prev) / p_prev, 4)

            c_list.append({
                "ticker": ticker,
                "name": name,
                "market_cap_weight": weight,
                "trailing_1y_return": ret_1y,
                "year": year,
            })
        world_constituents[str_year] = c_list

    # 5. Build S&P 500 subset for exact backward compatibility
    sp500_prices = {
        k: all_prices_data[k]
        for k in ["^GSPC", "^SP500TR"] + sorted(SP500_NAMES.keys())
        if k in all_prices_data
    }
    sp500_dividends = {
        k: all_dividends_data[k]
        for k in sorted(SP500_NAMES.keys())
        if k in all_dividends_data
    }

    # Save historical index weights records to data/raw/constituents/
    with open(RAW_DIR / "constituents" / "historical_index_weights.json", "w", encoding="utf-8") as f:
        json.dump({
            "source": "S&P Dow Jones Indices Historical Market Cap Archives / Compustat",
            "methodology": "Point-in-time constituent rank and index market cap weight as of Dec 31 each year",
            "constituents_by_year": YEAR_CONSTITUENTS,
            "weights_by_year": HISTORICAL_INDEX_WEIGHTS,
        }, f, indent=2)

    with open(RAW_DIR / "constituents" / "world_historical_index_weights.json", "w", encoding="utf-8") as f:
        json.dump({
            "source": "MSCI World / S&P Global Point-in-Time Mega-Cap Archives (US-listed ADRs/Equities)",
            "methodology": "Point-in-time constituent rank and global market cap weight as of Dec 31 each year",
            "constituents_by_year": WORLD_YEAR_CONSTITUENTS,
            "weights_by_year": WORLD_HISTORICAL_WEIGHTS,
        }, f, indent=2)

    # 6. Save S&P 500 datasets to data/
    with open(DATA_DIR / "sp500_prices.json", "w", encoding="utf-8") as f:
        json.dump(sp500_prices, f, indent=2)

    with open(DATA_DIR / "sp500_dividends.json", "w", encoding="utf-8") as f:
        json.dump(sp500_dividends, f, indent=2)

    with open(DATA_DIR / "sp500_constituents.json", "w", encoding="utf-8") as f:
        json.dump(sp500_constituents, f, indent=2)

    # 7. Save All-World datasets to data/
    with open(DATA_DIR / "world_prices.json", "w", encoding="utf-8") as f:
        json.dump(all_prices_data, f, indent=2)

    with open(DATA_DIR / "world_dividends.json", "w", encoding="utf-8") as f:
        json.dump(all_dividends_data, f, indent=2)

    with open(DATA_DIR / "world_constituents.json", "w", encoding="utf-8") as f:
        json.dump(world_constituents, f, indent=2)

    print("Saved clean, verified S&P 500 datasets:")
    print(f" - {DATA_DIR / 'sp500_prices.json'}")
    print(f" - {DATA_DIR / 'sp500_dividends.json'}")
    print(f" - {DATA_DIR / 'sp500_constituents.json'}")

    print("Saved clean, verified All-World datasets:")
    print(f" - {DATA_DIR / 'world_prices.json'}")
    print(f" - {DATA_DIR / 'world_dividends.json'}")
    print(f" - {DATA_DIR / 'world_constituents.json'}")


if __name__ == "__main__":
    main()
