"""Unit tests for S&P 500 DataLoader and dataset integrity."""

import os
from pathlib import Path
import unittest

import engine
from engine.data_loader import DataLoader
from engine.models import ConstituentSnapshot


class TestDataLoader(unittest.TestCase):
    """Test suite for DataLoader, constituent data, and split-adjusted price data."""

    SPX_BENCHMARKS = {
        1994: 459.27,
        1995: 615.93,
        1996: 740.74,
        1997: 970.43,
        1998: 1229.23,
        1999: 1469.25,
        2000: 1320.28,
        2001: 1148.08,
        2002: 879.82,
        2003: 1111.92,
        2004: 1211.92,
        2005: 1248.29,
        2006: 1418.30,
        2007: 1468.36,
        2008: 903.25,
        2009: 1115.10,
        2010: 1257.64,
        2011: 1257.60,
        2012: 1426.19,
        2013: 1848.36,
        2014: 2058.90,
        2015: 2043.94,
        2016: 2238.83,
        2017: 2673.61,
        2018: 2506.85,
        2019: 3230.78,
        2020: 3756.07,
        2021: 4766.18,
        2022: 3839.50,
        2023: 4769.83,
        2024: 5881.63,
    }

    def setUp(self):
        """Set up DataLoader instance for tests."""
        self.loader = DataLoader()

    def test_engine_reexport(self):
        """Verify DataLoader is exported from top-level engine package."""
        self.assertTrue(hasattr(engine, "DataLoader"))
        self.assertIs(engine.DataLoader, DataLoader)

    def test_custom_paths_and_missing_file_errors(self):
        """Verify explicit paths work and non-existent files raise FileNotFoundError."""
        repo_root = Path(__file__).resolve().parent.parent
        constituents_file = repo_root / "data" / "sp500_constituents.json"
        prices_file = repo_root / "data" / "sp500_prices.json"

        custom_loader = DataLoader(
            constituents_path=constituents_file, prices_path=prices_file
        )
        self.assertEqual(len(custom_loader.get_available_years()), 31)

        with self.assertRaises(FileNotFoundError):
            DataLoader(constituents_path="nonexistent_constituents.json")

        with self.assertRaises(FileNotFoundError):
            DataLoader(
                constituents_path=constituents_file,
                prices_path="nonexistent_prices.json",
            )

        with self.assertRaises(FileNotFoundError):
            DataLoader(
                constituents_path=constituents_file,
                prices_path=prices_file,
                dividends_path="nonexistent_dividends.json",
            )

    def test_available_years_coverage(self):
        """Verify DataLoader covers 31 years from 1994 through 2024 inclusive."""
        years = self.loader.get_available_years()
        expected_years = list(range(1994, 2025))
        self.assertEqual(years, expected_years)
        self.assertEqual(len(years), 31)

    def test_spx_benchmark_levels(self):
        """Verify S&P 500 index levels match historical benchmark closes for all 31 years."""
        for year, expected_level in self.SPX_BENCHMARKS.items():
            actual_level = self.loader.get_spx_level(year)
            self.assertAlmostEqual(
                actual_level,
                expected_level,
                places=2,
                msg=f"SPX level mismatch for year {year}",
            )

    def test_universe_loading_and_structure(self):
        """Verify load_universe returns valid ConstituentSnapshot list with at least 10 stocks per year."""
        for year in range(1994, 2025):
            universe = self.loader.load_universe(year)
            self.assertIsInstance(universe, list)
            self.assertGreaterEqual(
                len(universe),
                10,
                f"Year {year} has fewer than 10 constituents: {len(universe)}",
            )
            total_weight = sum(c.market_cap_weight for c in universe)
            self.assertGreater(total_weight, 0.10)
            self.assertLess(total_weight, 0.60)

            for c in universe:
                self.assertIsInstance(c, ConstituentSnapshot)
                self.assertEqual(c.year, year)
                self.assertIsInstance(c.ticker, str)
                self.assertTrue(len(c.ticker) > 0)
                self.assertIsInstance(c.name, str)
                self.assertTrue(len(c.name) > 0)
                self.assertIsInstance(c.market_cap_weight, (float, int))
                self.assertGreater(c.market_cap_weight, 0.0)
                self.assertIsInstance(c.trailing_1y_return, (float, int))

    def test_benchmark_years_top_constituents(self):
        """Verify key benchmark years feature historically accurate top constituents."""
        # 1995: GE, T (AT&T), XOM (Exxon) in top 3
        u_1995 = sorted(
            self.loader.load_universe(1995),
            key=lambda c: c.market_cap_weight,
            reverse=True,
        )
        top3_1995 = {c.ticker for c in u_1995[:3]}
        self.assertTrue(
            {"GE", "T", "XOM"}.issubset(top3_1995),
            f"1995 top 3 tickers was {top3_1995}, expected GE, T, XOM",
        )

        # 2000: GE, XOM, PFE, CSCO in top 4
        u_2000 = sorted(
            self.loader.load_universe(2000),
            key=lambda c: c.market_cap_weight,
            reverse=True,
        )
        top4_2000 = {c.ticker for c in u_2000[:4]}
        self.assertTrue(
            {"GE", "XOM", "PFE", "CSCO"}.issubset(top4_2000),
            f"2000 top 4 tickers was {top4_2000}, expected GE, XOM, PFE, CSCO",
        )

        # 2020: AAPL, MSFT, AMZN in top 3
        u_2020 = sorted(
            self.loader.load_universe(2020),
            key=lambda c: c.market_cap_weight,
            reverse=True,
        )
        top3_2020 = {c.ticker for c in u_2020[:3]}
        self.assertTrue(
            {"AAPL", "MSFT", "AMZN"}.issubset(top3_2020),
            f"2020 top 3 tickers was {top3_2020}, expected AAPL, MSFT, AMZN",
        )

        # 2024: AAPL, NVDA, MSFT in top 3
        u_2024 = sorted(
            self.loader.load_universe(2024),
            key=lambda c: c.market_cap_weight,
            reverse=True,
        )
        top3_2024 = {c.ticker for c in u_2024[:3]}
        self.assertTrue(
            {"AAPL", "NVDA", "MSFT"}.issubset(top3_2024),
            f"2024 top 3 tickers was {top3_2024}, expected AAPL, NVDA, MSFT",
        )

    def test_price_retrieval_and_positivity(self):
        """Verify price retrieval returns strictly positive floats for all constituents in all active years."""
        for year in range(1994, 2025):
            universe = self.loader.load_universe(year)
            for c in universe:
                price = self.loader.get_price(c.ticker, year)
                self.assertIsInstance(price, float)
                self.assertGreater(
                    price,
                    0.0,
                    f"Price for {c.ticker} in {year} must be positive, got {price}",
                )

    def test_price_return_consistency(self):
        """Verify trailing_1y_return in year t equals (P_t - P_{t-1}) / P_{t-1} when price at t-1 exists."""
        for year in range(1995, 2025):
            universe = self.loader.load_universe(year)
            for c in universe:
                try:
                    p_prev = self.loader.get_price(c.ticker, year - 1)
                except (KeyError, ValueError):
                    continue
                p_curr = self.loader.get_price(c.ticker, year)
                expected_return = (p_curr - p_prev) / p_prev
                self.assertAlmostEqual(
                    c.trailing_1y_return,
                    expected_return,
                    places=3,
                    msg=f"Return inconsistency for {c.ticker} in {year}: snapshot={c.trailing_1y_return}, calculated={expected_return}",
                )

    def test_error_handling_invalid_inputs(self):
        """Verify appropriate errors are raised for invalid years or unknown tickers."""
        # Invalid year for load_universe
        with self.assertRaises((KeyError, ValueError)):
            self.loader.load_universe(1980)

        with self.assertRaises((KeyError, ValueError)):
            self.loader.load_universe(2035)

        # Invalid year for get_spx_level
        with self.assertRaises((KeyError, ValueError)):
            self.loader.get_spx_level(1980)

        # Invalid ticker for get_price
        with self.assertRaises((KeyError, ValueError)):
            self.loader.get_price("NONEXISTENT_TICKER", 2020)

        # Invalid year for valid ticker
        with self.assertRaises(KeyError):
            self.loader.get_price("AAPL", 1950)

    def test_get_dividend(self):
        aapl_div = self.loader.get_dividend("AAPL", 2024)
        self.assertGreater(aapl_div, 0.0)
        unknown_div = self.loader.get_dividend("NONEXISTENT", 2024)
        self.assertEqual(unknown_div, 0.0)

    def test_spx_tr_and_dividend_yield(self):
        tr_2024 = self.loader.get_spx_tr_level(2024)
        self.assertGreater(tr_2024, 0.0)
        yield_2024 = self.loader.get_spx_dividend_yield(2024)
        self.assertGreaterEqual(yield_2024, 0.0)
        self.assertLess(yield_2024, 0.10)
        # Check 1994 yield calculation using 1993 base
        yield_1994 = self.loader.get_spx_dividend_yield(1994)
        self.assertGreaterEqual(yield_1994, 0.0)

    def test_available_universes(self):
        """Verify get_available_universes returns registered universes including sp500 and world."""
        universes = self.loader.get_available_universes()
        self.assertIn("sp500", universes)
        self.assertIn("world", universes)

    def test_load_world_universe(self):
        """Verify load_universe loads world dataset with valid snapshots and ADR tickers."""
        # Test default world loading
        world_2024 = self.loader.load_universe(2024, universe="world")
        self.assertGreater(len(world_2024), 0)
        tickers = {s.ticker for s in world_2024}
        self.assertTrue("TSM" in tickers or "ASML" in tickers or "NVO" in tickers)

        # Test alias 'all_world'
        world_alias = self.loader.load_universe(2024, universe="all_world")
        self.assertEqual(len(world_alias), len(world_2024))

        # Test invalid universe raises ValueError
        with self.assertRaises(ValueError):
            self.loader.load_universe(2024, universe="invalid_universe")


if __name__ == "__main__":
    unittest.main()
