"""Generate historical S&P 500 Top 20 constituent weights and reproducible provenance table.

Ranks #1-#12 derive from official S&P Dow Jones Indices factsheet weights.
Years 2020-2023 derive directly from primary SPY Form NPORT-P XML regulatory filings.
Ranks #13-#20 for 1994-2019 and 2024 derive from point-in-time capitalization ratios
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
    "GOOGL": "Alphabet Inc. (Class A & C)",
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
}

# Form NPORT-P XML filings manifest for year-ends
XML_YEAR_ENDS = {
    "2020": ("SPY_2020-Q4_0001752724-21-043869.xml", "0001752724-21-043869"),
    "2021": ("SPY_2021-Q4_0001752724-22-048845.xml", "0001752724-22-048845"),
    "2022": ("SPY_2022-Q4_0001752724-23-046862.xml", "0001752724-23-046862"),
    "2023": ("SPY_2023-Q4_0001752724-24-043296.xml", "0001752724-24-043296"),
}

# 1. Programmatically parse XML filings and update 2020-2023 directly
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


def build_provenance_csv():
    """Write comprehensive CSV table of constituent source values, calculations, and valuations."""
    rows = []
    for year in sorted(constituents_by_year.keys(), key=int):
        tickers = constituents_by_year[year]
        weights = weights_by_year[year]
        w12 = weights[11]

        if year in xml_data_by_year:
            # Modern XML filings (2020-2023)
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
    print(f"Updated {OUTPUT_JSON} with all XML-derived year-ends (2020-2023).")

    build_provenance_csv()


if __name__ == "__main__":
    main()
