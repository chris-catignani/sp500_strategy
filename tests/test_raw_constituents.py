"""Test raw historical constituents data integrity."""

import csv
import json
from pathlib import Path
import sys
import unittest
import warnings

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
                self.assertTrue(
                    row["methodology"].startswith("Official Factsheet Anchor"),
                    f"{row['year']} rank {row['rank']}: {row['methodology']}",
                )

    def test_provenance_table_marks_unsourced_ranks_unverified(self):
        """Ranks #13-#20 outside the NPORT-P years have no primary source and must say so."""
        with open(ROOT / "docs" / "historical_weights_table.csv", "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        xml_years = {"2020", "2021", "2022", "2023", "2024"}
        for row in reader:
            if row["year"] in xml_years:
                self.assertEqual(row["methodology"], "SEC Form NPORT-P Audited Holdings")
            elif int(row["rank"]) <= 12:
                # The suffixed variant qualifies a sourced weight whose share-class
                # composition is undetermined; the anchor itself is still sourced.
                self.assertTrue(
                    row["methodology"].startswith("Official Factsheet Anchor"),
                    f"{row['year']} rank {row['rank']}: {row['methodology']}",
                )
            else:
                self.assertEqual(
                    row["methodology"],
                    "Unverified Estimate (No Primary Source)",
                    f"{row['year']} rank {row['rank']} claims a source it does not have",
                )

    def test_company_label_consistency(self):
        """The Alphabet label names the issuer and claims nothing about share classes."""
        from scripts.generate_historical_weights import COMPANY_NAMES
        from scripts.build_datasets_from_raw import SP500_NAMES
        from scripts.extract_ground_truth_from_sec import CONSOLIDATED_ISSUERS

        canonical = "Alphabet Inc."
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
            self.assertTrue(items, f"{ds} yielded no constituent rows to check")
            googl_found = False
            for item in items:
                if item.get("ticker") == "GOOGL":
                    googl_found = True
                    self.assertEqual(
                        item.get("name"),
                        canonical,
                        f"Failed in {ds} for period {item.get('year')}-{item.get('quarter')}",
                    )
                self.assertNotEqual(
                    item.get("ticker"), "GOOG",
                    f"{ds} carries a separate Class C line; the issuer must hold one slot",
                )
            self.assertTrue(googl_found, f"GOOGL not found in {ds}")

    def test_alphabet_share_class_composition_is_declared_per_year(self):
        """Which Alphabet classes a weight covers varies by year and must be stated, not assumed."""
        from scripts.generate_historical_weights import (
            ALPHABET_SINGLE_CLASS_THROUGH,
            ALPHABET_UNDETERMINED_YEARS,
        )

        with open(ROOT / "docs" / "historical_weights_table.csv", "r", encoding="utf-8") as f:
            googl_rows = {r["year"]: r for r in csv.DictReader(f) if r["ticker"] == "GOOGL"}

        self.assertTrue(googl_rows, "no GOOGL rows in the provenance table")

        for year, row in googl_rows.items():
            if year in ALPHABET_UNDETERMINED_YEARS:
                # Class C existed but no December-dated primary source is archived, so the
                # table must say the composition is unverified rather than imply either.
                self.assertIn("Share-Class Composition Unverified", row["methodology"], year)
                self.assertIn("UNVERIFIED", row["source_citation"], year)
            elif int(year) > ALPHABET_SINGLE_CLASS_THROUGH:
                # 2020 onward is consolidated by consolidate_holdings() from a filing.
                self.assertIn("NPORT-P", row["source_citation"], year)
                self.assertNotIn("Unverified", row["methodology"], year)
            else:
                # Before 2014-04-03 Alphabet had one listed class; nothing to consolidate.
                self.assertNotIn("Share-Class", row["methodology"], year)

    def test_provenance_table_never_claims_unsourced_consolidation(self):
        """No GOOGL row may cite a bare factsheet for a weight of undetermined composition."""
        from scripts.generate_historical_weights import ALPHABET_UNDETERMINED_YEARS

        with open(ROOT / "docs" / "historical_weights_table.csv", "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["ticker"] == "GOOGL" and row["year"] in ALPHABET_UNDETERMINED_YEARS:
                    self.assertNotEqual(
                        row["methodology"], "Official Factsheet Anchor",
                        f"{row['year']} presents an unverified consolidation as a sourced weight",
                    )


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

    def test_parsed_total_matches_filing_stated_total(self):
        """For each of the 14 fixed-width filings (1995-2003, 2005-2009), total_val_usd == stated_total_usd."""
        manifest_path = self.dir / "sec_annual_filings_manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        target_years = [y for y in range(1995, 2010) if y != 2004]
        for year in target_years:
            filing_path = ROOT / manifest[str(year)]["file_path"]
            with self.subTest(year=year, filename=filing_path.name):
                parsed = self.parse(filing_path)
                self.assertEqual(
                    parsed["total_val_usd"],
                    parsed["stated_total_usd"],
                    f"{year} parsed total {parsed['total_val_usd']} != stated total {parsed['stated_total_usd']}",
                )

    def test_multi_fund_filing_is_refused(self):
        """Parsing a multi-fund report (e.g. 2004 Select Sector SPDR Trust) raises ScheduleParseError."""
        from scripts.extract_ground_truth_from_sec import ScheduleParseError

        with self.assertRaises(ScheduleParseError):
            self.parse(self.dir / "SELECT_SECTOR_SPDR_2004_N-CSR_0000950135-04-005558.txt")

    def test_2004_ground_truth_source_is_spy_not_select_sector(self):
        """The 2004 manifest entry references SPY's conformed N-30D, not Select Sector."""
        manifest_path = self.dir / "sec_annual_filings_manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        entry = manifest["2004"]
        self.assertEqual(entry["accession_number"], "0000950135-05-000037")
        self.assertEqual(entry["form"], "N-30D")

        filing_path = ROOT / entry["file_path"]
        self.assertTrue(filing_path.exists(), f"{filing_path} does not exist")

        lines = filing_path.read_text(encoding="utf-8", errors="replace").splitlines()[:40]
        header_text = "\n".join(lines)
        self.assertIn("SPDR TRUST SERIES 1", header_text)
        self.assertIn("CONFORMED PERIOD OF REPORT:", header_text)
        self.assertIn("20040930", header_text)

    def test_select_sector_filing_is_flagged_not_spy(self):
        """The mis-archived Select Sector filing is retained but flagged as non-SPY."""
        manifest_path = self.dir / "sec_annual_filings_manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertIn("2004-select-sector-spdr-trust", manifest)
        entry = manifest["2004-select-sector-spdr-trust"]
        self.assertFalse(entry.get("spy_schedule", True))

        filing_path = ROOT / entry["file_path"]
        self.assertTrue(filing_path.exists(), f"{filing_path} does not exist")

    def test_html_era_filing_is_refused(self):
        """Parsing an HTML-era filing lacking fixed-width anchors raises ScheduleParseError."""
        from scripts.extract_ground_truth_from_sec import ScheduleParseError

        with self.assertRaises(ScheduleParseError):
            self.parse(self.dir / "SPY_2010_N-30D_0000950123-10-109631.txt")

    def test_1999_recovers_rows_without_dot_leaders(self):
        """The 1999 filing's holdings include AIG with val == 167497004.0."""
        parsed = self.parse(self.dir / "SPY_1999_Q4_N-30D_0000950135-99-005434.txt")
        aig = next((h for h in parsed["holdings"] if h["ticker"] == "AIG"), None)
        self.assertIsNotNone(aig, "AIG was not found in parsed 1999 holdings")
        self.assertEqual(aig["val"], 167497004.0)

    def test_all_filings_resolve_top_30_to_tickers(self):
        """For every entry in N30D_HISTORICAL_FILINGS, assert_top_holdings_resolved does not raise."""
        from scripts.extract_ground_truth_from_sec import (
            N30D_HISTORICAL_FILINGS, assert_top_holdings_resolved,
        )

        for period, filename, *_ in N30D_HISTORICAL_FILINGS:
            parsed = self.parse(self.dir / filename)
            assert_top_holdings_resolved(parsed["holdings"], f"{period} ({filename})")

    def test_unmapped_top_holding_is_refused(self):
        """assert_top_holdings_resolved raises ScheduleParseError for unmapped names."""
        from scripts.extract_ground_truth_from_sec import (
            ScheduleParseError, assert_top_holdings_resolved,
        )

        synthetic_holdings = [
            {"ticker": "AAPL", "val": 100.0},
            {"ticker": "Some Unmapped Corp.", "val": 50.0},
        ]
        with self.assertRaises(ScheduleParseError) as ctx:
            assert_top_holdings_resolved(synthetic_holdings, "SPY_TEST_FILING")
        self.assertIn("SPY_TEST_FILING", str(ctx.exception))
        self.assertIn("Some Unmapped Corp.", str(ctx.exception))


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
        self.assertEqual(by_ticker["GOOGL"]["name"], "Alphabet Inc.")

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
        self.assertEqual(by_ticker["GOOGL"]["name"], "Alphabet Inc.")


class TestIssuerSeparation(unittest.TestCase):
    """Distinct issuers must not be merged, and multi-class issuers must not be missed."""

    def test_coca_cola_enterprises_is_not_merged_into_ko(self):
        """The bottler was its own S&P 500 constituent and must rank separately."""
        from scripts.extract_ground_truth_from_sec import (
            parse_n30d_filing, FILINGS_DIR, N30D_HISTORICAL_FILINGS,
        )

        for period, filename, *_ in N30D_HISTORICAL_FILINGS:
            parsed = parse_n30d_filing(FILINGS_DIR / filename)
            by_ticker = {h["ticker"]: h for h in parsed["holdings"]}
            self.assertIn("KO", by_ticker, period)
            self.assertIn("CCE", by_ticker, period)
            self.assertIn("Coca-Cola Co", by_ticker["KO"]["name"].replace(" Co.", " Co"), period)
            self.assertIn("Enterprises", by_ticker["CCE"]["name"], period)
            self.assertGreater(by_ticker["KO"]["val"], by_ticker["CCE"]["val"], period)

    def test_n30d_tickers_map_one_issuer_each(self):
        """No name pattern may absorb two differently named issuers into one ticker."""
        from scripts.extract_ground_truth_from_sec import (
            parse_n30d_filing, FILINGS_DIR, N30D_HISTORICAL_FILINGS, _n30d_ticker,
        )

        for period, filename, *_ in N30D_HISTORICAL_FILINGS:
            parsed = parse_n30d_filing(FILINGS_DIR / filename)
            for holding in parsed["holdings"]:
                self.assertEqual(
                    _n30d_ticker(holding["name"]), holding["ticker"],
                    f"{period}: {holding['name']!r} was consolidated under a foreign ticker",
                )

    def test_registered_issuer_consolidates_without_warning(self):
        from scripts.extract_ground_truth_from_sec import consolidate_holdings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = consolidate_holdings([
                {"name": "Alphabet Inc", "ticker": "GOOGL", "cusip": "02079K305", "val": 400.0},
                {"name": "Alphabet Inc", "ticker": "GOOG", "cusip": "02079K107", "val": 350.0},
            ])
        self.assertEqual(caught, [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["val"], 750.0)

    def test_unregistered_multi_class_issuer_warns(self):
        """An issuer filed under two tickers but absent from the registry must not pass silently."""
        from scripts.extract_ground_truth_from_sec import consolidate_holdings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = consolidate_holdings([
                {"name": "Fox Corp", "ticker": "FOXA", "cusip": "35137L105", "val": 10.0},
                {"name": "Fox Corp", "ticker": "FOX", "cusip": "35137L204", "val": 5.0},
                {"name": "Apple Inc", "ticker": "AAPL", "cusip": "037833100", "val": 99.0},
            ])
        self.assertEqual(len(caught), 1)
        self.assertIn("Fox Corp", str(caught[0].message))
        self.assertIn("CONSOLIDATED_ISSUERS", str(caught[0].message))
        # The warning reports the gap; it does not silently invent a consolidation.
        self.assertEqual(len(result), 3)

    def test_archived_filings_contain_no_unregistered_multi_class_issuer(self):
        """Every multi-class issuer in the archived NPORT-P filings must be registered."""
        import json
        import xml.etree.ElementTree as ET
        from scripts.extract_ground_truth_from_sec import (
            FILINGS_DIR, TICKER_TO_ISSUER, map_ticker, strip_ns,
            _warn_unregistered_multi_class, CUSIP_TO_ISSUER,
        )

        with open(FILINGS_DIR / "sec_filings_manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)

        for period, meta in sorted(manifest.items()):
            root = ET.parse(ROOT / meta["file_path"]).getroot()
            holdings = []
            for elem in root.iter():
                if strip_ns(elem.tag) != "invstOrSec":
                    continue
                fields = {strip_ns(c.tag): (c.text or "").strip() for c in elem}
                holdings.append({
                    "name": fields.get("name", ""),
                    "ticker": map_ticker(
                        fields.get("name", ""), fields.get("cusip", ""), fields.get("ticker", "")
                    ),
                    "cusip": fields.get("cusip", ""),
                })
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                unregistered = _warn_unregistered_multi_class(
                    holdings, CUSIP_TO_ISSUER, TICKER_TO_ISSUER
                )
            self.assertEqual(unregistered, [], f"{period} has unregistered multi-class issuers")


if __name__ == "__main__":
    unittest.main()
