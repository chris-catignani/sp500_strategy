"""Test raw historical constituents data integrity."""

import csv
import json
from pathlib import Path
import re
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

    def test_all_fifteen_annual_filings_extracted(self):
        """N30D_HISTORICAL_FILINGS has 15 entries (1995-Q4, 1996-Q4, 1997-Q3..2009-Q3) and all files exist."""
        from scripts.extract_ground_truth_from_sec import (
            N30D_HISTORICAL_FILINGS, FILINGS_DIR,
        )

        self.assertEqual(len(N30D_HISTORICAL_FILINGS), 15)
        expected_periods = ["1995-Q4", "1996-Q4"] + [f"{y}-Q3" for y in range(1997, 2010)]
        actual_periods = [entry[0] for entry in N30D_HISTORICAL_FILINGS]
        self.assertEqual(actual_periods, expected_periods)

        for period, filename, *_ in N30D_HISTORICAL_FILINGS:
            filing_file = FILINGS_DIR / filename
            self.assertTrue(
                filing_file.exists(),
                f"{period} filing file does not exist: {filing_file}",
            )

    def test_all_historical_filings_pass_period_assertion(self):
        """Every entry in N30D_HISTORICAL_FILINGS passes assert_filing_period_matches against its header."""
        from scripts.extract_ground_truth_from_sec import (
            N30D_HISTORICAL_FILINGS, FILINGS_DIR, assert_filing_period_matches,
        )

        for period, filename, _acc, _form, rep_dt, _file_dt in N30D_HISTORICAL_FILINGS:
            with self.subTest(period=period, filename=filename):
                assert_filing_period_matches(FILINGS_DIR / filename, rep_dt)

    def test_filing_period_assertion_raises_on_mismatch(self):
        """assert_filing_period_matches raises ScheduleParseError when given a deliberately wrong date."""
        from scripts.extract_ground_truth_from_sec import (
            FILINGS_DIR, ScheduleParseError, assert_filing_period_matches,
        )

        # 1995 filing is 1995-12-31; passing 1995-09-30 (the old defect) must raise
        file_1995 = FILINGS_DIR / "SPY_1995_N-30D_0000912057-96-003840.txt"
        with self.assertRaises(ScheduleParseError) as ctx:
            assert_filing_period_matches(file_1995, "1995-09-30")
        self.assertIn("1995-12-31", str(ctx.exception))
        self.assertIn("1995-09-30", str(ctx.exception))

        # 1997 filing is 1997-09-30; passing 1997-12-31 must raise
        file_1997 = FILINGS_DIR / "SPY_1997_N-30D_0000950135-97-004820.txt"
        with self.assertRaises(ScheduleParseError) as ctx:
            assert_filing_period_matches(file_1997, "1997-12-31")
        self.assertIn("1997-09-30", str(ctx.exception))
        self.assertIn("1997-12-31", str(ctx.exception))

    def test_relabelled_historical_periods_in_ground_truth(self):
        """1995-Q4 and 1996-Q4 are verified: true in ground-truth JSON; 1995-Q3 and 1996-Q3 are verified: false."""
        gt_path = ROOT / "data" / "raw" / "ground_truth" / "quarterly_ground_truth_holdings.json"
        with open(gt_path, "r", encoding="utf-8") as f:
            gt = json.load(f)

        for q4_period, expected_date in (("1995-Q4", "1995-12-31"), ("1996-Q4", "1996-12-31")):
            self.assertIn(q4_period, gt["periods"])
            entry = gt["periods"][q4_period]
            self.assertTrue(entry["verified"], f"{q4_period} should be verified: true")
            self.assertEqual(entry["report_date"], expected_date)
            self.assertEqual(len(entry["holdings"]), 10)

        for q3_period, expected_date in (("1995-Q3", "1995-09-30"), ("1996-Q3", "1996-09-30")):
            self.assertIn(q3_period, gt["periods"])
            entry = gt["periods"][q3_period]
            self.assertFalse(entry["verified"], f"{q3_period} should be verified: false")
            self.assertEqual(entry["holdings"], [])
            self.assertIn(expected_date, entry.get("note", ""))

    def test_ground_truth_json_matches_parsed_filings(self):
        """The committed ground-truth JSON must reproduce what the parser reads."""
        from scripts.extract_ground_truth_from_sec import N30D_HISTORICAL_FILINGS

        gt_path = ROOT / "data" / "raw" / "ground_truth" / "quarterly_ground_truth_holdings.json"
        with open(gt_path, "r", encoding="utf-8") as f:
            gt = json.load(f)

        for period, filename, *_ in N30D_HISTORICAL_FILINGS:
            parsed = self.parse(self.dir / filename)
            self.assertEqual(
                gt["periods"][period]["holdings"],
                [h["ticker"] for h in parsed["holdings"][:10]],
                f"{period} ground truth does not match parsed {filename}",
            )

    def test_parsed_total_matches_filing_stated_total(self):
        """For each of the 15 fixed-width filings (1995-2009), total_val_usd == stated_total_usd."""
        manifest_path = self.dir / "sec_annual_filings_manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        for year in range(1995, 2010):
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

    def test_universe_gap_report_matches_filings(self):
        """Every ticker in universe_gap_report.json has no raw json, and every omitted top-30 ticker has one."""
        from scripts.extract_ground_truth_from_sec import (
            FILINGS_DIR, iter_schedule_filings,
        )

        report_path = ROOT / "data" / "raw" / "ground_truth" / "universe_gap_report.json"
        self.assertTrue(report_path.exists(), "universe_gap_report.json does not exist")
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        self.assertEqual(report["depth"], 30)
        self.assertEqual(
            report["source"],
            "35 SPY Form N-30D reports, 1995-2019 (December 31 snapshots for 1995-1996, "
            "September 30 annual-report snapshots for 1997-2019, and March 31 "
            "semi-annual-report snapshots for 2010-2019)",
        )

        tickers_dir = ROOT / "data" / "raw" / "tickers"
        reported_missing = set(report["missing_tickers"].keys())

        # Every ticker reported as missing must not have a raw ticker file
        for ticker in reported_missing:
            self.assertFalse(
                (tickers_dir / f"{ticker}.json").exists(),
                f"Gap report claims {ticker} is missing, but data/raw/tickers/{ticker}.json exists",
            )

        # Collect all tickers appearing in the top 30 across all 35 archived schedules
        filing_top30_tickers = set()
        for _period, filename, _acc, _form, _rep, _filed, _ovr, parser in iter_schedule_filings():
            parsed = parser(FILINGS_DIR / filename)
            for h in parsed["holdings"][:30]:
                filing_top30_tickers.add(h["ticker"])

        # Every ticker in top 30 omitted from gap report must have a raw ticker file
        omitted = filing_top30_tickers - reported_missing
        for ticker in omitted:
            self.assertTrue(
                (tickers_dir / f"{ticker}.json").exists(),
                f"Top-30 ticker {ticker} omitted from gap report, but data/raw/tickers/{ticker}.json is missing",
            )

        # Every ticker in gap report must actually appear in at least one filing's top 30
        self.assertEqual(reported_missing - filing_top30_tickers, set())


class TestHtmlScheduleParser(unittest.TestCase):
    """The 2010-2019 HTML-era Schedules of Investments must be parsed, not transcribed."""

    @classmethod
    def setUpClass(cls):
        from scripts.extract_ground_truth_from_sec import (
            parse_html_schedule_filing, FILINGS_DIR,
        )
        cls.parse = staticmethod(parse_html_schedule_filing)
        cls.dir = FILINGS_DIR

    def test_2010_parsed_total_matches_stated_total(self):
        """The 2010 filing's parsed positions sum to the total it states, to the dollar."""
        parsed = self.parse(self.dir / "SPY_2010_N-30D_0000950123-10-109631.txt")
        self.assertEqual(parsed["stated_total_usd"], 78077851159.0)
        self.assertEqual(parsed["total_val_usd"], parsed["stated_total_usd"])

    def test_2019_page_break_repeat_rows_are_not_double_counted(self):
        """The 2019 filing repeats three rows across a page break; each must count once."""
        parsed = self.parse(self.dir / "SPY_2019_N-30D_0001193125-19-302203.txt")
        self.assertEqual(parsed["stated_total_usd"], 274267350525.0)
        self.assertEqual(parsed["total_val_usd"], parsed["stated_total_usd"])

        unh = next(h for h in parsed["holdings"] if h["ticker"] == "UNH")
        self.assertEqual(unh["val"], 2284798818.0)
        self.assertEqual(unh["shares"], 10513523.0)

    def test_all_html_era_filings_reconcile_and_resolve(self):
        """Every 2010-2019 filing reconciles to its stated total and resolves its top 30."""
        from scripts.extract_ground_truth_from_sec import (
            HTML_ERA_FILINGS, assert_top_holdings_resolved,
        )

        self.assertEqual(len(HTML_ERA_FILINGS), 20)
        for period, filename, *_ in HTML_ERA_FILINGS:
            with self.subTest(period=period):
                parsed = self.parse(self.dir / filename)
                self.assertEqual(parsed["total_val_usd"], parsed["stated_total_usd"])
                self.assertGreater(len(parsed["holdings"]), 450)
                assert_top_holdings_resolved(
                    parsed["holdings"], f"{period} ({filename})"
                )

    def test_fy2014_header_period_override_is_accepted(self):
        """FY2014's header wrongly says 2013-09-30; the declared override accepts only that."""
        from scripts.extract_ground_truth_from_sec import assert_filing_period_matches

        path = self.dir / "SPY_2014_Q4_N-30D_0001193125-14-428689.txt"
        assert_filing_period_matches(path, "2014-09-30", header_period_override="2013-09-30")

    def test_filing_period_override_must_match_the_header_it_excuses(self):
        """An override that does not equal the filing's own header value is still a failure."""
        from scripts.extract_ground_truth_from_sec import (
            ScheduleParseError, assert_filing_period_matches,
        )

        path = self.dir / "SPY_2014_Q4_N-30D_0001193125-14-428689.txt"
        with self.assertRaises(ScheduleParseError):
            assert_filing_period_matches(
                path, "2014-09-30", header_period_override="2012-09-30"
            )

    def test_every_html_era_filing_passes_the_period_assertion(self):
        """Each registered HTML-era filing agrees with its header, or declares the override."""
        from scripts.extract_ground_truth_from_sec import (
            HTML_ERA_FILINGS, assert_filing_period_matches,
        )

        for period, filename, _acc, _form, report_date, _filed, override in HTML_ERA_FILINGS:
            with self.subTest(period=period):
                assert_filing_period_matches(
                    self.dir / filename, report_date, header_period_override=override
                )

    def test_only_fy2014_declares_a_header_override(self):
        """The header override is a single documented exception, not a general relaxation."""
        from scripts.extract_ground_truth_from_sec import HTML_ERA_FILINGS

        overridden = [e[0] for e in HTML_ERA_FILINGS if e[6] is not None]
        self.assertEqual(overridden, ["2014-Q3"])

    def test_2019_alphabet_share_classes_consolidate_to_one_googl(self):
        """The HTML filings list Alphabet twice; ranking must treat it as one issuer."""
        parsed = self.parse(self.dir / "SPY_2019_N-30D_0001193125-19-302203.txt")
        tickers = [h["ticker"] for h in parsed["holdings"]]
        self.assertIn("GOOGL", tickers)
        self.assertNotIn("GOOG", tickers)

        googl = next(h for h in parsed["holdings"] if h["ticker"] == "GOOGL")
        # Class C 4,090,422,764 + Class A 4,061,358,997
        self.assertEqual(googl["val"], 8151781761.0)
        self.assertEqual(parsed["holdings"][2]["ticker"], "GOOGL")

    def test_every_year_2010_2019_registers_a_q1_and_a_q3_period(self):
        """Both of each year's reports are registered: March 31 semi-annual and September 30 annual."""
        from scripts.extract_ground_truth_from_sec import HTML_ERA_FILINGS

        by_period = {entry[0]: entry for entry in HTML_ERA_FILINGS}
        for year in range(2010, 2020):
            with self.subTest(year=year):
                self.assertIn(f"{year}-Q1", by_period)
                self.assertIn(f"{year}-Q3", by_period)
                self.assertEqual(by_period[f"{year}-Q1"][4], f"{year}-03-31")
                self.assertEqual(by_period[f"{year}-Q3"][4], f"{year}-09-30")

    def test_semi_annual_and_annual_reports_are_distinct_documents(self):
        """No year may register the same file for both its Q1 and its Q3 period.

        Both reports are Form N-30D under the same conformed filer name, so a
        mix-up would not announce itself; a shared file name is the symptom.
        """
        from scripts.extract_ground_truth_from_sec import HTML_ERA_FILINGS

        filenames = [entry[1] for entry in HTML_ERA_FILINGS]
        self.assertEqual(len(filenames), len(set(filenames)))

        accessions = [entry[2] for entry in HTML_ERA_FILINGS]
        self.assertEqual(len(accessions), len(set(accessions)))

    def test_semi_annual_filings_state_their_own_march_31_period(self):
        """Each Q1 filing's SEC header declares 03-31, with no override excusing it."""
        from scripts.extract_ground_truth_from_sec import (
            HTML_ERA_FILINGS, read_filing_period,
        )

        for period, filename, _acc, _form, report_date, _filed, override in HTML_ERA_FILINGS:
            if not period.endswith("-Q1"):
                continue
            with self.subTest(period=period):
                self.assertIsNone(override)
                self.assertEqual(read_filing_period(self.dir / filename), report_date)

    def test_html_era_consolidation_leaves_total_unchanged(self):
        """Consolidating share classes must not create or destroy market value."""
        from scripts.extract_ground_truth_from_sec import HTML_ERA_FILINGS

        for period, filename, *_ in HTML_ERA_FILINGS:
            with self.subTest(period=period):
                parsed = self.parse(self.dir / filename)
                self.assertEqual(
                    round(sum(h["val"] for h in parsed["holdings"]), 2),
                    round(parsed["stated_total_usd"], 2),
                )


class TestArchivedFilingCoverage(unittest.TestCase):
    """No archived filing may sit unread. Zero rows is the failure this class exists to stop."""

    @classmethod
    def setUpClass(cls):
        from scripts.extract_ground_truth_from_sec import (
            FILINGS_DIR, HTML_ERA_FILINGS, N30D_HISTORICAL_FILINGS,
            parse_html_schedule_filing, parse_n30d_filing,
        )
        cls.dir = FILINGS_DIR
        cls.registry = {}
        for entry in N30D_HISTORICAL_FILINGS:
            cls.registry[entry[1]] = parse_n30d_filing
        for entry in HTML_ERA_FILINGS:
            cls.registry[entry[1]] = parse_html_schedule_filing
        cls.expected_registered = len(N30D_HISTORICAL_FILINGS) + len(HTML_ERA_FILINGS)

    def test_every_archived_spy_filing_is_registered_for_extraction(self):
        """Each SPY_*.txt on disk is claimed by exactly one era's registry."""
        self.assertEqual(len(self.registry), self.expected_registered)
        archived = sorted(path.name for path in self.dir.glob("SPY_*.txt"))
        self.assertEqual(sorted(self.registry), archived)

    def test_manifest_points_at_the_filing_the_extraction_reads(self):
        """The archive manifest and the extraction registry must name the same document.

        The manifest's "2014" key previously named the March 31 semi-annual report,
        which would have published a Q1 snapshot in the Q3 annual slot - the error #36
        found in the 2004 entry, where the archived document was a different fund.
        """
        from scripts.extract_ground_truth_from_sec import HTML_ERA_FILINGS

        with open(self.dir / "sec_annual_filings_manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(
            Path(manifest["2014"]["file_path"]).name,
            "SPY_2014_Q4_N-30D_0001193125-14-428689.txt",
        )
        self.assertEqual(
            Path(manifest["2014-semi-annual"]["file_path"]).name,
            "SPY_2014_Q2_N-30D_0001193125-14-220028.txt",
        )

        registered = {entry[1] for entry in HTML_ERA_FILINGS}
        annual_keys = [str(y) for y in range(2010, 2020)]
        semi_annual_keys = [f"{y}-semi-annual" for y in range(2010, 2020)]
        for key in annual_keys + semi_annual_keys:
            with self.subTest(manifest_key=key):
                self.assertIn(Path(manifest[key]["file_path"]).name, registered)

        # An annual key must never name a March 31 document, and vice versa: that
        # confusion is what put a semi-annual in the "2014" annual slot before #50.
        for key in annual_keys:
            with self.subTest(annual_key=key):
                self.assertNotIn("-03-31", manifest[key].get("report_date", ""))
        for key in semi_annual_keys:
            with self.subTest(semi_annual_key=key):
                self.assertEqual(
                    manifest[key]["report_date"], f"{manifest[key]['year']}-03-31"
                )

    def test_every_archived_spy_filing_reconciles_to_its_stated_total(self):
        """A filing that parses to zero rows, or to a sum the filing contradicts, fails."""
        for filename, parser in sorted(self.registry.items()):
            with self.subTest(filing=filename):
                parsed = parser(self.dir / filename)
                self.assertGreater(len(parsed["holdings"]), 0)
                self.assertEqual(parsed["total_val_usd"], parsed["stated_total_usd"])


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

    def test_single_class_issuer_keeps_its_filed_name(self):
        """One class alone is not a consolidation; renaming it would misreport the filing.

        SPY's 2006-2009 schedules list only Google Class A, years before the company
        was renamed Alphabet. Relabelling that position "Alphabet Inc." would publish a
        name no source document contains.
        """
        from scripts.extract_ground_truth_from_sec import consolidate_holdings

        consolidated = consolidate_holdings([
            {"name": "Google, Inc.", "ticker": "GOOGL", "cusip": "", "val": 300.0},
        ])
        self.assertEqual(len(consolidated), 1)
        self.assertEqual(consolidated[0]["ticker"], "GOOGL")
        self.assertEqual(consolidated[0]["name"], "Google, Inc.")


class TestIssuerSeparation(unittest.TestCase):
    """Distinct issuers must not be merged, and multi-class issuers must not be missed."""

    def test_coca_cola_enterprises_is_not_merged_into_ko(self):
        """The bottler was its own S&P 500 constituent (1999-2009) and must rank separately."""
        from scripts.extract_ground_truth_from_sec import (
            parse_n30d_filing, FILINGS_DIR, N30D_HISTORICAL_FILINGS,
        )

        for period, filename, *_ in N30D_HISTORICAL_FILINGS:
            parsed = parse_n30d_filing(FILINGS_DIR / filename)
            by_ticker = {h["ticker"]: h for h in parsed["holdings"]}
            self.assertIn("KO", by_ticker, period)
            ko_name = by_ticker["KO"]["name"].replace("Coca Cola", "Coca-Cola").replace(" Co.", " Co")
            self.assertIn("Coca-Cola Co", ko_name, period)
            self.assertNotIn("Enterprises", by_ticker["KO"]["name"], period)
            year = int(period.split("-")[0])
            if year >= 1999:
                self.assertIn("CCE", by_ticker, period)
                self.assertIn("Enterprises", by_ticker["CCE"]["name"], period)
                self.assertGreater(by_ticker["KO"]["val"], by_ticker["CCE"]["val"], period)
            else:
                self.assertNotIn("CCE", by_ticker, period)

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

    def test_n30d_all_filings_tickers_map_one_issuer_each(self):
        """Across all 1995-2009 filings, no ticker may absorb multiple distinct source company names."""
        from scripts.extract_ground_truth_from_sec import (
            parse_n30d_filing, FILINGS_DIR, _n30d_ticker,
            _resolve_n30d_schedule_bounds, _extract_n30d_positions,
        )

        manifest_path = FILINGS_DIR / "sec_annual_filings_manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        for year in range(1995, 2010):
            meta = manifest[str(year)]
            filing_path = ROOT / meta["file_path"]
            lines = filing_path.read_text(encoding="utf-8", errors="replace").splitlines()
            start, end = _resolve_n30d_schedule_bounds(lines, filing_path.name)
            positions = _extract_n30d_positions(lines, start, end)

            ticker_to_names = {}
            for pos in positions:
                ticker = _n30d_ticker(pos["name"])
                ticker_to_names.setdefault(ticker, set()).add(pos["name"])

            for ticker, names in ticker_to_names.items():
                self.assertEqual(
                    len(names), 1,
                    f"Year {year}: ticker {ticker} backed by multiple distinct source names: {sorted(names)}",
                )

            # Assert separate tracking for known spun-off / separately listed entities
            parsed = parse_n30d_filing(filing_path)
            by_ticker = {h["ticker"]: h for h in parsed["holdings"]}
            if 2001 <= year <= 2004:
                self.assertIn("T", by_ticker, f"{year}: missing T")
                self.assertIn("AWE", by_ticker, f"{year}: missing AWE (AT&T Wireless)")
            if 2001 <= year <= 2007:
                self.assertIn("AAPL", by_ticker, f"{year}: missing AAPL")
                self.assertIn("ABI", by_ticker, f"{year}: missing ABI (Applera)")
            if year == 2009:
                self.assertIn("TWX", by_ticker, f"{year}: missing TWX")
                self.assertIn("TWC", by_ticker, f"{year}: missing TWC (Time Warner Cable)")

    def test_html_era_filings_tickers_map_one_issuer_each(self):
        """Across all 2010-2019 filings, no ticker may absorb multiple distinct source names.

        Checks every position, not just the top 30: #36 shipped three patterns that
        silently absorbed separately listed issuers because the check stopped at 30.
        """
        from scripts.extract_ground_truth_from_sec import (
            FILINGS_DIR, HTML_ERA_FILINGS, _extract_html_positions,
            _html_schedule_rows, _n30d_ticker, _resolve_html_schedule_bounds,
        )

        for period, filename, *_ in HTML_ERA_FILINGS:
            with self.subTest(period=period):
                path = FILINGS_DIR / filename
                rows = _html_schedule_rows(path.read_text(encoding="utf-8", errors="replace"))
                start, end = _resolve_html_schedule_bounds(rows, path.name)
                positions = _extract_html_positions(rows, start, end)

                ticker_to_names = {}
                for pos in positions:
                    ticker_to_names.setdefault(_n30d_ticker(pos["name"]), set()).add(pos["name"])

                for ticker, names in sorted(ticker_to_names.items()):
                    self.assertEqual(
                        len(names), 1,
                        f"{period}: ticker {ticker} backed by multiple distinct "
                        f"source names: {sorted(names)}",
                    )

    def test_html_era_separately_listed_issuers_stay_separate(self):
        """Alphabet's two share classes must reach ranking as two distinct positions."""
        from scripts.extract_ground_truth_from_sec import (
            FILINGS_DIR, _extract_html_positions, _html_schedule_rows,
            _n30d_ticker, _resolve_html_schedule_bounds,
        )

        path = FILINGS_DIR / "SPY_2019_N-30D_0001193125-19-302203.txt"
        rows = _html_schedule_rows(path.read_text(encoding="utf-8", errors="replace"))
        start, end = _resolve_html_schedule_bounds(rows, path.name)
        tickers = {_n30d_ticker(p["name"]) for p in _extract_html_positions(rows, start, end)}

        self.assertIn("GOOGL", tickers)
        self.assertIn("GOOG", tickers)

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


class TestIsValidSpyAnnualReport(unittest.TestCase):
    """Unit tests for the download validators and their regression guards."""

    SEMI_ANNUAL_2015 = "SPY_2015_Q2_N-30D_0001193125-15-211393.txt"
    ANNUAL_2015 = "SPY_2015_N-30D_0001193125-15-390230.txt"

    def test_valid_spy_filing_fixed_width_era(self):
        """A genuine 1995-2009 SPY filing passes validation and parsing."""
        from scripts.download_all_historical_sec_filings import is_valid_spy_annual_report

        file_path = ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / "SPY_1995_N-30D_0000912057-96-003840.txt"
        content = file_path.read_text(encoding="utf-8", errors="replace")
        self.assertTrue(is_valid_spy_annual_report(file_path, 1995, content))

    def test_valid_spy_filing_html_era(self):
        """A 2010-2019 SPY filing passes validation (regression guard for HTML era)."""
        from scripts.download_all_historical_sec_filings import is_valid_spy_annual_report

        file_path = ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / "SPY_2015_N-30D_0001193125-15-390230.txt"
        content = file_path.read_text(encoding="utf-8", errors="replace")
        self.assertTrue(is_valid_spy_annual_report(file_path, 2015, content))

    def test_select_sector_spdr_filing_rejected(self):
        """The mis-archived Select Sector document is rejected by description exclusion."""
        from scripts.download_all_historical_sec_filings import is_valid_spy_annual_report

        file_path = ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / "SELECT_SECTOR_SPDR_2004_N-CSR_0000950135-04-005558.txt"
        content = file_path.read_text(encoding="utf-8", errors="replace")
        self.assertFalse(is_valid_spy_annual_report(file_path, 2004, content))

    def test_foreign_company_conformed_name_rejected(self):
        """A filing with a foreign COMPANY CONFORMED NAME is rejected."""
        from scripts.download_all_historical_sec_filings import is_valid_spy_annual_report

        file_path = ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / "SPY_1995_N-30D_0000912057-96-003840.txt"
        content = file_path.read_text(encoding="utf-8", errors="replace").replace(
            "SPDR TRUST SERIES 1", "FOREIGN TRUST CORP"
        )
        self.assertFalse(is_valid_spy_annual_report(file_path, 1995, content))

    def test_schedule_parse_error_re_raised_for_fixed_width_era(self):
        """A ScheduleParseError on a genuine SPY filing (<= 2009) must not be swallowed."""
        from unittest.mock import patch
        from scripts.download_all_historical_sec_filings import is_valid_spy_annual_report
        from scripts.extract_ground_truth_from_sec import ScheduleParseError

        file_path = ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / "SPY_1995_N-30D_0000912057-96-003840.txt"
        content = file_path.read_text(encoding="utf-8", errors="replace")
        with patch("scripts.download_all_historical_sec_filings.parse_n30d_filing", side_effect=ScheduleParseError("stated total mismatch")):
            with self.assertRaises(ScheduleParseError) as ctx:
                is_valid_spy_annual_report(file_path, 1995, content)
            self.assertIn(file_path.name, str(ctx.exception))

    def test_schedule_parse_error_re_raised_for_html_era(self):
        """A ScheduleParseError on a genuine SPY filing (2010-2019) must not be swallowed."""
        from unittest.mock import patch
        from scripts.download_all_historical_sec_filings import is_valid_spy_annual_report
        from scripts.extract_ground_truth_from_sec import ScheduleParseError

        file_path = ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / "SPY_2015_N-30D_0001193125-15-390230.txt"
        content = file_path.read_text(encoding="utf-8", errors="replace")
        with patch(
            "scripts.download_all_historical_sec_filings.parse_html_schedule_filing",
            side_effect=ScheduleParseError("stated total mismatch"),
        ):
            with self.assertRaises(ScheduleParseError) as ctx:
                is_valid_spy_annual_report(file_path, 2015, content)
            self.assertIn(file_path.name, str(ctx.exception))

    def test_html_era_filing_is_parsed_during_validation(self):
        """Validation must actually read the 2010-2019 schedule, not wave it through."""
        from unittest.mock import patch
        from scripts.download_all_historical_sec_filings import is_valid_spy_annual_report

        file_path = ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / "SPY_2015_N-30D_0001193125-15-390230.txt"
        content = file_path.read_text(encoding="utf-8", errors="replace")
        with patch(
            "scripts.download_all_historical_sec_filings.parse_html_schedule_filing"
        ) as parser:
            self.assertTrue(is_valid_spy_annual_report(file_path, 2015, content))
        parser.assert_called_once_with(file_path)


    def test_semi_annual_validator_accepts_a_genuine_march_31_report(self):
        """A real semi-annual report passes: SPY's own document, period 2015-03-31."""
        from scripts.download_all_historical_sec_filings import (
            is_valid_spy_semi_annual_report,
        )

        file_path = ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / self.SEMI_ANNUAL_2015
        content = file_path.read_text(encoding="utf-8", errors="replace")
        self.assertTrue(is_valid_spy_semi_annual_report(file_path, 2015, content))

    def test_semi_annual_validator_rejects_the_same_year_annual_report(self):
        """The period, not the form, separates the two reports.

        FY2015's annual report is Form N-30D filed by 'SPDR S&P 500 ETF TRUST' -
        identical on both counts to the semi-annual. Only CONFORMED PERIOD OF REPORT
        (2015-09-30, not 2015-03-31) tells them apart, and it must.
        """
        from scripts.download_all_historical_sec_filings import (
            is_valid_spy_semi_annual_report,
        )

        file_path = ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / self.ANNUAL_2015
        content = file_path.read_text(encoding="utf-8", errors="replace")
        self.assertFalse(is_valid_spy_semi_annual_report(file_path, 2015, content))

    def test_semi_annual_validator_rejects_a_neighbouring_years_report(self):
        """A March 31 report from the wrong year is still the wrong filing for that key."""
        from scripts.download_all_historical_sec_filings import (
            is_valid_spy_semi_annual_report,
        )

        file_path = ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / self.SEMI_ANNUAL_2015
        content = file_path.read_text(encoding="utf-8", errors="replace")
        self.assertFalse(is_valid_spy_semi_annual_report(file_path, 2016, content))

    def test_semi_annual_validator_rejects_select_sector_document(self):
        """Co-filed Select Sector documents are excluded from the semi-annual pass too."""
        from scripts.download_all_historical_sec_filings import (
            is_valid_spy_semi_annual_report,
        )

        file_path = ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / "SELECT_SECTOR_SPDR_2004_N-CSR_0000950135-04-005558.txt"
        content = file_path.read_text(encoding="utf-8", errors="replace")
        self.assertFalse(is_valid_spy_semi_annual_report(file_path, 2004, content))

    def test_annual_validator_cannot_distinguish_a_semi_annual_report(self):
        """Documents the limitation the semi-annual pass exists to work around.

        is_valid_spy_annual_report asserts filer identity and a faithful parse, never
        the period, so it accepts a March 31 semi-annual as readily as a September 30
        annual report - the failure that once put a Q1 snapshot in the "2014" annual
        manifest slot. The annual pass is safe only because it scans QTR4/QTR1, where
        the semi-annual never files. If that ever changes, this test is the warning.
        """
        from scripts.download_all_historical_sec_filings import is_valid_spy_annual_report

        file_path = ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / self.SEMI_ANNUAL_2015
        content = file_path.read_text(encoding="utf-8", errors="replace")
        self.assertTrue(is_valid_spy_annual_report(file_path, 2015, content))

    def test_semi_annual_schedule_parse_error_is_re_raised(self):
        """A reconciliation failure on a genuine semi-annual must not be swallowed."""
        from unittest.mock import patch
        from scripts.download_all_historical_sec_filings import (
            is_valid_spy_semi_annual_report,
        )
        from scripts.extract_ground_truth_from_sec import ScheduleParseError

        file_path = ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / self.SEMI_ANNUAL_2015
        content = file_path.read_text(encoding="utf-8", errors="replace")
        with patch(
            "scripts.download_all_historical_sec_filings.parse_html_schedule_filing",
            side_effect=ScheduleParseError("stated total mismatch"),
        ):
            with self.assertRaises(ScheduleParseError) as ctx:
                is_valid_spy_semi_annual_report(file_path, 2015, content)
            self.assertIn(file_path.name, str(ctx.exception))


class TestVanguardArchiveCoverage(unittest.TestCase):
    """Vanguard Index Trust's December 31 filings (issue #55).

    SPY's fiscal year ends September 30, so no SPY filing anchors a December 31 price
    for 1997-2019. These filings do. The archive is only useful if every document on
    disk is a year-end annual report and the manifest says so truthfully.
    """

    FILINGS_DIR = ROOT / "data" / "raw" / "ground_truth" / "sec_filings"
    MANIFEST = FILINGS_DIR / "vanguard_annual_filings_manifest.json"

    @classmethod
    def setUpClass(cls):
        with open(cls.MANIFEST, "r", encoding="utf-8") as f:
            cls.manifest = json.load(f)

    def test_every_archived_vanguard_filing_is_claimed_by_the_manifest(self):
        """No archived filing may sit unclaimed, and no entry may name a missing file."""
        on_disk = sorted(path.name for path in self.FILINGS_DIR.glob("VG500_*.txt"))
        claimed = sorted(Path(entry["file_path"]).name for entry in self.manifest.values())
        self.assertEqual(claimed, on_disk)
        self.assertEqual(len(self.manifest), 13)

    def test_every_filing_states_a_december_31_period(self):
        """The SEC header, not the filename, decides what a filing is.

        Vanguard files a June 30 semi-annual under the same form as its December 31
        annual report, so form type and filer identity cannot separate them. Asserting
        the period on disk keeps a semi-annual from occupying a year-end slot, which is
        the failure documented in docs/DATA_PROVENANCE.md 4.3.6.
        """
        from scripts.extract_ground_truth_from_sec import read_filing_period

        for year_key, entry in self.manifest.items():
            path = ROOT / entry["file_path"]
            with self.subTest(year=year_key):
                self.assertTrue(path.exists(), f"missing archived filing: {path}")
                period = read_filing_period(path)
                self.assertEqual(period, f"{year_key}-12-31")
                self.assertEqual(entry["report_date"], period)

    def test_manifest_sizes_match_the_archived_documents(self):
        """A truncated download must not pass as a complete filing."""
        for year_key, entry in self.manifest.items():
            path = ROOT / entry["file_path"]
            with self.subTest(year=year_key):
                self.assertEqual(path.stat().st_size, entry["file_size_bytes"])

    def test_vanguard_filings_are_kept_out_of_the_spy_manifest(self):
        """Two filers, two manifests.

        Both are keyed by bare year, so a Vanguard entry in the SPY manifest would
        collide with the SPY filing for the same year and silently displace it.
        """
        spy_manifest_path = self.FILINGS_DIR / "sec_annual_filings_manifest.json"
        with open(spy_manifest_path, "r", encoding="utf-8") as f:
            spy_manifest = json.load(f)

        for entry in spy_manifest.values():
            self.assertNotIn("VG500", entry["file_path"])
            self.assertNotIn("/36405/", entry["sec_url"])

        for entry in self.manifest.values():
            self.assertIn("VG500", entry["file_path"])
            self.assertIn("/36405/", entry["sec_url"])


class TestVanguardImpliedPrices(unittest.TestCase):
    """Implied December-31 prices derived from Vanguard filings (issue #55)."""

    PATH = ROOT / "data" / "raw" / "ground_truth" / "vanguard_implied_prices.json"

    @classmethod
    def setUpClass(cls):
        with open(cls.PATH, "r", encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.prices = cls.data["prices_by_ticker"]

    def test_agrees_with_spy_filings_on_the_one_shared_date(self):
        """Two unrelated filers must report the same price for the same date.

        SPY's fiscal year ended December 31 through 1996, so its FY1995 annual report and
        Vanguard's cover the same date. This is the only independent check available on
        the implied-price method, and it is asserted rather than merely documented so a
        future change to the extraction path cannot quietly break it.

        Expected values are read from SPY's archived filing at test time, not hardcoded.
        """
        from scripts.extract_ground_truth_from_sec import parse_n30d_filing

        spy = parse_n30d_filing(
            ROOT / "data" / "raw" / "ground_truth" / "sec_filings"
            / "SPY_1995_N-30D_0000912057-96-003840.txt"
        )
        by_name = {h["name"]: h for h in spy["holdings"]}

        shared = {
            "MOB": "Mobil Corp",
            "GTE": "GTE Corp",
            "BLS": "BellSouth Corp",
            "RD": "Royal Dutch Petroleum",
            "SBC": "SBC Communications",
        }
        checked = 0
        for ticker, stem in shared.items():
            match = next((h for name, h in by_name.items() if name.startswith(stem)), None)
            if match is None or not match.get("shares"):
                continue
            spy_price = match["val"] / match["shares"]
            vanguard_price = self.prices[ticker]["1995"]["price_usd"]
            with self.subTest(ticker=ticker):
                # Published schedules round share counts, so the two filers agree to
                # within a cent rather than exactly.
                self.assertAlmostEqual(vanguard_price, spy_price, delta=0.01)
            checked += 1
        self.assertGreaterEqual(checked, 4, "cross-filer check degenerated to nothing")

    def test_every_price_is_corroborated_by_a_majority_of_schedules(self):
        """Each filing holds several funds owning the same security; most must agree."""
        for ticker, years in self.prices.items():
            for year, obs in years.items():
                agree, total = (int(x) for x in obs["corroborating_agreement"].split("/"))
                with self.subTest(ticker=ticker, year=year):
                    self.assertGreater(agree * 2, total)

    def test_split_records_are_cited_to_a_filing(self):
        """A split ratio without a source is indistinguishable from a recollection."""
        path = ROOT / "data" / "raw" / "corporate_actions" / "splits.json"
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)["splits_by_ticker"]

        for ticker, record in records.items():
            with self.subTest(ticker=ticker):
                self.assertTrue(record["accession_number"])
                self.assertTrue(record["cik"])
                if record["splits"]:
                    # A stated split must be backed by words actually in the filing.
                    self.assertTrue(record["quoted_sentence"].strip())
                for split in record["splits"]:
                    self.assertGreater(split["ratio"], 1.0)
                    self.assertRegex(split["effective_date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_split_adjustment_agrees_with_spy_filings(self):
        """Adjusted Vanguard and SPY prices must describe one continuous series.

        SPY reports September 30 and Vanguard December 31. Once both are expressed in the
        same share terms, their ratio is a single quarter's price move. A split missing
        from splits.json would instead show up as a ratio near 2.0 or 0.5, because one
        side of the comparison would still be in pre-split terms.

        The bound is deliberately loose: Q4 2000 saw genuine moves past 2x for Lucent and
        Sun Microsystems, and Lucent's own Form 10-K405 reports that quarter's range as
        $12.19-$34.63, corroborating the fall this test must not reject.
        """
        from scripts.extract_ground_truth_from_sec import parse_n30d_filing
        from scripts.extract_vanguard_prices import _split_factor

        with open(ROOT / "data" / "raw" / "corporate_actions" / "splits.json", "r", encoding="utf-8") as f:
            splits = json.load(f)["splits_by_ticker"]
        manifest_path = (
            ROOT / "data" / "raw" / "ground_truth" / "sec_filings" / "sec_annual_filings_manifest.json"
        )
        with open(manifest_path, "r", encoding="utf-8") as f:
            spy_manifest = json.load(f)

        stems = {"LU": "Lucent", "EMC": "EMC Corp", "BLS": "BellSouth", "DELL": "Dell"}
        compared = 0
        for year_key in sorted(k for k in spy_manifest if "-" not in k):
            entry = spy_manifest[year_key]
            year = int(year_key)
            # parse_n30d_filing reads the fixed-width era only; 2010 onward is HTML and
            # postdates every registrant compared here.
            if year > 2009:
                continue
            report_date = entry.get("report_date") or (
                f"{year}-12-31" if year <= 1996 else f"{year}-09-30"
            )
            holdings = parse_n30d_filing(ROOT / entry["file_path"])["holdings"]
            for holding in holdings:
                for ticker, stem in stems.items():
                    if not holding["name"].startswith(stem) or not holding.get("shares"):
                        continue
                    if str(year) not in self.prices.get(ticker, {}):
                        continue
                    record = splits[ticker]["splits"]
                    spy_adj = (holding["val"] / holding["shares"]) / _split_factor(record, report_date)
                    vanguard_adj = self.prices[ticker][str(year)]["split_adjusted_price_usd"]
                    with self.subTest(ticker=ticker, year=year):
                        self.assertGreater(spy_adj / vanguard_adj, 0.35)
                        self.assertLess(spy_adj / vanguard_adj, 2.85)
                    compared += 1
        self.assertGreater(compared, 25, "cross-filer split check degenerated")

    def test_prices_are_labelled_as_unadjusted(self):
        """These are as-traded prices.

        Reading them as a return series without each registrant's split record inverts the
        result: Lucent 1997->1999 reads as a decline as-traded where the split-adjusted
        move is a rise. The label is what stops a downstream consumer treating them as
        comparable to the split-adjusted series in data/raw/tickers/.
        """
        self.assertIn("AS-TRADED", self.data["adjustment_status"])
        self.assertIn("NOT directly", self.data["adjustment_status"])

    def test_every_observation_cites_the_filing_it_came_from(self):
        """A derived figure without its source is indistinguishable from an estimate."""
        archived = {
            p.name for p in (ROOT / "data" / "raw" / "ground_truth" / "sec_filings").glob("VG500_*.txt")
        }
        for ticker, years in self.prices.items():
            for year, obs in years.items():
                with self.subTest(ticker=ticker, year=year):
                    self.assertIn(Path(obs["source_file"]).name, archived)
                    self.assertTrue(obs["accession_number"])
                    self.assertEqual(obs["report_date"], f"{year}-12-31")

    def test_securities_that_ceased_to_exist_are_recorded_as_events(self):
        """An absent price must be explained, so omission is not mistaken for a gap."""
        notes = " ".join(self.data["corporate_action_notes"])
        self.assertNotIn("1999", self.prices.get("MOB", {}))
        self.assertIn("MOB 1999", notes)
        self.assertNotIn("2005", self.prices.get("SBC", {}))
        self.assertIn("SBC 2005", notes)


class TestVanguardAuditedRosters(unittest.TestCase):
    """December-31 index rosters read from a filing rather than estimated (#55)."""

    PATH = ROOT / "data" / "raw" / "ground_truth" / "vanguard_audited_rosters.json"

    @classmethod
    def setUpClass(cls):
        with open(cls.PATH, "r", encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.rosters = cls.data["rosters_by_year"]

    def test_every_published_roster_reconciles_dollar_exact(self):
        """A schedule that reads short is indistinguishable from one that read fully.

        This is the check whose absence once let a parser silently drop rows
        (docs/DATA_PROVENANCE.md 4.3.6), so it is asserted on the published data and not
        only inside the extractor.
        """
        for year, roster in self.rosters.items():
            with self.subTest(year=year):
                self.assertEqual(
                    round(roster["parsed_total_usd_thousands"]),
                    round(roster["stated_total_usd_thousands"]),
                )

    def test_every_published_roster_is_sp500_sized(self):
        """Roughly five hundred holdings is what identifies the S&P 500 tracker.

        Each filing contains several Vanguard funds. In the FY2002 filing the first
        schedule belongs to a fund holding 148 stocks, which reconciles perfectly against
        its own total and is simply the wrong fund, so reconciliation alone cannot
        establish that the right schedule was read.
        """
        for year, roster in self.rosters.items():
            with self.subTest(year=year):
                self.assertGreaterEqual(roster["position_count"], 450)
                self.assertLessEqual(roster["position_count"], 540)

    def test_holdings_are_ranked_and_weighted_consistently(self):
        for year, roster in self.rosters.items():
            holdings = roster["holdings"]
            with self.subTest(year=year):
                self.assertEqual([h["rank"] for h in holdings], list(range(1, len(holdings) + 1)))
                values = [h["value_usd_thousands"] for h in holdings]
                self.assertEqual(values, sorted(values, reverse=True))
                self.assertAlmostEqual(sum(h["weight"] for h in holdings), 1.0, places=3)

    def test_withheld_years_are_recorded_with_a_reason(self):
        """A year that could not be read is named, not quietly omitted."""
        withheld = self.data["unreconciled_years"]
        for year, reason in withheld.items():
            with self.subTest(year=year):
                self.assertTrue(reason.strip())
                self.assertNotIn(year, self.rosters)

    def test_audited_rosters_contradict_the_estimated_ones(self):
        """The point of this dataset: estimates omit constituents the filings record.

        At 2000-12-31 the filing places SBC, EMC and Royal Dutch inside the Top 20 while
        the estimated roster omits all three. That gap is the survivorship bias #37 exists
        to remove, evidenced here at a December 31 date rather than inferred from a
        September snapshot.
        """
        estimates_path = ROOT / "data" / "raw" / "constituents" / "historical_index_weights.json"
        with open(estimates_path, "r", encoding="utf-8") as f:
            estimated = json.load(f)["constituents_by_year"]["2000"]

        top20 = [h["name"] for h in self.rosters["2000"]["holdings"][:20]]
        self.assertTrue(any(n.startswith("SBC Communications") for n in top20))
        self.assertTrue(any(n.startswith("EMC Corp") for n in top20))
        self.assertTrue(any(n.startswith("Royal Dutch") for n in top20))
        for absent in ("SBC", "EMC", "RD"):
            self.assertNotIn(absent, estimated)


if __name__ == "__main__":
    unittest.main()
