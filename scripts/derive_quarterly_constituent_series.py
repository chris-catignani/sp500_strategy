"""Derive quarter-end price series for constituents that have no vendor price file.

Zero external dependencies - Python 3 standard library only.

The Q4 counterpart is derive_constituent_series.py, which reads the audited December-31
rosters. This reads two quarters, from two filers, by the same value/shares quotient and
through the same issuer-to-ticker map:

  Q2  Vanguard 500 Index Fund semi-annual (June 30), via
      extract_vanguard_semiannual_rosters.py. Values in THOUSANDS. UNAUDITED.
  Q3  SPDR S&P 500 Trust annual (September 30), already archived, via
      extract_ground_truth_from_sec.parse_n30d_filing. Values in EXACT DOLLARS. AUDITED,
      because September 30 is SPY's fiscal year end from 1997, so its September report is
      the annual one and carries a Report of Independent Accountants.

The two differ in unit and in grade, and both differences are handled explicitly rather
than averaged over: the unit in the quotient, the grade in a per-observation flag.

Why this exists: constituents recovered from the audited rosters were priced from
December-31 filings only, so they had no Q1-Q3 observation and were dropped from the
quarterly universe entirely, leaving the quarterly path carrying a survivorship bias the
annual path no longer has. See issue #63.

GRADE. Every observation carries an `audited` flag. Q2 is false and Q3 is true, and a Q4
observation from derive_constituent_series.py is audited. The flag is recorded per
observation rather than per dataset, so a consumer reading a single price can tell which
grade it is holding without knowing which quarter it came from.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.derive_constituent_series import _split_factor, normalise
from scripts.extract_ground_truth_from_sec import (
    FILINGS_DIR,
    N30D_HISTORICAL_FILINGS,
    parse_n30d_filing,
)

ROSTERS_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "vanguard_semiannual_rosters.json"
SEI_Q1_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sei_q1_rosters.json"
SEI_Q3_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "sei_q3_rosters.json"
PRUDENTIAL_Q1_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "prudential_q1_rosters.json"
ANNUAL_ROSTERS_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "vanguard_audited_rosters.json"
MAP_PATH = PROJECT_ROOT / "data" / "raw" / "constituents" / "issuer_ticker_map.json"
SPLITS_PATH = PROJECT_ROOT / "data" / "raw" / "corporate_actions" / "splits.json"
TICKERS_DIR = PROJECT_ROOT / "data" / "raw" / "tickers"
OUTPUT_PATH = (
    PROJECT_ROOT / "data" / "raw" / "ground_truth" / "derived_quarterly_constituent_series.json"
)


def _q3_rosters() -> Dict[str, Dict[str, Any]]:
    """SPY September-30 schedules, normalised to the shape the Q2 rosters use.

    SPY reports position values in exact dollars where Vanguard reports thousands, so the
    value is divided back by 1000 here rather than special-casing the quotient below. That
    keeps one derivation path for both filers and puts the unit difference in one place.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for period, filename, accession, _form, report_date, _filed in N30D_HISTORICAL_FILINGS:
        if not period.endswith("-Q3"):
            continue
        parsed = parse_n30d_filing(FILINGS_DIR / filename)
        out[period] = {
            "report_date": report_date,
            "accession_number": accession,
            "source_file": f"data/raw/ground_truth/sec_filings/{filename}",
            "audited": True,
            "holdings": [
                {
                    "rank": h["rank"],
                    "name": h["name"],
                    "shares": h["shares"],
                    "value_usd_thousands": h["val"] / 1000.0,
                }
                for h in parsed["holdings"]
            ],
        }
    return out


def _resolve(name: str, period: str, issuer_map: Dict[str, str]) -> Any:
    """Name to ticker, with the one string that changes registrant mid-series.

    SEI writes "AT&T" for AT&T Corp through its 2005 schedule, listing SBC Communications
    separately on the same page. SBC renamed itself AT&T Inc. in November 2005, so in the
    2006 schedule "AT&T" is that registrant and the SBC line is gone. The string is
    therefore resolved by period: T_CORP while Ma Bell was filing under it, and T -- which
    has a vendor price file and is skipped by the caller -- afterwards. A single map entry
    could only assert one of the two, and asserting T_CORP would extend its series a year
    past the registrant's existence. See docs/DATA_PROVENANCE.md 4.5.
    """
    if name == normalise("AT&T"):
        return "T_CORP" if period < "2006" else "T"
    return issuer_map.get(name)


def _q1_rosters() -> Dict[str, Dict[str, Any]]:
    """March-31 schedules, SEI preferred over Prudential where both filed (issue #63).

    Both filers already publish holdings in the shape this module consumes, so no unit
    conversion happens here: SEI reports thousands natively, and the Prudential extractor
    divides its exact-dollar values by 1000.0 as a float rather than truncating them.

    SEI wins the two overlapping periods because its March-31 statement of net assets is
    AUDITED -- its Report of Independent Accountants covers the schedule at that date and
    confirms the securities with the custodian. Prudential carries no auditor's report at
    all. The displaced Prudential rosters are not discarded: they are the independent
    second opinion in _cross_filer_check below.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for path in (PRUDENTIAL_Q1_PATH, SEI_Q1_PATH):  # SEI second, so it overwrites
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            for period, roster in json.load(f)["rosters_by_period"].items():
                out[period] = roster
    return out


def _q4_rosters() -> Dict[str, Dict[str, Any]]:
    """December-31 schedules from the audited Vanguard annual filings (4.3.10).

    The same rosters already price these constituents annually through
    derive_constituent_series.py, which merges into the ANNUAL dataset keyed by year. The
    quarterly path never saw them, so a constituent had no Q4 in its quarterly series and
    could not satisfy a rule that asks for every quarter it might be held at. This reads
    the same archived filings a second time and keys them as Q4.
    """
    if not ANNUAL_ROSTERS_PATH.exists():
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    with open(ANNUAL_ROSTERS_PATH, "r", encoding="utf-8") as f:
        for year, roster in json.load(f)["rosters_by_year"].items():
            out[f"{year}-Q4"] = {**roster, "audited": True}
    return out


def _sei_q3_rosters() -> Dict[str, Dict[str, Any]]:
    """September-30 schedules from SEI's semi-annual report.

    SEI's fiscal year ends March 31, so its September report is the SEMI-ANNUAL and is
    UNAUDITED -- the opposite grade to the March-31 filings this same trust supplies Q1
    from, and not a contradiction: one filer, two reports, one of which an accountant
    opines on. Read from the filings rather than from a form type: none carries a Report
    of Independent Accountants, and each marks its statement of net assets (UNAUDITED) on
    the heading itself.

    What SEI uniquely supplies is 1995-Q3 and 1996-Q3, which precede SPY's archive. Those
    two quarters were the reason five constituents could never be priced through a roster
    year: a roster year needs all four quarters of the FOLLOWING year, so roster 1994
    needed 1995-Q3 and roster 1995 needed 1996-Q3.
    """
    if not SEI_Q3_PATH.exists():
        return {}
    with open(SEI_Q3_PATH, "r", encoding="utf-8") as f:
        return dict(json.load(f)["rosters_by_period"])


def _compare_filers(
    rosters_a: Dict[str, Any],
    rosters_b: Dict[str, Any],
    key_a: str,
    key_b: str,
    issuer_map: Dict[str, str],
    published: str,
    note: str,
) -> Dict[str, Any]:
    """Price the same issuer on the same date from two independent filings."""

    def priced(roster: Dict[str, Any]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for h in roster["holdings"]:
            if h.get("no_value_printed") or h["shares"] <= 0:
                continue
            ticker = issuer_map.get(normalise(h["name"]))
            if ticker:
                out[ticker] = h["value_usd_thousands"] * 1000.0 / h["shares"]
        return out

    periods = sorted(set(rosters_a) & set(rosters_b))
    comparisons = []
    for period in periods:
        a, b = priced(rosters_a[period]), priced(rosters_b[period])
        for ticker in sorted(set(a) & set(b)):
            if b[ticker] <= 0:
                continue
            comparisons.append(
                {
                    "period": period,
                    "ticker": ticker,
                    f"{key_a}_price_usd": round(a[ticker], 4),
                    f"{key_b}_price_usd": round(b[ticker], 4),
                    "difference_usd": round(a[ticker] - b[ticker], 4),
                    "relative_difference": round(abs(a[ticker] - b[ticker]) / b[ticker], 6),
                }
            )
    worst = max(comparisons, key=lambda c: c["relative_difference"], default=None)
    return {
        "note": note,
        "overlapping_periods": periods,
        "published_source": published,
        "issuers_compared": len(comparisons),
        "max_relative_difference": worst["relative_difference"] if worst else None,
        "worst_pair": worst,
        "comparisons": comparisons,
    }


def _cross_filer_check(issuer_map: Dict[str, str]) -> Dict[str, Any]:
    """Every quarter that two independent filers can both price, checked.

    Two filers pricing the same issuer on the same date is a stronger check than
    reconciliation, which proves a schedule was read completely and not that the RIGHT
    schedule was read. Q1 and Q3 each have two filers; Q2 and Q4 have one, and there a
    parse error and a true price move still look alike.

    Agreement is not expected to be exact anywhere. Value is reported in whole thousands,
    so the implied price is coarser for a smaller fund: SEI's S&P 500 Index Portfolio is a
    fraction of SPY's size, and the residual is that rounding rather than a disagreement
    about the price.
    """
    checks: Dict[str, Any] = {}

    if SEI_Q1_PATH.exists() and PRUDENTIAL_Q1_PATH.exists():
        with open(SEI_Q1_PATH, "r", encoding="utf-8") as f:
            sei_q1 = json.load(f)["rosters_by_period"]
        with open(PRUDENTIAL_Q1_PATH, "r", encoding="utf-8") as f:
            pru = json.load(f)["rosters_by_period"]
        checks["Q1"] = _compare_filers(
            sei_q1, pru, "sei", "prudential", issuer_map,
            "SEI Index Funds (audited)",
            (
                "Ten of Prudential's thirteen filings are refused by its extractor, so the "
                "overlap is two years rather than the eleven both filers cover on paper. "
                "The refusals are recorded in prudential_q1_rosters.json."
            ),
        )

    sei_q3 = _sei_q3_rosters()
    if sei_q3:
        checks["Q3"] = _compare_filers(
            _q3_rosters(), sei_q3, "spy", "sei", issuer_map,
            "SPDR S&P 500 Trust (audited)",
            (
                "SPY is the published source because September 30 is its fiscal year end "
                "from 1997, making its September report the annual one; SEI's is the "
                "semi-annual and unaudited. SEI uniquely supplies 1995-Q3 and 1996-Q3, "
                "which precede SPY's archive and so are checked by nothing."
            ),
        )

    return checks


def derive() -> Dict[str, Any]:
    with open(ROSTERS_PATH, "r", encoding="utf-8") as f:
        rosters = json.load(f)["rosters_by_period"]
    # Order matters where two filers cover one period: the LAST one wins. SPY is loaded
    # after SEI's September schedules because SPY is audited at that date and SEI is not.
    rosters = {
        **rosters,
        **_sei_q3_rosters(),
        **_q3_rosters(),
        **_q1_rosters(),
        **_q4_rosters(),
    }
    with open(MAP_PATH, "r", encoding="utf-8") as f:
        issuer_map = {normalise(k): v for k, v in json.load(f)["map"].items()}
    with open(SPLITS_PATH, "r", encoding="utf-8") as f:
        split_records = json.load(f)["splits_by_ticker"]

    observations: Dict[str, Dict[str, Any]] = {}
    for period in sorted(rosters):
        roster = rosters[period]
        for holding in roster["holdings"]:
            if (
                holding.get("unidentified")
                or holding.get("no_value_printed")
                or holding["shares"] <= 0
                or holding["value_usd_thousands"] <= 0
            ):
                continue
            ticker = _resolve(normalise(holding["name"]), period, issuer_map)
            if ticker is None:
                continue
            # A vendor file is the authoritative source where one exists; deriving over it
            # would give one constituent two series adjusted to different bases.
            if (TICKERS_DIR / f"{ticker}.json").exists():
                continue

            price = holding["value_usd_thousands"] * 1000.0 / holding["shares"]
            entry = {
                "price_usd": round(price, 2),
                "matched_name": holding["name"],
                "rank": holding["rank"],
                "shares": holding["shares"],
                "value_usd_thousands": holding["value_usd_thousands"],
                "report_date": roster["report_date"],
                "accession_number": roster["accession_number"],
                "source_file": roster["source_file"],
                "audited": roster["audited"],
            }
            record = split_records.get(ticker)
            if record is not None:
                factor = _split_factor(record["splits"], roster["report_date"])
                entry["split_factor"] = round(factor, 6)
                entry["split_adjusted_price_usd"] = round(price / factor, 4)
                entry["split_source_accession"] = record["accession_number"]
            observations.setdefault(ticker, {})[period] = entry

    unadjusted = sorted(t for t in observations if t not in split_records)
    return {
        "description": (
            "Quarter-end price series for S&P 500 constituents with no vendor price file, "
            "derived as market value divided by share count from the March-31 schedules of "
            "SEI Index Funds and Prudential (Q1), the Vanguard June-30 semi-annual rosters "
            "(Q2), the SPY September-30 annual filings (Q3) and the Vanguard December-31 "
            "annual rosters (Q4)."
        ),
        "sources": {
            "Q1": (
                "data/raw/ground_truth/sei_q1_rosters.json (1995-2003, 2005-2006) and "
                "data/raw/ground_truth/prudential_q1_rosters.json (1994). 2004 has no Q1 "
                "from either filer: SEI's schedule is corrupt as filed -- its Microsoft "
                "value reads '0,600' in EDGAR's own bytes, short by exactly the 40,000k "
                "the reconciliation misses -- and Prudential's 2004 is the HTML era its "
                "extractor refuses. Reconstructing the missing digit from the "
                "reconciliation gap would be an inferred figure wearing a filing's "
                "provenance, so the year is absent instead."
            ),
            "Q2": "data/raw/ground_truth/vanguard_semiannual_rosters.json",
            "Q3": "SPY September-30 annual filings in data/raw/ground_truth/sec_filings/",
            "Q4": "data/raw/ground_truth/vanguard_audited_rosters.json",
        },
        "issuer_resolution": "data/raw/constituents/issuer_ticker_map.json",
        "split_records": "data/raw/corporate_actions/splits.json",
        "grade": (
            "MIXED, recorded per observation in the audited flag. Audited: Q1 from 1995 "
            "(SEI's Report of Independent Accountants covers its March-31 statement of net "
            "assets and confirms the securities with the custodian), Q3 (September 30 is "
            "SPY's fiscal year end from 1997) and Q4 (December 31 is Vanguard's). "
            "Unaudited: Q2, Vanguard's semi-annual, and Q1 1994 alone, which comes from "
            "Prudential because SEI's series starts in 1995. Do not read these as one "
            "grade. Audit status here was read out of each filing; the submissions API's "
            "fiscalYearEnd reports 0930 for SEI and is wrong for that trust."
        ),
        "cross_filer_validation": _cross_filer_check(issuer_map),
        "adjustment_status": (
            "price_usd is AS-TRADED. split_adjusted_price_usd is present only where a "
            "filing-cited split record exists, and is expressed in the share terms of "
            "that registrant's final observation rather than of 2024-12-31, so it is NOT "
            "directly comparable to the series in data/raw/tickers/."
        ),
        "tickers_without_a_split_record": unadjusted,
        "series_by_ticker": observations,
    }


def main() -> None:
    data = derive()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    series = data["series_by_ticker"]
    total = sum(len(v) for v in series.values())
    audited = sum(1 for v in series.values() for o in v.values() if o["audited"])
    by_quarter: Dict[str, int] = {}
    for obs in series.values():
        for period in obs:
            by_quarter[period[-2:]] = by_quarter.get(period[-2:], 0) + 1
    print(
        f"{total} observations across {len(series)} tickers "
        f"({audited} audited, {total - audited} unaudited; "
        + ", ".join(f"{q} {by_quarter[q]}" for q in sorted(by_quarter))
        + ")"
    )
    for ticker in sorted(series):
        periods = sorted(series[ticker])
        print(f"  {ticker:8s} {len(periods):2d}  {periods[0]} .. {periods[-1]}")
    print(f"Written: {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
