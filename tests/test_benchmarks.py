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
            "max_drawdown", "total_dividends_received",
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


class TestBenchmarkSyntheticHandCalculations(unittest.TestCase):
    """Deterministic hand-calculated verification for benchmark series metrics."""

    def test_deterministic_two_year_series_exact_math(self):
        """Verify exact compounding, dividend taxation, tax drag, and ending equity.

        Setup:
            Initial capital = $10,000, 2-year horizon (2020-2022).
            PR levels = [100.0, 110.0, 121.0] -> 10% price return each year.
            TR levels = [100.0, 112.0, 125.44] -> 12% total return each year (2% dividend yield).
            Tax rate = 30%.
            Net annual return = 10% + 2% * (1 - 0.30) = 11.4%.
            Year 1 equity = 10,000 * 1.114 = $11,140.00.
            Year 2 equity = 11,140 * 1.114 = $12,409.96.
            Expected tr_cagr = 12.0%, after_cagr = 11.4%, tax_drag = 0.6%.
        """
        from engine.benchmarks import _calculate_series_metrics
        metrics = _calculate_series_metrics(
            pr_levels=[100.0, 110.0, 121.0],
            tr_levels=[100.0, 112.0, 125.44],
            tax_rate=0.30,
            initial_capital=10000.0,
            horizon_years=2,
        )
        self.assertAlmostEqual(metrics.tr_cagr, 0.12, places=5)
        self.assertAlmostEqual(metrics.tr_cum, 0.2544, places=4)
        self.assertAlmostEqual(metrics.tr_max_dd, 0.0, places=5)
        self.assertAlmostEqual(metrics.after_cagr, 0.114, places=5)
        self.assertAlmostEqual(metrics.cum_return, 0.240996, places=5)
        self.assertAlmostEqual(metrics.tax_drag, 0.006, places=5)
        self.assertAlmostEqual(metrics.final_equity, 12409.96, places=2)
        self.assertAlmostEqual(metrics.max_dd, 0.0, places=5)

        # Dividend and tax cash flows
        # Yr 1: div = $200.0, tax = $60.0
        # Yr 2: div = 11140 * 0.02 = $222.80, tax = 222.80 * 0.3 = $66.84
        # Total div = $422.80, Total tax = $126.84
        self.assertAlmostEqual(metrics.total_dividends, 422.80, places=2)
        self.assertAlmostEqual(metrics.total_taxes, 126.84, places=2)

    def test_deterministic_drawdown_exact_math(self):
        """Verify discrete observation max drawdown on a known peak-to-trough series."""
        from engine.benchmarks import _calculate_series_metrics
        # Peak at 120.0, trough at 90.0 -> (90 - 120) / 120 = -0.25 (-25.0%)
        metrics = _calculate_series_metrics(
            pr_levels=[100.0, 120.0, 90.0, 110.0],
            tr_levels=[100.0, 120.0, 90.0, 110.0],
            tax_rate=0.0,
            initial_capital=10000.0,
            horizon_years=3,
        )
        self.assertAlmostEqual(metrics.tr_max_dd, -0.25, places=5)
        self.assertAlmostEqual(metrics.max_dd, -0.25, places=5)


class TestBenchmarkHistoricalRegressions(unittest.TestCase):
    """Pin exact historical benchmark statistics across standard horizons to prevent regression."""

    def setUp(self):
        self.data_loader = DataLoader()

    def test_spx_10y_exact_regression(self):
        spx = calculate_spx_benchmark(self.data_loader, 2014, 2024, 0.30, 10000.0)
        self.assertAlmostEqual(spx.tr_cagr, 0.131022, places=5)
        self.assertAlmostEqual(spx.after_cagr, 0.124918, places=5)
        self.assertAlmostEqual(spx.max_dd, -0.185105, places=5)
        self.assertAlmostEqual(spx.final_equity, 32449.60, places=1)
        self.assertAlmostEqual(spx.alpha, 0.0, places=5)

    def test_msci_world_10y_exact_regression(self):
        msci = calculate_msci_world_benchmark(self.data_loader, 2014, 2024, 0.30, 10000.0)
        self.assertAlmostEqual(msci.tr_cagr, 0.105222, places=5)
        self.assertAlmostEqual(msci.after_cagr, 0.097808, places=5)
        self.assertAlmostEqual(msci.max_dd, -0.182490, places=5)
        self.assertAlmostEqual(msci.final_equity, 25425.10, places=1)

    def test_nasdaq100_10y_exact_regression(self):
        ndx = calculate_nasdaq100_benchmark(self.data_loader, 2014, 2024, 0.30, 10000.0)
        self.assertAlmostEqual(ndx.tr_cagr, 0.182802, places=5)
        self.assertAlmostEqual(ndx.after_cagr, 0.180065, places=5)
        self.assertAlmostEqual(ndx.max_dd, -0.326158, places=5)
        self.assertAlmostEqual(ndx.final_equity, 52367.30, places=1)

    def test_fbgrx_10y_exact_regression(self):
        fbgrx = calculate_fbgrx_benchmark(self.data_loader, 2014, 2024, 0.30, 10000.0)
        self.assertAlmostEqual(fbgrx.tr_cagr, 0.180947, places=5)
        self.assertAlmostEqual(fbgrx.after_cagr, 0.164981, places=5)
        self.assertAlmostEqual(fbgrx.max_dd, -0.385415, places=5)
        self.assertAlmostEqual(fbgrx.final_equity, 46045.49, places=1)

    def test_spx_30y_exact_regression(self):
        spx30 = calculate_spx_benchmark(self.data_loader, 1994, 2024, 0.30, 10000.0)
        self.assertAlmostEqual(spx30.tr_cagr, 0.109242, places=5)
        self.assertAlmostEqual(spx30.after_cagr, 0.103085, places=5)
        self.assertAlmostEqual(spx30.max_dd, -0.383685, places=5)
        self.assertAlmostEqual(spx30.final_equity, 189788.57, places=1)


if __name__ == "__main__":
    unittest.main()

