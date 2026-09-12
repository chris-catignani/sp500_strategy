"""Unit tests for engine/scenarios.py scenario generation and data structures."""

import unittest
from engine.scenarios import (
    build_default_scenario_data,
    build_scenario_and_apps_script_data,
    compute_scenario_grid,
    format_apps_script_payloads,
)


class TestScenarios(unittest.TestCase):
    """Test suite for multi-horizon scenario matrix generation."""

    def test_build_scenario_and_apps_script_data_default(self):
        """Verify default invocation builds scenario data across universes and tax tiers."""
        scenario_data, annual_data, trades_data = build_scenario_and_apps_script_data()

        self.assertIn("scenario_rows", scenario_data)
        scenario_rows = scenario_data["scenario_rows"]
        self.assertGreater(len(scenario_rows), 0)
        # 18 columns per scenario row ending with RowType
        for row in scenario_rows:
            self.assertEqual(len(row), 18)
            self.assertIn(row[17], ("Strategy", "Index", "Mutual Fund"))
            self.assertIn(row[5], ("Market Cap", "Equal Weight"))

        # Verify benchmark rows exist without duplicates (5 tax rates x 3 horizons x 2 frequencies = 30 rows each)
        spx_bench_rows = [r for r in scenario_rows if r[4] == "S&P 500" and r[17] == "Index"]
        msci_bench_rows = [r for r in scenario_rows if r[4] == "MSCI World" and r[17] == "Index"]
        fbgrx_bench_rows = [r for r in scenario_rows if r[4] == "FBGRX" and r[17] == "Mutual Fund"]
        self.assertEqual(len(spx_bench_rows), 30)
        self.assertEqual(len(msci_bench_rows), 30)
        self.assertEqual(len(fbgrx_bench_rows), 30)
        self.assertEqual(sum(1 for r in spx_bench_rows if r[6] == "Annual"), 15)
        self.assertEqual(sum(1 for r in spx_bench_rows if r[6] == "Quarterly"), 15)
        self.assertEqual(sum(1 for r in msci_bench_rows if r[6] == "Annual"), 15)
        self.assertEqual(sum(1 for r in msci_bench_rows if r[6] == "Quarterly"), 15)
        self.assertEqual(sum(1 for r in fbgrx_bench_rows if r[6] == "Annual"), 15)
        self.assertEqual(sum(1 for r in fbgrx_bench_rows if r[6] == "Quarterly"), 15)

        # Verify active strategy rows exist for both Market Cap and Equal Weight (180 each = 360 total)
        strat_mc_rows = [r for r in scenario_rows if r[17] == "Strategy" and r[5] == "Market Cap"]
        strat_ew_rows = [r for r in scenario_rows if r[17] == "Strategy" and r[5] == "Equal Weight"]
        self.assertEqual(len(strat_mc_rows), 180)
        self.assertEqual(len(strat_ew_rows), 180)

        # Annual data checks
        expected_keys = [
            "top_3",
            "top_5",
            "top_10",
            "world_top_3",
            "world_top_5",
            "world_top_10",
            "spx",
            "era_data",
            "trajectory_data",
            "drawdown_data",
            "era_matrix",
            "trajectory_matrix",
            "drawdown_matrix",
        ]
        for key in expected_keys:
            self.assertIn(key, annual_data)
            self.assertGreater(len(annual_data[key]), 0)

        # Matrix dimensions (12 combos: 2 Universes x 3 Benchmarks x 2 Frequencies)
        # 31 years * 12 combos = 372 rows
        self.assertEqual(len(annual_data["trajectory_matrix"]), 372)
        for row in annual_data["trajectory_matrix"]:
            self.assertEqual(len(row), 6)  # LookupKey, Year, Top3, Top5, Top10, Bench

        self.assertEqual(len(annual_data["drawdown_matrix"]), 372)
        for row in annual_data["drawdown_matrix"]:
            self.assertEqual(len(row), 6)  # LookupKey, Year, Top3_DD, Top5_DD, Top10_DD, Bench_DD

        # 5 eras * 4 combos = 20 rows
        self.assertEqual(len(annual_data["era_matrix"]), 20)
        for row in annual_data["era_matrix"]:
            self.assertEqual(len(row), 9)  # LookupKey, Era, Context, Top3, Top5, Top10, Bench, Alpha, WinRate

        # Trades data checks
        self.assertIsInstance(trades_data, list)
        self.assertGreater(len(trades_data), 0)

    def test_build_scenario_single_universe(self):
        """Verify single universe does not crash era or trajectory generation."""
        scenario_data, annual_data, trades_data = build_scenario_and_apps_script_data(
            universes=["world"],
            initial_capital=50000.0,
            strategy_name="performance",
        )
        self.assertIn("scenario_rows", scenario_data)
        self.assertIn("world_top_3", annual_data)
        # Trajectories should have full 31 years (1994..2024)
        self.assertEqual(len(annual_data["trajectory_data"]), 31)
        self.assertEqual(len(annual_data["drawdown_data"]), 31)
        # Single universe with 3 benchmarks x 2 frequencies = 31 * 6 = 186 rows
        self.assertEqual(len(annual_data["trajectory_matrix"]), 186)
        self.assertEqual(len(annual_data["drawdown_matrix"]), 186)
        # 5 eras * 2 frequencies = 10 rows
        self.assertEqual(len(annual_data["era_matrix"]), 10)

    def test_build_default_scenario_data_helper(self):
        """Verify backward-compatible build_default_scenario_data dictionary contract."""
        defaults = build_default_scenario_data()
        self.assertIsInstance(defaults, dict)
        required_keys = [
            "scenario_rows",
            "top3_annual",
            "top5_annual",
            "top10_annual",
            "world_top3_annual",
            "world_top5_annual",
            "world_top10_annual",
            "spx_data",
            "trades_data",
            "era_data",
            "trajectory_data",
            "drawdown_data",
            "era_matrix",
            "trajectory_matrix",
            "drawdown_matrix",
        ]
        for k in required_keys:
            self.assertIn(k, defaults)
            self.assertGreater(len(defaults[k]), 0)

    def test_compute_scenario_grid_isolated(self):
        """Verify compute_scenario_grid generates raw simulation outputs independently."""
        grid = compute_scenario_grid(universes=["sp500"], initial_capital=20000.0)
        self.assertIsInstance(grid, dict)
        self.assertEqual(grid["initial_capital"], 20000.0)
        self.assertIn("pretax_cache", grid)
        self.assertIn("active_results", grid)
        self.assertIn("spx_benchmarks", grid)
        self.assertIn("spx_q_benchmarks", grid)
        self.assertIn("res_30y_map", grid)
        self.assertIn("trades_30y_map", grid)
        self.assertGreater(len(grid["active_results"]), 0)

        # Ensure active_results entries have unrounded raw numbers and correct keys
        sample = grid["active_results"][0]
        self.assertIn("pre_cagr", sample)
        self.assertIn("post_cagr", sample)
        self.assertIn("alpha", sample)
        self.assertIsInstance(sample["pre_cagr"], float)

        # Test format_apps_script_payloads consumes grid output
        scenario_data, annual_data, trades_data = format_apps_script_payloads(grid)
        self.assertIn("scenario_rows", scenario_data)
        self.assertIn("spx", annual_data)
        self.assertIn("top_10", annual_data)
        self.assertGreater(len(trades_data), 0)


if __name__ == "__main__":
    unittest.main()
