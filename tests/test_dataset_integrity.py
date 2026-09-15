import json
import unittest
from pathlib import Path


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
        self.assertIn("T", data)
        # Verify 1996 Lucent and NCR spinoffs present in compiled data
        t_spinoffs = {ev["spinco_ticker"]: ev for ev in data["T"]}
        self.assertIn("LU", t_spinoffs)
        self.assertIn("NCR", t_spinoffs)
        self.assertIn("WBD", t_spinoffs)
        self.assertEqual(t_spinoffs["LU"]["year"], 1996)
        self.assertEqual(t_spinoffs["LU"]["quarter"], 3)
        self.assertEqual(t_spinoffs["LU"]["distribution_per_share"], 14.87)
        self.assertEqual(t_spinoffs["LU"]["basis_retention_ratio"], 0.7201)
        self.assertEqual(t_spinoffs["NCR"]["year"], 1996)
        self.assertEqual(t_spinoffs["NCR"]["quarter"], 4)
        self.assertEqual(t_spinoffs["NCR"]["distribution_per_share"], 2.10)
        self.assertEqual(t_spinoffs["NCR"]["basis_retention_ratio"], 0.9523)

    def test_att_decoupled_series_1994_1997(self):
        with open(self.dividends_path, "r", encoding="utf-8") as f:
            divs = json.load(f)
        with open(self.prices_path, "r", encoding="utf-8") as f:
            prices = json.load(f)
        # Verify AT&T Corp decoupled values (not SBC Communications)
        self.assertEqual(prices["T"]["1994"], 50.25)
        self.assertEqual(prices["T"]["1995"], 64.75)
        self.assertEqual(prices["T"]["1996"], 43.50)
        self.assertEqual(prices["T"]["1997"], 61.25)
        for yr in ["1994", "1995", "1996", "1997"]:
            self.assertAlmostEqual(divs["T"][yr], 1.32, places=2)

    def test_att_quarterly_decoupled_series_1993_1994(self):
        q_prices_path = self.data_dir / "sp500_quarterly_prices.json"
        q_constituents_path = self.data_dir / "sp500_quarterly_constituents.json"
        with open(q_prices_path, "r", encoding="utf-8") as f:
            q_prices = json.load(f)
        with open(q_constituents_path, "r", encoding="utf-8") as f:
            q_constituents = json.load(f)

        # Assert 1993-Q1 price is decoupled (>= 50.0, not SBC unadjusted ~14.75)
        self.assertIn("1993-Q1", q_prices["T"])
        self.assertGreaterEqual(q_prices["T"]["1993-Q1"], 50.0)
        self.assertEqual(q_prices["T"]["1993-Q1"], 52.50)
        self.assertEqual(q_prices["T"]["1993-Q2"], 54.00)
        self.assertEqual(q_prices["T"]["1993-Q3"], 56.25)

        # Assert 1994-Q1 trailing 1y return is realistic (between -0.20 and +0.20, not +250%)
        t_entry = next((c for c in q_constituents["1994-Q1"] if c["ticker"] == "T"), None)
        self.assertIsNotNone(t_entry, "T not found in 1994-Q1 constituents")
        ret_1y = t_entry["trailing_1y_return"]
        self.assertGreaterEqual(ret_1y, -0.20, f"Trailing 1y return {ret_1y} too negative")
        self.assertLessEqual(ret_1y, 0.20, f"Trailing 1y return {ret_1y} spiked unexpectedly")

    def test_build_datasets_script_syntax_and_import(self):
        """Verify scripts/build_datasets_from_raw.py compiles without IndentationError or SyntaxError."""
        build_script = Path(__file__).resolve().parent.parent / "scripts" / "build_datasets_from_raw.py"
        self.assertTrue(build_script.exists())
        with open(build_script, "r", encoding="utf-8") as f:
            code = f.read()
        compiled = compile(code, str(build_script), "exec")
        self.assertIsNotNone(compiled)


if __name__ == "__main__":
    unittest.main()

