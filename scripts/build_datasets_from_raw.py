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
DERIVED_SOURCE_KEYS = {"VIA": "VIA.B"}

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

# Load historical constituents and factsheet weights directly from raw archives
with open(RAW_DIR / "constituents" / "historical_index_weights.json", "r", encoding="utf-8") as f:
    raw_sp500 = json.load(f)
YEAR_CONSTITUENTS = {int(k): v for k, v in raw_sp500["constituents_by_year"].items()}
HISTORICAL_INDEX_WEIGHTS = {int(k): v for k, v in raw_sp500["weights_by_year"].items()}

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

                t_prices = quarterly_prices.get(t, {})
                p_base = t_prices.get(f"{year - 1}-Q4")
                p_curr = t_prices.get(q_key)
                p_1y_prior = t_prices.get(f"{year - 1}-Q{q}")

                if p_curr is not None and p_base is not None and p_base > 0:
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

        if ticker == "T":
            t_corp_file = RAW_DIR / "tickers" / "T_CORP_HISTORICAL.json"
            if not t_corp_file.exists():
                raise FileNotFoundError(f"Missing required historical decoupled series: {t_corp_file}")
            t_corp_chart = load_raw_chart(t_corp_file)
            t_corp_prices = extract_year_end_closes(t_corp_chart)
            t_corp_divs = extract_annual_dividends(t_corp_chart)
            t_corp_q_prices = extract_quarterly_closes(t_corp_chart)
            t_corp_q_divs = extract_quarterly_dividends(t_corp_chart)

            # Strip pre-1999 SBC data so pre-1999 strictly originates from T_CORP_HISTORICAL
            ticker_prices = {k: v for k, v in ticker_prices.items() if int(k) > 1998}
            ticker_divs = {k: v for k, v in ticker_divs.items() if int(k) > 1998}
            ticker_q_prices = {k: v for k, v in ticker_q_prices.items() if int(k.split("-")[0]) > 1998}
            ticker_q_divs = {k: v for k, v in ticker_q_divs.items() if int(k.split("-")[0]) > 1998}

            for yr_str, price in t_corp_prices.items():
                if int(yr_str) <= 1998:
                    ticker_prices[yr_str] = price

            for yr_str, div in t_corp_divs.items():
                if int(yr_str) <= 1998:
                    ticker_divs[yr_str] = div

            for q_key, q_price in t_corp_q_prices.items():
                q_yr = int(q_key.split("-")[0])
                if q_yr <= 1998:
                    ticker_q_prices[q_key] = q_price

            for q_key, q_div in t_corp_q_divs.items():
                q_yr = int(q_key.split("-")[0])
                if q_yr <= 1998:
                    ticker_q_divs[q_key] = q_div

            # The model credits children at distribution-date endpoints. The
            # contemporary parent quotes still include those entitlements, so
            # reconstruct a parent-only value rather than count them twice.
            with open(RAW_DIR / "corporate_actions" / "att_1996_endpoint_valuations.json", encoding="utf-8") as f:
                endpoint_valuations = json.load(f)["observations"]
            with open(RAW_DIR / "corporate_actions" / "spinoffs.json", encoding="utf-8") as f:
                att_events = json.load(f)["T"]
            for observation in endpoint_valuations:
                event, = [e for e in att_events
                          if e["ex_date"] == observation["date"]
                          and e["spinco_ticker"] == observation["spinco_ticker"]]
                parent_value = round(observation["cum_distribution_close"]
                                     - event["distribution_per_share"], 2)
                if parent_value <= 0:
                    raise ValueError("AT&T post-distribution value must be positive")
                year, quarter = observation["year"], observation["quarter"]
                ticker_q_prices[f"{year}-Q{quarter}"] = parent_value
                if quarter == 4:
                    ticker_prices[str(year)] = parent_value

            # Keep chronological key ordering
            ticker_prices = dict(sorted(ticker_prices.items(), key=lambda x: int(x[0])))
            ticker_divs = dict(sorted(ticker_divs.items(), key=lambda x: int(x[0])))
            ticker_q_prices = dict(sorted(ticker_q_prices.items()))
            ticker_q_divs = dict(sorted(ticker_q_divs.items()))

        all_prices_data[ticker] = ticker_prices
        all_dividends_data[ticker] = ticker_divs
        all_quarterly_prices_data[ticker] = ticker_q_prices
        all_quarterly_dividends_data[ticker] = ticker_q_divs

    print(f"Processed prices and dividends for {len(NAMES)} tickers ({len(SP500_NAMES)} SP500, {len(NON_US_NAMES)} Non-US).")

    # Constituents with no vendor price series (issue #55). Their year-end prices are
    # derived from Vanguard Index Trust Schedules of Investments as value / shares and
    # split-adjusted from filing-cited records, so they are merged from a second input
    # rather than read from data/raw/tickers/. The T_CORP_HISTORICAL splice above is the
    # existing precedent for a conditional second source.
    derived_path = RAW_DIR / "ground_truth" / "vanguard_implied_prices.json"
    derived_merged = 0
    if derived_path.exists():
        with open(derived_path, "r", encoding="utf-8") as f:
            derived = json.load(f)["prices_by_ticker"]

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
            all_prices_data[ticker] = dict(sorted(series.items(), key=lambda kv: int(kv[0])))
            # No dividend history is derived for these issuers. Schedules of Investments
            # report holdings, not distributions, so an empty series is the honest value;
            # a zero-filled one would understate total return without saying so.
            all_dividends_data.setdefault(ticker, {})
            derived_merged += 1

        print(
            f"Merged {derived_merged} derived constituent series from "
            f"{derived_path.relative_to(REPO_ROOT)}"
        )

    # Load raw spinoff distributions for total return calculations
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
                d = float(ev["distribution_per_share"])
                q_key = f"{y}-Q{q}"
                all_quarterly_spinoffs[t][q_key] = all_quarterly_spinoffs[t].get(q_key, 0.0) + d
                all_annual_spinoffs[t][y] = all_annual_spinoffs[t].get(y, 0.0) + d

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
    sp500_quarterly_constituents = build_quarterly_constituents(
        YEAR_CONSTITUENTS,
        HISTORICAL_INDEX_WEIGHTS,
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
    sp500_quarterly_prices = {
        k: all_quarterly_prices_data[k]
        for k in BENCHMARK_PRICE_KEYS + sorted(SP500_NAMES.keys())
        if k in all_quarterly_prices_data
    }
    sp500_quarterly_dividends = {
        k: all_quarterly_dividends_data[k]
        for k in sorted(SP500_NAMES.keys())
        if k in all_quarterly_dividends_data
    }

    # 7. Compile spinoff distributions from raw corporate actions
    spinoffs_raw = RAW_DIR / "corporate_actions" / "spinoffs.json"
    if spinoffs_raw.exists():
        with open(spinoffs_raw, "r", encoding="utf-8") as f:
            spinoffs_data = json.load(f)
        with open(DATA_DIR / "spinoff_distributions.json", "w", encoding="utf-8") as f:
            json.dump(spinoffs_data, f, indent=2)
        print(f"Compiled spinoff distributions to {DATA_DIR / 'spinoff_distributions.json'}")

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
