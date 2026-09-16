"""Test raw historical constituents data integrity."""

import csv
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestRawConstituents(unittest.TestCase):
    def test_sp500_historical_weights_top20(self):
        path = ROOT / "data" / "raw" / "constituents" / "historical_index_weights.json"
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
        path = ROOT / "data" / "raw" / "constituents" / "historical_index_weights.json"
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
        path = ROOT / "data" / "raw" / "constituents" / "historical_index_weights.json"
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
        weights_path = ROOT / "data" / "raw" / "constituents" / "historical_index_weights.json"
        with open(weights_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        all_tickers = set()
        for tickers in data["constituents_by_year"].values():
            all_tickers.update(tickers)

        tickers_dir = ROOT / "data" / "raw" / "tickers"
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
        """Verify 2020-2024 candidates and weights strictly reproduce the Form NPORT-P XML filings."""
        from scripts.extract_ground_truth_from_sec import parse_xml_filing, FILINGS_DIR

        weights_path = ROOT / "data" / "raw" / "constituents" / "historical_index_weights.json"
        with open(weights_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        xml_map = {
            "2020": "SPY_2020-Q4_0001752724-21-043869.xml",
            "2021": "SPY_2021-Q4_0001752724-22-048845.xml",
            "2022": "SPY_2022-Q4_0001752724-23-046862.xml",
            "2023": "SPY_2023-Q4_0001752724-24-043296.xml",
            "2024": "SPY_2024-Q4_0001752724-25-043826.xml",
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

        tickers_2024 = data["constituents_by_year"]["2024"]
        self.assertIn("NFLX", tickers_2024)
        self.assertNotIn("ORCL", tickers_2024)

    test_xml_filing_exact_derivation = test_xml_generated_candidates_and_weights

    def test_sec_ground_truth_filing_accuracy(self):
        """Verify ground-truth historical and modern holdings against SEC filings."""
        gt_path = ROOT / "data" / "raw" / "ground_truth" / "quarterly_ground_truth_holdings.json"
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

        # 2024-Q3 and 2024-Q4 are now archived Form NPORT-P filings (Issue #39)
        gt_2024_q3 = gt["periods"]["2024-Q3"]
        self.assertTrue(gt_2024_q3["verified"])
        self.assertNotIn("ORCL", gt_2024_q3["holdings"][:10])

        gt_2024_q4 = gt["periods"]["2024-Q4"]
        self.assertTrue(gt_2024_q4["verified"])

        # Provenance table reproducibility check
        csv_path = ROOT / "docs" / "historical_weights_table.csv"
        self.assertTrue(csv_path.exists(), "historical_weights_table.csv does not exist")
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        self.assertEqual(len(reader), 620, f"Expected 620 rows, got {len(reader)}")

        for row in reader:
            self.assertIn("underlying_value_usd", row)
            self.assertIn("anchor_value_usd", row)
            if row["methodology"] == "SEC Form NPORT-P Audited Holdings":
                # Audited rows publish the exact figures the weight is computed from,
                # and the published formula must actually reproduce the weight.
                self.assertTrue(row["underlying_value_usd"].startswith("$"))
                self.assertTrue(row["anchor_value_usd"].startswith("$"))
                val = float(row["underlying_value_usd"].lstrip("$").replace(",", ""))
                total = float(row["anchor_value_usd"].lstrip("$").replace(",", ""))
                self.assertAlmostEqual(
                    round(val / total, 4),
                    float(row["weight"]),
                    places=4,
                    msg=f"{row['year']} rank {row['rank']} weight not reproducible from NPORT values",
                )
            elif row["methodology"] == "Unverified Estimate (No Primary Source)":
                # No primary source reports these capitalizations, so the row must not
                # publish numbers back-solved from the weight they purport to explain.
                self.assertEqual(row["underlying_value_usd"], "")
                self.assertEqual(row["anchor_value_usd"], "")
                self.assertTrue(row["source_citation"].startswith("UNVERIFIED"))
            else:
                self.assertEqual(row["methodology"], "Official Factsheet Anchor")

    def test_provenance_table_marks_unsourced_ranks_unverified(self):
        """Ranks #13-#20 outside the NPORT-P years have no primary source and must say so."""
        with open(ROOT / "docs" / "historical_weights_table.csv", "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        xml_years = {"2020", "2021", "2022", "2023", "2024"}
        for row in reader:
            if row["year"] in xml_years:
                self.assertEqual(row["methodology"], "SEC Form NPORT-P Audited Holdings")
            elif int(row["rank"]) <= 12:
                self.assertEqual(row["methodology"], "Official Factsheet Anchor")
            else:
                self.assertEqual(
                    row["methodology"],
                    "Unverified Estimate (No Primary Source)",
                    f"{row['year']} rank {row['rank']} claims a source it does not have",
                )

    def test_company_label_consistency(self):
        """Verify GOOGL company label is harmonized across scripts, mappings, and datasets."""
        from scripts.generate_historical_weights import COMPANY_NAMES
        from scripts.build_datasets_from_raw import SP500_NAMES
        from scripts.extract_ground_truth_from_sec import CONSOLIDATED_ISSUERS

        canonical = "Alphabet Inc. (Class A & C)"
        self.assertEqual(COMPANY_NAMES["GOOGL"], canonical)
        self.assertEqual(SP500_NAMES["GOOGL"], canonical)
        self.assertEqual(CONSOLIDATED_ISSUERS["GOOGL"]["canonical_name"], canonical)

        datasets = [
            "sp500_constituents.json",
            "sp500_quarterly_constituents.json",
            "world_constituents.json",
            "world_quarterly_constituents.json",
        ]
        for ds in datasets:
            with open(ROOT / "data" / ds, "r", encoding="utf-8") as f:
                content = json.load(f)
            items = []
            if isinstance(content, dict):
                for v in content.values():
                    if isinstance(v, list):
                        items.extend(v)
            googl_found = False
            for item in items:
                if item.get("ticker") == "GOOGL":
                    googl_found = True
                    self.assertEqual(
                        item.get("name"),
                        canonical,
                        f"Failed in {ds} for period {item.get('year')}-{item.get('quarter')}",
                    )
            self.assertTrue(googl_found, f"GOOGL not found in {ds}")


class TestN30DScheduleParser(unittest.TestCase):
    """The historical Form N-30D Schedules of Investments must be parsed, not transcribed."""

    @classmethod
    def setUpClass(cls):
        from scripts.extract_ground_truth_from_sec import parse_n30d_filing, FILINGS_DIR
        cls.parse = staticmethod(parse_n30d_filing)
        cls.dir = FILINGS_DIR

    def test_1999_q3_schedule_top10(self):
        """1999-09-30 (Acc 0000950135-99-005434): Lucent #7, Merck #9, no JNJ or PFE."""
        parsed = self.parse(self.dir / "SPY_1999_Q4_N-30D_0000950135-99-005434.txt")
        top10 = [h["ticker"] for h in parsed["holdings"][:10]]
        self.assertEqual(
            top10, ["MSFT", "GE", "INTC", "CSCO", "IBM", "WMT", "LU", "XOM", "MRK", "C"]
        )
        by_ticker = {h["ticker"]: h for h in parsed["holdings"][:12]}
        self.assertAlmostEqual(by_ticker["LU"]["val"], 247966717.0, places=2)
        self.assertAlmostEqual(by_ticker["MRK"]["val"], 189235584.0, places=2)
        self.assertEqual(by_ticker["PFE"]["rank"], 11)

    def test_2000_q3_schedule_top10(self):
        """2000-09-30 (Acc 0000950135-00-005227): EMC #10, IBM displaced to #12."""
        parsed = self.parse(self.dir / "SPY_2000_Q4_N-30D_0000950135-00-005227.txt")
        top10 = [h["ticker"] for h in parsed["holdings"][:10]]
        self.assertEqual(
            top10, ["GE", "CSCO", "MSFT", "XOM", "PFE", "INTC", "C", "ORCL", "AIG", "EMC"]
        )
        by_ticker = {h["ticker"]: h for h in parsed["holdings"][:12]}
        self.assertAlmostEqual(by_ticker["EMC"]["val"], 414591105.0, places=2)
        self.assertEqual(by_ticker["IBM"]["rank"], 12)

    def test_2008_q3_schedule_top10(self):
        """2008-09-30 (Acc 0000950135-08-007648): BAC #9, IBM #10, WMT #11, CSCO #12."""
        parsed = self.parse(self.dir / "SPY_2008_Q4_N-30D_0000950135-08-007648.txt")
        top10 = [h["ticker"] for h in parsed["holdings"][:10]]
        self.assertEqual(
            top10, ["XOM", "GE", "PG", "MSFT", "JNJ", "JPM", "CVX", "T", "BAC", "IBM"]
        )
        by_ticker = {h["ticker"]: h for h in parsed["holdings"][:12]}
        self.assertAlmostEqual(by_ticker["BAC"]["val"], 1457715385.0, places=2)
        self.assertAlmostEqual(by_ticker["IBM"]["val"], 1447278479.0, places=2)
        self.assertEqual(by_ticker["WMT"]["rank"], 11)
        self.assertEqual(by_ticker["CSCO"]["rank"], 12)

    def test_wrapped_constituent_names_are_joined(self):
        """Names wrapped across lines (e.g. International Business Machines Corp.) must parse."""
        parsed = self.parse(self.dir / "SPY_2008_Q4_N-30D_0000950135-08-007648.txt")
        ibm = next(h for h in parsed["holdings"] if h["ticker"] == "IBM")
        self.assertIn("International Business", ibm["name"])
        self.assertIn("Machines", ibm["name"])

    def test_ground_truth_json_matches_parsed_filings(self):
        """The committed ground-truth JSON must reproduce what the parser reads."""
        gt_path = ROOT / "data" / "raw" / "ground_truth" / "quarterly_ground_truth_holdings.json"
        with open(gt_path, "r", encoding="utf-8") as f:
            gt = json.load(f)

        for period, filename in (
            ("1999-Q3", "SPY_1999_Q4_N-30D_0000950135-99-005434.txt"),
            ("2000-Q3", "SPY_2000_Q4_N-30D_0000950135-00-005227.txt"),
            ("2008-Q3", "SPY_2008_Q4_N-30D_0000950135-08-007648.txt"),
        ):
            parsed = self.parse(self.dir / filename)
            self.assertEqual(
                gt["periods"][period]["holdings"],
                [h["ticker"] for h in parsed["holdings"][:10]],
                f"{period} ground truth does not match parsed {filename}",
            )


class TestConsolidateHoldings(unittest.TestCase):
    """Unit tests for multi-class equity holdings consolidation at issuer level."""

    def test_consolidate_holdings_alphabet(self):
        from scripts.extract_ground_truth_from_sec import consolidate_holdings

        raw_holdings = [
            {"name": "Apple Inc.", "ticker": "AAPL", "cusip": "037833100", "val": 1000.0},
            {"name": "Alphabet Inc. Cl A", "ticker": "GOOGL", "cusip": "02079K305", "val": 400.0},
            {"name": "Alphabet Inc. Cl C", "ticker": "GOOG", "cusip": "02079K107", "val": 350.0},
            {"name": "Microsoft Corp.", "ticker": "MSFT", "cusip": "594918104", "val": 900.0},
        ]
        consolidated = consolidate_holdings(raw_holdings)
        by_ticker = {h["ticker"]: h for h in consolidated}

        self.assertEqual(len(consolidated), 3)
        self.assertIn("AAPL", by_ticker)
        self.assertEqual(by_ticker["AAPL"]["val"], 1000.0)
        self.assertIn("MSFT", by_ticker)
        self.assertEqual(by_ticker["MSFT"]["val"], 900.0)
        self.assertIn("GOOGL", by_ticker)
        self.assertEqual(by_ticker["GOOGL"]["val"], 750.0)
        self.assertEqual(by_ticker["GOOGL"]["cusip"], "02079K305")
        self.assertEqual(by_ticker["GOOGL"]["name"], "Alphabet Inc. (Class A & C)")

    def test_consolidate_holdings_synthetic_dual_class(self):
        from scripts.extract_ground_truth_from_sec import consolidate_holdings

        custom_issuers = {
            "TEST": {
                "primary_ticker": "TEST.A",
                "canonical_name": "Test Company Inc. (Class A & B)",
                "primary_cusip": "111111111",
                "member_cusips": {"111111111", "222222222"},
                "member_tickers": {"TEST.A", "TEST.B"},
            }
        }
        raw_holdings = [
            {"name": "Test Class A", "ticker": "TEST.A", "cusip": "111111111", "val": 50.0},
            {"name": "Test Class B", "ticker": "TEST.B", "cusip": "222222222", "val": 75.0},
            {"name": "Other Corp", "ticker": "OTHR", "cusip": "999999999", "val": 200.0},
        ]
        consolidated = consolidate_holdings(raw_holdings, issuers=custom_issuers)
        by_ticker = {h["ticker"]: h for h in consolidated}

        self.assertEqual(len(consolidated), 2)
        self.assertIn("OTHR", by_ticker)
        self.assertEqual(by_ticker["OTHR"]["val"], 200.0)
        self.assertIn("TEST.A", by_ticker)
        self.assertEqual(by_ticker["TEST.A"]["val"], 125.0)
        self.assertEqual(by_ticker["TEST.A"]["cusip"], "111111111")
        self.assertEqual(by_ticker["TEST.A"]["name"], "Test Company Inc. (Class A & B)")

    def test_consolidate_holdings_ticker_fallback(self):
        from scripts.extract_ground_truth_from_sec import consolidate_holdings

        # Holdings without CUSIP but with valid ticker
        raw_holdings = [
            {"name": "Google Class A", "ticker": "GOOGL", "cusip": "", "val": 300.0},
            {"name": "Google Class C", "ticker": "GOOG", "cusip": None, "val": 200.0},
            {"name": "Amazon", "ticker": "AMZN", "cusip": None, "val": 500.0},
        ]
        consolidated = consolidate_holdings(raw_holdings)
        by_ticker = {h["ticker"]: h for h in consolidated}

        self.assertEqual(len(consolidated), 2)
        self.assertIn("AMZN", by_ticker)
        self.assertEqual(by_ticker["AMZN"]["val"], 500.0)
        self.assertIn("GOOGL", by_ticker)
        self.assertEqual(by_ticker["GOOGL"]["val"], 500.0)
        self.assertEqual(by_ticker["GOOGL"]["cusip"], "02079K305")
        self.assertEqual(by_ticker["GOOGL"]["name"], "Alphabet Inc. (Class A & C)")


if __name__ == "__main__":
    unittest.main()
