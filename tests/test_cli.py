"""Unit tests for the CLI runner (run_backtest.py)."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from engine.selector import MarketCapSelector, PerformanceSelector


class TestCLI(unittest.TestCase):
    """Test suite for CLI argument parsing, strategy execution, and reporting."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, "outputs")
        self.scripts_dir = os.path.join(self.test_dir, "scripts")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_arguments(self):
        """Test default CLI argument parsing."""
        import run_backtest

        parser = run_backtest.build_parser()
        args = parser.parse_args([])

        self.assertEqual(args.strategy, "market_cap")
        self.assertAlmostEqual(args.tax_rate, 0.30)
        self.assertAlmostEqual(args.initial_capital, 10000.0)
        self.assertEqual(args.output_dir, "outputs")
        self.assertEqual(args.scripts_dir, "scripts")
        self.assertFalse(args.quiet)

        horizons = run_backtest.resolve_horizons(args.horizons)
        self.assertEqual(
            horizons,
            [("10y", 2014, 2024), ("20y", 2004, 2024), ("30y", 1994, 2024)],
        )

        n_values = run_backtest.resolve_n_values(args.n)
        self.assertEqual(n_values, [3, 5, 10])

    def test_custom_arguments(self):
        """Test custom CLI argument overrides."""
        import run_backtest

        parser = run_backtest.build_parser()
        args = parser.parse_args(
            [
                "--strategy", "performance",
                "--tax-rate", "0.20",
                "--initial-capital", "25000",
                "--output-dir", "custom_outputs",
                "--scripts-dir", "custom_scripts",
                "--horizons", "10y,20y",
                "--n", "3,5",
                "-q",
            ]
        )

        self.assertEqual(args.strategy, "performance")
        self.assertAlmostEqual(args.tax_rate, 0.20)
        self.assertAlmostEqual(args.initial_capital, 25000.0)
        self.assertEqual(args.output_dir, "custom_outputs")
        self.assertEqual(args.scripts_dir, "custom_scripts")
        self.assertTrue(args.quiet)

        horizons = run_backtest.resolve_horizons(args.horizons)
        self.assertEqual(
            horizons,
            [("10y", 2014, 2024), ("20y", 2004, 2024)],
        )

        n_values = run_backtest.resolve_n_values(args.n)
        self.assertEqual(n_values, [3, 5])

    def test_multi_value_list_arguments(self):
        """Test space-separated list arguments for horizons and N."""
        import run_backtest

        parser = run_backtest.build_parser()
        args = parser.parse_args(
            [
                "--horizons", "10y", "30y",
                "--n", "5", "10",
            ]
        )

        horizons = run_backtest.resolve_horizons(args.horizons)
        self.assertEqual(
            horizons,
            [("10y", 2014, 2024), ("30y", 1994, 2024)],
        )

        n_values = run_backtest.resolve_n_values(args.n)
        self.assertEqual(n_values, [5, 10])

    def test_resolve_selector(self):
        """Test selector factory resolution."""
        import run_backtest

        sel_mc = run_backtest.resolve_selector("market_cap", n=5)
        self.assertIsInstance(sel_mc, MarketCapSelector)
        self.assertEqual(sel_mc.n, 5)

        sel_perf = run_backtest.resolve_selector("performance", n=10)
        self.assertIsInstance(sel_perf, PerformanceSelector)
        self.assertEqual(sel_perf.n, 10)

        with self.assertRaises(ValueError):
            run_backtest.resolve_selector("invalid_strategy", n=5)

    def test_format_terminal_table(self):
        """Test ASCII terminal table formatting."""
        import run_backtest

        rows = [
            {
                "horizon": "10y",
                "strategy": "Top 3",
                "pre_cagr": 0.152,
                "post_cagr": 0.134,
                "post_liq_cagr": 0.128,
                "cum_return": 2.50,
                "max_dd": -0.18,
                "tax_drag": 0.024,
                "alpha": 0.031,
            },
            {
                "horizon": "10y",
                "strategy": "S&P 500",
                "pre_cagr": 0.121,
                "post_cagr": 0.121,
                "post_liq_cagr": 0.121,
                "cum_return": 2.14,
                "max_dd": -0.23,
                "tax_drag": 0.0,
                "alpha": 0.0,
            },
        ]
        table_str = run_backtest.format_terminal_table(rows, tax_rate=0.30, initial_capital=10000.0)
        self.assertIn("Top 3", table_str)
        self.assertIn("S&P 500", table_str)
        self.assertIn("15.20%", table_str)
        self.assertIn("Horizon", table_str)
        self.assertIn("Alpha", table_str)

    def test_run_backtest_integration(self):
        """Test programmatic execution of run_backtest on a single horizon and N."""
        import run_backtest

        parser = run_backtest.build_parser()
        args = parser.parse_args(
            [
                "--strategy", "market_cap",
                "--tax-rate", "0.30",
                "--initial-capital", "10000.0",
                "--output-dir", self.output_dir,
                "--scripts-dir", self.scripts_dir,
                "--horizons", "10y",
                "--n", "5",
                "--quiet",
            ]
        )

        exit_code = run_backtest.run_backtest(args)
        self.assertEqual(exit_code, 0)

        # Verify output files exist
        summary_path = os.path.join(self.output_dir, "summary_metrics.csv")
        annual_path = os.path.join(self.output_dir, "annual_breakdown.csv")
        trades_path = os.path.join(self.output_dir, "trade_log.csv")
        script_path = os.path.join(self.scripts_dir, "google_apps_script.js")

        self.assertTrue(os.path.exists(summary_path), "summary_metrics.csv should exist")
        self.assertTrue(os.path.exists(annual_path), "annual_breakdown.csv should exist")
        self.assertTrue(os.path.exists(trades_path), "trade_log.csv should exist")
        self.assertTrue(os.path.exists(script_path), "google_apps_script.js should exist")

        # Verify summary_metrics.csv content
        with open(summary_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertGreater(len(lines), 1)

        # Verify google_apps_script.js content
        with open(script_path, "r", encoding="utf-8") as f:
            js_content = f.read()
            self.assertIn("buildAllSheets", js_content)
            self.assertIn("SCENARIO_DATA", js_content)

    def test_cli_subprocess_help(self):
        """Test running the CLI via subprocess with --help."""
        cmd = [sys.executable, "run_backtest.py", "--help"]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--strategy", res.stdout)
        self.assertIn("--tax-rate", res.stdout)
        self.assertIn("--initial-capital", res.stdout)
        self.assertIn("--universes", res.stdout)

    def test_resolve_universes(self):
        """Test universe normalization and validation."""
        import run_backtest

        self.assertEqual(run_backtest.resolve_universes(["sp500", "world"]), ["sp500", "world"])
        self.assertEqual(run_backtest.resolve_universes("sp500,world"), ["sp500", "world"])
        self.assertEqual(run_backtest.resolve_universes("US,GLOBAL"), ["sp500", "world"])
        self.assertEqual(run_backtest.resolve_universes(["all_world"]), ["world"])

        # Error on invalid universe
        with self.assertRaises(ValueError):
            run_backtest.resolve_universes("crypto", available_universes=["sp500", "world"])

    def test_format_terminal_table_with_universe(self):
        """Test terminal table formatting with Universe column."""
        import run_backtest

        rows = [
            {
                "universe": "S&P 500",
                "horizon": "10y",
                "strategy": "Top 5",
                "pre_cagr": 0.15,
                "post_cagr": 0.13,
                "post_liq_cagr": 0.12,
                "cum_return": 2.10,
                "max_dd": -0.20,
                "tax_drag": 0.03,
                "alpha": 0.02,
            },
            {
                "universe": "All World",
                "horizon": "10y",
                "strategy": "World Top 5",
                "pre_cagr": 0.16,
                "post_cagr": 0.14,
                "post_liq_cagr": 0.13,
                "cum_return": 2.30,
                "max_dd": -0.19,
                "tax_drag": 0.03,
                "alpha": 0.03,
            },
        ]
        table = run_backtest.format_terminal_table(rows)
        self.assertIn("Universe", table)
        self.assertIn("All World", table)
        self.assertIn("World Top 5", table)

    def test_run_backtest_multi_universe_integration(self):
        """Test programmatic execution with multiple universes."""
        import run_backtest

        parser = run_backtest.build_parser()
        args = parser.parse_args(
            [
                "--strategy", "market_cap",
                "--tax-rate", "0.30",
                "--initial-capital", "10000.0",
                "--output-dir", self.output_dir,
                "--scripts-dir", self.scripts_dir,
                "--horizons", "10y",
                "--n", "3",
                "--universes", "sp500,world",
                "--quiet",
            ]
        )

        exit_code = run_backtest.run_backtest(args)
        self.assertEqual(exit_code, 0)

        # Verify summary_metrics.csv contains both universes
        summary_path = os.path.join(self.output_dir, "summary_metrics.csv")
        with open(summary_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Top_3_MarketCap", content)
            self.assertIn("World_Top_3_MarketCap", content)


if __name__ == "__main__":
    unittest.main()
