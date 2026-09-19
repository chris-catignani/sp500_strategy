"""Build split-adjusted prices, dividends, and constituent datasets from raw API responses.

Zero external dependencies - Python 3 standard library only.
Operates 100% offline using data/raw/.
"""

import datetime
import json
import re
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
    "GOOGL": "Alphabet Inc.",
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
    "AMGN": "Amgen Inc.",
    "BMY": "Bristol-Myers Squibb Company",
    "COST": "Costco Wholesale Corporation",
    "DIS": "The Walt Disney Company",
    "FNMA": "Federal National Mortgage Association",
    "MA": "Mastercard Incorporated",
    "MCD": "McDonald's Corporation",
    "ORCL": "Oracle Corporation",
    "PEP": "PepsiCo Inc.",
    "PM": "Philip Morris International Inc.",
    "PYPL": "PayPal Holdings Inc.",
    "QCOM": "QUALCOMM Incorporated",
    "UPS": "United Parcel Service Inc.",
    "VZ": "Verizon Communications Inc.",
    "ABBV": "AbbVie Inc.",
    "ADBE": "Adobe Inc.",
    "CMCSA": "Comcast Corporation",
    "NFLX": "Netflix, Inc.",
    "COP": "ConocoPhillips",
    "SLB": "Schlumberger Limited",
    "GILD": "Gilead Sciences, Inc.",
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

# Constituents with no vendor price series, whose year-end prices are derived from
# Vanguard Index Trust filings (issue #55). Kept out of NAMES deliberately: the loop over
# NAMES requires a file in data/raw/tickers/ and raises when one is absent, which is the
# correct behaviour for a vendor-sourced ticker and the wrong behaviour for these.
DERIVED_NAMES = {
    "AN": "Amoco Corp.",
    "GM": "General Motors Corp.",
    "MOT": "Motorola, Inc.",
    "RD": "Royal Dutch Petroleum Co.",
    "SBC": "SBC Communications Inc.",
    "TYC": "Tyco International Ltd.",
    "T_CORP": "AT&T Corp. (pre-2005 Ma Bell)",
    "LU": "Lucent Technologies, Inc.",
    "EMC": "EMC Corp.",
    "AOL": "America Online, Inc. / AOL Time Warner, Inc.",
    "SUNW": "Sun Microsystems, Inc.",
    "MOB": "Mobil Corp.",
    "NT": "Nortel Networks Corp.",
    "MCIC": "MCI WorldCom, Inc.",
    "BLS": "BellSouth Corp.",
    "DELL": "Dell Computer Corp. / Dell Inc.",
    "GTE": "GTE Corp.",
    "VIA": "Viacom Inc. (Class B)",
    "DD": "E.I. du Pont de Nemours and Co.",
}

# Viacom listed two classes at different prices. Class B is carried because it is the
# larger holding in every filing examined; routing through one class follows the
# dual-class execution convention established for Alphabet in #38 and documented in
# docs/DATA_PROVENANCE.md 4.3.8.
DERIVED_SOURCE_KEYS: Dict[str, str] = {}

EFFECTIVE_INCLUSION_DATES = {
    "TSLA": "2020-12-21",
    "GOOGL": "2006-03-31",
    "BRK.B": "2010-01-21",
    "META": "2013-12-23",
    "V": "2009-11-30",
    "MA": "2008-07-18",
    "PM": "2008-03-31",
    "PYPL": "2015-07-20",
    "QCOM": "1999-11-19",
    "UPS": "2002-07-22",
    "ABBV": "2013-01-02",
    "ADBE": "1997-05-05",
    "CMCSA": "2002-11-18",
    "NFLX": "2010-12-17",
}
QUARTER_END_DATES = {
    1: "03-31",
    2: "06-30",
    3: "09-30",
    4: "12-31",
}

# Index removal is the mirror of inclusion (docs/DATA_PROVENANCE.md 4.3.4). A constituent
# cannot be selected at a quarter end after it stopped trading any more than it can before
# it was admitted, so the two filters sit side by side and are applied at the same point.
#
# The dates are not restated here. Every one is the effective_date of a terminal action
# already sourced to a filing in terminal_actions.json and re-checkable with
# `python3 scripts/verify_provenance.py terminal`, so this reads them rather than copying
# them: a correction at the source reaches the filter without a second edit, and there is
# no second list to fall out of step.
TERMINAL_ACTIONS_PATH = RAW_DIR / "corporate_actions" / "terminal_actions.json"
TERMINAL_ACTIONS: Dict[str, dict] = {}
if TERMINAL_ACTIONS_PATH.exists():
    with open(TERMINAL_ACTIONS_PATH, "r", encoding="utf-8") as f:
        TERMINAL_ACTIONS = json.load(f)["actions_by_ticker"]

EFFECTIVE_REMOVAL_DATES = {
    ticker: action["effective_date"] for ticker, action in TERMINAL_ACTIONS.items()
}

# A fund schedule dated within this many days of an effective date values what the holder
# received, not a trade in a security that had already stopped trading. The Vanguard 500
# schedule of 2006-12-31 lists BellSouth two days after its merger closed; nine months
# after Tyco's separation it lists a continuing company that merely kept the ticker. The
# window is what separates those two cases mechanically rather than by inspection.
TERMINAL_OBSERVATION_WINDOW_DAYS = 31


def _period_end_date(period: str) -> str:
    """Return the calendar date a price observation key falls on.

    Accepts either a bare year ("2006") or a quarter key ("2006-Q4").
    """
    if "-Q" in period:
        year, quarter = period.split("-Q")
        return f"{year}-{QUARTER_END_DATES[int(quarter)]}"
    return f"{period}-12-31"


def _days_between(start_date: str, end_date: str) -> int:
    """Return end_date - start_date in days; negative when end_date is the earlier one."""
    fmt = "%Y-%m-%d"
    return (
        datetime.datetime.strptime(end_date, fmt) - datetime.datetime.strptime(start_date, fmt)
    ).days


def _partition_post_removal(ticker: str, series: Dict[str, float]):
    """Split a price series at the ticker's index-removal date.

    Returns (kept, withheld). A price is a statement that the named security traded at
    that value on that date, so an observation dated after the security stopped trading
    cannot be published as one whatever it measures -- and the two things it can measure
    are different enough to matter. Withheld observations are returned rather than dropped
    so the compiled dataset can record what was removed and why.
    """
    removal_date = EFFECTIVE_REMOVAL_DATES.get(ticker)
    if removal_date is None:
        return dict(series), {}
    kept, withheld = {}, {}
    for period, value in series.items():
        target = withheld if _period_end_date(period) > removal_date else kept
        target[period] = value
    return kept, withheld

# Load historical constituents and factsheet weights directly from raw archives
with open(RAW_DIR / "constituents" / "historical_index_weights.json", "r", encoding="utf-8") as f:
    raw_sp500 = json.load(f)
YEAR_CONSTITUENTS = {int(k): v for k, v in raw_sp500["constituents_by_year"].items()}
HISTORICAL_INDEX_WEIGHTS = {int(k): v for k, v in raw_sp500["weights_by_year"].items()}


ESTIMATED_YEAR_CONSTITUENTS = {int(k): list(v) for k, v in raw_sp500["constituents_by_year"].items()}
ESTIMATED_INDEX_WEIGHTS = {int(k): list(v) for k, v in raw_sp500["weights_by_year"].items()}


def _apply_audited_rosters():
    """Replace estimated year-end rosters with ones read from a primary filing.

    For 1994-2006 the Vanguard 500 Index Fund's December-31 Schedule of Investments is an
    audited point-in-time roster of the index (docs/DATA_PROVENANCE.md 4.3.10), so ranks
    and weights for those years are read rather than estimated. Outside that span the
    estimated rosters stand, including the 208 rows labelled Unverified Estimate.

    This is the step that removes survivorship bias. The estimates omit constituents the
    filings record -- SBC, EMC and Royal Dutch are all inside the audited 2000 Top 20 and
    absent from the estimate for that year -- and a universe that drops constituents is
    measuring something other than the strategy.
    """
    rosters_path = RAW_DIR / "ground_truth" / "vanguard_audited_rosters.json"
    map_path = RAW_DIR / "constituents" / "issuer_ticker_map.json"
    if not rosters_path.exists() or not map_path.exists():
        return {}

    with open(rosters_path, "r", encoding="utf-8") as f:
        rosters = json.load(f)["rosters_by_year"]
    with open(map_path, "r", encoding="utf-8") as f:
        issuer_map = {
            re.sub(r"^[#*^\s]+", "", k).strip().rstrip(".").strip(): v
            for k, v in json.load(f)["map"].items()
        }

    replaced = {}
    for year_key, roster in rosters.items():
        year = int(year_key)

        # A dual-class issuer is filed as two positions, and its enterprise weight is the
        # sum of them (4.3.8). Taking the larger line and dropping the other -- which is
        # what this loop used to do -- halves the issuer and drops it in the ranking: it
        # put Alphabet at rank 20 in 2014 on its Class A weight alone, when consolidated
        # it ranks 4th. That is the same understatement issue #45 was opened about,
        # arriving through the dataset builder instead of through the committed anchors.
        consolidated = {}
        for holding in roster["holdings"]:
            if holding.get("unidentified"):
                continue
            name = re.sub(r"^[#*^\s]+", "", holding["name"]).strip().rstrip(".").strip()
            ticker = issuer_map.get(name)
            if ticker is None:
                continue
            consolidated[ticker] = consolidated.get(ticker, 0.0) + holding["weight"]

        ranked = sorted(consolidated.items(), key=lambda kv: -kv[1])[:20]
        if len(ranked) == 20:
            YEAR_CONSTITUENTS[year] = [t for t, _ in ranked]
            HISTORICAL_INDEX_WEIGHTS[year] = [round(w, 6) for _, w in ranked]
            replaced[year] = YEAR_CONSTITUENTS[year]
    return replaced


AUDITED_ROSTER_YEARS = _apply_audited_rosters()

with open(RAW_DIR / "constituents" / "world_historical_index_weights.json", "r", encoding="utf-8") as f:
    raw_world = json.load(f)
WORLD_YEAR_CONSTITUENTS = {int(k): v for k, v in raw_world["constituents_by_year"].items()}
WORLD_HISTORICAL_WEIGHTS = {int(k): v for k, v in raw_world["weights_by_year"].items()}

MSCIWORLD_PR_LEVELS = {
    "1993": 1000.0, "1994": 1051.0, "1995": 1242.81, "1996": 1396.05, "1997": 1573.21,
    "1998": 1914.75, "1999": 2379.46, "2000": 2065.85, "2001": 1697.09, "2002": 1339.86,
    "2003": 1741.95, "2004": 1958.65, "2005": 2103.98, "2006": 2474.07, "2007": 2636.12,
    "2008": 1511.29, "2009": 1914.05, "2010": 2096.84, "2011": 1928.88, "2012": 2183.11,
    "2013": 2709.23, "2014": 2788.61, "2015": 2712.2, "2016": 2856.49, "2017": 3430.93,
    "2018": 3072.74, "2019": 3846.76, "2020": 4387.62, "2021": 5271.28, "2022": 4245.49,
    "2023": 5169.73, "2024": 6048.59
}

MSCIWORLD_TR_LEVELS = {
    "1993": 1000.0, "1994": 1076.4, "1995": 1302.77, "1996": 1496.62, "1997": 1738.18,
    "1998": 2161.6, "1999": 2711.29, "2000": 2365.6, "2001": 1975.75, "2002": 1580.99,
    "2003": 2108.89, "2004": 2430.49, "2005": 2677.19, "2006": 3229.99, "2007": 3546.53,
    "2008": 2116.22, "2009": 2767.79, "2010": 3109.62, "2011": 2955.69, "2012": 3444.56,
    "2013": 4387.34, "2014": 4628.64, "2015": 4613.83, "2016": 4989.85, "2017": 6141.01,
    "2018": 5637.45, "2019": 7238.48, "2020": 8432.83, "2021": 10317.57, "2022": 8488.27,
    "2023": 10561.1, "2024": 12587.77
}


with open(RAW_DIR / "corporate_actions" / "splits.json", "r", encoding="utf-8") as f:
    SPLITS_BY_TICKER = json.load(f)["splits_by_ticker"]


def spinoff_split_factor(ticker: str, ex_date: str) -> float:
    """Divisor converting a value quoted at ex_date into final share terms.

    The same convention scripts/derive_constituent_series.py applies to prices: every
    split effective after the quote compounds into the factor. A ticker with no filed
    split record returns 1.0, which is correct for the vendor-priced constituents --
    their series arrives already adjusted and their distributions are quoted on the
    same basis.
    """
    record = SPLITS_BY_TICKER.get(ticker)
    if not record:
        return 1.0
    factor = 1.0
    for split in record["splits"]:
        if split["effective_date"] > ex_date:
            factor *= split["ratio"]
    return factor


def load_raw_chart(file_path: Path) -> dict:
    """Load and return chart result from a raw JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["chart"]["result"][0]


def extract_year_end_closes(chart_data: dict, source_field: str = "close") -> Dict[str, float]:
    """Extract split-adjusted year-end closes (December of each year)."""
    timestamps = chart_data.get("timestamp", [])
    if source_field == "adjclose":
        adj_list = chart_data.get("indicators", {}).get("adjclose")
        closes = adj_list[0].get("adjclose", []) if (adj_list and adj_list[0] is not None) else []
    else:
        quote_list = chart_data.get("indicators", {}).get("quote")
        closes = quote_list[0].get("close", []) if (quote_list and quote_list[0] is not None) else []

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


def extract_quarterly_closes(chart_data: dict, source_field: str = "close") -> Dict[str, float]:
    """Extract split-adjusted quarter-end closes (Mar, Jun, Sep, Dec)."""
    timestamps = chart_data.get("timestamp", [])
    if source_field == "adjclose":
        adj_list = chart_data.get("indicators", {}).get("adjclose")
        closes = adj_list[0].get("adjclose", []) if (adj_list and adj_list[0] is not None) else []
    else:
        quote_list = chart_data.get("indicators", {}).get("quote")
        closes = quote_list[0].get("close", []) if (quote_list and quote_list[0] is not None) else []

    quarter_closes = {}
    for ts, c in zip(timestamps, closes):
        if c is not None:
            dt = datetime.datetime.utcfromtimestamp(ts)
            if dt.month in (3, 6, 9, 12):
                q = (dt.month - 1) // 3 + 1
                rounded_c = round(float(c), 4 if c < 1.0 else 2)
                quarter_closes[f"{dt.year}-Q{q}"] = rounded_c
    return quarter_closes


def extract_quarterly_closes_raw(chart_data: dict, source_field: str = "close") -> Dict[str, float]:
    """Extract unrounded quarter-end closes keeping raw float precision."""
    timestamps = chart_data.get("timestamp", [])
    if source_field == "adjclose":
        adj_list = chart_data.get("indicators", {}).get("adjclose")
        closes = adj_list[0].get("adjclose", []) if (adj_list and adj_list[0] is not None) else []
    else:
        quote_list = chart_data.get("indicators", {}).get("quote")
        closes = quote_list[0].get("close", []) if (quote_list and quote_list[0] is not None) else []

    quarter_closes = {}
    for ts, c in zip(timestamps, closes):
        if c is not None:
            dt = datetime.datetime.utcfromtimestamp(ts)
            if dt.month in (3, 6, 9, 12):
                q = (dt.month - 1) // 3 + 1
                quarter_closes[f"{dt.year}-Q{q}"] = float(c)
    return quarter_closes


def extract_quarterly_dividends(chart_data: dict) -> Dict[str, float]:
    """Extract quarterly split-adjusted cash dividends per share."""
    events = chart_data.get("events", {})
    divs = events.get("dividends", {})

    quarter_totals: Dict[str, float] = {}
    for k, div in divs.items():
        dt = datetime.datetime.utcfromtimestamp(div["date"])
        q = (dt.month - 1) // 3 + 1
        key = f"{dt.year}-Q{q}"
        quarter_totals[key] = quarter_totals.get(key, 0.0) + float(div["amount"])

    result = {}
    for yr in range(1993, 2025):
        for q in (1, 2, 3, 4):
            key = f"{yr}-Q{q}"
            result[key] = round(quarter_totals.get(key, 0.0), 4)
    return result


def _get_trailing_4q_keys(year: int, quarter: int) -> List[str]:
    """Return keys for the 4 quarters ending at (year, quarter)."""
    keys = []
    for offset in range(4):
        total_q = year * 4 + (quarter - 1) - offset
        y = total_q // 4
        q = (total_q % 4) + 1
        keys.append(f"{y}-Q{q}")
    return keys


def build_quarterly_constituents(
    year_constituents: Dict[int, List[str]],
    historical_weights: Dict[int, List[float]],
    quarterly_prices: Dict[str, Dict[str, float]],
    benchmark_key: str,
    name_map: Dict[str, str],
    quarterly_dividends: Optional[Dict[str, Dict[str, float]]] = None,
    quarterly_spinoffs: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, List[dict]]:
    """Build quarterly point-in-time constituent lists.

    Q4 re-anchors to official year-end factsheet.
    Q1..Q3 dynamically drift market-cap weights and compute rolling 4-quarter total returns.
    """
    result = {}
    for year in range(1994, 2025):
        prev_year = year - 1
        base_tickers = year_constituents.get(prev_year, year_constituents[year])
        base_weights = historical_weights.get(prev_year, historical_weights[year])
        candidate_tickers = list(base_tickers)

        base_w_map = {t: w for t, w in zip(base_tickers, base_weights)}

        bmk_prices = quarterly_prices.get(benchmark_key, {})
        p_bmk_base = bmk_prices.get(f"{year - 1}-Q4", bmk_prices.get(f"{year}-Q1", 1.0))

        for q in (1, 2, 3):
            q_key = f"{year}-Q{q}"
            p_bmk_q = bmk_prices.get(q_key, p_bmk_base)
            bmk_mult = (p_bmk_q / p_bmk_base) if p_bmk_base > 0 else 1.0
            q_trailing_keys = _get_trailing_4q_keys(year, q)

            scored_candidates = []
            for t in candidate_tickers:
                q_end_date = f"{year}-{QUARTER_END_DATES[q]}"
                if t in EFFECTIVE_INCLUSION_DATES and q_end_date < EFFECTIVE_INCLUSION_DATES[t]:
                    continue
                if t in EFFECTIVE_REMOVAL_DATES and q_end_date > EFFECTIVE_REMOVAL_DATES[t]:
                    continue

                t_prices = quarterly_prices.get(t, {})
                p_base = t_prices.get(f"{year - 1}-Q4")
                p_curr = t_prices.get(q_key)
                p_1y_prior = t_prices.get(f"{year - 1}-Q{q}")

                # Constituents without a quarter-end price cannot be priced;
                # carrying an undrifted anchor weight would let a stale number compete.
                if p_curr is None:
                    continue

                if p_base is not None and p_base > 0:
                    stock_mult = p_curr / p_base
                    drifted_w = base_w_map[t] * (stock_mult / bmk_mult if bmk_mult > 0 else 1.0)
                else:
                    drifted_w = base_w_map[t]

                t_divs = quarterly_dividends.get(t, {}) if quarterly_dividends else {}
                t_spinoffs = quarterly_spinoffs.get(t, {}) if quarterly_spinoffs else {}
                div_1y = sum(t_divs.get(qk, 0.0) for qk in q_trailing_keys) + sum(t_spinoffs.get(qk, 0.0) for qk in q_trailing_keys)

                if p_curr is not None and p_1y_prior is not None and p_1y_prior > 0:
                    ret_1y = round((p_curr - p_1y_prior + div_1y) / p_1y_prior, 4)
                else:
                    ret_1y = None

                scored_candidates.append({
                    "ticker": t,
                    "name": name_map.get(t, t),
                    "market_cap_weight": round(drifted_w, 4),
                    "trailing_1y_return": ret_1y,
                    "year": year,
                    "quarter": q,
                })

            scored_candidates.sort(key=lambda x: x["market_cap_weight"], reverse=True)
            result[q_key] = scored_candidates[:len(base_tickers)]

        # Q4: Official factsheet re-anchoring
        q4_key = f"{year}-Q4"
        q4_tickers = year_constituents[year]
        q4_weights = historical_weights[year]
        q4_trailing_keys = _get_trailing_4q_keys(year, 4)
        q4_list = []
        for rank, t in enumerate(q4_tickers):
            t_prices = quarterly_prices.get(t, {})
            p_curr = t_prices.get(q4_key)
            p_1y_prior = t_prices.get(f"{year - 1}-Q4")
            t_divs = quarterly_dividends.get(t, {}) if quarterly_dividends else {}
            t_spinoffs = quarterly_spinoffs.get(t, {}) if quarterly_spinoffs else {}
            div_1y = sum(t_divs.get(qk, 0.0) for qk in q4_trailing_keys) + sum(t_spinoffs.get(qk, 0.0) for qk in q4_trailing_keys)
            ret_1y = (
                round((p_curr - p_1y_prior + div_1y) / p_1y_prior, 4)
                if (p_curr is not None and p_1y_prior is not None and p_1y_prior > 0)
                else None
            )
            q4_list.append({
                "ticker": t,
                "name": name_map.get(t, t),
                "market_cap_weight": q4_weights[rank],
                "trailing_1y_return": ret_1y,
                "year": year,
                "quarter": 4,
            })
        result[q4_key] = q4_list

    return result


def main():
    print("Building datasets from raw data in data/raw/...")

    all_prices_data: Dict[str, Dict[str, float]] = {}
    all_dividends_data: Dict[str, Dict[str, float]] = {}
    all_quarterly_prices_data: Dict[str, Dict[str, float]] = {}
    all_quarterly_dividends_data: Dict[str, Dict[str, float]] = {}

    # 1. Process benchmarks
    gspc_data = load_raw_chart(RAW_DIR / "benchmarks" / "GSPC.json")
    sp500tr_data = load_raw_chart(RAW_DIR / "benchmarks" / "SP500TR.json")
    urth_raw = RAW_DIR / "benchmarks" / "URTH.json"

    all_prices_data["^GSPC"] = extract_year_end_closes(gspc_data)
    all_prices_data["^SP500TR"] = extract_year_end_closes(sp500tr_data)
    all_quarterly_prices_data["^GSPC"] = extract_quarterly_closes(gspc_data)
    all_quarterly_prices_data["^SP500TR"] = extract_quarterly_closes(sp500tr_data)

    if urth_raw.exists():
        urth_chart = load_raw_chart(urth_raw)
        all_prices_data["URTH"] = extract_year_end_closes(urth_chart)
        all_quarterly_prices_data["URTH"] = extract_quarterly_closes(urth_chart)

    fbgrx_raw = RAW_DIR / "benchmarks" / "FBGRX.json"
    if fbgrx_raw.exists():
        fbgrx_chart = load_raw_chart(fbgrx_raw)
        all_prices_data["FBGRX"] = extract_year_end_closes(fbgrx_chart, source_field="close")
        all_prices_data["FBGRX_TR"] = extract_year_end_closes(fbgrx_chart, source_field="adjclose")
        all_quarterly_prices_data["FBGRX"] = extract_quarterly_closes(fbgrx_chart, source_field="close")
        all_quarterly_prices_data["FBGRX_TR"] = extract_quarterly_closes(fbgrx_chart, source_field="adjclose")

    all_prices_data["^MSCIWORLD_PR"] = dict(MSCIWORLD_PR_LEVELS)
    all_prices_data["^MSCIWORLD_TR"] = dict(MSCIWORLD_TR_LEVELS)

    # Quarterly MSCI World levels (calibrated from observed quarterly closes in data/raw/benchmarks/MSCIWORLD.json)
    msci_raw = load_raw_chart(RAW_DIR / "benchmarks" / "MSCIWORLD.json")
    qc_msci = extract_quarterly_closes(msci_raw)

    q_msci_pr = {"1993-Q4": MSCIWORLD_PR_LEVELS["1993"]}
    q_msci_tr = {"1993-Q4": MSCIWORLD_TR_LEVELS["1993"]}

    for yr in range(1994, 2025):
        p_pr_base = MSCIWORLD_PR_LEVELS[str(yr - 1)]
        p_pr_target = MSCIWORLD_PR_LEVELS[str(yr)]
        p_tr_base = MSCIWORLD_TR_LEVELS[str(yr - 1)]
        p_tr_target = MSCIWORLD_TR_LEVELS[str(yr)]

        raw_base = qc_msci[f"{yr-1}-Q4"]
        raw_target = qc_msci[f"{yr}-Q4"]
        raw_tot_ret = (raw_target - raw_base) / raw_base if raw_base > 0 else 0.0
        target_pr_ret = (p_pr_target - p_pr_base) / p_pr_base if p_pr_base > 0 else 0.0
        ann_div_yield = max(0.0, (p_tr_target / p_tr_base) - (p_pr_target / p_pr_base))

        for q in (1, 2, 3):
            raw_c = qc_msci[f"{yr}-Q{q}"]
            frac_ret = (raw_c - raw_base) / raw_base if raw_base > 0 else 0.0
            scaled_ret = (
                frac_ret * (target_pr_ret / raw_tot_ret)
                if abs(raw_tot_ret) > 1e-6
                else target_pr_ret * (q / 4.0)
            )
            q_msci_pr[f"{yr}-Q{q}"] = round(p_pr_base * (1.0 + scaled_ret), 2)
            q_msci_tr[f"{yr}-Q{q}"] = round(p_tr_base * (1.0 + scaled_ret + ann_div_yield * (q / 4.0)), 2)

        q_msci_pr[f"{yr}-Q4"] = p_pr_target
        q_msci_tr[f"{yr}-Q4"] = p_tr_target

    all_quarterly_prices_data["^MSCIWORLD_PR"] = q_msci_pr
    all_quarterly_prices_data["^MSCIWORLD_TR"] = q_msci_tr

    # Nasdaq 100 (^NDX Price Return & ^NDXT Total Return Composite)
    ndx_raw = RAW_DIR / "benchmarks" / "NDX.json"
    qqq_raw = RAW_DIR / "benchmarks" / "QQQ.json"

    if ndx_raw.exists() and qqq_raw.exists():
        ndx_chart = load_raw_chart(ndx_raw)
        qqq_chart = load_raw_chart(qqq_raw)

        # 1. Price return series (^NDX)
        all_prices_data["^NDX"] = extract_year_end_closes(ndx_chart, source_field="close")
        all_quarterly_prices_data["^NDX"] = extract_quarterly_closes(ndx_chart, source_field="close")

        # 2. Total return composite series (^NDXT) synthesized from ^NDX and QQQ
        ndx_q_raw = extract_quarterly_closes_raw(ndx_chart, source_field="close")
        qqq_q_raw = extract_quarterly_closes_raw(qqq_chart, source_field="close")
        qqq_q_divs = extract_quarterly_dividends(qqq_chart)

        composite_q_tr: Dict[str, float] = {}
        base_tr = 398.28
        composite_q_tr["1993-Q4"] = base_tr

        # Backward chain for 1993-Q3, 1993-Q2, 1993-Q1
        curr_tr = base_tr
        for t_key, prev_key in [("1993-Q4", "1993-Q3"), ("1993-Q3", "1993-Q2"), ("1993-Q2", "1993-Q1")]:
            ndx_t = ndx_q_raw[t_key]
            ndx_prev = ndx_q_raw[prev_key]
            r_pr = (ndx_t - ndx_prev) / ndx_prev
            y_t = 0.0025 / 4.0
            r_tr = r_pr + y_t
            prev_tr = curr_tr / (1.0 + r_tr)
            composite_q_tr[prev_key] = prev_tr
            curr_tr = prev_tr

        # Forward chain from 1994-Q1 to 2024-Q4
        curr_tr = base_tr
        prev_key = "1993-Q4"
        for yr in range(1994, 2025):
            for q in (1, 2, 3, 4):
                t_key = f"{yr}-Q{q}"
                ndx_t = ndx_q_raw[t_key]
                ndx_prev = ndx_q_raw[prev_key]
                r_pr = (ndx_t - ndx_prev) / ndx_prev

                if t_key >= "1999-Q2":
                    div_qqq = qqq_q_divs.get(t_key, 0.0)
                    p_qqq_prev = qqq_q_raw[prev_key]
                    y_t = div_qqq / p_qqq_prev if p_qqq_prev > 0.0 else 0.0
                elif t_key == "1999-Q1":
                    y_t = 0.0
                else:
                    # 1993-Q1 to 1998-Q4: 0.25% annualized nominal yield
                    y_t = 0.0025 / 4.0

                r_tr = r_pr + y_t
                curr_tr = curr_tr * (1.0 + r_tr)
                composite_q_tr[t_key] = curr_tr
                prev_key = t_key

        all_quarterly_prices_data["^NDXT"] = {
            k: round(v, 2)
            for k, v in sorted(composite_q_tr.items())
        }

        all_prices_data["^NDXT"] = {
            str(yr): all_quarterly_prices_data["^NDXT"][f"{yr}-Q4"]
            for yr in range(1993, 2025)
        }

        print(f"Processed ^NDX: {len(all_prices_data['^NDX'])} years, {len(all_quarterly_prices_data['^NDX'])} quarters")
        print(f"Processed ^NDXT: {len(all_prices_data['^NDXT'])} years, {len(all_quarterly_prices_data['^NDXT'])} quarters")

    print(f"Processed ^GSPC: {len(all_prices_data['^GSPC'])} years, {len(all_quarterly_prices_data['^GSPC'])} quarters")
    print(f"Processed ^SP500TR: {len(all_prices_data['^SP500TR'])} years, {len(all_quarterly_prices_data['^SP500TR'])} quarters")

    # 2. Process all tickers (US + non-US)
    for ticker in sorted(NAMES.keys()):
        raw_file = RAW_DIR / "tickers" / f"{ticker}.json"
        if not raw_file.exists():
            raise FileNotFoundError(f"Missing raw file for {ticker}: {raw_file}")

        chart = load_raw_chart(raw_file)
        ticker_prices = extract_year_end_closes(chart)
        ticker_divs = extract_annual_dividends(chart)
        ticker_q_prices = extract_quarterly_closes(chart)
        ticker_q_divs = extract_quarterly_dividends(chart)

        all_prices_data[ticker] = ticker_prices
        all_dividends_data[ticker] = ticker_divs
        all_quarterly_prices_data[ticker] = ticker_q_prices
        all_quarterly_dividends_data[ticker] = ticker_q_divs

    print(f"Processed prices and dividends for {len(NAMES)} tickers ({len(SP500_NAMES)} SP500, {len(NON_US_NAMES)} Non-US).")

    # Constituents with no vendor price series (issue #55). Their year-end prices are
    # derived from Vanguard Index Trust Schedules of Investments as value / shares and
    # split-adjusted from filing-cited records, so they are merged from a second input
    # rather than read from data/raw/tickers/. These derived records provide ground-truth
    # pricing directly from fund filings when vendor price files are unavailable.
    derived_path = RAW_DIR / "ground_truth" / "derived_constituent_series.json"
    derived_merged = 0
    withheld_annual_prices: Dict[str, Dict[str, float]] = {}
    if derived_path.exists():
        with open(derived_path, "r", encoding="utf-8") as f:
            derived = json.load(f)["series_by_ticker"]

        for ticker in sorted(DERIVED_NAMES):
            observations = derived.get(DERIVED_SOURCE_KEYS.get(ticker, ticker), {})
            # Only issuers whose split record was established from a filing carry an
            # adjusted price; without one the series is as-traded and a split inside the
            # holding period would register as a price collapse that never happened.
            series = {
                year: obs["split_adjusted_price_usd"]
                for year, obs in observations.items()
                if "split_adjusted_price_usd" in obs
            }
            if not series:
                continue
            if ticker in all_prices_data:
                raise ValueError(
                    f"{ticker}: derived prices would overwrite a vendor series from "
                    "data/raw/tickers/. A constituent must have exactly one price source."
                )
            series, withheld = _partition_post_removal(ticker, series)
            if withheld:
                withheld_annual_prices[ticker] = withheld
            all_prices_data[ticker] = dict(sorted(series.items(), key=lambda kv: int(kv[0])))
            # A Schedule of Investments reports holdings, not distributions, so no
            # dividend is derivable from the source the price comes from. Where the
            # issuer's own filings or a verified successor series supply one it is merged
            # below (#76); where nothing does, the series stays EMPTY rather than
            # zero-filled, because unknown and nil are different claims.
            all_dividends_data.setdefault(ticker, {})
            derived_merged += 1

        print(
            f"Merged {derived_merged} derived constituent series from "
            f"{derived_path.relative_to(REPO_ROOT)}"
        )

    # The same constituents at Q2 and Q3 (issue #63). Without these they have only a
    # December-31 observation, so they cannot be drifted or priced at a quarter end and
    # drop out of the quarterly universe entirely - which left the quarterly path carrying
    # a survivorship bias the annual path no longer has.
    #
    # Q1 arrives from the March-31 schedules of SEI Index Funds (audited, 1995-2006) and
    # Prudential (unaudited, 1994), and Q4 from the audited December-31 rosters that
    # already price these constituents annually. Coverage is still not complete, and the
    # gaps are sources rather than parsing: there is no September-30 filing before
    # 1997-Q3, SEI's 2004 schedule is corrupt as filed, and only Q3 exists after 2006.
    # Eligibility below is what makes partial coverage safe, so the series is merged as it
    # stands rather than withheld whole.
    derived_q_path = RAW_DIR / "ground_truth" / "derived_quarterly_constituent_series.json"
    derived_q_merged = 0
    incomplete_q_series: Dict[str, List[str]] = {}
    withheld_quarterly_prices: Dict[str, Dict[str, float]] = {}
    if derived_q_path.exists():
        with open(derived_q_path, "r", encoding="utf-8") as f:
            derived_q = json.load(f)["series_by_ticker"]

        for ticker in sorted(DERIVED_NAMES):
            observations = derived_q.get(DERIVED_SOURCE_KEYS.get(ticker, ticker), {})
            series = {
                period: obs["split_adjusted_price_usd"]
                for period, obs in observations.items()
                if "split_adjusted_price_usd" in obs
            }
            # Every price that was read from a filing is published. Whether the
            # constituent may be SELECTED in a given year is decided by the eligibility
            # rule in section 5, which is where the valuation requirement belongs: a
            # constituent that cannot be priced at some quarter is simply not a candidate
            # for the year that would hold it there.
            #
            # Withholding the whole ticker instead, as this did while Q1 was missing, is
            # too blunt now that coverage is partial rather than absent - one unsourceable
            # year would discard every sourced year the constituent has.
            if not series:
                continue
            series, withheld = _partition_post_removal(ticker, series)
            if withheld:
                withheld_quarterly_prices[ticker] = withheld
            incomplete_q_series[ticker] = sorted(
                year
                for year in {period[:4] for period in series}
                if not all(f"{year}-Q{q}" in series for q in (1, 2, 3, 4))
            )
            if ticker in all_quarterly_prices_data:
                raise ValueError(
                    f"{ticker}: derived quarterly prices would overwrite a vendor series "
                    "from data/raw/tickers/. A constituent must have exactly one price "
                    "source."
                )
            all_quarterly_prices_data[ticker] = dict(sorted(series.items()))
            all_quarterly_dividends_data.setdefault(ticker, {})
            derived_q_merged += 1

        print(
            f"Merged {derived_q_merged} derived quarterly constituent series from "
            f"{derived_q_path.relative_to(REPO_ROOT)}"
        )
        partial = {t: y for t, y in incomplete_q_series.items() if y}
        if partial:
            print(
                f"  {len(partial)} carry years without all four quarters; those years are "
                "not eligible for selection. Gaps are sources, not parsing: no September-30 "
                "filing for 1994, no Q2 2005, and only Q3 after 2006. 2004-Q1 was on this "
                "list until #83 read Prudential's HTML-era schedule; SEI's 2004 filing is "
                "still refused as corrupt, which is a separate fact and stays recorded."
            )

    # Dividends for the derived constituents (#76), from the issuers' own filings and from
    # the two verified successor series. docs/DATA_PROVENANCE.md 4.3.15 holds the sourcing
    # and the reconcile-or-withhold gate; the figures arrive here already converted into
    # the price basis. A SOURCED ZERO -- a registrant that states in its own filing that it
    # has never paid -- is written as an explicit 0.0 for the years the statement covers,
    # which is a different and stronger claim than an absent year and is what lets
    # test_derived_constituents_carry_no_fabricated_dividends tell the two apart.
    dividend_path = RAW_DIR / "ground_truth" / "derived_dividend_series.json"
    dividend_tickers, zero_tickers = [], []
    if dividend_path.exists():
        with open(dividend_path, "r", encoding="utf-8") as f:
            derived_dividends = json.load(f)["series_by_ticker"]

        for ticker in sorted(DERIVED_NAMES):
            record = derived_dividends.get(ticker)
            if not record:
                continue
            priced_years = set(all_prices_data.get(ticker, {}))
            priced_quarters = set(all_quarterly_prices_data.get(ticker, {}))

            annual = {
                year: obs["dividend_per_share"]
                for year, obs in record.get("annual", {}).items()
                if year in priced_years
            }
            quarterly = {
                period: obs["dividend_per_share"]
                for period, obs in record.get("quarterly", {}).items()
                if period in priced_quarters
            }

            zero = record.get("sourced_zero") or {}
            if zero and not zero.get("voided"):
                # The statement bounds the claim: it covers everything up to the filing
                # that made it and says nothing afterwards. Years past that bound are left
                # absent, not zeroed.
                bound = zero["through_filing_date"][:4]
                annual.update({y: 0.0 for y in priced_years if y <= bound})
                quarterly.update({q: 0.0 for q in priced_quarters if q[:4] <= bound})
                zero_tickers.append(ticker)

            if annual:
                all_dividends_data[ticker] = dict(sorted(annual.items(), key=lambda kv: int(kv[0])))
            if quarterly:
                all_quarterly_dividends_data[ticker] = dict(sorted(quarterly.items()))
            if annual or quarterly:
                dividend_tickers.append(ticker)

        print(
            f"Merged dividend series for {len(dividend_tickers)} derived constituents from "
            f"{dividend_path.relative_to(REPO_ROOT)}"
        )
        if zero_tickers:
            print(f"  sourced zeros (read, not assumed): {', '.join(zero_tickers)}")
        still_unknown = sorted(set(DERIVED_NAMES) - set(dividend_tickers))
        if still_unknown:
            print(f"  dividend series still unknown: {', '.join(still_unknown)}")

    # Load raw spinoff distributions for total return calculations.
    #
    # spinoffs.json records each distribution as it was quoted on its ex-date, which is
    # the right thing for a raw source file to hold. The engine, though, computes
    # shares_held * distribution_per_share, and shares_held follows from a price series
    # expressed in final share terms (4.3.12). A distribution and the price it is
    # credited against must therefore share units, so each event is converted here by
    # the same factor that adjusts prices.
    #
    # This is a no-op for every event in the catalog except AT&T Corp's two 1996
    # distributions: splits.json carries records only for constituents priced from
    # filings, and of those only T_CORP has a split after one of its own distributions.
    # It has TWO -- the three-for-two of 1999-04-15 and the 1-for-5 reverse of
    # 2002-11-18 -- compounding to a factor of 0.3, which puts its 1996 events
    # ten-for-three out of step with its 1996 price. This comment said five-for-one
    # until #104, describing the record as it stood before #76 recovered the 1999 split;
    # the code was always right, because it reads the record rather than a constant.
    all_quarterly_spinoffs: Dict[str, Dict[str, float]] = {}
    all_annual_spinoffs: Dict[str, Dict[int, float]] = {}
    spinoffs_raw = RAW_DIR / "corporate_actions" / "spinoffs.json"
    spinoffs_data = {}
    if spinoffs_raw.exists():
        with open(spinoffs_raw, "r", encoding="utf-8") as f:
            spinoffs_data = json.load(f)
        for t, events in spinoffs_data.items():
            all_quarterly_spinoffs[t] = {}
            all_annual_spinoffs[t] = {}
            for ev in events:
                y = int(ev["year"])
                q = int(ev["quarter"])
                factor = spinoff_split_factor(t, ev["ex_date"])
                d = round(float(ev["distribution_per_share"]) / factor, 4)
                # The compiled dataset the engine reads must carry the converted value,
                # not the as-traded one the raw file holds.
                ev["distribution_per_share"] = d
                q_key = f"{y}-Q{q}"
                all_quarterly_spinoffs[t][q_key] = all_quarterly_spinoffs[t].get(q_key, 0.0) + d
                all_annual_spinoffs[t][y] = all_annual_spinoffs[t].get(y, 0.0) + d

    # A filing dated on a distribution's ex-date values the parent BEFORE the child
    # separated, so that endpoint observation still carries the entitlement. The engine
    # credits the child separately at the same endpoint, so the parent's value must have
    # it deducted or the same wealth is counted twice.
    #
    # The 1996-12-31 Schedule of Investments is the case that made this visible: it values
    # AT&T Corp cum-NCR, and the contemporaneous quote in att_1996_endpoint_valuations.json
    # -- 43.375 against the filing's 43.50, one tick apart -- states explicitly that it
    # carries the entitlement. Were the filed price ex-NCR, the cum value would be 45.60, a
    # 2.20 gap between two same-day valuations of one security.
    #
    # Until #108 this ran on the ANNUAL series alone, and named NCR explicitly. That left
    # the quarterly series carrying both 1996 entitlements: Q4 the same cum-NCR value, and
    # Q3 the SEI September-30 value, which is cum-Lucent on the same argument -- the fund
    # holds 9,000 Lucent shares against an entitlement of 222,699 x 0.324084 = 72,173, so
    # it had not booked the distribution. engine/data_loader.py prefers the quarterly file,
    # so the corrected annual value was never reached on that path.
    #
    # The test is the date, not the ticker: an endpoint carries an entitlement exactly when
    # the child went ex on the endpoint's own observation date. Lucent needs no deduction
    # from the ANNUAL series for the same reason -- it went ex a quarter before the
    # December filing date, so the year-end quote is already clear of it.
    #
    # Restricted to constituents priced from filings. A vendor series arrives already
    # adjusted for the distribution, and deducting there would subtract it twice.
    #
    # The deducted amount is not a choice. To conserve the quoted wealth it must equal
    # exactly what the engine credits, which is the converted figure computed above.
    quarter_end_suffix = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}

    def deduct_entitlement(series, key, event, ticker, label):
        """Replace a cum-distribution endpoint with its parent-only value."""
        cum_value = series[key]
        parent_value = round(cum_value - event["distribution_per_share"], 4)
        if parent_value <= 0:
            raise ValueError(
                f"{ticker} {label} post-distribution value must be positive: "
                f"{cum_value} - {event['distribution_per_share']} = {parent_value}"
            )
        series[key] = parent_value
        return parent_value

    reconciled = 0
    for ticker in sorted(spinoffs_data):
        if ticker not in DERIVED_NAMES:
            continue
        for event in spinoffs_data[ticker]:
            year = int(event["year"])
            quarter = int(event["quarter"])
            ex_date = event["ex_date"]

            annual_series = all_prices_data.get(ticker, {})
            if ex_date == f"{year}-12-31" and str(year) in annual_series:
                deduct_entitlement(annual_series, str(year), event, ticker, str(year))
                reconciled += 1

            period = f"{year}-Q{quarter}"
            quarterly_series = all_quarterly_prices_data.get(ticker, {})
            if ex_date == f"{year}-{quarter_end_suffix[quarter]}" and period in quarterly_series:
                deduct_entitlement(quarterly_series, period, event, ticker, period)
                reconciled += 1

    if reconciled:
        print(f"Reconciled {reconciled} endpoint(s) carrying a distribution entitlement")

    # 3. Build S&P 500 constituents
    sp500_constituents: Dict[str, List[dict]] = {}
    for year in range(1994, 2025):
        str_year = str(year)
        tickers = YEAR_CONSTITUENTS[year]
        weights = HISTORICAL_INDEX_WEIGHTS[year]

        c_list = []
        for rank, ticker in enumerate(tickers):
            weight = weights[rank]
            # A constituent read from an audited roster may be priced from a derived
            # series rather than a vendor file, so both name maps are consulted.
            name = SP500_NAMES.get(ticker) or DERIVED_NAMES[ticker]
            p_curr = all_prices_data[ticker].get(str_year)
            p_prev = all_prices_data[ticker].get(str(year - 1))
            div = all_dividends_data.get(ticker, {}).get(str_year, 0.0)
            spinoff_dist = all_annual_spinoffs.get(ticker, {}).get(year, 0.0)
            # None (not 0.0) when the trailing window is not computable: an imputed
            # 0.0 outranks every genuine loser in a down year on fabricated evidence.
            ret_1y = (
                round((p_curr - p_prev + div + spinoff_dist) / p_prev, 4)
                if (p_curr is not None and p_prev is not None and p_prev > 0)
                else None
            )

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
            p_curr = all_prices_data[ticker].get(str_year)
            p_prev = all_prices_data[ticker].get(str(year - 1))
            div = all_dividends_data.get(ticker, {}).get(str_year, 0.0)
            spinoff_dist = all_annual_spinoffs.get(ticker, {}).get(year, 0.0)
            # None (not 0.0) when the trailing window is not computable: an imputed
            # 0.0 outranks every genuine loser in a down year on fabricated evidence.
            ret_1y = (
                round((p_curr - p_prev + div + spinoff_dist) / p_prev, 4)
                if (p_curr is not None and p_prev is not None and p_prev > 0)
                else None
            )

            c_list.append({
                "ticker": ticker,
                "name": name,
                "market_cap_weight": weight,
                "trailing_1y_return": ret_1y,
                "year": year,
            })
        world_constituents[str_year] = c_list

    # 5. Build Quarterly constituents (pluggable, re-anchoring at Q4)
    # The quarterly path derives from the same audited rosters as the annual one, minus
    # any constituent with no quarterly price. Constituents recovered from the audited
    # rosters are priced from December-31 filings only (4.3.12), so they have no Q1-Q3
    # observation to drift from and selecting one raises on a missing quarterly price.
    #
    # Dropping them leaves the quarterly universe a SUBSET of the annual one, which is
    # what the zero-lookahead invariant requires: every quarterly candidate must appear in
    # the prior year-end roster. Building the two from different roster sources instead
    # would put them in disagreement, which that invariant correctly rejects.
    #
    # A constituent is a candidate for `year` only where it can be priced at every quarter
    # that year could hold it. engine/backtest.py values every open position at every
    # quarter end BEFORE selection runs (backtest.py:180), so the requirement is the four
    # quarters of `year` plus the following Q1: a constituent bought at Q4 is still held
    # when the next year's first valuation happens, and declining to select it then does
    # not help, because it is already held. The following Q1 is not required in the final
    # year, which liquidates rather than carrying a position forward.
    #
    # Asking only for SOME quarter of `year`, as this did, is what made partial coverage
    # unsafe: the constituent was kept for the year, carried at its stale undrifted
    # prior-year-end weight wherever a quarter was missing, and then raised KeyError at
    # data_loader.py:445 if it won a slot. Every ticker priced from a vendor file already
    # satisfies the stricter rule, so this narrows nothing that was previously sound.
    quarterly_year_constituents, quarterly_index_weights = {}, {}
    horizon = {
        key
        for series in all_quarterly_prices_data.values()
        for key in series
    }
    first_year = min(YEAR_CONSTITUENTS, key=int)
    for year, tickers in YEAR_CONSTITUENTS.items():
        weights = HISTORICAL_INDEX_WEIGHTS[year]
        # A roster year is consumed at two places: it re-anchors ITS OWN Q4, and it is the
        # zero-lookahead candidate list for the NEXT year's Q1-Q3 (line 401), which drift
        # from its Q4 price. So the year's roster must be priceable at its own Q4 and
        # through all four quarters of the following year -- the fourth because a
        # constituent absent from the next roster stops being a target at that Q4 and is
        # sold there, which still needs a price.
        #
        # Consecutive roster years chain: year Y+1 carries its own Q4 and Y+2's quarters,
        # so a constituent held across several years is priced at every quarter in
        # between, and the last roster it appears in covers the quarter it is sold at.
        required = {f"{year}-Q4"} | {f"{int(year) + 1}-Q{q}" for q in (1, 2, 3, 4)}
        # The earliest roster year is consumed twice over. build_quarterly_constituents
        # falls back to the CURRENT year's roster when there is no prior one (line 401),
        # so the first year supplies its own Q1-Q3 as well as its Q4. A constituent
        # admitted there can be bought at Q1 and must therefore be priceable at Q2 and Q3
        # of that same year -- which is why 1994-Q3, with no September-30 filing behind it
        # in any filer, keeps a 1994-only constituent out however well 1995 is covered.
        if year == first_year:
            required |= {f"{year}-Q{q}" for q in (1, 2, 3)}
        required &= horizon
        kept = [
            (ticker, weight)
            for ticker, weight in zip(tickers, weights)
            if required <= set(all_quarterly_prices_data.get(ticker, {}))
        ]
        quarterly_year_constituents[year] = [t for t, _ in kept]
        quarterly_index_weights[year] = [w for _, w in kept]

    sp500_quarterly_constituents = build_quarterly_constituents(
        quarterly_year_constituents,
        quarterly_index_weights,
        all_quarterly_prices_data,
        "^GSPC",
        SP500_NAMES,
        all_quarterly_dividends_data,
        all_quarterly_spinoffs,
    )
    world_quarterly_constituents = build_quarterly_constituents(
        WORLD_YEAR_CONSTITUENTS,
        WORLD_HISTORICAL_WEIGHTS,
        all_quarterly_prices_data,
        "^GSPC",
        NAMES,
        all_quarterly_dividends_data,
        all_quarterly_spinoffs,
    )

    # 6. Build S&P 500 subsets for exact backward compatibility
    BENCHMARK_PRICE_KEYS = [
        "^GSPC", "^SP500TR", "^MSCIWORLD_PR", "^MSCIWORLD_TR", "FBGRX", "FBGRX_TR", "^NDX", "^NDXT"
    ]
    constituent_keys = sorted(set(SP500_NAMES) | set(DERIVED_NAMES))
    sp500_prices = {
        k: all_prices_data[k]
        for k in BENCHMARK_PRICE_KEYS + constituent_keys
        if k in all_prices_data
    }
    sp500_dividends = {
        k: all_dividends_data[k]
        for k in constituent_keys
        if k in all_dividends_data
    }
    # constituent_keys, not SP500_NAMES alone: the derived constituents now carry Q2 and Q3
    # observations (issue #63), and filtering them out here would publish a quarterly
    # candidate the quarterly price file cannot price. The annual subset above has always
    # included them; this keeps the two symmetric.
    sp500_quarterly_prices = {
        k: all_quarterly_prices_data[k]
        for k in BENCHMARK_PRICE_KEYS + constituent_keys
        if k in all_quarterly_prices_data
    }
    sp500_quarterly_dividends = {
        k: all_quarterly_dividends_data[k]
        for k in constituent_keys
        if k in all_quarterly_dividends_data
    }

    # 7. Compile spinoff distributions from raw corporate actions.
    # Written from the in-memory catalog, whose distributions have been converted into
    # final share terms above. Re-reading the raw file here would ship the as-traded
    # values to the engine and silently undo that conversion.
    if spinoffs_data:
        with open(DATA_DIR / "spinoff_distributions.json", "w", encoding="utf-8") as f:
            json.dump(spinoffs_data, f, indent=2)
        print(f"Compiled spinoff distributions to {DATA_DIR / 'spinoff_distributions.json'}")

    # 7b. Compile terminal actions from raw corporate actions (issue #56).
    #
    # The raw file records what a holder of one share received when each constituent
    # stopped trading. What the engine needs on top of that is a period to act in and, for
    # a stock conversion, a value per share -- neither of which is a figure any filing
    # states, so both are derived here and labelled with the basis they were derived on.
    #
    # Share terms need no conversion. Every one of these series is adjusted to its own
    # final observation (4.3.9), and every split on record for these registrants precedes
    # that observation, so a held share IS an as-traded share on the effective date and the
    # filing's cash amounts and exchange ratios apply to it directly. The spinoff catalog
    # needs the conversion above because its distributions predate a later split; a
    # terminal action, by construction, has nothing after it.
    compiled_terminal_actions: Dict[str, dict] = {}
    for ticker, action in sorted(TERMINAL_ACTIONS.items()):
        effective_date = action["effective_date"]
        year = int(effective_date[:4])
        quarter = (int(effective_date[5:7]) - 1) // 3 + 1

        record = {
            "effective_date": effective_date,
            "year": year,
            "quarter": quarter,
            "consideration_type": action["consideration_type"],
            "cash_per_share": action.get("cash_per_share"),
            "stock_exchange_ratio": action.get("stock_exchange_ratio"),
            "acquirer_ticker": action.get("acquirer_ticker"),
            "accession_number": action["accession_number"],
        }

        # A stock conversion has to be marked at some value per share, and no filing states
        # one: the exchange ratio is in the acquirer's shares, whose series is adjusted to
        # 2024-12-31 while this one is adjusted to its own final observation. Converting
        # between the two bases would mean deriving an adjustment factor per acquirer, and
        # for BP and Shell no such factor exists -- neither appears in any archived
        # schedule, both being non-US. So the position's VALUE is carried across the
        # conversion instead, and the only question is what that value was.
        has_stock_leg = action["consideration_type"] in ("stock", "cash_and_stock")

        for frequency, kept, withheld in (
            ("annual", all_prices_data.get(ticker, {}), withheld_annual_prices.get(ticker, {})),
            (
                "quarterly",
                all_quarterly_prices_data.get(ticker, {}),
                withheld_quarterly_prices.get(ticker, {}),
            ),
        ):
            value, basis, source_period = None, None, None

            # Only a stock leg needs a derived value. Where the filing states the
            # consideration outright -- a cash amount, or nothing at all for the two
            # bankruptcies -- that figure is the terminal value and is already on the
            # record above; deriving a second one here would put a number next to it that
            # looks like what the holder received and is not.
            if has_stock_leg:
                # A schedule filed within days of the effective date reports what the
                # holder received, so it is the terminal value itself rather than an
                # estimate of it.
                in_window = sorted(
                    (period for period in withheld
                     if _days_between(effective_date, _period_end_date(period))
                     <= TERMINAL_OBSERVATION_WINDOW_DAYS),
                    key=_period_end_date,
                )
                if in_window:
                    source_period = in_window[0]
                    value = withheld[source_period]
                    basis = "filing_observed"
                else:
                    on_or_before = [p for p in kept if _period_end_date(p) <= effective_date]
                    if on_or_before:
                        source_period = max(on_or_before, key=_period_end_date)
                        value = kept[source_period]
                        basis = "last_observed_price"

            record[frequency] = {
                "stock_leg_value_per_share": value,
                "stock_leg_value_basis": basis,
                "source_period": source_period,
                "withheld_observations": dict(sorted(withheld.items())),
            }

        compiled_terminal_actions[ticker] = record

    if compiled_terminal_actions:
        with open(DATA_DIR / "terminal_actions.json", "w", encoding="utf-8") as f:
            json.dump(compiled_terminal_actions, f, indent=2)
        withheld_count = sum(
            len(rec[freq]["withheld_observations"])
            for rec in compiled_terminal_actions.values()
            for freq in ("annual", "quarterly")
        )
        print(
            f"Compiled {len(compiled_terminal_actions)} terminal actions to "
            f"{DATA_DIR / 'terminal_actions.json'} "
            f"({withheld_count} post-removal price observations withheld)"
        )

    # 8. Save S&P 500 datasets to data/
    with open(DATA_DIR / "sp500_prices.json", "w", encoding="utf-8") as f:
        json.dump(sp500_prices, f, indent=2)

    with open(DATA_DIR / "sp500_dividends.json", "w", encoding="utf-8") as f:
        json.dump(sp500_dividends, f, indent=2)

    with open(DATA_DIR / "sp500_constituents.json", "w", encoding="utf-8") as f:
        json.dump(sp500_constituents, f, indent=2)

    with open(DATA_DIR / "sp500_quarterly_prices.json", "w", encoding="utf-8") as f:
        json.dump(sp500_quarterly_prices, f, indent=2)

    with open(DATA_DIR / "sp500_quarterly_dividends.json", "w", encoding="utf-8") as f:
        json.dump(sp500_quarterly_dividends, f, indent=2)

    with open(DATA_DIR / "sp500_quarterly_constituents.json", "w", encoding="utf-8") as f:
        json.dump(sp500_quarterly_constituents, f, indent=2)

    # 8. Save All-World datasets to data/
    with open(DATA_DIR / "world_prices.json", "w", encoding="utf-8") as f:
        json.dump(all_prices_data, f, indent=2)

    with open(DATA_DIR / "world_dividends.json", "w", encoding="utf-8") as f:
        json.dump(all_dividends_data, f, indent=2)

    with open(DATA_DIR / "world_constituents.json", "w", encoding="utf-8") as f:
        json.dump(world_constituents, f, indent=2)

    with open(DATA_DIR / "world_quarterly_prices.json", "w", encoding="utf-8") as f:
        json.dump(all_quarterly_prices_data, f, indent=2)

    with open(DATA_DIR / "world_quarterly_dividends.json", "w", encoding="utf-8") as f:
        json.dump(all_quarterly_dividends_data, f, indent=2)

    with open(DATA_DIR / "world_quarterly_constituents.json", "w", encoding="utf-8") as f:
        json.dump(world_quarterly_constituents, f, indent=2)

    print("Saved clean, verified corporate actions & S&P 500 datasets (annual & quarterly):")
    print(f" - {DATA_DIR / 'spinoff_distributions.json'}")
    print(f" - {DATA_DIR / 'sp500_prices.json'}")
    print(f" - {DATA_DIR / 'sp500_dividends.json'}")
    print(f" - {DATA_DIR / 'sp500_constituents.json'}")
    print(f" - {DATA_DIR / 'sp500_quarterly_prices.json'}")
    print(f" - {DATA_DIR / 'sp500_quarterly_dividends.json'}")
    print(f" - {DATA_DIR / 'sp500_quarterly_constituents.json'}")

    print("Saved clean, verified All-World datasets (annual & quarterly):")
    print(f" - {DATA_DIR / 'world_prices.json'}")
    print(f" - {DATA_DIR / 'world_dividends.json'}")
    print(f" - {DATA_DIR / 'world_constituents.json'}")
    print(f" - {DATA_DIR / 'world_quarterly_prices.json'}")
    print(f" - {DATA_DIR / 'world_quarterly_dividends.json'}")
    print(f" - {DATA_DIR / 'world_quarterly_constituents.json'}")


if __name__ == "__main__":
    main()
