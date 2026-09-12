"""Unit tests for Mutual Fund comparison framework and FBGRX benchmark integration.

Zero external dependencies - Python 3 standard library unittest only.
"""

import unittest

from engine.data_loader import DataLoader
from engine.metrics import calculate_benchmark_annual_series, calculate_cagr


class TestMutualFundDataLoader(unittest.TestCase):
    """Test DataLoader benchmark retrieval for FBGRX and generic benchmarks."""

    def setUp(self):
        self.loader = DataLoader()

    def test_fbgrx_annual_levels(self):
        """Verify annual FBGRX NAV and TR levels are positive and cover 1993-2024."""
        pr_1993 = self.loader.get_fbgrx_level(1993)
        tr_1993 = self.loader.get_fbgrx_tr_level(1993)
        pr_2024 = self.loader.get_fbgrx_level(2024)
        tr_2024 = self.loader.get_fbgrx_tr_level(2024)

        self.assertGreater(pr_1993, 0.0)
        self.assertGreater(tr_1993, 0.0)
        self.assertGreater(pr_2024, pr_1993)
        self.assertGreater(tr_2024, tr_1993)

        # Test generic method with different case inputs
        self.assertEqual(self.loader.get_benchmark_level("FBGRX", 2024), pr_2024)
        self.assertEqual(self.loader.get_benchmark_level("fbgrx", 2024), pr_2024)
        self.assertEqual(self.loader.get_benchmark_tr_level("FBGRX", 2024), tr_2024)
        self.assertEqual(self.loader.get_benchmark_tr_level("fbgrx", 2024), tr_2024)

    def test_fbgrx_quarterly_levels(self):
        """Verify quarterly FBGRX levels cover 1993-Q4 to 2024-Q4."""
        pr_q4_1993 = self.loader.get_fbgrx_quarterly_level(1993, 4)
        tr_q4_1993 = self.loader.get_fbgrx_tr_quarterly_level(1993, 4)
        pr_q4_2024 = self.loader.get_fbgrx_quarterly_level(2024, 4)
        tr_q4_2024 = self.loader.get_fbgrx_tr_quarterly_level(2024, 4)

        self.assertGreater(pr_q4_1993, 0.0)
        self.assertGreater(tr_q4_1993, 0.0)
        self.assertGreater(pr_q4_2024, 0.0)
        self.assertGreater(tr_q4_2024, 0.0)

        # Q4 quarterly level must match annual level
        self.assertAlmostEqual(pr_q4_2024, self.loader.get_fbgrx_level(2024), places=2)

    def test_fbgrx_distribution_yield(self):
        """Verify FBGRX implied distribution yield calculation is non-negative."""
        for yr in range(1994, 2025):
            yld = self.loader.get_fbgrx_dividend_yield(yr)
            self.assertGreaterEqual(yld, 0.0)
            generic_yld = self.loader.get_benchmark_dividend_yield("FBGRX", yr)
            self.assertAlmostEqual(yld, generic_yld, places=6)

    def test_generic_benchmark_loader_spx_and_msci(self):
        """Verify generic methods work seamlessly for S&P 500, MSCI World, and canonical TR tickers."""
        spx_pr = self.loader.get_benchmark_level("sp500", 2024)
        spx_tr = self.loader.get_benchmark_tr_level("sp500", 2024)
        self.assertEqual(spx_pr, self.loader.get_spx_level(2024))
        self.assertEqual(spx_tr, self.loader.get_spx_tr_level(2024))

        # Test canonical total return ticker string '^SP500TR'
        self.assertEqual(self.loader.get_benchmark_tr_level("^SP500TR", 2024), spx_tr)
        self.assertEqual(self.loader.get_benchmark_level("^SP500TR", 2024), spx_pr)
        self.assertAlmostEqual(self.loader.get_benchmark_dividend_yield("^SP500TR", 2024), self.loader.get_spx_dividend_yield(2024), places=6)

        msci_pr = self.loader.get_benchmark_level("msci_world", 2024)
        msci_tr = self.loader.get_benchmark_tr_level("msci_world", 2024)
        self.assertEqual(msci_pr, self.loader.get_msci_world_level(2024))
        self.assertEqual(msci_tr, self.loader.get_msci_world_tr_level(2024))
        self.assertEqual(self.loader.get_benchmark_tr_level("^MSCIWORLD_TR", 2024), msci_tr)

        # Test generic quarterly methods
        self.assertEqual(self.loader.get_benchmark_quarterly_level("sp500", 2024, 4), self.loader.get_spx_quarterly_level(2024, 4))
        self.assertEqual(self.loader.get_benchmark_quarterly_tr_level("sp500", 2024, 4), self.loader.get_spx_tr_quarterly_level(2024, 4))
        self.assertEqual(self.loader.get_benchmark_quarterly_level("fbgrx", 2024, 4), self.loader.get_fbgrx_quarterly_level(2024, 4))
        self.assertEqual(self.loader.get_benchmark_quarterly_tr_level("fbgrx", 2024, 4), self.loader.get_fbgrx_tr_quarterly_level(2024, 4))
        self.assertEqual(self.loader.get_benchmark_quarterly_tr_level("^SP500TR", 2024, 4), self.loader.get_spx_tr_quarterly_level(2024, 4))


class TestMutualFundPerformanceCalculations(unittest.TestCase):
    """Test performance and tax series modeling for FBGRX."""

    def setUp(self):
        self.loader = DataLoader()

    def test_fbgrx_30y_series_modeling(self):
        """Verify pre-tax and after-tax calculations for FBGRX over 30y."""
        years = list(range(1993, 2025))
        pr_series = [self.loader.get_fbgrx_level(y) for y in years]
        tr_series = [self.loader.get_fbgrx_tr_level(y) for y in years]

        # Pre-tax calculation
        res_pre = calculate_benchmark_annual_series(
            pr_levels=pr_series,
            tr_levels=tr_series,
            tax_rate=0.30,
            initial_capital=10000.0,
            is_after_tax=False,
        )

        # After-tax calculation
        res_post = calculate_benchmark_annual_series(
            pr_levels=pr_series,
            tr_levels=tr_series,
            tax_rate=0.30,
            initial_capital=10000.0,
            is_after_tax=True,
        )

        # Pre-tax wealth must exceed after-tax wealth
        self.assertGreater(res_pre["final_equity"], res_post["final_equity"])
        self.assertGreater(res_post["total_taxes_paid"], 0.0)
        self.assertGreater(res_post["terminal_liq_tax"], 0.0)

        # Verify positive CAGR over 30 years
        cagr_pre = calculate_cagr(10000.0, res_pre["final_equity"], 31)
        cagr_post = calculate_cagr(10000.0, res_post["final_equity"], 31)
        self.assertGreater(cagr_pre, 0.10)
        self.assertGreater(cagr_post, 0.08)
        self.assertGreater(cagr_pre, cagr_post)

    def test_fbgrx_quarterly_series_modeling(self):
        """Verify quarterly trajectory and series calculation for FBGRX."""
        quarters = []
        for yr in range(1994, 2025):
            for q in range(1, 5):
                quarters.append((yr, q))
        pr_q_series = [self.loader.get_fbgrx_quarterly_level(1993, 4)] + [
            self.loader.get_fbgrx_quarterly_level(yr, q) for (yr, q) in quarters
        ]
        tr_q_series = [self.loader.get_fbgrx_tr_quarterly_level(1993, 4)] + [
            self.loader.get_fbgrx_tr_quarterly_level(yr, q) for (yr, q) in quarters
        ]
        self.assertEqual(len(pr_q_series), 1 + 31 * 4)
        self.assertEqual(len(tr_q_series), 1 + 31 * 4)

        res_q_pre = calculate_benchmark_annual_series(
            pr_levels=pr_q_series,
            tr_levels=tr_q_series,
            tax_rate=0.30,
            initial_capital=10000.0,
            is_after_tax=False,
        )
        res_q_post = calculate_benchmark_annual_series(
            pr_levels=pr_q_series,
            tr_levels=tr_q_series,
            tax_rate=0.30,
            initial_capital=10000.0,
            is_after_tax=True,
        )
        self.assertGreater(res_q_pre["final_equity"], res_q_post["final_equity"])


if __name__ == "__main__":
    unittest.main()
