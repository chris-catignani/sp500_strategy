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


if __name__ == "__main__":
    unittest.main()
