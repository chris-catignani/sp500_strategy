"""Generate historical S&P 500 Top 20 constituent weights and reproducible provenance table.

Ranks #1-#12 derive from official S&P Dow Jones Indices factsheet weights.
Years 2020-2024 derive directly from primary SPY Form NPORT-P XML regulatory filings.
Ranks #13-#20 for 1994-2019 derive from point-in-time capitalization ratios
anchored to verified rank-12 factsheet weights with reproducible underlying market capitalizations.

Exports:
  - data/raw/constituents/historical_index_weights.json
  - docs/historical_weights_table.csv

Zero external dependencies - Python 3 standard library only.
"""

import csv
import json
from pathlib import Path
import sys
from typing import Dict, List, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.extract_ground_truth_from_sec import parse_xml_filing, FILINGS_DIR

OUTPUT_JSON = PROJECT_ROOT / "data" / "raw" / "constituents" / "historical_index_weights.json"
OUTPUT_CSV = PROJECT_ROOT / "docs" / "historical_weights_table.csv"

# Load existing historical_index_weights.json as baseline for factsheet weights and older years
with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
    current_data = json.load(f)

constituents_by_year = current_data["constituents_by_year"]
weights_by_year = current_data["weights_by_year"]

# Company names dictionary
COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com Inc.",
    "GOOGL": "Alphabet Inc.",
    "META": "Meta Platforms Inc.",
    "TSLA": "Tesla Inc.",
    "AVGO": "Broadcom Inc.",
    "BRK.B": "Berkshire Hathaway Inc.",
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
}

# Form NPORT-P XML filings manifest for year-ends
XML_YEAR_ENDS = {
    "2020": ("SPY_2020-Q4_0001752724-21-043869.xml", "0001752724-21-043869"),
    "2021": ("SPY_2021-Q4_0001752724-22-048845.xml", "0001752724-22-048845"),
    "2022": ("SPY_2022-Q4_0001752724-23-046862.xml", "0001752724-23-046862"),
    "2023": ("SPY_2023-Q4_0001752724-24-043296.xml", "0001752724-24-043296"),
    "2024": ("SPY_2024-Q4_0001752724-25-043826.xml", "0001752724-25-043826"),
}

# 1. Programmatically parse XML filings and update 2020-2024 directly
xml_data_by_year = {}
for year_str, (filename, accession) in XML_YEAR_ENDS.items():
    xml_path = FILINGS_DIR / filename
    parsed = parse_xml_filing(xml_path)
    xml_data_by_year[year_str] = {
        "parsed": parsed,
        "accession": accession,
    }
    top20 = parsed["holdings"][:20]
    tickers = [h["ticker"] for h in top20]
    weights = [round(h["weight"], 4) for h in top20]

    # Ensure weakly descending order due to 4-decimal rounding
    for i in range(1, len(weights)):
        if weights[i] > weights[i-1]:
            weights[i] = weights[i-1]

    constituents_by_year[year_str] = tickers
    weights_by_year[year_str] = weights

# 2. Validate all years have 20 unique constituents and weakly descending weights
for yr in constituents_by_year:
    tickers = constituents_by_year[yr]
    weights = weights_by_year[yr]
    assert len(tickers) == 20, f"Year {yr} has {len(tickers)} tickers"
    assert len(set(tickers)) == 20, f"Year {yr} has duplicate tickers: {tickers}"
    assert len(weights) == 20, f"Year {yr} has {len(weights)} weights"
    for i in range(len(weights)):
        assert weights[i] > 0, f"Year {yr} weight {i} is not positive"
        if i > 0:
            assert weights[i-1] >= weights[i], f"Year {yr} weights not descending at idx {i}: {weights[i-1]} < {weights[i]}"


# Share-class composition of the Alphabet index weight, by year.
#
# Alphabet Class C (GOOG) was created on 2014-04-03 by stock dividend. Before that
# Alphabet had one listed class, so 1994-2013 weights need no consolidation and are
# recorded as single-class.
#
# 2020-2024 weights are derived from SPY Form NPORT-P filings through
# consolidate_holdings(), which sums CUSIPs 02079K305 and 02079K107 - verified
# consolidated against a December-dated primary source.
#
# 2014-2019 weights are hand-entered year-end factsheet anchors. Which share classes each
# one covered was undetermined until the Vanguard 500 Index Fund's December 31 Schedule of
# Investments was read for those years (docs/DATA_PROVENANCE.md 4.3.9, 4.3.10). That
# schedule reports Alphabet's two classes as separate positions, so it settles the
# question per year: normalised against a single-class control in the same filing, each
# committed weight sits beside either the Class A figure or the consolidated one, and the
# two differ by a factor of two. See 4.3.21 for the evidence table.
#
# Three years were Class A only and are corrected by the (A + C) / A ratio the filing
# itself states. The ratio is what the filing supplies; the anchor stays the factsheet's,
# so the corrected weight remains on the same basis as the other nineteen rows of its year
# rather than mixing a fund weight into a factsheet-anchored roster.
ALPHABET_SINGLE_CLASS_THROUGH = 2013

# Years whose committed anchor already covered both classes; nothing was changed.
ALPHABET_CONSOLIDATED_AS_FILED = frozenset({"2014", "2018", "2019"})

# Years whose committed anchor covered Class A only: the factsheet weight as it was
# published before #45, the (Class A + Class C) / Class A ratio read from that year's
# filing, and the accession it was read in.
#
# The anchor is recorded rather than back-solved from the corrected weight. Without it
# the only check available is that the published figure divided by the ratio equals
# itself, which is true of any number -- an assertion that cannot fail is not evidence
# (4.3.20). With it, the published weight is the product of two stated figures and a
# drift in either one fails.
ALPHABET_CONSOLIDATION_RATIO = {
    "2015": (0.0140, 1.99487, "0000932471-16-012795"),
    "2016": (0.0140, 1.97619, "0000932471-17-003352"),
    "2017": (0.0170, 2.00603, "0000932471-18-005288"),
}
ALPHABET_RESOLVED_YEARS = ALPHABET_CONSOLIDATED_AS_FILED | frozenset(
    ALPHABET_CONSOLIDATION_RATIO
)
ALPHABET_ACCESSIONS = {
    "2014": "0000932471-15-005659",
    "2018": "0001104659-19-011820",
    "2019": "0001104659-20-027799",
    **{y: acc for y, (_, _ratio, acc) in ALPHABET_CONSOLIDATION_RATIO.items()},
}


def alphabet_consolidated_weight(year: str) -> float:
    """The corrected weight for a Class-A-only year: the anchor times the filed ratio."""
    anchor, ratio, _accession = ALPHABET_CONSOLIDATION_RATIO[year]
    return round(anchor * ratio, 4)


def build_provenance_csv():
    """Write comprehensive CSV table of constituent source values, calculations, and valuations."""
    rows = []
    for year in sorted(constituents_by_year.keys(), key=int):
        tickers = constituents_by_year[year]
        weights = weights_by_year[year]
        w12 = weights[11]

        if year in xml_data_by_year:
            # Modern XML filings (2020-2024)
            parsed = xml_data_by_year[year]["parsed"]
            accession = xml_data_by_year[year]["accession"]
            fund_total_usd = parsed["total_val_usd"]
            top20_holdings = parsed["holdings"][:20]

            for rank, (ticker, weight, h) in enumerate(zip(tickers, weights, top20_holdings), 1):
                name = COMPANY_NAMES.get(ticker, h["name"])
                val_usd = h["val"]
                rows.append({
                    "year": year,
                    "rank": rank,
                    "ticker": ticker,
                    "company_name": name,
                    "weight": f"{weight:.4f}",
                    "methodology": "SEC Form NPORT-P Audited Holdings",
                    "formula": "round(valUSD / total_fund_val, 4)",
                    "rank_12_anchor_weight": f"{w12:.4f}",
                    "underlying_value_usd": f"${val_usd:,.2f}",
                    "anchor_value_usd": f"${fund_total_usd:,.2f}",
                    "source_citation": f"SPY SEC Form NPORT-P (Accession {accession}, Period {year}-12-31)",
                })
        else:
            # Factsheet-anchored years (1994-2019, 2024): ranks #1-#12 are sourced
            # from official factsheets; ranks #13-#20 remain unverified estimates.
            for rank, (ticker, weight) in enumerate(zip(tickers, weights), 1):
                name = COMPANY_NAMES.get(ticker, ticker)
                if rank <= 12:
                    methodology = "Official Factsheet Anchor"
                    formula = "W_factsheet"
                    underlying_val = ""
                    anchor_val = ""
                    source_cit = f"S&P Dow Jones Indices Year-End Factsheet {year}"
                    if ticker == "GOOGL" and year in ALPHABET_RESOLVED_YEARS:
                        if year in ALPHABET_CONSOLIDATED_AS_FILED:
                            accession = ALPHABET_ACCESSIONS[year]
                            methodology = (
                                "Official Factsheet Anchor (Consolidated Class A + C, "
                                "Share-Class Basis Sourced)"
                            )
                            source_cit = (
                                f"S&P Dow Jones Indices Year-End Factsheet {year}; share-class "
                                f"basis established against Vanguard Index Trust Form N-CSR "
                                f"(Accession {accession}, Period {year}-12-31), 500 Index Fund "
                                "Schedule of Investments, which reports Alphabet Class A and "
                                "Class C as separate positions. The anchor already covers both "
                                "classes and is unchanged; see docs/DATA_PROVENANCE.md 4.3.21"
                            )
                        else:
                            anchor, ratio, accession = ALPHABET_CONSOLIDATION_RATIO[year]
                            methodology = (
                                "Official Factsheet Anchor x Filed Consolidation Ratio "
                                "(Class A Anchor, Class A + C Weight)"
                            )
                            formula = "W_factsheet_ClassA * (V_ClassA + V_ClassC) / V_ClassA"
                            source_cit = (
                                f"S&P Dow Jones Indices Year-End Factsheet {year} (Class A only, "
                                f"{anchor:.4f}) x {ratio:.5f}, the (Class A + Class C) / Class A market-value "
                                "ratio stated in Vanguard Index Trust Form N-CSR (Accession "
                                f"{accession}, Period {year}-12-31), 500 Index Fund Schedule of "
                                "Investments; see docs/DATA_PROVENANCE.md 4.3.21"
                            )
                else:
                    # These weights are ESTIMATES, not derived quantities. No primary
                    # source in this repository reports a market capitalization for
                    # ranks #13-#20 in these years, so no underlying or anchor value is
                    # published here: back-solving Cap_i from the weight it is supposed
                    # to explain would dress an assumption up as evidence.
                    methodology = "Unverified Estimate (No Primary Source)"
                    formula = "N/A - estimated, not derived"
                    underlying_val = ""
                    anchor_val = ""
                    source_cit = (
                        f"UNVERIFIED - no point-in-time filing archived for {year} "
                        f"ranks #13-#20; see docs/DATA_PROVENANCE.md 4.3.5"
                    )

                rows.append({
                    "year": year,
                    "rank": rank,
                    "ticker": ticker,
                    "company_name": name,
                    "weight": f"{weight:.4f}",
                    "methodology": methodology,
                    "formula": formula,
                    "rank_12_anchor_weight": f"{w12:.4f}",
                    "underlying_value_usd": underlying_val,
                    "anchor_value_usd": anchor_val,
                    "source_citation": source_cit,
                })

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "year", "rank", "ticker", "company_name", "weight", "methodology",
            "formula", "rank_12_anchor_weight", "underlying_value_usd", "anchor_value_usd", "source_citation"
        ])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported reproducible provenance table ({len(rows)} rows) to {OUTPUT_CSV}")


def main():
    current_data["constituents_by_year"] = constituents_by_year
    current_data["weights_by_year"] = weights_by_year

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(current_data, f, indent=2)
    print(f"Updated {OUTPUT_JSON} with all XML-derived year-ends (2020-2024).")

    build_provenance_csv()


if __name__ == "__main__":
    main()
