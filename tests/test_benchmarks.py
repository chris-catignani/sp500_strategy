import unittest
from engine.data_loader import DataLoader
from engine.benchmarks import (
    BenchmarkMetrics,
    BenchmarkSuite,
    calculate_spx_benchmark,
    calculate_msci_world_benchmark,
    calculate_fbgrx_benchmark,
    calculate_nasdaq100_benchmark,
    compute_all_benchmarks,
)


class TestBenchmarks(unittest.TestCase):
    def setUp(self):
        self.data_loader = DataLoader()

    def test_spx_benchmark_annual(self):
        metrics = calculate_spx_benchmark(
            self.data_loader,
            s_yr=2014,
            e_yr=2024,
            tax_rate=0.30,
            initial_capital=10000.0,
            is_quarterly=False,
        )
        self.assertIsInstance(metrics, BenchmarkMetrics)
        self.assertGreater(metrics.tr_cagr, 0.05)
        self.assertGreater(metrics.after_cagr, 0.05)
        self.assertLess(metrics.after_cagr, metrics.tr_cagr)
        self.assertGreater(metrics.total_dividends, 0.0)
        self.assertGreater(metrics.final_equity, 10000.0)
        self.assertIn("pre_liquidation_wealth", metrics.bench_post)
        self.assertEqual(metrics.alpha, 0.0)

    def test_spx_benchmark_quarterly(self):
        metrics = calculate_spx_benchmark(
            self.data_loader,
            s_yr=2014,
            e_yr=2024,
            tax_rate=0.30,
            initial_capital=10000.0,
            is_quarterly=True,
        )
        self.assertIsInstance(metrics, BenchmarkMetrics)
        self.assertGreater(metrics.tr_cagr, 0.05)
        self.assertGreater(metrics.final_equity, 10000.0)

    def test_other_benchmarks_annual(self):
        msci = calculate_msci_world_benchmark(self.data_loader, 2014, 2024, 0.30, 10000.0)
        fbgrx = calculate_fbgrx_benchmark(self.data_loader, 2014, 2024, 0.30, 10000.0)
        ndx = calculate_nasdaq100_benchmark(self.data_loader, 2014, 2024, 0.30, 10000.0)
        self.assertGreater(msci.tr_cagr, 0.0)
        self.assertGreater(fbgrx.tr_cagr, 0.0)
        self.assertGreater(ndx.tr_cagr, 0.0)
        self.assertIsInstance(msci, BenchmarkMetrics)
        self.assertIsInstance(fbgrx, BenchmarkMetrics)
        self.assertIsInstance(ndx, BenchmarkMetrics)

    def test_other_benchmarks_quarterly(self):
        msci = calculate_msci_world_benchmark(self.data_loader, 2014, 2024, 0.30, 10000.0, is_quarterly=True)
        fbgrx = calculate_fbgrx_benchmark(self.data_loader, 2014, 2024, 0.30, 10000.0, is_quarterly=True)
        ndx = calculate_nasdaq100_benchmark(self.data_loader, 2014, 2024, 0.30, 10000.0, is_quarterly=True)
        self.assertGreater(msci.tr_cagr, 0.0)
        self.assertGreater(fbgrx.tr_cagr, 0.0)
        self.assertGreater(ndx.tr_cagr, 0.0)

    def test_compute_all_benchmarks(self):
        horizons = [("10y", 2014, 2024)]
        suite = compute_all_benchmarks(
            self.data_loader,
            horizons=horizons,
            tax_rate=0.30,
            initial_capital=10000.0,
            frequency="annual",
            compare_frequencies=False,
        )
        self.assertIsInstance(suite, BenchmarkSuite)
        self.assertIn("10y", suite.spx_annual)
        self.assertIn("10y", suite.spx_quarterly)
        self.assertIn("10y", suite.msci_annual)
        self.assertIn("10y", suite.msci_quarterly)
        self.assertIn("10y", suite.fbgrx_annual)
        self.assertIn("10y", suite.fbgrx_quarterly)
        self.assertIn("10y", suite.nasdaq_annual)
        self.assertIn("10y", suite.nasdaq_quarterly)

        # Check lookup keys in spx_benchmarks
        self.assertIn("10y", suite.spx_benchmarks)
        self.assertIn(10, suite.spx_benchmarks)
        self.assertIn("10", suite.spx_benchmarks)
        self.assertIn(("10y", 0.30), suite.spx_benchmarks)
        self.assertIn(("10y", 0.0), suite.spx_benchmarks)
        self.assertIn((10, 0.30), suite.spx_benchmarks)

    def test_build_synthetic_results_annual(self):
        horizons = [("10y", 2014, 2024)]
        suite = compute_all_benchmarks(self.data_loader, horizons, 0.30, 10000.0)
        results = suite.build_synthetic_results(horizons, 0.30, 10000.0, frequency="annual", compare_frequencies=False)
        self.assertEqual(len(results), 8)
        self.assertTrue(any(r.strategy_name == "S&P 500" and not r.is_after_tax for r in results))
        self.assertTrue(any(r.strategy_name == "S&P 500" and r.is_after_tax for r in results))
        self.assertTrue(any(r.strategy_name == "MSCI World" and not r.is_after_tax for r in results))
        self.assertTrue(any(r.strategy_name == "FBGRX" and not r.is_after_tax for r in results))
        self.assertTrue(any(r.strategy_name == "Nasdaq 100" and not r.is_after_tax for r in results))
        for r in results:
            self.assertEqual(r.rebalance_frequency, "annual")

    def test_build_synthetic_results_quarterly(self):
        horizons = [("10y", 2014, 2024)]
        suite = compute_all_benchmarks(self.data_loader, horizons, 0.30, 10000.0, frequency="quarterly")
        results = suite.build_synthetic_results(horizons, 0.30, 10000.0, frequency="quarterly", compare_frequencies=False)
        self.assertEqual(len(results), 8)
        self.assertTrue(any(r.strategy_name == "S&P 500" and not r.is_after_tax for r in results))
        self.assertTrue(any(r.strategy_name == "S&P 500" and r.is_after_tax for r in results))
        self.assertTrue(any(r.strategy_name == "Nasdaq 100" and r.is_after_tax for r in results))
        for r in results:
            self.assertEqual(r.rebalance_frequency, "quarterly")

    def test_build_synthetic_results_compare_frequencies(self):
        horizons = [("10y", 2014, 2024)]
        suite = compute_all_benchmarks(self.data_loader, horizons, 0.30, 10000.0, compare_frequencies=True)
        results = suite.build_synthetic_results(horizons, 0.30, 10000.0, frequency="annual", compare_frequencies=True)
        self.assertEqual(len(results), 16)
        self.assertTrue(any(r.strategy_name == "S&P 500 (Annual)" for r in results))
        self.assertTrue(any(r.strategy_name == "S&P 500 (Quarterly)" for r in results))
        self.assertTrue(any(r.strategy_name == "MSCI World (Annual)" for r in results))
        self.assertTrue(any(r.strategy_name == "MSCI World (Quarterly)" for r in results))
        self.assertTrue(any(r.strategy_name == "FBGRX (Annual)" for r in results))
        self.assertTrue(any(r.strategy_name == "FBGRX (Quarterly)" for r in results))
        self.assertTrue(any(r.strategy_name == "Nasdaq 100 (Annual)" for r in results))
        self.assertTrue(any(r.strategy_name == "Nasdaq 100 (Quarterly)" for r in results))

    def test_build_synthetic_results_attributes(self):
        horizons = [("10y", 2014, 2024)]
        suite = compute_all_benchmarks(self.data_loader, horizons, 0.30, 10000.0)
        results = suite.build_synthetic_results(horizons, 0.30, 10000.0, frequency="annual", compare_frequencies=False)
        expected_attrs = [
            "strategy_name", "universe", "start_year", "end_year",
            "initial_capital", "final_equity", "cagr", "cumulative_return",
            "max_drawdown", "tax_drag", "alpha", "total_dividends_received",
            "total_taxes_paid", "is_after_tax", "rebalance_frequency",
            "pre_liquidation_wealth", "post_liquidation_wealth", "post_liquidation_cagr",
        ]
        for r in results:
            for attr in expected_attrs:
                self.assertTrue(hasattr(r, attr), f"Missing attribute {attr} on {r.strategy_name}")
            self.assertEqual(r.start_year, 2014)
            self.assertEqual(r.end_year, 2024)
            self.assertEqual(r.initial_capital, 10000.0)
            self.assertGreater(r.final_equity, 0.0)
            self.assertGreater(r.cagr, 0.0)
            self.assertGreater(r.cumulative_return, 0.0)
            self.assertLessEqual(r.max_drawdown, 0.0)
            self.assertGreaterEqual(r.total_dividends_received, 0.0)
            self.assertGreater(r.pre_liquidation_wealth, 0.0)
            self.assertGreater(r.post_liquidation_wealth, 0.0)
            self.assertGreater(r.post_liquidation_cagr, 0.0)

            if not r.is_after_tax:
                self.assertEqual(r.tax_rate, 0.0)
                self.assertEqual(r.total_taxes_paid, 0.0)
            else:
                self.assertEqual(r.tax_rate, 0.30)
                self.assertGreater(r.total_taxes_paid, 0.0)


if __name__ == "__main__":
    unittest.main()

