import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestDatasetIntegrity(unittest.TestCase):
    def setUp(self):
        self.data_dir = Path(__file__).resolve().parent.parent / "data"
        self.dividends_path = self.data_dir / "sp500_dividends.json"
        self.prices_path = self.data_dir / "sp500_prices.json"

    def test_dividends_dataset_exists_and_valid(self):
        self.assertTrue(self.dividends_path.exists(), "sp500_dividends.json missing")
        with open(self.dividends_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("AAPL", data)
        self.assertIn("MSFT", data)
        self.assertIn("KO", data)
        for ticker, years in data.items():
            for yr, dps in years.items():
                self.assertGreaterEqual(dps, 0.0, f"Negative DPS for {ticker} in {yr}")

    def test_sp500_tr_series_present(self):
        with open(self.prices_path, "r", encoding="utf-8") as f:
            prices = json.load(f)
        self.assertIn("^GSPC", prices)
        self.assertIn("^SP500TR", prices)
        # Verify 1993 base level is present for 1994 return calculation
        self.assertIn("1993", prices["^GSPC"])
        self.assertIn("1993", prices["^SP500TR"])
        for yr in range(1994, 2025):
            str_yr = str(yr)
            self.assertIn(str_yr, prices["^SP500TR"])
            self.assertGreater(prices["^SP500TR"][str_yr], 0.0)
            self.assertGreaterEqual(prices["^SP500TR"][str_yr], prices["^GSPC"][str_yr])

    def test_benchmark_1994_dividend_yield(self):
        from engine.data_loader import DataLoader
        loader = DataLoader()
        y_1994 = loader.get_spx_dividend_yield(1994)
        # Yield should reflect the historical ~2.86% dividend yield, not an erroneous 17.17%
        self.assertGreaterEqual(y_1994, 0.025)
        self.assertLessEqual(y_1994, 0.032)
        self.assertAlmostEqual(y_1994, 0.0286, places=3)

    def test_walmart_split_adjustment(self):
        from engine.data_loader import DataLoader
        loader = DataLoader()
        p_2023 = loader.get_price("WMT", 2023)
        p_2024 = loader.get_price("WMT", 2024)
        ret_2024 = (p_2024 - p_2023) / p_2023
        # 2023 to 2024 return should be ~+69.2%, not an unadjusted +238%
        self.assertGreater(ret_2024, 0.65)
        self.assertLess(ret_2024, 0.75)

    def test_ge_historical_returns(self):
        from engine.data_loader import DataLoader
        loader = DataLoader()
        p_1998 = loader.get_price("GE", 1998)
        p_1999 = loader.get_price("GE", 1999)
        p_2000 = loader.get_price("GE", 2000)
        ret_1999 = (p_1999 - p_1998) / p_1998
        ret_2000 = (p_2000 - p_1999) / p_1999
        # GE gained ~+51.7% in 1999 and dropped ~-7.07% in 2000 (not -53.5%)
        self.assertGreater(ret_1999, 0.48)
        self.assertLess(ret_1999, 0.55)
        self.assertGreater(ret_2000, -0.10)
        self.assertLess(ret_2000, -0.05)

    def test_aig_crisis_and_recovery_returns(self):
        from engine.data_loader import DataLoader
        loader = DataLoader()
        p_2007 = loader.get_price("AIG", 2007)
        p_2008 = loader.get_price("AIG", 2008)
        p_2009 = loader.get_price("AIG", 2009)
        ret_2008 = (p_2008 - p_2007) / p_2007
        ret_2009 = (p_2009 - p_2008) / p_2008
        # AIG crashed ~-97.3% in 2008 and stabilized in 2009 (~-4.5%)
        self.assertLess(ret_2008, -0.95)
        self.assertGreater(ret_2009, -0.10)
        self.assertLess(ret_2009, 0.05)

    def test_raw_cache_files_exist(self):
        raw_tickers_dir = self.data_dir / "raw" / "tickers"
        raw_benchmarks_dir = self.data_dir / "raw" / "benchmarks"
        self.assertTrue(raw_tickers_dir.exists())
        self.assertTrue(raw_benchmarks_dir.exists())
        self.assertGreaterEqual(len(list(raw_tickers_dir.glob("*.json"))), 33)
        self.assertGreaterEqual(len(list(raw_benchmarks_dir.glob("*.json"))), 2)
        # Check key S&P 500 and Non-US ADR tickers
        self.assertTrue((raw_tickers_dir / "AAPL.json").exists())
        self.assertTrue((raw_tickers_dir / "TSM.json").exists())
        self.assertTrue((raw_tickers_dir / "SHEL.json").exists())

    def test_world_datasets_exist_and_valid(self):
        world_prices_path = self.data_dir / "world_prices.json"
        world_dividends_path = self.data_dir / "world_dividends.json"
        world_constituents_path = self.data_dir / "world_constituents.json"

        self.assertTrue(world_prices_path.exists())
        self.assertTrue(world_dividends_path.exists())
        self.assertTrue(world_constituents_path.exists())

        with open(world_constituents_path, "r", encoding="utf-8") as f:
            constituents = json.load(f)
        with open(world_prices_path, "r", encoding="utf-8") as f:
            prices = json.load(f)

        for yr in range(1994, 2025):
            str_yr = str(yr)
            self.assertIn(str_yr, constituents)
            self.assertEqual(len(constituents[str_yr]), 12)
            for c in constituents[str_yr]:
                ticker = c["ticker"]
                self.assertIn(ticker, prices)
                self.assertIn(str_yr, prices[ticker])
                self.assertGreater(prices[ticker][str_yr], 0.0)

    def test_spinoffs_raw_catalog_valid(self):
        spinoffs_file = self.data_dir / "raw" / "corporate_actions" / "spinoffs.json"
        self.assertTrue(spinoffs_file.exists(), "raw spinoffs.json missing")
        with open(spinoffs_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for ticker in ["MO", "T", "GE"]:
            self.assertIn(ticker, data)
            for event in data[ticker]:
                self.assertIn("ex_date", event)
                self.assertIn("year", event)
                self.assertIn("quarter", event)
                self.assertGreater(event["distribution_per_share"], 0.0)
                self.assertGreater(event["basis_retention_ratio"], 0.0)
                self.assertLess(event["basis_retention_ratio"], 1.0)

    def test_att_corp_historical_raw_exists(self):
        t_hist_file = self.data_dir / "raw" / "tickers" / "T_CORP_HISTORICAL.json"
        self.assertTrue(t_hist_file.exists(), "T_CORP_HISTORICAL.json missing")
        with open(t_hist_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        chart = data["chart"]["result"][0]
        self.assertEqual(chart["meta"]["symbol"], "T_CORP")

    def test_spinoff_distributions_compiled(self):
        compiled_file = self.data_dir / "spinoff_distributions.json"
        self.assertTrue(compiled_file.exists(), "spinoff_distributions.json missing")
        with open(compiled_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("MO", data)
        self.assertIn("GE", data)
        self.assertIn("T_CORP", data)
        self.assertIn("T", data)

        # Verify 1996 Lucent and NCR spinoffs present in compiled data for T_CORP
        t_corp_spinoffs = {ev["spinco_ticker"]: ev for ev in data["T_CORP"]}
        self.assertIn("LU", t_corp_spinoffs)
        self.assertIn("NCR", t_corp_spinoffs)
        self.assertEqual(t_corp_spinoffs["LU"]["year"], 1996)
        self.assertEqual(t_corp_spinoffs["LU"]["quarter"], 3)
        # Converted into final share terms: the as-traded 14.87 of spinoffs.json over
        # T_CORP's 0.2 split factor. The compiled dataset is what the engine reads, so
        # it must carry the converted value, not the raw one.
        self.assertEqual(t_corp_spinoffs["LU"]["distribution_per_share"], 74.35)
        self.assertEqual(t_corp_spinoffs["LU"]["basis_retention_ratio"], 0.7201)

        self.assertEqual(t_corp_spinoffs["NCR"]["year"], 1996)
        self.assertEqual(t_corp_spinoffs["NCR"]["quarter"], 4)
        self.assertEqual(t_corp_spinoffs["NCR"]["distribution_per_share"], 10.50)
        self.assertEqual(t_corp_spinoffs["NCR"]["basis_retention_ratio"], 0.9523)

        # Verify 2022 Warner Bros. Discovery spinoff present in compiled data for T (AT&T Inc.)
        t_spinoffs = {ev["spinco_ticker"]: ev for ev in data["T"]}
        self.assertIn("WBD", t_spinoffs)
        self.assertEqual(t_spinoffs["WBD"]["year"], 2022)
        self.assertEqual(t_spinoffs["WBD"]["quarter"], 2)
        self.assertEqual(t_spinoffs["WBD"]["distribution_per_share"], 5.81)
        self.assertEqual(t_spinoffs["WBD"]["basis_retention_ratio"], 0.7623)

    def test_att_decoupled_series_1994_1997(self):
        """Verify T_CORP derived series from audited Vanguard 500 filings."""
        with open(self.dividends_path, "r", encoding="utf-8") as f:
            divs = json.load(f)
        with open(self.prices_path, "r", encoding="utf-8") as f:
            prices = json.load(f)
        self.assertIn("T_CORP", prices)
        self.assertAlmostEqual(prices["T_CORP"]["1994"], 251.2494, places=4)
        self.assertAlmostEqual(prices["T_CORP"]["1995"], 323.7504, places=4)
        # 1996 is the filed 217.5002 less the separately credited NCR entitlement: the
        # distribution went ex on the filing date, so the filed value carries it.
        self.assertAlmostEqual(prices["T_CORP"]["1996"], 207.0002, places=4)
        self.assertAlmostEqual(prices["T_CORP"]["1997"], 306.2499, places=4)
        # Derived series have no dividend records (filings report holdings, not distributions)
        self.assertEqual(divs.get("T_CORP", {}), {})

    def test_att_distribution_endpoints_conserve_quoted_wealth(self):
        """Parent plus credited child must equal the filed package quote.

        The 1996-12-31 Schedule of Investments values AT&T Corp at 217.5002 in final
        share terms, cum-NCR. The model splits that one number into two: a parent price
        and a separately credited distribution. Neither may be changed without the other,
        or the endpoint gains or loses wealth that the filing does not record.
        """
        with open(self.prices_path, "r", encoding="utf-8") as f:
            prices = json.load(f)
        with open(self.data_dir / "spinoff_distributions.json", "r", encoding="utf-8") as f:
            spinoffs = json.load(f)

        ncr, = [ev for ev in spinoffs["T_CORP"] if ev["spinco_ticker"] == "NCR"]
        parent = prices["T_CORP"]["1996"]
        self.assertAlmostEqual(parent + ncr["distribution_per_share"], 217.5002, places=4)

        # Lucent went ex on 1996-09-30, a quarter before the filing date, so the
        # year-end quote is already clear of it and it must NOT be added back.
        lucent, = [ev for ev in spinoffs["T_CORP"] if ev["spinco_ticker"] == "LU"]
        self.assertNotAlmostEqual(
            parent + ncr["distribution_per_share"] + lucent["distribution_per_share"],
            217.5002,
            places=4,
        )

    def test_att_sbc_identity_separation(self):
        """Lock in identity separation across annual constituent rosters.

        - T appears in no annual constituent roster for any year before 2005.
        - T_CORP appears in no annual constituent roster for 2000 or later.
        - T and SBC never both appear in the same year's roster.
        """
        constituents_path = self.data_dir / "sp500_constituents.json"
        with open(constituents_path, "r", encoding="utf-8") as f:
            rosters = json.load(f)

        for yr_str, entries in rosters.items():
            year = int(yr_str)
            tickers = {c["ticker"] for c in entries}

            if year < 2005:
                self.assertNotIn(
                    "T",
                    tickers,
                    f"T unexpectedly found in {year} roster before 2005",
                )
            if year >= 2000:
                self.assertNotIn(
                    "T_CORP",
                    tickers,
                    f"T_CORP unexpectedly found in {year} roster from 2000 on",
                )
            self.assertFalse(
                "T" in tickers and "SBC" in tickers,
                f"T and SBC both appeared in {year} roster",
            )

    def test_build_datasets_script_syntax_and_import(self):
        """Verify scripts/build_datasets_from_raw.py compiles without IndentationError or SyntaxError."""
        build_script = Path(__file__).resolve().parent.parent / "scripts" / "build_datasets_from_raw.py"
        self.assertTrue(build_script.exists())
        with open(build_script, "r", encoding="utf-8") as f:
            code = f.read()
        compiled = compile(code, str(build_script), "exec")
        self.assertIsNotNone(compiled)


class TestDerivedConstituentSeries(unittest.TestCase):
    """Constituents whose prices are derived from filings rather than a vendor (#55)."""

    @classmethod
    def setUpClass(cls):
        from scripts.build_datasets_from_raw import DERIVED_NAMES, SP500_NAMES
        cls.derived = DERIVED_NAMES
        cls.vendor = SP500_NAMES
        with open(ROOT / "data" / "sp500_prices.json", "r", encoding="utf-8") as f:
            cls.prices = json.load(f)
        with open(ROOT / "data" / "sp500_dividends.json", "r", encoding="utf-8") as f:
            cls.dividends = json.load(f)

    def test_each_derived_constituent_reaches_the_built_dataset(self):
        for ticker in self.derived:
            with self.subTest(ticker=ticker):
                self.assertIn(ticker, self.prices)
                self.assertTrue(self.prices[ticker])

    def test_a_constituent_has_exactly_one_price_source(self):
        """Vendor and derived series must never both claim a ticker.

        They are adjusted to different bases - Yahoo adjusts to the present, a delisted
        series to its own final trading date - so silently preferring one would produce a
        series that is internally inconsistent without saying so.
        """
        for ticker in self.derived:
            with self.subTest(ticker=ticker):
                self.assertNotIn(ticker, self.vendor)
                self.assertFalse((ROOT / "data" / "raw" / "tickers" / f"{ticker}.json").exists())

    def test_derived_constituents_carry_no_fabricated_dividends(self):
        """A Schedule of Investments reports holdings, not distributions.

        An empty dividend series is the honest value. Zero-filling it would understate
        total return for these issuers without recording that the figure is unknown
        rather than nil.
        """
        for ticker in self.derived:
            with self.subTest(ticker=ticker):
                self.assertEqual(self.dividends.get(ticker, {}), {})

    def test_derived_series_reach_the_quarterly_datasets(self):
        """Quarterly coverage now exists for these constituents (#63).

        They were withheld entirely while no archived source priced them at March 31. Q1
        is now sourced -- SEI Index Funds' audited March-31 statements of net assets for
        1995-2006, and Prudential's unaudited 1994 -- and Q4 is derived from the same
        audited December-31 rosters that already price them annually.
        """
        with open(ROOT / "data" / "sp500_quarterly_prices.json", "r", encoding="utf-8") as f:
            quarterly = json.load(f)
        for ticker in self.derived:
            with self.subTest(ticker=ticker):
                self.assertIn(ticker, quarterly)
                self.assertTrue(quarterly[ticker])

    def test_every_quarterly_candidate_can_be_priced_wherever_it_is_held(self):
        """The rule that makes partial coverage safe, asserted against the built data.

        engine/backtest.py values every OPEN POSITION at every quarter end before
        selection runs (backtest.py:180), so buying a constituent commits the run to
        pricing it again at the next quarter end -- the one where it is sold if it has
        dropped out of the universe. The exact requirement is therefore: every quarter a
        constituent can be a candidate in must carry a price, and so must the quarter
        immediately after it.

        This is the invariant that replaced withholding the series outright. Asserting it
        on the built dataset rather than trusting the builder is the point: the earlier
        rule -- keep the ticker if it has ANY quarter of the year -- also produced a
        dataset that looked complete, and its failure showed up only as a KeyError part
        way through a run.
        """
        with open(ROOT / "data" / "sp500_quarterly_prices.json", "r", encoding="utf-8") as f:
            quarterly = json.load(f)
        with open(
            ROOT / "data" / "sp500_quarterly_constituents.json", "r", encoding="utf-8"
        ) as f:
            constituents = json.load(f)

        def next_quarter(key):
            year, q = int(key[:4]), int(key[-1])
            return f"{year}-Q{q + 1}" if q < 4 else f"{year + 1}-Q1"

        horizon = sorted({k for series in quarterly.values() for k in series})
        candidate_quarters = {}
        for key, entries in constituents.items():
            for entry in entries:
                ticker = entry["ticker"] if isinstance(entry, dict) else entry
                candidate_quarters.setdefault(ticker, set()).add(key)

        for ticker, quarters in sorted(candidate_quarters.items()):
            if ticker not in quarterly:
                continue
            priced = set(quarterly[ticker])
            needed = set(quarters)
            # The quarter a position is sold in, for every quarter it could be bought in.
            # Past the end of the price horizon there is no next quarter to value at.
            needed |= {
                nxt for q in quarters if (nxt := next_quarter(q)) <= horizon[-1]
            }
            with self.subTest(ticker=ticker):
                self.assertEqual(
                    sorted(needed - priced),
                    [],
                    f"{ticker} is a quarterly candidate but has no price where an open "
                    f"position would be valued",
                )


if __name__ == "__main__":
    unittest.main()
