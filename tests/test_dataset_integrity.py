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
        self.assertEqual(len(list(raw_tickers_dir.glob("*.json"))), 33)
        self.assertEqual(len(list(raw_benchmarks_dir.glob("*.json"))), 2)


if __name__ == "__main__":
    unittest.main()
