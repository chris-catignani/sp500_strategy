"""Test raw historical constituents data integrity."""

import json
import unittest
from pathlib import Path


class TestRawConstituents(unittest.TestCase):
    def test_sp500_historical_weights_top20(self):
        path = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "raw"
            / "constituents"
            / "historical_index_weights.json"
        )
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        constituents = data["constituents_by_year"]
        weights = data["weights_by_year"]
        for year in range(1994, 2025):
            year_str = str(year)
            self.assertIn(year_str, constituents)
            self.assertEqual(
                len(constituents[year_str]),
                20,
                f"Year {year} constituents length != 20",
            )
            self.assertEqual(
                len(weights[year_str]),
                20,
                f"Year {year} weights length != 20",
            )

    def test_no_duplicate_tickers_per_year(self):
        """Verify no duplicate tickers exist in any year's factsheet."""
        path = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "raw"
            / "constituents"
            / "historical_index_weights.json"
        )
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for year, tickers in data["constituents_by_year"].items():
            self.assertEqual(
                len(tickers),
                len(set(tickers)),
                f"Duplicate ticker found in year {year}: {tickers}"
            )

    def test_strictly_positive_descending_weights(self):
        """Verify weights are strictly positive and weakly descending."""
        path = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "raw"
            / "constituents"
            / "historical_index_weights.json"
        )
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for year, weights in data["weights_by_year"].items():
            for i in range(len(weights)):
                self.assertGreater(weights[i], 0.0, f"Weight not positive in {year} at idx {i}")
                if i > 0:
                    self.assertGreaterEqual(
                        weights[i - 1],
                        weights[i],
                        f"Weights not descending in {year} at idx {i}: {weights[i-1]} < {weights[i]}"
                    )

    def test_constituent_price_and_dividend_coverage(self):
        """Verify every constituent in factsheets has a raw ticker archive file with prices."""
        root = Path(__file__).resolve().parent.parent
        weights_path = root / "data" / "raw" / "constituents" / "historical_index_weights.json"
        with open(weights_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        all_tickers = set()
        for tickers in data["constituents_by_year"].values():
            all_tickers.update(tickers)

        tickers_dir = root / "data" / "raw" / "tickers"
        for t in all_tickers:
            ticker_file = tickers_dir / f"{t}.json"
            self.assertTrue(
                ticker_file.exists(),
                f"Raw market data missing for factsheet ticker: {t}"
            )
            with open(ticker_file, "r", encoding="utf-8") as f:
                t_data = json.load(f)
            chart = t_data.get("chart", {}).get("result", [{}])[0]
            quotes = chart.get("indicators", {}).get("quote", [{}])[0]
            self.assertTrue(len(quotes.get("close", [])) > 0, f"No close prices for {t}")


    def test_xml_generated_candidates_and_weights(self):
        """Verify 2020-2023 candidates and weights strictly reproduce the Form NPORT-P XML filings."""
        import sys
        root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(root))
        from scripts.extract_ground_truth_from_sec import parse_xml_filing, FILINGS_DIR

        weights_path = root / "data" / "raw" / "constituents" / "historical_index_weights.json"
        with open(weights_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        xml_map = {
            "2020": "SPY_2020-Q4_0001752724-21-043869.xml",
            "2021": "SPY_2021-Q4_0001752724-22-048845.xml",
            "2022": "SPY_2022-Q4_0001752724-23-046862.xml",
            "2023": "SPY_2023-Q4_0001752724-24-043296.xml",
        }

        for year, xml_file in xml_map.items():
            parsed = parse_xml_filing(FILINGS_DIR / xml_file)
            xml_top20 = [h["ticker"] for h in parsed["holdings"][:20]]
            xml_weights = [round(h["weight"], 4) for h in parsed["holdings"][:20]]

            # Ensure weakly descending
            for i in range(1, len(xml_weights)):
                if xml_weights[i] > xml_weights[i - 1]:
                    xml_weights[i] = xml_weights[i - 1]

            stored_tickers = data["constituents_by_year"][year]
            stored_weights = data["weights_by_year"][year]

            self.assertEqual(stored_tickers, xml_top20, f"Year {year} tickers do not match XML {xml_file}")
            self.assertEqual(stored_weights, xml_weights, f"Year {year} weights do not match XML {xml_file}")

        # Specific constituent checks per reviewer feedback
        tickers_2020 = data["constituents_by_year"]["2020"]
        self.assertIn("ADBE", tickers_2020)
        self.assertIn("CMCSA", tickers_2020)
        self.assertNotIn("WMT", tickers_2020)
        self.assertNotIn("BAC", tickers_2020)

        tickers_2021 = data["constituents_by_year"]["2021"]
        self.assertIn("ADBE", tickers_2021)
        self.assertIn("AVGO", tickers_2021)
        self.assertNotIn("WMT", tickers_2021)

        tickers_2022 = data["constituents_by_year"]["2022"]
        self.assertIn("ABBV", tickers_2022)
        self.assertIn("MRK", tickers_2022)
        self.assertNotIn("META", tickers_2022)

        tickers_2023 = data["constituents_by_year"]["2023"]
        self.assertIn("COST", tickers_2023)
        self.assertIn("MRK", tickers_2023)
        self.assertNotIn("WMT", tickers_2023)

    def test_sec_ground_truth_filing_accuracy(self):
        """Verify ground-truth historical and modern holdings against SEC filings."""
        import csv
        root = Path(__file__).resolve().parent.parent
        gt_path = root / "data" / "raw" / "ground_truth" / "quarterly_ground_truth_holdings.json"
        with open(gt_path, "r", encoding="utf-8") as f:
            gt = json.load(f)

        # 1999-Q3 Schedule of Investments: Lucent Technologies (#7) and Merck & Co (#9)
        gt_1999_q3 = gt["periods"]["1999-Q3"]
        self.assertTrue(gt_1999_q3["verified"])
        self.assertIn("LU", gt_1999_q3["holdings"])
        self.assertIn("MRK", gt_1999_q3["holdings"])
        self.assertNotIn("PFE", gt_1999_q3["holdings"])
        self.assertNotIn("JNJ", gt_1999_q3["holdings"])

        # 2000-Q3 Schedule of Investments: EMC Corp (#10) replaces IBM (#12)
        gt_2000_q3 = gt["periods"]["2000-Q3"]
        self.assertTrue(gt_2000_q3["verified"])
        self.assertIn("EMC", gt_2000_q3["holdings"])
        self.assertNotIn("IBM", gt_2000_q3["holdings"])

        # 2008-Q3 Schedule of Investments: Bank of America (#9) and IBM (#10) replace WMT and CSCO
        gt_2008_q3 = gt["periods"]["2008-Q3"]
        self.assertTrue(gt_2008_q3["verified"])
        self.assertIn("BAC", gt_2008_q3["holdings"])
        self.assertIn("IBM", gt_2008_q3["holdings"])
        self.assertNotIn("WMT", gt_2008_q3["holdings"])
        self.assertNotIn("CSCO", gt_2008_q3["holdings"])

        # 2024-Q3 must be unverified (no regulatory filing archived)
        gt_2024_q3 = gt["periods"]["2024-Q3"]
        self.assertFalse(gt_2024_q3["verified"])

        # Provenance table reproducibility check
        csv_path = root / "docs" / "historical_weights_table.csv"
        self.assertTrue(csv_path.exists(), "historical_weights_table.csv does not exist")
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        self.assertEqual(len(reader), 620, f"Expected 620 rows, got {len(reader)}")

        for row in reader:
            self.assertIn("underlying_value_usd", row)
            self.assertIn("anchor_value_usd", row)
            if row["methodology"] == "SEC Form NPORT-P Audited Holdings":
                self.assertTrue(row["underlying_value_usd"].startswith("$"))
                self.assertTrue(row["anchor_value_usd"].startswith("$"))
            elif row["methodology"] == "Empirical Capitalization Ratio":
                self.assertTrue(row["underlying_value_usd"].endswith("B"))
                self.assertTrue(row["anchor_value_usd"].endswith("B"))


if __name__ == "__main__":
    unittest.main()
